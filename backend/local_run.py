#!/usr/bin/env python3
"""
Local development server script
"""
import sys
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Build obj2voxel C++ executable if not already built
obj2voxel_exe = Path("src/utils/cpp/obj2vox/build/obj2voxel")
if not obj2voxel_exe.exists():
    print("Building obj2voxel executable...")
    build_dir = Path("src/utils/cpp/obj2vox/build")
    build_dir.mkdir(parents=True, exist_ok=True)
    
    subprocess.run(["cmake", ".."], cwd=str(build_dir), check=True)
    subprocess.run(["make"], cwd=str(build_dir), check=True)
    print("obj2voxel build complete")

if __name__ == "__main__":
    import uvicorn
    from src.api import app
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        reload=False,  # Disable reload to avoid subprocess issues
        log_level="info"
    )