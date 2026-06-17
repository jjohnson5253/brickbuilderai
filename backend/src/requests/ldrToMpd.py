"""
LDR to MPD Conversion API

This module handles the conversion of LDR (LEGO Draw) files to MPD format.
It includes functionality to create both full models and last-step-only models.
"""
import asyncio
import os
import tempfile
import logging
from pydantic import BaseModel, validator
from fastapi import HTTPException

# Import utilities
from ..utils.pack_ldraw_model import LDrawPacker
from ..utils.posthog_client import track_api_call, track_error

logger = logging.getLogger(__name__)


class LdrToMpdRequest(BaseModel):
    """Request model for converting LDR to MPD"""
    ldr_content: str
    
    @validator('ldr_content')
    def validate_ldr_content(cls, v):
        if not v or not v.strip():
            raise ValueError("LDR content cannot be empty")
        return v


class LdrToMpdResponse(BaseModel):
    """Response model containing MPD file content"""
    mpd_content: str
    mpd_last_step_content: str
    message: str = "Successfully converted LDR to MPD format"


def extract_last_step_from_ldr(ldr_content: str) -> str:
    """
    Extract only the last step from an LDR file content
    Returns LDR content containing only bricks from the final step
    """
    lines = ldr_content.strip().split('\n')
    last_step_lines = []
    current_step_lines = []
    
    for line in lines:
        line = line.strip()
        if line == "0 STEP":
            # Save current step as the last step seen so far
            if current_step_lines:
                last_step_lines = current_step_lines.copy()
            current_step_lines = []
        elif line.startswith("1 "):  # Brick line
            current_step_lines.append(line)
    
    # If there were lines after the last STEP, those are the final step
    if current_step_lines:
        last_step_lines = current_step_lines
    
    # If no steps found, return all brick lines
    if not last_step_lines:
        last_step_lines = [line for line in lines if line.strip().startswith("1 ")]
    
    return '\n'.join(last_step_lines) + '\n'


async def ldr_to_mpd(request: LdrToMpdRequest, auth_info: dict) -> LdrToMpdResponse:
    """
    Convert an LDR file to MPD format with all dependencies packed
    
    This endpoint:
    1. Takes LDR file content as input
    2. Uses the LDraw packer to bundle all dependencies
    3. Returns TWO packed MPD files:
       - Full model with all steps
       - Last step only model
    
    Authentication: TEMPORARILY allows anonymous users (normally requires sign in or API token).
    Credit usage: UNLIMITED - no credits are deducted for this endpoint.
    
    Args:
        request: JSON body containing:
        - ldr_content: The LDR file content as a string
    
    Returns:
        JSON response containing:
        - mpd_content: The packed MPD file content (full model)
        - mpd_last_step_content: The packed MPD file content (last step only)
        - message: Status message
    """
    
    # Extract user info for tracking (same as imageToBricks)
    user_email = auth_info.get('user_email', 'anonymous')
    is_developer = auth_info.get('is_developer', False)
    auth_method = auth_info.get('auth_method', 'unknown')
    is_anonymous = auth_info.get('is_anonymous', False)
    
    # Track API call - simple tracking for logged-in users only
    track_api_call(
        endpoint="/ldrToMpd",
        user_id=user_email,
        is_developer=is_developer,
        auth_method=auth_method,
        ldr_content_length=len(request.ldr_content)
    )
    
    # Check authentication - TEMPORARILY allow anonymous users
    # No credit deduction for this endpoint (unlimited usage for all users)
    logger.info(f"ldrToMpd auth debug - user_email: {user_email}, is_anonymous: {is_anonymous}, auth_method: {auth_method}")
    
    # TEMPORARY: Allow anonymous users for ldrToMpd endpoint
    if is_anonymous:
        logger.info("TEMPORARY: Anonymous user allowed for ldrToMpd endpoint")
    else:
        logger.info(f"Authenticated user {user_email} (developer: {is_developer}) - unlimited ldrToMpd usage")
    
    try:
        # Create temporary files for LDR processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_ldr_path = os.path.join(temp_dir, "input.ldr")
            
            # Write LDR content to temporary file
            with open(temp_ldr_path, 'w', encoding='utf-8') as f:
                f.write(request.ldr_content)
            
            # Initialize the LDraw packer (same as imageToBricks endpoint)
            packer = LDrawPacker()
            
            # Pack the LDR file to MPD
            mpd_path = await asyncio.get_event_loop().run_in_executor(
                None, packer.pack_ldraw_model, temp_ldr_path
            )
            
            logger.info(f"Successfully packed LDR to MPD: {mpd_path}")
            
            # No credit deduction - this endpoint is unlimited for authenticated users
            logger.info(f"LDR to MPD conversion completed for {user_email} - no credit deduction")
            
            # Read the generated MPD file
            if not os.path.exists(mpd_path):
                raise HTTPException(
                    status_code=500,
                    detail="MPD file was not created successfully"
                )
            
            with open(mpd_path, 'r', encoding='utf-8') as f:
                mpd_content = f.read()
            
            # Create last step only MPD
            last_step_ldr_content = extract_last_step_from_ldr(request.ldr_content)
            temp_last_step_ldr_path = os.path.join(temp_dir, "input_last_step.ldr")
            
            # Write last step LDR content to temporary file
            with open(temp_last_step_ldr_path, 'w', encoding='utf-8') as f:
                f.write(last_step_ldr_content)
            
            # Pack the last step LDR to MPD
            last_step_mpd_path = await asyncio.get_event_loop().run_in_executor(
                None, packer.pack_ldraw_model, temp_last_step_ldr_path
            )
            
            logger.info(f"Successfully packed last step LDR to MPD: {last_step_mpd_path}")
            
            # Read the last step MPD file
            if not os.path.exists(last_step_mpd_path):
                raise HTTPException(
                    status_code=500,
                    detail="Last step MPD file was not created successfully"
                )
            
            with open(last_step_mpd_path, 'r', encoding='utf-8') as f:
                last_step_mpd_content = f.read()
            
            logger.info(f"Successfully converted LDR to MPD (full + last step) for user {user_email}")
            
            return LdrToMpdResponse(
                mpd_content=mpd_content,
                mpd_last_step_content=last_step_mpd_content,
                message="Successfully converted LDR to MPD format (full model + last step only)"
            )
    
    except Exception as e:
        logger.error(f"Error in ldrToMpd endpoint: {str(e)}", exc_info=True)
        
        # Track error
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint="/ldrToMpd",
            user_id=user_email
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )