import logging

from fastapi import HTTPException
from pydantic import BaseModel

from ..utils.auth import handle_auth_and_tracking
from ..utils.generation_storage import generation_storage
from ..utils.posthog_client import track_error

logger = logging.getLogger(__name__)


class ToggleGenerationLikeRequest(BaseModel):
    generation_id: str


class ToggleGenerationLikeResponse(BaseModel):
    generation_id: str
    like_count: int
    has_liked: bool


async def toggle_generation_like(
    request: ToggleGenerationLikeRequest,
    auth_info: dict,
) -> ToggleGenerationLikeResponse:
    user_email = "anonymous"

    try:
        if auth_info.get("is_anonymous", False) or not auth_info.get("authenticated", False):
            raise HTTPException(
                status_code=401,
                detail="Authentication required to like community models",
            )

        if generation_storage is None:
            raise HTTPException(
                status_code=404,
                detail=f"Generation {request.generation_id} not found",
            )

        user_info = handle_auth_and_tracking(
            auth_info=auth_info,
            endpoint="/toggleGenerationLike",
            track_properties={"generation_id": request.generation_id},
            required_credits=0,
        )
        user_email = user_info["user_email"]
        authenticated_user_id = auth_info.get("user_id")

        if not authenticated_user_id:
            raise HTTPException(
                status_code=401,
                detail="Authenticated user has no user_id",
            )

        generation_result = (
            generation_storage.client
            .table("generations")
            .select("id, is_community, like_count")
            .eq("id", request.generation_id)
            .execute()
        )

        if not generation_result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Generation {request.generation_id} not found",
            )

        generation = generation_result.data[0]
        if not generation.get("is_community"):
            raise HTTPException(
                status_code=400,
                detail="Only community models can be liked",
            )

        existing_like = (
            generation_storage.client
            .table("generation_likes")
            .select("generation_id")
            .eq("generation_id", request.generation_id)
            .eq("user_id", authenticated_user_id)
            .limit(1)
            .execute()
        )

        has_liked = not bool(existing_like.data)
        if has_liked:
            insert_result = (
                generation_storage.client
                .table("generation_likes")
                .insert({
                    "generation_id": request.generation_id,
                    "user_id": authenticated_user_id,
                })
                .execute()
            )
            if not insert_result.data:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to add like for generation {request.generation_id}",
                )
        else:
            delete_result = (
                generation_storage.client
                .table("generation_likes")
                .delete()
                .eq("generation_id", request.generation_id)
                .eq("user_id", authenticated_user_id)
                .execute()
            )
            if delete_result.data is None:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to remove like for generation {request.generation_id}",
                )

        refreshed_generation = (
            generation_storage.client
            .table("generations")
            .select("like_count")
            .eq("id", request.generation_id)
            .limit(1)
            .execute()
        )
        refreshed_row = (refreshed_generation.data or [{}])[0]

        return ToggleGenerationLikeResponse(
            generation_id=request.generation_id,
            like_count=int(refreshed_row.get("like_count") or 0),
            has_liked=has_liked,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to toggle generation like")
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint="/toggleGenerationLike",
            user_id=user_email,
        )
        raise HTTPException(status_code=500, detail="Failed to toggle generation like")
