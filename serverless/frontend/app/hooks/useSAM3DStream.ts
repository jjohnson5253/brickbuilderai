"use client";

import { useState, useCallback, useRef } from "react";
import type {
  Voxel,
  MeshData,
  LogEntry,
  RenderMode,
  StreamEvent,
} from "../lib/types";
import { decodeVoxels, decodeMesh, decodeGLB } from "../lib/decoders";

export interface UseSAM3DStreamReturn {
  // State
  isStreaming: boolean;
  voxels: Voxel[];
  meshData: MeshData | null;
  glbData: ArrayBuffer | null;
  logs: LogEntry[];
  currentStage: string;
  progress: number;
  glbUrl: string | null;
  splatUrl: string | null;
  renderMode: RenderMode;
  // Actions
  startStream: (imageUrl: string, prompt: string) => Promise<void>;
  cancelStream: () => void;
  clearState: () => void;
}

export function useSAM3DStream(): UseSAM3DStreamReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [voxels, setVoxels] = useState<Voxel[]>([]);
  const [meshData, setMeshData] = useState<MeshData | null>(null);
  const [glbData, setGlbData] = useState<ArrayBuffer | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [currentStage, setCurrentStage] = useState<string>("");
  const [progress, setProgress] = useState(0);
  const [glbUrl, setGlbUrl] = useState<string | null>(null);
  const [splatUrl, setSplatUrl] = useState<string | null>(null);
  const [renderMode, setRenderMode] = useState<RenderMode>("voxels");

  const abortControllerRef = useRef<AbortController | null>(null);
  const logIdRef = useRef(0);

  const addLog = useCallback(
    (stage: string, message: string, type: LogEntry["type"] = "info") => {
      const entry: LogEntry = {
        id: logIdRef.current++,
        stage,
        message,
        timestamp: new Date(),
        type,
      };
      setLogs((prev) => [...prev, entry]);
    },
    []
  );

  const clearState = useCallback(() => {
    setVoxels([]);
    setMeshData(null);
    setGlbData(null);
    setLogs([]);
    setCurrentStage("");
    setProgress(0);
    setGlbUrl(null);
    setSplatUrl(null);
    setRenderMode("voxels");
    logIdRef.current = 0;
  }, []);

  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  const startStream = useCallback(
    async (imageUrl: string, prompt: string) => {
      // Reset state
      clearState();
      setIsStreaming(true);
      addLog("init", "Starting stream...", "info");

      // Create abort controller
      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch("/api/stream-3d", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            imageUrl,
            prompt,
            streamGeometryEvery: 1,
            streamColorsEvery: 2,
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        if (!response.body) {
          throw new Error("No response body");
        }

        addLog("init", "Connected to stream", "success");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const e: StreamEvent = JSON.parse(line.slice(6));
                const stage = e.stage || "unknown";
                setCurrentStage(stage);

                if (e.progress !== undefined) {
                  setProgress(e.progress * 100);
                }

                if (stage === "geometry" || stage === "appearance") {
                  const decoded = decodeVoxels(e);
                  if (decoded.length > 0) {
                    setVoxels(decoded);
                    setRenderMode("voxels");
                    addLog(
                      stage,
                      `Step ${e.step}/${e.total_steps}: ${decoded.length} voxels`,
                      "data"
                    );
                  }
                } else if (stage === "mesh_preview") {
                  const mesh = decodeMesh(e);
                  if (mesh) {
                    setMeshData(mesh);
                    setRenderMode("mesh");
                    addLog(
                      stage,
                      `Mesh preview: ${e.vertex_count} vertices, ${e.face_count} faces`,
                      "data"
                    );
                  }
                } else if (stage === "glb_ready") {
                  const glb = decodeGLB(e);
                  if (glb) {
                    setGlbData(glb);
                    setRenderMode("glb");
                    addLog(stage, "GLB model ready!", "success");
                  }
                } else if (stage === "postprocessing") {
                  addLog(
                    stage,
                    e.message || "Texture baking in progress...",
                    "info"
                  );
                } else if (stage === "complete") {
                  setGlbUrl(e.model_glb_url || null);
                  setSplatUrl(e.gaussian_splat_url || null);
                  addLog("complete", "Generation complete!", "success");
                  if (e.model_glb_url) {
                    addLog("complete", `GLB: ${e.model_glb_url}`, "success");
                  }
                  if (e.gaussian_splat_url) {
                    addLog(
                      "complete",
                      `Splat: ${e.gaussian_splat_url}`,
                      "success"
                    );
                  }
                } else if (stage === "error") {
                  addLog("error", e.error || "Unknown error", "error");
                  if (e.traceback) {
                    addLog("error", e.traceback, "error");
                  }
                } else {
                  addLog(stage, e.message || `Stage: ${stage}`, "info");
                }
              } catch {
                console.warn("Failed to parse SSE event:", line);
              }
            }
          }
        }
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") {
          addLog("info", "Stream cancelled", "info");
        } else {
          addLog(
            "error",
            error instanceof Error ? error.message : "Stream failed",
            "error"
          );
        }
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [addLog, clearState]
  );

  return {
    isStreaming,
    voxels,
    meshData,
    glbData,
    logs,
    currentStage,
    progress,
    glbUrl,
    splatUrl,
    renderMode,
    startStream,
    cancelStream,
    clearState,
  };
}
