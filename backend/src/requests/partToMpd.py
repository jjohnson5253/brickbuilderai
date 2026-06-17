"""
Part to MPD Conversion API

This module handles the conversion of individual LDraw parts to MPD format.
It creates simple LDR files containing single parts and packs them with all dependencies.
"""
import asyncio
import os
import tempfile
from typing import Optional
import logging
from pydantic import BaseModel, validator
from fastapi import HTTPException

# Import utilities
from ..utils.pack_ldraw_model import LDrawPacker
from ..utils.posthog_client import track_api_call, track_error

logger = logging.getLogger(__name__)


class PartToMpdRequest(BaseModel):
    """Request model for converting LDraw part to MPD"""
    part_number: str
    color: Optional[int] = 4  # Default to red (LDraw color 4)
    
    @validator('part_number')
    def validate_part_number(cls, v):
        if not v or not v.strip():
            raise ValueError("Part number cannot be empty")
        
        # Ensure it ends with .DAT if not already
        v = v.strip().upper()
        if not v.endswith('.DAT'):
            v += '.DAT'
        
        return v
    
    @validator('color')
    def validate_color(cls, v):
        if v is not None:
            # Valid LDraw color ranges based on LDConfig.ldr:
            # - Standard colors: 0-511
            # - Extended colors: 10000-31002 (includes Rubber, Modulex, etc.)
            if not ((0 <= v <= 511) or (10000 <= v <= 31002)):
                raise ValueError("Color must be in valid LDraw color range (0-511 or 10000-31002)")
        return v


class PartToMpdResponse(BaseModel):
    """Response model containing part MPD file content"""
    mpd_content: str
    part_number: str
    color: int
    message: str = "Successfully converted part to MPD format"


async def part_to_mpd(request: PartToMpdRequest, auth_info: dict) -> PartToMpdResponse:
    """
    Convert an LDraw part number to MPD format with all dependencies packed
    
    This endpoint:
    1. Takes an LDraw part number and optional color as input
    2. Creates a simple LDR file containing just that part in the specified color
    3. Uses the LDraw packer to bundle all dependencies
    4. Returns the packed MPD file content
    
    Authentication: TEMPORARILY allows anonymous users (normally requires sign in or API token).
    Credit usage: UNLIMITED - no credits are deducted for this endpoint.
    
    Args:
        request: JSON body containing:
        - part_number: The LDraw part number (e.g., "3004.DAT" or "3004")
        - color: Optional LDraw color number (0-511, default: 4 = red)
    
    Returns:
        JSON response containing:
        - mpd_content: The packed MPD file content
        - part_number: The processed part number
        - color: The color used
        - message: Status message
    """
    
    # Extract user info for tracking
    user_email = auth_info.get('user_email', 'anonymous')
    is_developer = auth_info.get('is_developer', False)
    auth_method = auth_info.get('auth_method', 'unknown')
    is_anonymous = auth_info.get('is_anonymous', False)
    
    # Track API call
    track_api_call(
        endpoint="/partToMpd",
        user_id=user_email,
        is_developer=is_developer,
        auth_method=auth_method,
        part_number=request.part_number,
        color=request.color
    )
    
    # Check authentication - TEMPORARILY allow anonymous users
    logger.info(f"partToMpd auth debug - user_email: {user_email}, is_anonymous: {is_anonymous}, auth_method: {auth_method}")
    
    # TEMPORARY: Allow anonymous users for partToMpd endpoint
    if is_anonymous:
        logger.info("TEMPORARY: Anonymous user allowed for partToMpd endpoint")
    else:
        logger.info(f"Authenticated user {user_email} (developer: {is_developer}) - unlimited partToMpd usage")
    
    try:
        # Create temporary files for part processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_ldr_path = os.path.join(temp_dir, "part.ldr")
            
            # Create a simple LDR file with just the requested part
            # Use the specified color and place at origin
            ldr_content = f"1 {request.color} 0 0 0 1 0 0 0 1 0 0 0 1 {request.part_number}\n"
            
            # Write LDR content to temporary file
            with open(temp_ldr_path, 'w', encoding='utf-8') as f:
                f.write(ldr_content)
            
            # Initialize the LDraw packer
            packer = LDrawPacker()
            
            # Pack the LDR file to MPD
            mpd_path = await asyncio.get_event_loop().run_in_executor(
                None, packer.pack_ldraw_model, temp_ldr_path
            )
            
            logger.info(f"Successfully packed part {request.part_number} to MPD: {mpd_path}")
            
            # Read the generated MPD file
            if not os.path.exists(mpd_path):
                raise HTTPException(
                    status_code=500,
                    detail=f"MPD file was not created successfully for part {request.part_number}"
                )
            
            with open(mpd_path, 'r', encoding='utf-8') as f:
                mpd_content = f.read()
            
            logger.info(f"Successfully converted part {request.part_number} to MPD for user {user_email}")
            
            return PartToMpdResponse(
                mpd_content=mpd_content,
                part_number=request.part_number,
                color=request.color,
                message=f"Successfully converted part {request.part_number} (color {request.color}) to MPD format"
            )
    
    except Exception as e:
        logger.error(f"Error in partToMpd endpoint: {str(e)}", exc_info=True)
        
        # Track error
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint="/partToMpd",
            user_id=user_email
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )