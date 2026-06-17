// Voxel data structure
export interface Voxel {
  x: number;
  y: number;
  z: number;
  r: number;
  g: number;
  b: number;
}

// Mesh data structure
export interface MeshData {
  vertices: Float32Array;
  faces: Uint32Array;
  vertexColors: Uint8Array;
}

// SSE Stream event from SAM-3D endpoint
export interface StreamEvent {
  stage?: StreamStage;
  step?: number;
  total_steps?: number;
  progress?: number;
  message?: string;
  // Voxel data
  voxel_data?: string;
  bounds_min?: [number, number, number];
  bounds_max?: [number, number, number];
  voxel_count?: number;
  color_quality?: "approximate" | "accurate";
  encoding?: string;
  // Mesh preview data
  vertices_data?: string;
  faces_data?: string;
  vertex_colors_data?: string;
  vertex_count?: number;
  face_count?: number;
  // GLB data
  glb_data?: string;
  // Final URLs
  model_glb_url?: string;
  gaussian_splat_url?: string;
  // Error
  error?: string;
  traceback?: string;
}

// All possible stream stages
export type StreamStage =
  | "loading"
  | "preprocessing"
  | "geometry_start"
  | "geometry"
  | "appearance_start"
  | "appearance"
  | "mesh_preview"
  | "postprocessing"
  | "glb_ready"
  | "finalizing"
  | "complete"
  | "error";

// Log entry for the log panel
export interface LogEntry {
  id: number;
  stage: string;
  message: string;
  timestamp: Date;
  type: "info" | "success" | "error" | "data";
}

// Render mode for the viewer
export type RenderMode = "voxels" | "mesh" | "glb";

// Stream state returned by the hook
export interface StreamState {
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
}

// Stream configuration
export interface StreamConfig {
  endpointId: string;
  apiKey: string;
  imageUrl: string;
  prompt: string;
  streamGeometryEvery?: number;
  streamColorsEvery?: number;
}

