"""
Update LDR and Parts List API

This module handles updating an existing generation's LDR file and parts list CSV.
"""
import logging
import time
from typing import Optional

from pydantic import BaseModel
from fastapi import HTTPException

from ..utils.generation_storage import generation_storage
from ..utils.brickowl_utils import generate_parts_list_csv
from ..utils.posthog_client import track_api_call, track_error
from ..utils.auth import handle_auth_and_tracking

logger = logging.getLogger(__name__)


class UpdateLdrAndPartsListRequest(BaseModel):
    generation_id: str
    ldr_content: str


class UpdateLdrAndPartsListResponse(BaseModel):
    generation_id: str
    ldr_url: str
    parts_list_csv_url: Optional[str] = None
    success: bool
    message: str = "Successfully updated LDR and parts list"


async def update_ldr_and_parts_list(request: UpdateLdrAndPartsListRequest, auth_info: dict) -> UpdateLdrAndPartsListResponse:
    """
    Update a generation's LDR file and parts list CSV
    
    This endpoint:
    1. Verifies the generation exists
    2. Uploads new LDR content to Supabase storage
    3. Updates the ldr_url in the generations table
    4. Generates a new parts list CSV from the LDR content
    5. Uploads the CSV to Supabase storage
    6. Updates the parts_list_csv_url in the generations table
    
    Args:
        request: UpdateLdrAndPartsListRequest containing generation_id and ldr_content
        auth_info: Authentication information
        
    Returns:
        UpdateLdrAndPartsListResponse with updated URLs
    """
    user_email = "anonymous"
    
    # Allowed emails for this endpoint
    ALLOWED_EMAILS = ["jakejohnson3700@gmail.com"]
    
    try:
        # Require authentication
        if not auth_info or not auth_info.get("authenticated"):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user_email = auth_info.get("user_email", "")
        
        # Check if user is in the allowed list
        if user_email not in ALLOWED_EMAILS:
            logger.warning(f"Unauthorized access attempt to /updateLdrAndPartsList by {user_email}")
            raise HTTPException(status_code=403, detail="You are not authorized to use this endpoint")
        
        # Handle authentication and tracking
        track_properties = {
            "generation_id": request.generation_id,
            "ldr_content_length": len(request.ldr_content),
        }
        
        user_info = handle_auth_and_tracking(
            auth_info=auth_info,
            endpoint="/updateLdrAndPartsList", 
            track_properties=track_properties,
            required_credits=0  # No credits required - just updating existing data
        )
        
        user_email = user_info["user_email"]
        is_developer = user_info["is_developer"]

        # Verify the generation exists
        generation = await generation_storage.get_generation(request.generation_id)
        if not generation:
            raise HTTPException(status_code=404, detail=f"Generation {request.generation_id} not found")

        logger.info(f"Updating LDR and parts list for generation: {request.generation_id}")

        # Use a timestamp to create unique file paths and bust CDN cache
        timestamp = int(time.time())

        # Upload LDR file with timestamped path
        ldr_file_path = f"generations/{request.generation_id}/ldr_model_{timestamp}.ldr"
        ldr_url = await generation_storage._upload_file_to_storage(
            file_content=request.ldr_content,
            file_path=ldr_file_path,
            content_type="text/plain"
        )
        
        # Update the ldr_url in the generations table
        generation_storage.client.table("generations").update(
            {"ldr_url": ldr_url}
        ).eq("id", request.generation_id).execute()
        
        logger.info(f"Successfully stored LDR file: {ldr_url}")

        # Generate the parts list CSV and upload with timestamped path
        csv_content = generate_parts_list_csv(request.ldr_content)
        csv_file_path = f"generations/{request.generation_id}/parts_list_{timestamp}.csv"
        parts_list_csv_url = await generation_storage._upload_file_to_storage(
            file_content=csv_content,
            file_path=csv_file_path,
            content_type="text/csv"
        )
        
        # Update the parts_list_csv_url in the generations table
        generation_storage.client.table("generations").update(
            {"parts_list_csv_url": parts_list_csv_url}
        ).eq("id", request.generation_id).execute()
        
        if not parts_list_csv_url:
            logger.warning(f"Failed to store parts list CSV for generation {request.generation_id}")
        else:
            logger.info(f"Successfully stored parts list CSV: {parts_list_csv_url}")

        # Track successful update
        track_api_call(
            endpoint="/updateLdrAndPartsList",
            user_id=user_email,
            success=True,
            generation_id=request.generation_id,
            is_developer=is_developer
        )

        logger.info(f"Successfully updated LDR and parts list for generation {request.generation_id}")

        return UpdateLdrAndPartsListResponse(
            generation_id=request.generation_id,
            ldr_url=ldr_url,
            parts_list_csv_url=parts_list_csv_url,
            success=True,
            message="Successfully updated LDR and parts list"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update LDR and parts list")
        track_error(
            error_type=type(e).__name__, 
            error_message=str(e), 
            endpoint="/updateLdrAndPartsList", 
            user_id=user_email
        )
        raise HTTPException(status_code=500, detail=f"Failed to update LDR and parts list: {str(e)}")
