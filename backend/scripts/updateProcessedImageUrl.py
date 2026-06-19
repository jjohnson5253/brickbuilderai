"""
Update a generation's processed_image_url in Supabase by uploading a local image.

Usage:
    python scripts/updateProcessedImageUrl.py <generation_id> <local_image_path>

Example:
    python scripts/updateProcessedImageUrl.py 31522db3-c87c-49b9-b75a-508755aabc50 src/images/Nyan_Cat.png
"""
import os
import sys
import time
import argparse

from dotenv import load_dotenv

# Load env vars from .env before importing supabase client
load_dotenv(".env")

# Make the `src` package importable when run from the repo root
sys.path.insert(0, "src")
from utils.auth import supabase_client  # type: ignore  # noqa: E402

BUCKET = "generations"


def update_processed_image_url(generation_id: str, local_path: str) -> str:
    if supabase_client is None:
        raise RuntimeError("Supabase client not initialized (check .env)")

    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local image not found: {local_path}")

    # Confirm the generation exists
    existing = (
        supabase_client.table("generations")
        .select("id, preview_image_url")
        .eq("id", generation_id)
        .execute()
    )
    print(f"Existing row: {existing.data}")
    if not existing.data:
        raise SystemExit(f"No generation found with id {generation_id}")

    with open(local_path, "rb") as f:
        png_bytes = f.read()
    print(f"Read {len(png_bytes)} bytes from {local_path}")

    timestamp = int(time.time())
    file_path = f"generations/{generation_id}/processed_image_{timestamp}.png"

    result = supabase_client.storage.from_(BUCKET).upload(
        path=file_path,
        file=png_bytes,
        file_options={"content-type": "image/png", "upsert": "true"},
    )
    print(f"Upload result: {result}")

    public_url = supabase_client.storage.from_(BUCKET).get_public_url(file_path)
    print(f"Public URL: {public_url}")

    update = (
        supabase_client.table("generations")
        .update({"preview_image_url": public_url})
        .eq("id", generation_id)
        .execute()
    )
    print(f"Update result: {update.data}")

    return public_url


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload a local image and set it as a generation's preview_image_url."
    )
    parser.add_argument("generation_id", help="UUID of the generation to update")
    parser.add_argument("local_image_path", help="Path to the local image file (PNG)")
    args = parser.parse_args()

    update_processed_image_url(args.generation_id, args.local_image_path)


if __name__ == "__main__":
    main()
