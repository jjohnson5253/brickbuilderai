"""
LDR Price Estimation API

This module handles price estimation for LDR (LEGO Draw) files using BrickOwl's catalog cart API.
"""
import asyncio
import json
import os
from typing import Dict, List, Optional
import httpx
from pydantic import BaseModel, validator
from fastapi import HTTPException

from ..utils.brickowl_utils import parse_ldr_file, map_ldraw_to_lego_color

import logging
logger = logging.getLogger(__name__)


class PartItem(BaseModel):
    """Individual part item in the parts list"""
    design_id: str  # LDraw part number (without PARTS/ prefix)
    color_id: int   # LEGO color ID
    quantity: int


class EstimatePriceRequest(BaseModel):
    """Request model for estimating price from LDR"""
    ldr_content: str
    condition: str = "usedg"  # new, news, newc, newi, used, usedc, usedi, usedn, usedg, useda, other
    country: str = "US"  # shipping destination country
    user_email: str
    
    @validator('ldr_content')
    def validate_ldr_content(cls, v):
        if not v or not v.strip():
            raise ValueError("LDR content cannot be empty")
        return v
    
    @validator('condition')
    def validate_condition(cls, v):
        valid_conditions = [
            "new",      # New
            "news",     # New (Sealed)
            "newc",     # New (Complete)
            "newi",     # New (Incomplete)
            "used",     # Used
            "usedc",    # Used (Complete)
            "usedi",    # Used (Incomplete)
            "usedn",    # Used (Like New)
            "usedg",    # Used (Good)
            "useda",    # Used (Acceptable)
            "other"     # Other
        ]
        if v not in valid_conditions:
            raise ValueError(f"Condition must be one of: {valid_conditions}")
        return v
    
    @validator('user_email')
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError("User email cannot be empty")
        # Basic email validation
        if '@' not in v or '.' not in v:
            raise ValueError("Invalid email format")
        return v


class EstimatePriceResponse(BaseModel):
    """Response model for price estimation"""
    cart_id: Optional[str]
    total_price: Optional[str]
    currency: Optional[str]
    parts_count: int
    mapped_parts: int
    unmapped_parts: int
    message: str
    parts_list: List[PartItem] = []  # Same format as sent to BrickOwl catalog API


async def get_price_estimate_from_brickowl(
    api_key: str,
    parts: List[Dict[str, any]],
    condition: str = "usedg",
    country: str = "US"
) -> Dict[str, any]:
    """
    Get price estimate from BrickOwl using catalog/cart_basic endpoint
    
    Args:
        api_key: BrickOwl API key
        parts: List of parts with design_id, color_id (LEGO), and quantity
        condition: Part condition (new, news, newc, newi, used, usedc, usedi, usedn, usedg, useda, other)
        country: Shipping destination country code
        
    Returns:
        Price estimation response from BrickOwl
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Prepare items for BrickOwl cart API
        items = []
        for part in parts:
            items.append({
                "design_id": part["design_id"],
                "color_id": part["color_id"],  # LEGO color ID
                "qty": str(part["quantity"])
            })
        
        items_data = {"items": items}
        
        # Prepare request parameters
        params = {
            "key": api_key,
            "items": json.dumps(items_data),
            "condition": condition,
            "country": country
        }
        
        logger.info(f"Getting price estimate for {len(items)} parts (condition: {condition}, country: {country})")
        
        # Make request to BrickOwl catalog/cart_basic endpoint
        cart_url = "https://api.brickowl.com/v1/catalog/cart_basic"
        response = await client.post(cart_url, data=params)
        
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON response: {response.text}")
        else:
            raise httpx.HTTPStatusError(
                message=f"API error: {response.status_code}",
                request=response.request,
                response=response
            )


async def estimate_price(request: EstimatePriceRequest, auth_info: dict):
    """
    Estimate price for an LDR file using BrickOwl catalog prices
    
    This endpoint:
    1. Parses the LDR file to extract parts and colors
    2. Maps LDraw color IDs to LEGO color IDs using the CSV
    3. Calls BrickOwl catalog/cart_basic API to get price estimates
    """
    from ..utils.posthog_client import track_api_call, track_error
    
    try:
        # Extract user email from auth info
        user_email = auth_info.get('user_email', 'unknown')
        logger.info(f"Estimating price for user: {user_email}")
        
        # Get BrickOwl API key from environment
        brickowl_api_key = os.getenv("BRICKOWL_API_KEY")
        if not brickowl_api_key:
            raise HTTPException(
                status_code=500,
                detail="BrickOwl API key not configured"
            )
        
        # Track API call
        track_api_call(
            endpoint="/estimatePrice",
            user_id=user_email,
            request_data={
                "ldr_content_length": len(request.ldr_content),
                "condition": request.condition,
                "country": request.country,
                "user_email": request.user_email
            }
        )
        
        # Parse LDR file
        parts_dict = parse_ldr_file(request.ldr_content)
        total_parts_parsed = sum(parts_dict.values())
        logger.info(f"Parsed {len(parts_dict)} unique part/color combinations, {total_parts_parsed} total parts")
        
        if not parts_dict:
            raise HTTPException(
                status_code=400,
                detail="No valid parts found in LDR file"
            )
        
        # Map parts to BrickOwl format with LEGO color IDs
        brickowl_parts = []
        unmapped_colors = set()
        total_parts = 0
        
        for (part_number, ldraw_color), quantity in parts_dict.items():
            total_parts += quantity
            
            # Map LDraw color to LEGO color using the mapping function
            lego_color = map_ldraw_to_lego_color(ldraw_color)
            
            if lego_color is None:
                unmapped_colors.add(ldraw_color)
                continue
            
            # Remove "PARTS/" prefix if present for BrickOwl API
            design_id = part_number.replace("PARTS/", "") if part_number.startswith("PARTS/") else part_number
            
            brickowl_parts.append({
                "design_id": design_id,
                "color_id": lego_color,  # LEGO color ID for BrickOwl catalog API
                "quantity": quantity
            })
        
        if unmapped_colors:
            logger.warning(f"Unmapped LDraw colors: {unmapped_colors}")
        
        if not brickowl_parts:
            raise HTTPException(
                status_code=400,
                detail=f"No parts could be mapped. Unmapped colors: {list(unmapped_colors)}"
            )
        
        logger.info(f"Mapped {len(brickowl_parts)} part types, {len(unmapped_colors)} unmapped colors")

        total_brickowl_parts = sum(part["quantity"] for part in brickowl_parts)

        # Get price estimate from BrickOwl
        try:
            # Comment out brickowl API call. Doesn't work for more than 50 unique parts.
            # price_response = await get_price_estimate_from_brickowl(
            #     brickowl_api_key,
            #     brickowl_parts,
            #     request.condition,
            #     request.country
            # )
            
            # cart_id = price_response.get("cart_id")
            # total_price = price_response.get("total")  # BrickOwl returns "total", not "total_price"
            # currency = price_response.get("currency")
            
            # Just estimate price based on $0.10 per part.
            total_price = total_brickowl_parts * 0.10 # estimate $0.10 per part
            total_price = round(total_price, 2)  # round to 2 decimal places
            cart_id = "null"
            currency = "USD"
            
            logger.info(f"Price estimation completed: {total_price} {currency}")
            
            mapped_parts = len(brickowl_parts)
            unmapped_parts = len(parts_dict) - mapped_parts
            
            message = f"Price estimate: {total_price} {currency} for {mapped_parts} part types"
            if unmapped_parts > 0:
                message += f" ({unmapped_parts} part types could not be mapped)"
            
            
            logger.info(f"Returning response with {len(brickowl_parts)} part types, {total_brickowl_parts} total parts")
            logger.info(f"Cart id: {cart_id}")

            return EstimatePriceResponse(
                cart_id=cart_id,
                total_price=str(total_price) if total_price is not None else None,
                currency=currency,
                parts_count=total_brickowl_parts,
                mapped_parts=mapped_parts,
                unmapped_parts=unmapped_parts,
                message=message,
                parts_list=brickowl_parts
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
                    detail_msg = "Invalid BrickOwl API key. Please check your API key is correct."
                else:
                    detail_msg = f"BrickOwl API permission denied: {error_details}"
            elif e.response.status_code == 401:
                detail_msg = "BrickOwl API authentication failed. Please check your API key."
            elif e.response.status_code == 400:
                detail_msg = f"BrickOwl API bad request: {error_details}"
            else:
                detail_msg = f"({e.response.status_code}): {error_details}"
                
            raise HTTPException(
                status_code=400,
                detail=detail_msg
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error estimating price: {str(e)}", exc_info=True)
        
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint="/estimatePrice",
            user_id=user_email
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )