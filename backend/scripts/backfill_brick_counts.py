"""Backfill brick_count for generation rows that already have an LDR file.

Run from the backend directory after applying the Supabase migration:
    uv run python scripts/backfill_brick_counts.py
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.brickowl_utils import parse_ldr_file


PAGE_SIZE = 500


def main() -> None:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_role_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    client = create_client(url, service_role_key)
    updated = 0
    failed = 0
    offset = 0

    while True:
        result = (
            client.table("generations")
            .select("id,ldr_url")
            .not_.is_("ldr_url", "null")
            .order("created_at")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        rows = result.data or []

        for row in rows:
            try:
                response = requests.get(row["ldr_url"], timeout=30)
                response.raise_for_status()
                brick_count = sum(parse_ldr_file(response.text).values())
                (
                    client.table("generations")
                    .update({"brick_count": brick_count})
                    .eq("id", row["id"])
                    .execute()
                )
                updated += 1
            except Exception as exc:
                failed += 1
                print(f"Could not backfill {row['id']}: {exc}")

        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    print(f"Backfill complete: {updated} updated, {failed} failed")


if __name__ == "__main__":
    main()
