#!/usr/bin/env python3

import subprocess
import shutil
from pathlib import Path
from typing import Tuple, Optional


def obj_to_voxel(
    obj_path: str,
    mtl_path: Optional[str],
    texture_path: Optional[str],
    input_stem: str,
    voxel_size: float
) -> Path:
    """
    Convert OBJ file to voxel format using obj2voxel executable.
    
    Args:
        obj_path: Path to the OBJ file
        mtl_path: Optional path to the MTL file
        texture_path: Optional path to the texture file
        input_stem: Base name for output files
        voxel_size: Resolution for voxelization
        
    Returns:
        Path to the generated XYZRGB file
        
    Raises:
        RuntimeError: If obj2voxel build directory or executable not found, or if conversion fails
    """
    print(f"\n🔄 Step 2: Voxelizing OBJ using obj2voxel...")
    obj2vox_build_dir = Path("src/utils/cpp/obj2vox/build")
    
    if not obj2vox_build_dir.exists():
        raise RuntimeError(f"obj2voxel build directory not found: {obj2vox_build_dir}. Run 'uv run local_run.py' or build manually.")
    
    # Copy files to build directory
    obj_build_path = obj2vox_build_dir / Path(obj_path).name
    shutil.copy(obj_path, obj_build_path)
    print(f"  📋 Copied OBJ to: {obj_build_path}")
    
    if mtl_path:
        mtl_build_path = obj2vox_build_dir / Path(mtl_path).name
        shutil.copy(mtl_path, mtl_build_path)
        print(f"  📋 Copied MTL to: {mtl_build_path}")
    
    # Copy ALL texture/image files that live next to the OBJ. When a GLB has
    # multiple materials, trimesh emits several textures (material_0.png,
    # material_1.png, ...) and the MTL references all of them. Copying only the
    # first one makes obj2voxel abort on faces using the other materials.
    copied_textures = []
    source_dir = Path(obj_path).parent
    texture_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tga"}
    for img_file in sorted(source_dir.iterdir()):
        if img_file.suffix.lower() in texture_exts:
            dest = obj2vox_build_dir / img_file.name
            shutil.copy(img_file, dest)
            copied_textures.append(dest)
            print(f"  📋 Copied texture to: {dest}")

    # Fall back to the explicitly provided texture if it lives elsewhere and
    # wasn't already copied above.
    texture_build_path = None
    if texture_path:
        texture_build_path = obj2vox_build_dir / Path(texture_path).name
        if texture_build_path not in copied_textures:
            shutil.copy(texture_path, texture_build_path)
            print(f"  📋 Copied texture to: {texture_build_path}")
    
    # Run obj2voxel executable
    xyzrgb_filename = f"{input_stem}.xyzrgb"
    xyzrgb_build_path = obj2vox_build_dir / xyzrgb_filename
    
    # Get absolute path to the executable
    obj2voxel_exe = (obj2vox_build_dir / "obj2voxel").resolve()
    
    if not obj2voxel_exe.exists():
        raise RuntimeError(f"obj2voxel executable not found: {obj2voxel_exe}")
    
    obj2voxel_cmd = [
        str(obj2voxel_exe),
        str(obj_build_path.name),  # Just filename since we're in build dir
        xyzrgb_filename,
        "-r", str(int(voxel_size)),
        "-s", "max",
        "-p", "xZy"
    ]
    
    if texture_build_path:
        obj2voxel_cmd.extend(["-t", str(texture_build_path.name)])
    
    print(f"  🔧 Running: {' '.join(obj2voxel_cmd)}")
    
    result = subprocess.run(
        obj2voxel_cmd,
        cwd=str(obj2vox_build_dir.resolve()),
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"  ❌ obj2voxel failed:")
        print(f"  stdout: {result.stdout}")
        print(f"  stderr: {result.stderr}")
        raise RuntimeError(f"obj2voxel failed with return code {result.returncode}")
    
    print(f"  ✅ Created voxel file: {xyzrgb_build_path}")
    if result.stdout:
        print(f"  📄 obj2voxel output:\n{result.stdout}")
    
    return xyzrgb_build_path
