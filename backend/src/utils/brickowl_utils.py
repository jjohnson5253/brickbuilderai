"""
BrickOwl utility functions for LDR parsing and color mapping.

This module contains utility functions for:
- Parsing LDR files to extract parts and colors
- Loading and caching color mappings between LDraw, BrickOwl, and LEGO
- Converting LDraw color IDs to BrickOwl color IDs
- Converting LDraw color IDs to LEGO color IDs
- Creating BrickOwl wishlists via API
"""
import csv
import json
import re
from pathlib import Path
from typing import Dict, Tuple, Optional, List
import httpx
import logging

logger = logging.getLogger(__name__)


def parse_ldr_file(ldr_content: str) -> Dict[Tuple[str, int], int]:
    """
    Parse LDR file to extract part numbers, colors, and quantities
    
    LDR files are simpler than MPD files - they contain only the model data
    without embedded color configurations or sub-parts.
    
    Returns:
        Dict mapping (part_number, color_id) -> quantity
    """
    parts_dict = {}
    lines = ldr_content.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Skip comments, empty lines, and STEP markers
        if not line or line.startswith('0 '):
            continue
            
        # Look for part lines (start with "1 ")
        if line.startswith('1 '):
            parts = line.split()
            if len(parts) >= 15:  # Standard LDraw line format
                try:
                    color_id = int(parts[1])
                    part_file = parts[14].upper()
                    
                    # Remove .DAT extension if present and get part number
                    if part_file.endswith('.DAT'):
                        part_number = part_file[:-4]
                    else:
                        part_number = part_file
                    
                    key = (part_number, color_id)
                    parts_dict[key] = parts_dict.get(key, 0) + 1
                    
                except (ValueError, IndexError):
                    # Skip malformed lines
                    continue
    
    return parts_dict


def load_color_mapping() -> Dict[int, Dict[str, int]]:
    """
    Load color mapping from LDraw ID to BrickOwl ID and LEGO ID from CSV
    
    Returns:
        Dict mapping ldraw_color_id -> {"brickowl_id": int, "lego_color_id": int}
    """
    color_mapping = {}
    csv_path = Path(__file__).parent.parent.parent / "gobrick_colors.csv"
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ldraw_col = row.get('LDraw', '')
                brickowl_col = row.get('BrickOwl', '')
                lego_col = row.get('LEGO', '')
                
                # Extract IDs using regex
                ldraw_match = re.search(r'^(\d+)', ldraw_col)
                brickowl_match = re.search(r'^(\d+)', brickowl_col)
                lego_match = re.search(r'^(\d+)', lego_col)
                
                if ldraw_match and brickowl_match and lego_match:
                    ldraw_id = int(ldraw_match.group(1))
                    brickowl_id = int(brickowl_match.group(1))
                    lego_id = int(lego_match.group(1))
                    color_mapping[ldraw_id] = {
                        "brickowl_id": brickowl_id,
                        "lego_color_id": lego_id
                    }
                    
    except Exception as e:
        logger.error(f"Error loading color mapping: {e}")
    
    return color_mapping


def load_full_color_mapping() -> Dict[int, Dict[str, any]]:
    """
    Load full color mapping from LDraw ID including BrickLink ID and color name from CSV
    
    Returns:
        Dict mapping ldraw_color_id -> {
            "brickowl_id": int, 
            "lego_color_id": int, 
            "bricklink_id": int, 
            "name": str
        }
    """
    color_mapping = {}
    csv_path = Path(__file__).parent.parent.parent / "gobrick_colors.csv"
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ldraw_col = row.get('LDraw', '')
                brickowl_col = row.get('BrickOwl', '')
                lego_col = row.get('LEGO', '')
                bricklink_col = row.get('BrickLink', '')
                color_name = row.get('Name', 'Unknown')
                
                # Extract IDs using regex
                ldraw_match = re.search(r'^(\d+)', ldraw_col)
                brickowl_match = re.search(r'^(\d+)', brickowl_col)
                lego_match = re.search(r'^(\d+)', lego_col)
                bricklink_match = re.search(r'^(\d+)', bricklink_col)
                
                if ldraw_match and brickowl_match and lego_match and bricklink_match:
                    ldraw_id = int(ldraw_match.group(1))
                    brickowl_id = int(brickowl_match.group(1))
                    lego_id = int(lego_match.group(1))
                    bricklink_id = int(bricklink_match.group(1))
                    color_mapping[ldraw_id] = {
                        "brickowl_id": brickowl_id,
                        "lego_color_id": lego_id,
                        "bricklink_id": bricklink_id,
                        "name": color_name.strip()
                    }
                    
    except Exception as e:
        logger.error(f"Error loading full color mapping: {e}")
    
    return color_mapping


# Global cache for color mapping to avoid loading CSV repeatedly
_color_mapping_cache = None


def map_ldraw_to_brickowl_color(ldraw_color_id: int) -> str:
    """
    Map LDraw color ID to BrickOwl color ID using gobrick_colors.csv
    
    Uses cached mapping loaded from CSV file for efficiency.
    """
    global _color_mapping_cache
    
    # Load color mapping from CSV if not already cached
    if _color_mapping_cache is None:
        _color_mapping_cache = load_color_mapping()
        logger.info(f"Loaded color mapping from CSV with {len(_color_mapping_cache)} colors")
    
    # Get color info from mapping
    color_info = _color_mapping_cache.get(ldraw_color_id)
    
    if color_info is not None:
        return str(color_info["brickowl_id"])
    else:
        # Return None for unmapped colors (no fallback)
        logger.warning(f"Unmapped LDraw color {ldraw_color_id}, skipping part")
        return None


def map_ldraw_to_lego_color(ldraw_color_id: int) -> int:
    """
    Map LDraw color ID to LEGO color ID using gobrick_colors.csv
    
    Uses cached mapping loaded from CSV file for efficiency.
    
    Returns:
        LEGO color ID as integer, or None if not found
    """
    global _color_mapping_cache
    
    # Load color mapping from CSV if not already cached
    if _color_mapping_cache is None:
        _color_mapping_cache = load_color_mapping()
        logger.info(f"Loaded color mapping from CSV with {len(_color_mapping_cache)} colors")
    
    # Get color info from mapping
    color_info = _color_mapping_cache.get(ldraw_color_id)
    
    if color_info is not None:
        return color_info["lego_color_id"]
    else:
        # Return None for unmapped colors (no fallback)
        logger.warning(f"Unmapped LDraw color {ldraw_color_id}, skipping part")
        return None


def parts_list_to_brickowl_parts_list(parts_dict: Dict[Tuple[str, int], int]) -> List[Dict[str, any]]:
    """
    Convert a parts dictionary to BrickOwl format with color mapping.
    
    Args:
        parts_dict: Dictionary mapping (part_number, ldraw_color_id) -> quantity
        
    Returns:
        List of parts in BrickOwl format with mapped colors
    """
    brickowl_parts = []
    unmapped_colors = set()
    
    for (part_number, ldraw_color), quantity in parts_dict.items():
        # Map LDraw color to BrickOwl color using the mapping function
        brickowl_color = map_ldraw_to_brickowl_color(ldraw_color)
        
        if brickowl_color is None:
            unmapped_colors.add(ldraw_color)
            continue
        
        brickowl_parts.append({
            "boid": part_number,  # BrickOwl uses 'boid' for part ID
            "color_id": brickowl_color,  # This should be BrickOwl color ID
            "quantity": quantity
        })
    
    if unmapped_colors:
        logger.warning(f"Unmapped LDraw colors: {unmapped_colors}")
    
    return brickowl_parts


async def create_brickowl_wishlist(
    api_key: str, 
    wishlist_name: str, 
    parts: List[Dict[str, any]]
) -> Dict[str, any]:
    """
    Create a wishlist on BrickOwl using their API with batch operations for efficiency
    
    Args:
        api_key: BrickOwl API key
        wishlist_name: Name for the wishlist
        parts: List of parts with boid, color_id, and quantity (where boid is actually LDraw part number)
        
    Returns:
        API response from BrickOwl
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Create the wishlist first
        create_list_url = "https://api.brickowl.com/v1/wishlist/create_list"
        list_form_data = {
            "key": api_key,
            "name": wishlist_name,
            "description": ""
        }
        
        logger.info(f"Creating BrickOwl wishlist: {wishlist_name}")
        list_response = await client.post(create_list_url, data=list_form_data)
        list_response.raise_for_status()
        list_result = list_response.json()
        
        if "wishlist_id" not in list_result:
            raise ValueError(f"Failed to create wishlist: {list_result}")
        
        wishlist_id = list_result["wishlist_id"]
        logger.info(f"Created wishlist with ID: {wishlist_id}")
        
        # Step 2: Batch lookup BOIDs for LDraw part numbers
        batch_url = "https://api.brickowl.com/v1/bulk/batch"
        
        # Extract unique part numbers and strip "PARTS/" prefix for BrickOwl lookup
        raw_part_numbers = set(part["boid"] for part in parts)
        unique_part_numbers = []
        for part_num in raw_part_numbers:
            # Remove "PARTS/" prefix if present
            clean_part_num = part_num.replace("PARTS/", "") if part_num.startswith("PARTS/") else part_num
            unique_part_numbers.append(clean_part_num)
        
        logger.info(f"Looking up BOIDs for {len(unique_part_numbers)} unique LDraw part numbers")
        
        # Batch lookup BOIDs (up to 50 at a time)
        boid_mapping = {}
        batch_size = 50
        
        for i in range(0, len(unique_part_numbers), batch_size):
            batch_parts = unique_part_numbers[i:i + batch_size]
            
            # Prepare batch request for BOID lookup
            lookup_requests = []
            for part_num in batch_parts:
                lookup_requests.append({
                    "endpoint": "catalog/id_lookup",
                    "request_method": "GET",
                    "params": [{
                        "id": part_num,
                        "type": "Part",
                        "id_type": "design_id"
                    }]
                })
            
            # Send batch lookup request
            lookup_form_data = {
                "key": api_key,
                "requests": json.dumps({"requests": lookup_requests})
            }
            
            logger.info(f"Looking up BOIDs for batch {i//batch_size + 1} ({len(batch_parts)} parts)")
            lookup_response = await client.post(batch_url, data=lookup_form_data)
            
            if lookup_response.status_code == 200:
                lookup_results = lookup_response.json()
                
                # Process lookup results
                for j, result in enumerate(lookup_results):
                    part_num = batch_parts[j]
                    if result.get("code") == 200 and result.get("body"):
                        body = result["body"]
                        if isinstance(body, dict) and "boids" in body:
                            boids_list = body["boids"]
                            if isinstance(boids_list, list) and len(boids_list) > 0:
                                # Take the first BOID from the list
                                first_boid = boids_list[0]
                                boid_mapping[part_num] = first_boid
                                logger.info(f"Mapped {part_num} -> BOID {first_boid} (from {len(boids_list)} options)")
                            else:
                                logger.warning(f"Empty boids list for LDraw part {part_num}")
                        else:
                            logger.warning(f"No boids field in result for {part_num}: {body}")
                    else:
                        logger.warning(f"Lookup failed for {part_num}: {result}")
            else:
                logger.error(f"BOID lookup batch failed: {lookup_response.status_code} - {lookup_response.text}")
        
        logger.info(f"Successfully mapped {len(boid_mapping)} out of {len(unique_part_numbers)} part numbers to BOIDs")
        
        # Step 3: Filter parts to only those with valid BOIDs and map colors
        valid_parts = []
        for part in parts:
            ldraw_part = part["boid"]
            # Remove "PARTS/" prefix for BOID lookup (same as we did when building the mapping)
            clean_part_num = ldraw_part.replace("PARTS/", "") if ldraw_part.startswith("PARTS/") else ldraw_part
            
            if clean_part_num in boid_mapping:
                # Extract base BOID from colored BOID (remove -COLOR suffix)
                colored_boid = boid_mapping[clean_part_num]
                base_boid = colored_boid.split('-')[0] if '-' in colored_boid else colored_boid
                
                # The color_id should already be a BrickOwl color ID (not LDraw)
                # No need to map again - just use it directly
                brickowl_color = str(part["color_id"])  # Ensure it's a string for BrickOwl API
                valid_parts.append({
                    "boid": base_boid,
                    "color_id": brickowl_color,
                    "quantity": part["quantity"]
                })
            else:
                logger.warning(f"Skipping part {ldraw_part} - no BOID mapping found")
        
        if not valid_parts:
            logger.warning("No valid parts found after BOID mapping")
            return {
                "wishlist_id": wishlist_id,
                "wishlist_name": wishlist_name,
                "lots_added": 0,
                "total_parts": len(parts),
                "brickowl_url": f"https://www.brickowl.com/wishlist/view/{wishlist_id}",
                "mapping_failures": len(parts)
            }
        
        # Step 4: Create lots and update quantities
        total_added = 0
        created_lot_ids = []  # Store lot IDs for quantity updates
        
        for i in range(0, len(valid_parts), batch_size):
            batch_parts = valid_parts[i:i + batch_size]
            
            # Prepare batch request for creating lots (without quantity)
            create_lot_requests = []
            for part in batch_parts:
                logger.info(f"🔍 Creating lot: BOID={part['boid']}, color={part['color_id']}, will update quantity to {part['quantity']}")
                
                create_lot_requests.append({
                    "endpoint": "wishlist/create_lot",
                    "request_method": "POST",
                    "params": [{
                        "wishlist_id": str(wishlist_id),
                        "boid": str(part["boid"]),
                        "color_id": str(part["color_id"])
                        # Note: No quantity parameter - BrickOwl API doesn't support it in create_lot
                    }]
                })
            
            # Send batch create lot request
            lot_form_data = {
                "key": api_key,
                "requests": json.dumps({"requests": create_lot_requests})
            }
            
            logger.info(f"Creating lots for batch {i//batch_size + 1} ({len(batch_parts)} parts)")
            lot_response = await client.post(batch_url, data=lot_form_data)
            
            if lot_response.status_code == 200:
                lot_results = lot_response.json()
                
                # Process results and prepare for quantity updates
                update_requests = []
                successful_adds = 0
                
                for j, result in enumerate(lot_results):
                    if result.get("code") == 200 and result.get("body"):
                        lot_id = result["body"].get("lot_id")
                        if lot_id and j < len(batch_parts):
                            part = batch_parts[j]
                            quantity = part["quantity"]
                            
                            # Only update if quantity > 1 (BrickOwl defaults to 1)
                            if quantity > 1:
                                update_requests.append({
                                    "endpoint": "wishlist/update",
                                    "request_method": "POST",
                                    "params": [{
                                        "wishlist_id": str(wishlist_id),
                                        "lot_id": str(lot_id),
                                        "minimum_quantity": str(quantity)
                                    }]
                                })
                            
                            successful_adds += 1
                    else:
                        logger.warning(f"Failed to create lot: {result}")
                
                # Send batch update requests for quantities > 1 (smaller batches for updates)
                if update_requests:
                    update_batch_size = 10  # Smaller batch size for updates to avoid timeouts
                    
                    for k in range(0, len(update_requests), update_batch_size):
                        update_batch = update_requests[k:k + update_batch_size]
                        
                        update_form_data = {
                            "key": api_key,
                            "requests": json.dumps({"requests": update_batch})
                        }
                        
                        logger.info(f"Updating quantities for batch {k//update_batch_size + 1} ({len(update_batch)} lots)")
                        
                        try:
                            update_response = await client.post(batch_url, data=update_form_data)
                            
                            if update_response.status_code == 200:
                                update_results = update_response.json()
                                successful_updates = sum(1 for r in update_results if r.get("code") == 200)
                                logger.info(f"Successfully updated {successful_updates}/{len(update_batch)} lot quantities")
                            else:
                                logger.error(f"Update quantities batch failed: {update_response.status_code} - {update_response.text}")
                                
                        except Exception as e:
                            logger.error(f"Error updating quantities batch: {str(e)}")
                            # Continue with other batches even if one fails
                
                total_added += successful_adds
                logger.info(f"Batch completed: {successful_adds}/{len(batch_parts)} lots created successfully")
            else:
                logger.error(f"Create lot batch failed: {lot_response.status_code} - {lot_response.text}")
        
        return {
            "wishlist_id": wishlist_id,
            "wishlist_name": wishlist_name,
            "lots_added": total_added,
            "total_parts": len(parts),
            "valid_parts": len(valid_parts),
            "mapping_failures": len(parts) - len(valid_parts),
            "brickowl_url": f"https://www.brickowl.com/wishlist/view/{wishlist_id}"
        }


async def create_wishlist_from_generation_id(
    generation_id: str,
    api_key: str,
    wishlist_name: Optional[str] = None
) -> Optional[str]:
    """
    Create a BrickOwl wishlist from a generation ID
    
    This function:
    1. Gets the parts list for the generation using generation_storage
    2. Converts the parts to BrickOwl format
    3. Creates a wishlist on BrickOwl
    
    Args:
        generation_id: The generation ID to create wishlist from
        api_key: BrickOwl API key
        wishlist_name: Optional custom wishlist name (defaults to generation_id)
        
    Returns:
        BrickOwl wishlist URL, or None if failed
    """
    from .generation_storage import generation_storage
    from datetime import datetime
    
    try:
        # Get parts list from generation
        parts_dict = await generation_storage.get_parts_list(generation_id)
        if not parts_dict:
            logger.error(f"Failed to get parts list for generation {generation_id}")
            return None
        
        # Convert to BrickOwl format
        brickowl_parts = parts_list_to_brickowl_parts_list(parts_dict)
        if not brickowl_parts:
            logger.error(f"No parts could be mapped to BrickOwl for generation {generation_id}")
            return None
        
        # Create wishlist name if not provided
        if not wishlist_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            wishlist_name = f"generation_{generation_id}_{timestamp}"
        
        # Create wishlist on BrickOwl
        response = await create_brickowl_wishlist(api_key, wishlist_name, brickowl_parts)
        
        brickowl_url = response.get("brickowl_url")
        if brickowl_url:
            logger.info(f"Created BrickOwl wishlist for generation {generation_id}: {brickowl_url}")
            return brickowl_url
        else:
            logger.error(f"No URL returned from BrickOwl API for generation {generation_id}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to create wishlist from generation {generation_id}: {e}")
        return None


# Global cache for full color mapping
_full_color_mapping_cache = None


# Part weights in kg (per piece)
PART_WEIGHTS: Dict[str, float] = {
    "2456.dat": 0.003261,
    "3001.dat": 0.002226,
    "3003.dat": 0.001164,
    "3004.dat": 0.000794,
    "3005.dat": 0.000427,
    "3010.dat": 0.00153,
}

# Default weight for parts not in the weights table (in kg)
DEFAULT_PART_WEIGHT = 0.001


def generate_parts_list_csv(ldr_content: str) -> str:
    """
    Generate a parts list CSV from LDR content.
    
    This function parses the LDR file and creates a CSV with columns:
    BLItemNo, ElementId, LdrawId, PartName, BLColorId, LDrawColorId, ColorName, ColorCategory, Qty, Weight
    
    Args:
        ldr_content: The LDR file content as a string
        
    Returns:
        CSV content as a string
    """
    global _full_color_mapping_cache
    
    # Load full color mapping if not cached
    if _full_color_mapping_cache is None:
        _full_color_mapping_cache = load_full_color_mapping()
        logger.info(f"Loaded full color mapping with {len(_full_color_mapping_cache)} colors")
    
    # Parse LDR file to get parts
    parts_dict = parse_ldr_file(ldr_content)
    
    # Create CSV rows
    headers = ['BLItemNo', 'ElementId', 'LdrawId', 'PartName', 'BLColorId', 'LDrawColorId', 'ColorName', 'ColorCategory', 'Qty', 'Weight']
    rows = []
    
    for (part_number, ldraw_color), quantity in parts_dict.items():
        color_info = _full_color_mapping_cache.get(ldraw_color)
        bricklink_color_id = color_info['bricklink_id'] if color_info else ldraw_color
        color_name = color_info['name'] if color_info else 'Unknown'
        
        # LdrawId is the lowercase part file name with .dat extension
        ldraw_id = f"{part_number.lower()}.dat"
        
        # Get weight from weights table, default if not found
        weight = PART_WEIGHTS.get(ldraw_id, DEFAULT_PART_WEIGHT)
        
        row = [
            part_number,           # BLItemNo
            '',                    # ElementId (empty)
            ldraw_id,              # LdrawId (lowercase .dat)
            '',                    # PartName (empty)
            str(bricklink_color_id),  # BLColorId (BrickLink color)
            str(ldraw_color),      # LDrawColorId
            color_name,            # ColorName
            'Solid Colors',        # ColorCategory (hardcoded)
            str(quantity),         # Qty
            str(weight)            # Weight (in kg)
        ]
        rows.append(row)
    
    # Sort rows by part number and color
    rows.sort(key=lambda r: (r[0], int(r[5]) if r[5].isdigit() else 0))
    
    # Calculate totals
    total_qty = sum(int(row[8]) for row in rows)  # Qty is at index 8
    total_weight = sum(float(row[9]) * int(row[8]) for row in rows)  # Weight * Qty
    
    # Build CSV content
    csv_lines = [','.join(headers)]
    for row in rows:
        csv_lines.append(','.join(row))
    
    return '\n'.join(csv_lines)