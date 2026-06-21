from typing import Any, Optional

from fastapi import HTTPException


generation_storage: Optional[Any] = None


def _get_generation_storage() -> Any:
    if generation_storage is not None:
        return generation_storage

    from .generation_storage import generation_storage as storage

    return storage


async def get_owned_generation_or_403(generation_id: str, auth_info: dict) -> dict:
    if auth_info.get("is_anonymous") or not auth_info.get("authenticated"):
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = auth_info.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authenticated user has no user_id")

    row = await _get_generation_storage().get_generation(generation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")

    if row.get("user_type") != "authenticated" or row.get("user_id") != user_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this generation",
        )

    return row


async def get_generation_or_404(generation_id: str, auth_info: dict) -> dict:
    """Fetch a generation without enforcing ownership.

    Allows reading any generation regardless of owner. Both authenticated
    and anonymous callers are permitted, as long as they have a stable
    user_id (anonymous callers are identified by their anonymous id). Used
    by endpoints that derive a new generation (owned by the current user)
    from an existing one.
    """
    if not auth_info.get("user_id"):
        raise HTTPException(status_code=401, detail="Authentication required")

    row = await _get_generation_storage().get_generation(generation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")

    return row