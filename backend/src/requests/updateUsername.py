import logging
import re

from pydantic import BaseModel, Field, validator
from fastapi import HTTPException

from ..utils.auth import handle_auth_and_tracking, supabase_client
from ..utils.posthog_client import track_error

logger = logging.getLogger(__name__)


# Allow alphanumeric, underscore, hyphen, period; 3-30 chars
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


class UpdateUsernameRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)

    @validator("username")
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not USERNAME_PATTERN.match(v):
            raise ValueError(
                "Username must be 3-30 characters and contain only letters, "
                "numbers, underscores, hyphens, or periods"
            )
        return v


class UpdateUsernameResponse(BaseModel):
    username: str


async def update_username(
    request: UpdateUsernameRequest,
    auth_info: dict,
) -> UpdateUsernameResponse:
    """
    Update the `username` column on the authenticated user's row in the
    `user_profiles` table.

    - Requires authentication (anonymous users rejected with 401).
    - Rejects with 409 if the username is already taken by another user.
    """
    user_email = "anonymous"

    try:
        # Require authentication
        if auth_info.get("is_anonymous", False) or not auth_info.get("authenticated", False):
            raise HTTPException(
                status_code=401,
                detail="Authentication required to update username",
            )

        user_info = handle_auth_and_tracking(
            auth_info=auth_info,
            endpoint="/updateUsername",
            track_properties={"username": request.username},
            required_credits=0,
        )
        user_email = user_info["user_email"]

        if not user_email or user_email == "anonymous":
            raise HTTPException(
                status_code=401,
                detail="Authenticated user has no email",
            )

        if not supabase_client:
            raise HTTPException(
                status_code=500,
                detail="Authentication system not configured",
            )

        new_username = request.username

        # Check if username is already taken by another user
        existing = (
            supabase_client
            .table("user_profiles")
            .select("email, username")
            .eq("username", new_username)
            .execute()
        )

        if existing.data:
            for row in existing.data:
                if row.get("email") != user_email:
                    raise HTTPException(
                        status_code=409,
                        detail="Username is already taken",
                    )

        # Update the current user's username
        update_result = (
            supabase_client
            .table("user_profiles")
            .update({"username": new_username})
            .eq("email", user_email)
            .execute()
        )

        if not update_result.data:
            raise HTTPException(
                status_code=404,
                detail="User profile not found",
            )

        logger.info(f"Updated username for {user_email} to '{new_username}'")

        return UpdateUsernameResponse(username=new_username)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update username")
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint="/updateUsername",
            user_id=user_email,
        )
        raise HTTPException(status_code=500, detail="Failed to update username")
