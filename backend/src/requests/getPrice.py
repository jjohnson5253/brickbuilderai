"""
Get Price API

This module handles price calculation for a generation based on its parts list CSV.
"""
import csv
import io
import logging
from typing import Dict, Optional

import httpx
from pydantic import BaseModel
from fastapi import HTTPException

from ..utils.posthog_client import track_api_call, track_error
from ..utils.generation_storage import generation_storage

logger = logging.getLogger(__name__)

# Part pricing table (part_id with .dat extension -> cost in USD)
PART_PRICES: Dict[str, float] = {
    "2456.dat": 0.22,
    "3001.dat": 0.15,
    "3003.dat": 0.09,
    "3004.dat": 0.06,
    "3005.dat": 0.04,
    "3010.dat": 0.10,
}

# Default price for parts not in the pricing table
DEFAULT_PART_PRICE = 0.10

# Margin/upsale percentage to add to the final price (0.20 = 20%)
MARGIN_UPSALE_PERCENTAGE = 0.20


class GetPriceRequest(BaseModel):
    """Request model for getting price from generation ID"""
    generation_id: str


class PartPriceDetail(BaseModel):
    """Price detail for a single part type"""
    part_id: str
    quantity: int
    unit_price: float
    total_price: float


class GetPriceResponse(BaseModel):
    """Response model for price calculation"""
    generation_id: str
    total_price: float
    total_parts: int
    total_weight: float  # Total weight in kg
    unique_part_types: int
    currency: str = "USD"
    parts_breakdown: list[PartPriceDetail] = []
    message: str


async def fetch_csv_content(url: str) -> str:
    """
    Fetch CSV content from a URL
    
    Args:
        url: URL to fetch the CSV from
        
    Returns:
        CSV content as string
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def parse_parts_list_csv(csv_content: str) -> tuple[Dict[str, int], float]:
    """
    Parse the parts list CSV and return part quantities and total weight
    
    The CSV has columns: BLItemNo, ElementId, LdrawId, PartName, BLColorId, LDrawColorId, ColorName, ColorCategory, Qty, Weight
    We use LdrawId (lowercase .dat format) to match against our pricing table
    Total weight is calculated from Weight * Qty for each row
    
    Args:
        csv_content: CSV content as string
        
    Returns:
        Tuple of (Dict mapping part_id (LdrawId) -> total quantity, total_weight in kg)
    """
    parts_dict: Dict[str, int] = {}
    total_weight = 0.0
    
    # Parse the parts data
    reader = csv.DictReader(io.StringIO(csv_content))
    
    for row in reader:
        ldraw_id = row.get('LdrawId', '').strip()
        qty_str = row.get('Qty', '0').strip()
        weight_str = row.get('Weight', '0').strip()
        
        if not ldraw_id:
            continue
            
        try:
            quantity = int(qty_str)
        except ValueError:
            quantity = 0
        
        try:
            weight_per_piece = float(weight_str)
        except ValueError:
            weight_per_piece = 0.0
            
        if quantity > 0:
            # Aggregate by part_id (ignore color for pricing)
            if ldraw_id in parts_dict:
                parts_dict[ldraw_id] += quantity
            else:
                parts_dict[ldraw_id] = quantity
            
            # Add to total weight (weight per piece * quantity)
            total_weight += weight_per_piece * quantity
    
    return parts_dict, total_weight


def calculate_price(parts_dict: Dict[str, int]) -> tuple[float, list[PartPriceDetail]]:
    """
    Calculate total price based on parts and pricing table
    
    Args:
        parts_dict: Dict mapping part_id -> quantity
        
    Returns:
        Tuple of (total_price, list of part price details)
    """
    total_price = 0.0
    parts_breakdown = []
    
    for part_id, quantity in parts_dict.items():
        unit_price = PART_PRICES.get(part_id, DEFAULT_PART_PRICE)
        part_total = unit_price * quantity
        total_price += part_total
        
        parts_breakdown.append(PartPriceDetail(
            part_id=part_id,
            quantity=quantity,
            unit_price=unit_price,
            total_price=round(part_total, 2)
        ))
    
    # Sort breakdown by total price descending
    parts_breakdown.sort(key=lambda x: x.total_price, reverse=True)
    
    return round(total_price, 2), parts_breakdown


async def get_price(request: GetPriceRequest, auth_info: dict) -> GetPriceResponse:
    """
    Get price for a generation based on its parts list CSV
    
    This endpoint:
    1. Looks up the generation by ID
    2. Fetches the parts_list_csv_url from the generations table
    3. Downloads and parses the CSV
    4. Calculates price based on the pricing table
    """
    user_email = auth_info.get("user_email", "anonymous") if isinstance(auth_info, dict) else "anonymous"
    
    try:
        logger.info(f"Getting price for generation: {request.generation_id}")
        
        # Track API call
        track_api_call(
            endpoint="/getPrice",
            user_id=user_email,
            request_data={"generation_id": request.generation_id}
        )
        
        # Fetch generation from database
        generation = await generation_storage.get_generation(request.generation_id)
        if not generation:
            raise HTTPException(
                status_code=404,
                detail=f"Generation {request.generation_id} not found"
            )
        
        # Get parts_list_csv_url
        parts_list_csv_url = generation.get("parts_list_csv_url")
        if not parts_list_csv_url:
            raise HTTPException(
                status_code=400,
                detail=f"Parts list CSV not found for generation {request.generation_id}"
            )
        
        logger.info(f"Fetching parts list CSV from: {parts_list_csv_url}")
        
        # Fetch and parse CSV
        try:
            csv_content = await fetch_csv_content(parts_list_csv_url)
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch CSV: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch parts list CSV: {e.response.status_code}"
            )
        except Exception as e:
            logger.error(f"Failed to fetch CSV: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch parts list CSV: {str(e)}"
            )
        
        # Parse CSV
        parts_dict, total_weight = parse_parts_list_csv(csv_content)
        
        if not parts_dict:
            raise HTTPException(
                status_code=400,
                detail="No valid parts found in parts list CSV"
            )
        
        # Calculate price
        base_price, parts_breakdown = calculate_price(parts_dict)
        total_parts = sum(parts_dict.values())
        unique_part_types = len(parts_dict)
        
        # Apply margin upsale percentage
        total_price = round(base_price * (1 + MARGIN_UPSALE_PERCENTAGE), 2)
        
        logger.info(f"Price calculated: ${base_price} + {MARGIN_UPSALE_PERCENTAGE*100}% margin = ${total_price} for {total_parts} parts ({unique_part_types} unique types), weight: {total_weight}kg")
        
        message = f"Price estimate: ${total_price:.2f} USD for {total_parts} parts"
        
        return GetPriceResponse(
            generation_id=request.generation_id,
            total_price=total_price,
            total_parts=total_parts,
            total_weight=total_weight,
            unique_part_types=unique_part_types,
            currency="USD",
            parts_breakdown=parts_breakdown,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price: {str(e)}", exc_info=True)
        
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint="/getPrice",
            user_id=user_email
        )
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
