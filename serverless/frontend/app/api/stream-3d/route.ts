import { NextRequest } from "next/server";

/**
 * Server-side proxy that forwards a SAM-3D generation request to a RunPod
 * Serverless endpoint and re-emits the worker's streamed events as SSE
 * (`data: {...}\n\n`) in the exact shape the original fal endpoint produced.
 *
 * The frontend hook (`useSAM3DStream`) is unchanged — it parses the same
 * `stage`, `progress`, `voxel_data`, `mesh_preview`, `glb_ready`, `complete`,
 * and `error` events as before.
 *
 * Required env vars:
 *   RUNPOD_API_KEY        – RunPod account API key
 *   RUNPOD_ENDPOINT_ID    – ID of your deployed SAM-3D endpoint
 *
 * Optional:
 *   RUNPOD_API_BASE         – defaults to https://api.runpod.ai/v2
 *   RUNPOD_POLL_INTERVAL_MS – ms between /stream polls (default 500)
 */

const DEFAULT_API_BASE = "https://api.runpod.ai/v2";
const DEFAULT_POLL_INTERVAL_MS = 500;
const STREAM_TIMEOUT_MS = 10 * 60 * 1000; // 10 min hard cap

export const dynamic = "force-dynamic";
export const maxDuration = 800;

interface RunPodStreamItem {
  output?: Record<string, unknown> | Array<Record<string, unknown>>;
}

interface RunPodStreamResponse {
  status?: string;
  stream?: RunPodStreamItem[];
  output?: unknown;
  error?: string;
}

export async function POST(request: NextRequest) {
  const apiKey = process.env.RUNPOD_API_KEY;
  const endpointId = process.env.RUNPOD_ENDPOINT_ID;
  const apiBase = process.env.RUNPOD_API_BASE || DEFAULT_API_BASE;
  const pollIntervalMs = Number(
    process.env.RUNPOD_POLL_INTERVAL_MS || DEFAULT_POLL_INTERVAL_MS,
  );

  if (!apiKey) {
    return jsonError("RUNPOD_API_KEY not configured", 500);
  }
  if (!endpointId) {
    return jsonError("RUNPOD_ENDPOINT_ID not configured", 500);
  }

  let body: {
    imageUrl?: string;
    imageB64?: string;
    prompt?: string;
    streamGeometryEvery?: number;
    streamColorsEvery?: number;
    seed?: number;
  };
  try {
    body = await request.json();
  } catch {
    return jsonError("Invalid JSON body", 400);
  }

  if (!body.imageUrl && !body.imageB64) {
    return jsonError("Missing imageUrl or imageB64", 400);
  }

  // 1. Submit the job.
  let jobId: string;
  try {
    const runRes = await fetch(`${apiBase}/${endpointId}/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        input: {
          image_url: body.imageUrl,
          image_b64: body.imageB64,
          prompt: body.prompt || "",
          stream_geometry_every: body.streamGeometryEvery ?? 1,
          stream_colors_every: body.streamColorsEvery ?? 2,
          seed: body.seed,
        },
      }),
      signal: request.signal,
    });

    if (!runRes.ok) {
      const text = await runRes.text();
      return jsonError(`RunPod /run failed: ${text}`, runRes.status);
    }
    const runJson = (await runRes.json()) as { id?: string; error?: string };
    if (!runJson.id) {
      return jsonError(
        `RunPod /run did not return a job id: ${runJson.error ?? "unknown error"}`,
        502,
      );
    }
    jobId = runJson.id;
  } catch (err) {
    return jsonError(
      `Failed to submit RunPod job: ${err instanceof Error ? err.message : String(err)}`,
      502,
    );
  }

  // 2. Poll /stream/{id} and re-emit each chunk as SSE.
  const encoder = new TextEncoder();
  const streamUrl = `${apiBase}/${endpointId}/stream/${jobId}`;
  const cancelUrl = `${apiBase}/${endpointId}/cancel/${jobId}`;
  const startedAt = Date.now();

  const stream = new ReadableStream({
    async start(controller) {
      const writeEvent = (obj: unknown) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
      };

      const cancelJob = () => {
        void fetch(cancelUrl, {
          method: "POST",
          headers: { Authorization: `Bearer ${apiKey}` },
        }).catch(() => {});
      };

      const onClientAbort = () => {
        cancelJob();
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      };
      request.signal.addEventListener("abort", onClientAbort);

      try {
        while (true) {
          if (Date.now() - startedAt > STREAM_TIMEOUT_MS) {
            writeEvent({
              stage: "error",
              error: `Stream exceeded ${STREAM_TIMEOUT_MS / 1000}s timeout`,
            });
            cancelJob();
            break;
          }

          let res: Response;
          try {
            res = await fetch(streamUrl, {
              method: "GET",
              headers: { Authorization: `Bearer ${apiKey}` },
              signal: request.signal,
            });
          } catch (err) {
            if (request.signal.aborted) break;
            writeEvent({
              stage: "error",
              error: `RunPod /stream fetch failed: ${err instanceof Error ? err.message : String(err)}`,
            });
            break;
          }

          if (!res.ok) {
            const text = await res.text();
            writeEvent({
              stage: "error",
              error: `RunPod /stream HTTP ${res.status}: ${text}`,
            });
            break;
          }

          const data = (await res.json()) as RunPodStreamResponse;

          for (const item of data.stream ?? []) {
            const output = item.output;
            if (Array.isArray(output)) {
              for (const e of output) writeEvent(e);
            } else if (output && typeof output === "object") {
              writeEvent(output);
            }
          }

          const status = (data.status || "").toUpperCase();
          if (
            status === "COMPLETED" ||
            status === "FAILED" ||
            status === "CANCELLED" ||
            status === "TIMED_OUT"
          ) {
            if (status !== "COMPLETED") {
              writeEvent({
                stage: "error",
                error: `RunPod job ${status.toLowerCase()}: ${
                  typeof data.error === "string" ? data.error : "no detail"
                }`,
              });
            }
            break;
          }

          await sleep(pollIntervalMs, request.signal);
          if (request.signal.aborted) break;
        }
      } finally {
        request.signal.removeEventListener("abort", onClientAbort);
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

function jsonError(message: string, status: number): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal?.aborted) return resolve();
    const t = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      resolve();
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}
