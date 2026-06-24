"""
3D Model Generation from Image

This module contains the function for generating 3D models from images using Trellis API.
"""

import os
import logging
import tempfile
import asyncio
from typing import Tuple, Optional, Callable

from .falApiClient import FalApiClient
from .conversions.glb2brick import glb2brick
from .generate_image import generate_image_from_image

# Configure logging
logger = logging.getLogger(__name__)


async def generate_3d_model_from_image(
    image_input: str, 
    model: str,
    is_base64: bool = False, 
    detail_level: float = 1.6,
    apply_image_editing: bool = False,
    status_callback: Optional[Callable[[str], None]] = None,
    model_option: str = "a",
    voxelizer: str = "trimesh",
) -> Tuple[str, str, str, str, str, Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Generate a 3D model from an image using specified AI model and convert to LDR format.
    
    Args:
        image_input: Either a URL to an image or base64 encoded image data
        model: Model to use for 3D generation ("trellis", "trellis-2", or "sam3d")
        is_base64: Whether the image_input is base64 encoded
        detail_level: Detail level for brick generation (default: 1.6)
        apply_image_editing: Whether to apply nano banana image editing preprocessing
        status_callback: Optional callback function(status) for queue updates
        model_option: "a" or "b" to select prompt enhancement version (defaults to "a")
        voxelizer: Which voxelizer to use, "trimesh" (default) or "obj2voxel"
    
    Returns:
        Tuple containing:
        - mesh_path: Path to the downloaded GLB mesh file
        - ldr_path: Path to the generated LDR file
        - vox_path: Path to the VOX file
        - xyzrgb_path: Path to the XYZRGB voxel file
        - model_url: URL to the 3D model from Trellis API
        - original_resized_url: URL to resized original image (if editing applied, else None)
        - processed_image_url: URL to processed/edited image (if editing applied, else None)
        - problematic_xyzrgb_path: Path to problematic voxels file (if any, else None)
        - prompt_enhancement: The prompt enhancement text used (if editing applied, else None)
    
    Raises:
        HTTPException: If any step in the process fails
    """
    logger.info("Starting 3D model generation from image")
    
    # Initialize the fal.ai API client
    fal_ai_client = FalApiClient()
    
    # Create temporary files
    temp_dir = tempfile.mkdtemp()
    mesh_path = os.path.join(temp_dir, "model.glb")
    ldr_path = os.path.join(temp_dir, "output.ldr")
    
    # Initialize variables for image processing
    original_resized_url = None
    processed_image_url = None
    prompt_enhancement_used = None
    final_image_input = image_input
    final_is_base64 = is_base64
    
    # Apply image editing if requested
    if apply_image_editing:
        logger.info("Applying nano banana edit preprocessing to image")
        
        # Edit the image using nano banana - returns both resized original and edited image URLs
        # Pass None for edit_prompt to use default 3D style enhancement based on model_option
        original_resized_url, edited_image_url, prompt_enhancement_used = await asyncio.get_event_loop().run_in_executor(
            None, generate_image_from_image, image_input, is_base64, None, model_option
        )
        
        # Use the edited image for 3D model generation
        processed_image_url = edited_image_url
        final_image_input = edited_image_url
        final_is_base64 = False  # The edited image is now a URL
        
        logger.info(f"Image editing completed. Original resized: {original_resized_url[:50]}..., Edited: {edited_image_url[:50]}...")
    
    # Step 1: Generate 3D model using specified AI model
    logger.info(f"Generating 3D model using '{model}'")
    model_url = await asyncio.get_event_loop().run_in_executor(
        None, fal_ai_client.generate_3d_model, final_image_input, model, final_is_base64, status_callback
    )
    
    # Step 2: Download the mesh file
    logger.info("Downloading mesh file")
    await fal_ai_client.download_mesh_file(model_url, mesh_path)
    
    # Step 3: Convert mesh to LDR using glb2brick
    logger.info("Converting mesh to LDR format")
    info = glb2brick(
        mesh_path,
        world_size=25.0,
        voxel_size=detail_level,
        voxelizer=voxelizer
    )
    
    # Get the paths from the info dict
    ldr_path = info['ldr_file']
    vox_path = info['vox_file']
    xyzrgb_path = info['xyzrgb_file']
    problematic_xyzrgb_path = info.get('problematic_xyzrgb_file')  # May be None if no problematic voxels
    
    logger.info("Successfully completed 3D model generation from image")
    return mesh_path, ldr_path, vox_path, xyzrgb_path, model_url, original_resized_url, processed_image_url, problematic_xyzrgb_path, prompt_enhancement_used