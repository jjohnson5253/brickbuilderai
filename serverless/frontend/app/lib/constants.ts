// Stage colors for UI display
export const STAGE_COLORS: Record<string, string> = {
  loading: "text-amber-400",
  preprocessing: "text-amber-400",
  geometry_start: "text-cyan-400",
  geometry: "text-cyan-400",
  appearance_start: "text-violet-400",
  appearance: "text-violet-400",
  mesh_preview: "text-pink-400",
  postprocessing: "text-orange-400",
  glb_ready: "text-emerald-400",
  finalizing: "text-emerald-400",
  complete: "text-emerald-400",
  error: "text-red-400",
  init: "text-zinc-400",
  info: "text-zinc-400",
};

// Stage background colors for progress indicator
export const STAGE_BG_COLORS: Record<string, string> = {
  loading: "bg-amber-400/20",
  preprocessing: "bg-amber-400/20",
  geometry_start: "bg-cyan-400/20",
  geometry: "bg-cyan-400/20",
  appearance_start: "bg-violet-400/20",
  appearance: "bg-violet-400/20",
  mesh_preview: "bg-pink-400/20",
  postprocessing: "bg-orange-400/20",
  glb_ready: "bg-emerald-400/20",
  finalizing: "bg-emerald-400/20",
  complete: "bg-emerald-400/20",
  error: "bg-red-400/20",
};

// Default values
export const DEFAULT_IMAGE_URL =
  "https://v3b.fal.media/files/b/0a8439e5/TyAmfW5w_sqRXRzWVBGsW_car.jpeg";

export const DEFAULT_PROMPT = "the car";

// API configuration
export const FAL_API_BASE_URL = "https://fal.run";

