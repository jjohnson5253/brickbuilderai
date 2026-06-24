"""
Model to Bricks (GLB or OBJ upload)

Upload a 3D model and run it through the glb2brick pipeline, choosing the
voxelizer (trimesh or obj2voxel). Accepts either:
- a single .glb file, or
- a .obj file plus its referenced .mtl (and texture images).

OBJ uploads are converted to GLB (preserving materials/textures) and then fed
through the same pipeline. Mirrors the imageToBricks flow: creates a generation
record, processes in a background task, and returns the generation_id
immediately for polling.
"""

import os
import shutil
import logging
import asyncio
import tempfile
from typing import List

from fastapi import UploadFile, Depends, HTTPException
from pydantic import BaseModel

from ..utils.auth import get_user_with_optional_auth, handle_auth_and_tracking
from ..utils.posthog_client import track_image_conversion, track_error
from ..utils.pack_ldraw_model import LDrawPacker
from ..utils.generation_storage import generation_storage
from ..utils.conversions.glb2brick import glb2brick

logger = logging.getLogger(__name__)


class GlbToBricksResponse(BaseModel):
    """Response model - returns generation_id immediately."""
    generation_id: str
    message: str = "Generation started"


def _safe_name(name: str) -> str:
    """Return just the basename, stripped of any path components."""
    return os.path.basename((name or "").replace("\\", "/"))


def _referenced_mtl_names(obj_path: str) -> List[str]:
    """Extract the .mtl filenames referenced by an OBJ's `mtllib` lines."""
    names: List[str] = []
    try:
        with open(obj_path, "r", errors="ignore") as f:
            for line in f:
                if line.lower().startswith("mtllib"):
                    names.extend(_safe_name(p) for p in line.split()[1:])
    except Exception as e:
        logger.warning(f"Failed to parse mtllib from OBJ: {e}")
    return names


def _convert_obj_to_glb(obj_path: str, glb_path: str) -> None:
    """Load an OBJ (with adjacent MTL/textures) and export it as GLB."""
    import trimesh

    loaded = trimesh.load(obj_path, process=False)
    loaded.export(glb_path)


async def process_model_to_bricks_task(
    generation_id: str,
    work_dir: str,
    main_filename: str,
    voxelizer: str,
    detail_level: float,
    user_email: str,
    is_developer: bool,
):
    """Background task: convert (if needed) and run glb2brick, then store artifacts."""
    heartbeat_task = None
    try:
        await generation_storage.update_status(generation_id, "processing")

        # Heartbeat to keep updated_at fresh while processing.
        async def heartbeat():
            while True:
                await asyncio.sleep(5)
                try:
                    generation_storage.client.table("generations").update(
                        {"updated_at": __import__("datetime").datetime.utcnow().isoformat()}
                    ).eq("id", generation_id).execute()
                except Exception as e:
                    logger.warning(f"Heartbeat update failed: {e}")

        heartbeat_task = asyncio.create_task(heartbeat())

        main_path = os.path.join(work_dir, main_filename)

        # Convert OBJ -> GLB so the rest of the pipeline is uniform.
        if main_filename.lower().endswith(".obj"):
            glb_path = os.path.join(work_dir, os.path.splitext(main_filename)[0] + ".glb")
            logger.info(f"Converting OBJ to GLB: {main_path} -> {glb_path}")
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: _convert_obj_to_glb(main_path, glb_path)
            )
        else:
            glb_path = main_path

        # Run the GLB -> bricks pipeline with the selected voxelizer.
        logger.info(f"Running glb2brick (voxelizer={voxelizer}) for {glb_path}")
        info = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: glb2brick(
                glb_path,
                world_size=25.0,
                voxel_size=detail_level,
                voxelizer=voxelizer,
            ),
        )

        ldr_path = info["ldr_file"]
        vox_path = info.get("vox_file", "")
        xyzrgb_path = info.get("xyzrgb_file", "")
        problematic_xyzrgb_path = info.get("problematic_xyzrgb_file")

        if not os.path.exists(ldr_path):
            raise Exception("LDR file was not created successfully")

        with open(ldr_path, "r") as f:
            ldr_content = f.read()

        # Pack LDR to MPD.
        packer = LDrawPacker()
        mpd_path = await asyncio.get_event_loop().run_in_executor(
            None, packer.pack_ldraw_model, ldr_path
        )
        with open(mpd_path, "r") as f:
            mpd_content = f.read()

        # Store the (converted) GLB.
        with open(glb_path, "rb") as f:
            glb_content = f.read()
        await generation_storage.store_model_file(
            generation_id=generation_id,
            file_content=glb_content,
            file_type="glb",
        )

        # Store LDR.
        await generation_storage.store_model_file(
            generation_id=generation_id,
            file_content=ldr_content,
            file_type="ldr",
        )

        # Store parts list CSV.
        await generation_storage.store_parts_list_csv(
            generation_id=generation_id,
            ldr_content=ldr_content,
        )

        # Store MPD.
        await generation_storage.store_model_file(
            generation_id=generation_id,
            file_content=mpd_content,
            file_type="mpd",
        )

        # Store VOX.
        if vox_path and os.path.exists(vox_path):
            with open(vox_path, "rb") as f:
                await generation_storage.store_model_file(
                    generation_id=generation_id,
                    file_content=f.read(),
                    file_type="vox",
                )

        # Store XYZRGB.
        if xyzrgb_path and os.path.exists(xyzrgb_path):
            with open(xyzrgb_path, "r") as f:
                await generation_storage.store_model_file(
                    generation_id=generation_id,
                    file_content=f.read(),
                    file_type="xyzrgb",
                )

        # Store problematic XYZRGB (if any).
        if problematic_xyzrgb_path and os.path.exists(problematic_xyzrgb_path):
            with open(problematic_xyzrgb_path, "r") as f:
                await generation_storage.store_model_file(
                    generation_id=generation_id,
                    file_content=f.read(),
                    file_type="problematic_xyzrgb",
                )

        await generation_storage.update_status(generation_id, "completed")

        if heartbeat_task:
            heartbeat_task.cancel()

        track_image_conversion(
            user_id=user_email,
            success=True,
            has_mpd=True,
            ldr_size=len(ldr_content),
            mpd_size=len(mpd_content),
            image_type="model_upload",
            is_developer=is_developer,
        )
        logger.info(f"Successfully completed model generation {generation_id}")

    except Exception as e:
        logger.error(f"Model upload task failed for generation {generation_id}: {e}")
        if heartbeat_task:
            heartbeat_task.cancel()
        try:
            await generation_storage.update_status(generation_id, "failed", str(e))
        except Exception:
            pass
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint="/glbToBricks",
            user_id=user_email,
        )
    finally:
        try:
            if work_dir and os.path.isdir(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


async def glb_to_bricks(
    files: List[UploadFile],
    voxelizer: str,
    detail_level: float,
    auth_info: dict,
) -> GlbToBricksResponse:
    """
    Upload a model (GLB, or OBJ + its MTL/textures) and convert it to bricks.

    Returns generation_id immediately; poll GET /generation/{id} for status.
    """
    if voxelizer not in ("trimesh", "obj2voxel"):
        raise HTTPException(status_code=400, detail="voxelizer must be 'trimesh' or 'obj2voxel'")

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Save all uploaded files into a temp working directory under their names.
    work_dir = tempfile.mkdtemp(prefix="model_upload_")
    saved_names: List[str] = []
    total_bytes = 0
    try:
        for up in files:
            name = _safe_name(up.filename or "")
            if not name:
                continue
            contents = await up.read()
            total_bytes += len(contents)
            with open(os.path.join(work_dir, name), "wb") as f:
                f.write(contents)
            saved_names.append(name)

        if not saved_names:
            raise HTTPException(status_code=400, detail="No valid files uploaded")

        # Identify the main model file (prefer GLB, else OBJ).
        glb_files = [n for n in saved_names if n.lower().endswith(".glb")]
        obj_files = [n for n in saved_names if n.lower().endswith(".obj")]
        if glb_files:
            main_filename = glb_files[0]
        elif obj_files:
            main_filename = obj_files[0]
        else:
            raise HTTPException(
                status_code=400,
                detail="Upload must include a .glb or .obj file",
            )

        # For OBJ, ensure the referenced .mtl file(s) were also uploaded.
        if main_filename.lower().endswith(".obj"):
            obj_path = os.path.join(work_dir, main_filename)
            referenced = _referenced_mtl_names(obj_path)
            uploaded_lower = {n.lower() for n in saved_names}
            missing = [m for m in referenced if m.lower() not in uploaded_lower]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "This OBJ references material file(s) that were not uploaded: "
                        f"{', '.join(missing)}. Please upload the .mtl (and any textures) "
                        "alongside the .obj."
                    ),
                )
    except HTTPException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.error(f"Failed to save uploaded files: {e}")
        raise HTTPException(status_code=400, detail="Failed to read uploaded files")

    user_info = handle_auth_and_tracking(
        auth_info=auth_info,
        endpoint="/glbToBricks",
        track_properties={
            "voxelizer": voxelizer,
            "detail_level": detail_level,
            "upload_bytes": total_bytes,
            "main_format": "obj" if main_filename.lower().endswith(".obj") else "glb",
            "file_count": len(saved_names),
        },
        required_credits=0,
    )

    user_email = user_info["user_email"]
    is_developer = user_info["is_developer"]
    is_anonymous = user_info["is_anonymous"]

    if is_anonymous:
        user_id = auth_info["user_id"]
        user_type = "anonymous"
    elif is_developer:
        user_id = user_email
        user_type = "authenticated"
    else:
        user_id = auth_info.get("user_id", user_email)
        user_type = "authenticated"

    try:
        generation_id = await generation_storage.create_generation(
            user_id=user_id,
            user_type=user_type,
            prompt=f"Model upload: {main_filename}",
            detail_level=detail_level,
            endpoint="glbToBricks",
            model_3d=f"upload:{voxelizer}",
        )

        asyncio.create_task(
            process_model_to_bricks_task(
                generation_id=generation_id,
                work_dir=work_dir,
                main_filename=main_filename,
                voxelizer=voxelizer,
                detail_level=detail_level,
                user_email=user_email,
                is_developer=is_developer,
            )
        )

        return GlbToBricksResponse(
            generation_id=generation_id,
            message="Generation started. Poll /generation/{generation_id} for status.",
        )
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.error(f"Failed to start model generation: {e}")
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint="/glbToBricks",
            user_id=user_email,
        )
        raise HTTPException(status_code=500, detail="Failed to start generation")
