"""
Headless-compatible mesh2brick implementation for Railway deployment
This module provides fallback mechanisms for Open3D in headless environments
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)

def configure_headless_environment():
    """Configure environment variables for headless Open3D operation"""
    # Set headless mode before importing Open3D
    os.environ.setdefault("DISPLAY", ":99")
    os.environ.setdefault("OPEN3D_HEADLESS", "1") 
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    
    # Disable GUI-related warnings
    os.environ.setdefault("PYTHONWARNINGS", "ignore")

def import_open3d_safely():
    """Safely import Open3D with proper error handling for headless environments"""
    # Only configure headless mode if we're in a deployment environment
    # Check for Railway deployment or if explicitly requested
    is_deployment = (
        os.environ.get("RAILWAY_ENVIRONMENT") or 
        os.environ.get("RENDER") or 
        os.environ.get("HEROKU") or
        os.environ.get("FORCE_HEADLESS") == "1"
    )
    
    try:
        if is_deployment:
            configure_headless_environment()
            logger.info("Configuring headless environment for deployment")
        
        import open3d as o3d
        logger.info("Open3D imported successfully")
        return o3d
    except Exception as e:
        logger.error(f"Failed to import Open3D: {e}")
        
        # Only try headless fallback if not already tried
        if not is_deployment:
            try:
                logger.info("Attempting headless fallback...")
                configure_headless_environment()
                import open3d as o3d
                logger.info("Open3D imported successfully with headless fallback")
                return o3d
            except Exception as fallback_e:
                logger.error(f"Headless fallback also failed: {fallback_e}")
        
        raise ImportError(
            "Open3D failed to load. This typically happens when X11 libraries are missing. "
            "Please ensure your deployment environment includes libX11 and related graphics libraries."
        ) from e