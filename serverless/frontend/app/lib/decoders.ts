import type { Voxel, MeshData, StreamEvent } from "./types";

/**
 * Decode base64 string to Uint8Array
 */
export function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Decode voxel data from stream event
 * Returns array of voxels with positions and colors
 */
export function decodeVoxels(event: StreamEvent): Voxel[] {
  if (!event.voxel_data || !event.bounds_min || !event.bounds_max) {
    return [];
  }

  const bytes = base64ToBytes(event.voxel_data);
  const voxels: Voxel[] = [];
  const [xMin, yMin, zMin] = event.bounds_min;
  const [xMax, yMax, zMax] = event.bounds_max;

  for (let i = 0; i < bytes.length; i += 6) {
    // Normalized coords (0-255)
    const xNorm = bytes[i] / 255;
    const yNorm = bytes[i + 1] / 255;
    const zNorm = bytes[i + 2] / 255;

    // Denormalize to world space
    const x = xMin + xNorm * (xMax - xMin);
    const y = yMin + yNorm * (yMax - yMin);
    const z = zMin + zNorm * (zMax - zMin);

    // RGB colors (0-255)
    const r = bytes[i + 3];
    const g = bytes[i + 4];
    const b = bytes[i + 5];

    voxels.push({ x, y, z, r, g, b });
  }

  return voxels;
}

/**
 * Decode mesh data from stream event
 * Returns vertices, faces, and vertex colors
 */
export function decodeMesh(event: StreamEvent): MeshData | null {
  if (!event.vertices_data || !event.faces_data || !event.vertex_colors_data) {
    return null;
  }

  // Decode vertices (float32 array)
  const vertexBytes = base64ToBytes(event.vertices_data);
  const vertices = new Float32Array(vertexBytes.buffer);

  // Decode faces (uint32 array)
  const faceBytes = base64ToBytes(event.faces_data);
  const faces = new Uint32Array(faceBytes.buffer);

  // Decode vertex colors (uint8 RGB)
  const vertexColors = base64ToBytes(event.vertex_colors_data);

  return { vertices, faces, vertexColors };
}

/**
 * Decode GLB data from stream event
 * Returns ArrayBuffer for GLTFLoader
 */
export function decodeGLB(event: StreamEvent): ArrayBuffer | null {
  if (!event.glb_data) {
    return null;
  }

  const bytes = base64ToBytes(event.glb_data);
  // Ensure we get an ArrayBuffer, not SharedArrayBuffer
  return bytes.buffer.slice(0) as ArrayBuffer;
}

