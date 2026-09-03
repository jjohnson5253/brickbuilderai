"""Backfill brick_count for generation rows that already have an LDR file.

Run from the backend directory after applying the Supabase migration:
    uv run python scripts/backfill_brick_counts.py
"""

import os
import random
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.brickowl_utils import parse_ldr_file


PAGE_SIZE = 500
MAX_DOWNLOAD_ATTEMPTS = 7


def format_duration(seconds: float) -> str:
    """Format a duration as a compact human-readable estimate."""
    total_seconds = max(0, round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def storage_location(storage_url: str) -> tuple[str, str]:
    """Extract the bucket and object path from a Supabase Storage URL."""
    url_path = unquote(urlparse(storage_url).path)
    marker = "/storage/v1/object/"
    if marker not in url_path:
        raise ValueError("Not a Supabase Storage URL")

    storage_path = url_path.split(marker, 1)[1].lstrip("/")
    segments = storage_path.split("/")
    if segments[0] in {"public", "sign", "authenticated"}:
        segments = segments[1:]
    if len(segments) < 2:
        raise ValueError("Storage URL does not contain a bucket and object path")

    return segments[0], "/".join(segments[1:])


def download_ldr(client, storage_url: str) -> str:
    """Download through the authenticated Storage API with 429-safe retries."""
    bucket, object_path = storage_location(storage_url)

    for attempt in range(MAX_DOWNLOAD_ATTEMPTS):
        try:
            content = client.storage.from_(bucket).download(object_path)
            return content.decode("utf-8")
        except Exception as exc:
            message = str(exc)
            retryable = any(
                status in message
                for status in ("429", "Too Many Requests", "500", "502", "503", "504")
            )
            if not retryable or attempt == MAX_DOWNLOAD_ATTEMPTS - 1:
                raise

            delay = min(2 ** attempt, 30) + random.uniform(0, 0.5)
            print(
                f"Storage throttled; retrying in {delay:.1f}s "
                f"({attempt + 2}/{MAX_DOWNLOAD_ATTEMPTS})",
                flush=True,
            )
            time.sleep(delay)


def main() -> None:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_role_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    client = create_client(url, service_role_key)
    request_delay = float(os.getenv("BACKFILL_DELAY_SECONDS", "0.25"))
    updated = 0
    failed = 0
    offset = 0
    rows_to_backfill = []

    # Collect the complete candidate list before updating it so pagination is
    # stable even though each successful update removes a row from this query.
    print("Scanning Supabase for generations that still need a brick count...", flush=True)
    while True:
        result = (
            client.table("generations")
            .select("id,ldr_url")
            .not_.is_("ldr_url", "null")
            .is_("brick_count", "null")
            .order("created_at")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        rows = result.data or []
        rows_to_backfill.extend(rows)
        print(
            f"  Found {len(rows_to_backfill)} candidate rows so far...",
            flush=True,
        )

        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    total = len(rows_to_backfill)
    if total == 0:
        print("Everything is already backfilled. Nothing to do.", flush=True)
        return

    # Each row makes one Storage request and one database update. The network
    # portion varies, so this is only a starting estimate; the rolling ETA below
    # switches to the measured rate after work begins.
    rough_seconds = total * (request_delay + 0.75)
    print(
        f"Found {total} generations to backfill. "
        f"Rough initial estimate: {format_duration(rough_seconds)}.",
        flush=True,
    )
    print(
        "The ETA will adjust after each generation based on the actual speed.",
        flush=True,
    )

    started_at = time.monotonic()

    for index, row in enumerate(rows_to_backfill, start=1):
        if index > 1 and request_delay > 0:
            time.sleep(request_delay)

        print(
            f"[{index}/{total}] Processing {row['id']}...",
            flush=True,
        )
        outcome = "failed"
        try:
            ldr_content = download_ldr(client, row["ldr_url"])
            brick_count = sum(parse_ldr_file(ldr_content).values())
            (
                client.table("generations")
                .update({"brick_count": brick_count})
                .eq("id", row["id"])
                .execute()
            )
            updated += 1
            outcome = f"saved {brick_count:,} bricks"
        except Exception as exc:
            failed += 1
            print(f"  Error: {exc}", flush=True)

        elapsed = time.monotonic() - started_at
        rows_per_second = index / elapsed if elapsed else 0
        eta_seconds = (total - index) / rows_per_second if rows_per_second else 0
        percent = index / total * 100
        print(
            f"  {outcome} | {percent:.1f}% complete | "
            f"elapsed {format_duration(elapsed)} | "
            f"ETA {format_duration(eta_seconds)} | "
            f"{rows_per_second:.2f} generations/sec",
            flush=True,
        )

    elapsed = time.monotonic() - started_at
    print(
        f"Backfill complete in {format_duration(elapsed)}: "
        f"{updated} updated, {failed} failed",
        flush=True,
    )


if __name__ == "__main__":
    main()
