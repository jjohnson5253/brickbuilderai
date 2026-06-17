#!/usr/bin/env bash
# Smoke-test the RunPod SAM-3D endpoint and verify all appearance steps stream.
#
# Usage:
#   ./scripts/test-runpod-stream.sh [IMAGE_URL]
#
# Reads RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID from frontend/.env.local
# unless they are already set in the environment.

set -euo pipefail

IMAGE_URL="${1:-https://v3b.fal.media/files/b/0a8439e5/TyAmfW5w_sqRXRzWVBGsW_car.jpeg}"

# Load env from frontend/.env.local if creds aren't already exported.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../frontend/.env.local"
if [[ -z "${RUNPOD_API_KEY:-}" || -z "${RUNPOD_ENDPOINT_ID:-}" ]] && [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${RUNPOD_API_KEY:?RUNPOD_API_KEY not set}"
: "${RUNPOD_ENDPOINT_ID:?RUNPOD_ENDPOINT_ID not set}"

API_BASE="${RUNPOD_API_BASE:-https://api.runpod.ai/v2}"
POLL_INTERVAL="${RUNPOD_POLL_INTERVAL_S:-1}"

echo "Submitting job to $API_BASE/$RUNPOD_ENDPOINT_ID/run ..."
RUN_RESPONSE=$(curl -sS -X POST "$API_BASE/$RUNPOD_ENDPOINT_ID/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg url "$IMAGE_URL" '{
        input: {
          image_url: $url,
          prompt: "",
          stream_geometry_every: 1,
          stream_colors_every: 2
        }
      }')")

JOB_ID=$(echo "$RUN_RESPONSE" | jq -r '.id // empty')
if [[ -z "$JOB_ID" ]]; then
  echo "Failed to submit job:"
  echo "$RUN_RESPONSE" | jq .
  exit 1
fi
echo "Job ID: $JOB_ID"
echo "Polling $API_BASE/$RUNPOD_ENDPOINT_ID/stream/$JOB_ID every ${POLL_INTERVAL}s ..."
echo

trap 'echo "Cancelling job $JOB_ID ..."; curl -sS -X POST "$API_BASE/$RUNPOD_ENDPOINT_ID/cancel/$JOB_ID" -H "Authorization: Bearer $RUNPOD_API_KEY" >/dev/null || true; exit 130' INT TERM

while true; do
  RESP=$(curl -sS "$API_BASE/$RUNPOD_ENDPOINT_ID/stream/$JOB_ID" \
    -H "Authorization: Bearer $RUNPOD_API_KEY")

  # Print each streamed event, stripping the huge base64 voxel/mesh/glb blobs.
  echo "$RESP" | jq -r '
    (.stream // []) as $items
    | $items[]
    | (.output // {})
    | if (type == "array") then .[] else . end
    | {
        stage: (.stage // .event // .type // "unknown"),
        step: .step,
        total_steps: .total_steps,
        progress: .progress,
        voxel_count: .voxel_count,
        vertex_count: .vertex_count,
        face_count: .face_count,
        glb_size_bytes: .glb_size_bytes,
        message: .message,
        error: .error,
        heartbeat: .heartbeat
      }
    | with_entries(select(.value != null))
    | tostring
  '

  STATUS=$(echo "$RESP" | jq -r '.status // "IN_PROGRESS"')
  case "$STATUS" in
    COMPLETED|FAILED|CANCELLED|TIMED_OUT)
      echo
      echo "Job finished: $STATUS"
      if [[ "$STATUS" != "COMPLETED" ]]; then
        echo "$RESP" | jq '{status, error}'
      fi
      exit 0
      ;;
  esac

  sleep "$POLL_INTERVAL"
done
