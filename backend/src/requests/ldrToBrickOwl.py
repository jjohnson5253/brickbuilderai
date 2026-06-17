"""
LDR to BrickOwl Wishlist Creation API

This module handles the conversion of LDR (LEGO Draw) files to BrickOwl wishlists.
It includes BOID lookup and wishlist creation.
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
import httpx
from pydantic import BaseModel, validator
from fastapi import HTTPException

from ..utils.brickowl_utils import parse_ldr_file, map_ldraw_to_brickowl_color, create_brickowl_wishlist, parts_list_to_brickowl_parts_list

import logging
logger = logging.getLogger(__name__)


class LdrToBrickOwlRequest(BaseModel):
    """Request model for creating BrickOwl wishlist from LDR"""
    ldr_content: str
    brickowl_api_key: str
    user_email: str
    
    @validator('ldr_content')
    def validate_ldr_content(cls, v):
        if not v or not v.strip():
            raise ValueError("LDR content cannot be empty")
        return v
    
    @validator('brickowl_api_key')
    def validate_api_key(cls, v):
        if not v or not v.strip():
            raise ValueError("BrickOwl API key cannot be empty")
        return v
    
    @validator('user_email')
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError("User email cannot be empty")
        # Basic email validation
        if '@' not in v or '.' not in v:
            raise ValueError("Invalid email format")
        return v


class LdrToBrickOwlResponse(BaseModel):
    """Response model for BrickOwl wishlist creation"""
    wishlist_id: Optional[str]
    wishlist_name: str
    parts_count: int
    brickowl_url: Optional[str]
    message: str


async def ldr_to_brickowl(request: LdrToBrickOwlRequest, auth_info: dict):
    """
    Create a BrickOwl wishlist from an LDR file
    
    This endpoint:
    1. Parses the LDR file to extract parts and colors
    2. Maps LDraw color IDs to BrickOwl color IDs using the CSV
    3. Creates a wishlist on BrickOwl with the mapped parts
    """
    from ..utils.posthog_client import track_api_call, track_error
    
    try:
        # Extract user email from auth info
        user_email = auth_info.get('user_email', 'unknown')
        logger.info(f"Creating BrickOwl wishlist for user: {user_email}")
        
        # Track API call
        track_api_call(
            endpoint="/ldrToBrickOwl",
            user_id=user_email,
            request_data={
                "ldr_content_length": len(request.ldr_content),
                "user_email": request.user_email
            }
        )
        
        # Parse LDR file
        parts_dict = parse_ldr_file(request.ldr_content)
        logger.info(f"Parsed {len(parts_dict)} unique part/color combinations")
        
        if not parts_dict:
            raise HTTPException(
                status_code=400,
                detail="No valid parts found in LDR file"
            )
        
        # Map parts to BrickOwl format
        brickowl_parts = parts_list_to_brickowl_parts_list(parts_dict)
        
        if not brickowl_parts:
            raise HTTPException(
                status_code=400,
                detail="No parts could be mapped to BrickOwl. Check logs for unmapped colors."
            )
        
        # Create wishlist name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        wishlist_name = f"image2brick_build_{request.user_email}_{timestamp}"
        
        # Create wishlist on BrickOwl
        try:
            brickowl_response = await create_brickowl_wishlist(
                request.brickowl_api_key,
                wishlist_name,
                brickowl_parts
            )
            
            wishlist_id = brickowl_response.get("wishlist_id")
            brickowl_url = brickowl_response.get("brickowl_url")
            lots_added = brickowl_response.get("lots_added", 0)
            valid_parts = brickowl_response.get("valid_parts", 0)
            mapping_failures = brickowl_response.get("mapping_failures", 0)
            
            logger.info(f"BrickOwl integration completed: {lots_added} lots added, {mapping_failures} mapping failures")
            
            message = f"Successfully created BrickOwl wishlist with {lots_added} parts"
            if mapping_failures > 0:
                message += f" ({mapping_failures} parts could not be mapped to BrickOwl BOIDs)"
            
            return LdrToBrickOwlResponse(
                wishlist_id=wishlist_id,
                wishlist_name=wishlist_name,
                parts_count=lots_added,
                brickowl_url=brickowl_url,
                message=message
            )
            
        except httpx.HTTPStatusError as e:
            error_details = ""
            try:
                error_response = e.response.json()
                error_details = error_response.get("error", e.response.text)
            except:
                error_details = e.response.text
                
            logger.error(f"BrickOwl API error: {e.response.status_code} - {error_details}")
            
            if e.response.status_code == 403:
                if "Invalid key" in error_details:
                    detail_msg = "Invalid BrickOwl API key. Please check your API key is correct and has permission to create wishlists."
                else:
                    detail_msg = f"BrickOwl API permission denied: {error_details}"
            elif e.response.status_code == 401:
                detail_msg = "BrickOwl API authentication failed. Please check your API key."
            elif e.response.status_code == 400:
                detail_msg = f"BrickOwl API bad request: {error_details}"
            else:
                detail_msg = f"API error ({e.response.status_code}): {error_details}"
                
            raise HTTPException(
                status_code=400,
                detail=detail_msg
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating BrickOwl wishlist: {str(e)}", exc_info=True)
        
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint="/ldrToBrickOwl",
            user_id=user_email
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )