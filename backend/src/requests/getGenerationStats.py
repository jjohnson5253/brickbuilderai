import logging

from fastapi import HTTPException
from pydantic import BaseModel

from ..utils.generation_storage import generation_storage

logger = logging.getLogger(__name__)


class GetGenerationStatsResponse(BaseModel):
    generation_count: int
    brick_count: int


async def get_generation_stats() -> GetGenerationStatsResponse:
    """Return aggregate counts without exposing generation records."""
    if generation_storage is None:
        return GetGenerationStatsResponse(generation_count=0, brick_count=0)

    try:
        stats = await generation_storage.get_generation_stats()
        return GetGenerationStatsResponse(**stats)
    except Exception as exc:
        logger.error("Failed to load public generation stats: %s", exc)
        raise HTTPException(status_code=503, detail="Generation stats unavailable")
