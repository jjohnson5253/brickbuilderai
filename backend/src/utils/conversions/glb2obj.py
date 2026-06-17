#!/usr/bin/env python3
"""
GLB to OBJ Converter

Converts GLB files to OBJ format with associated MTL and texture files.
Uses trimesh to handle the conversion and preserve materials/textures.

Usage:
    python -m src.utils.conversions.glb2obj input.glb
    python -m src.utils.conversions.glb2obj input.glb --output custom_output.obj
"""

import argparse
import sys
from pathlib import Path
from typing import Tuple

try:
    import trimesh
except ImportError:
    print("Error: trimesh is required. Install with: pip install trimesh")
    sys.exit(1)


def glb_to_obj(glb_path: str, output_path: str = None) -> Tuple[str, str, str]:
    """
    Convert a GLB file to OBJ format with materials and textures.
    
    Args:
        glb_path: Path to input GLB file
        output_path: Optional path for output OBJ file. If not provided,
                    uses the same name as input with .obj extension
    
    Returns:
        Tuple of (obj_path, mtl_path, texture_path) - paths to generated files
        
    Raises:
        FileNotFoundError: If input GLB file doesn't exist
        RuntimeError: If conversion fails
    """
    glb_path = Path(glb_path)
    
    if not glb_path.exists():
        raise FileNotFoundError(f"GLB file not found: {glb_path}")
    
    # Determine output path
    if output_path is None:
        output_path = glb_path.with_suffix('.obj')
    else:
        output_path = Path(output_path)
    
    print(f"🔄 Converting GLB to OBJ: {glb_path}")
    
    try:
        # Load the GLB file
        mesh = trimesh.load(glb_path)
        
        # Export to OBJ - trimesh will automatically create .mtl and texture files
        # if materials and textures are present in the mesh
        mesh.export(str(output_path))
        
        # Determine the paths of generated files
        obj_path = str(output_path)
        output_dir = output_path.parent
        
        # Trimesh uses these standard names
        mtl_path = str(output_dir / "material.mtl")
        texture_path = str(output_dir / "material_0.png")
        
        print(f"✅ Conversion complete!")
        print(f"  📄 OBJ: {obj_path}")
        print(f"  🎨 MTL: {mtl_path}")
        print(f"  🖼️  Texture: {texture_path}")
        
        return obj_path, mtl_path, texture_path
        
    except Exception as e:
        raise RuntimeError(f"Failed to convert GLB to OBJ: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert GLB files to OBJ format with materials and textures"
    )
    parser.add_argument("input", help="Input GLB file path")
    parser.add_argument(
        "--output", "-o",
        help="Output OBJ file path (default: same name as input with .obj extension)"
    )
    
    args = parser.parse_args()
    
    try:
        obj_path, mtl_path, texture_path = glb_to_obj(args.input, args.output)
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
