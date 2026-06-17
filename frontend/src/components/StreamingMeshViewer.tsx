import React, { useEffect, useRef, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { VoxelDataEvent } from '../services/imageToBricksApi';

interface StreamingMeshViewerProps {
  /** Latest voxel data event from SSE stream */
  voxelData: VoxelDataEvent | null;
  className?: string;
}

/** Decode a base64 string into a Uint8Array. */
function base64ToUint8Array(base64: string): Uint8Array {
  const binaryStr = atob(base64);
  const bytes = new Uint8Array(binaryStr.length);
  for (let i = 0; i < binaryStr.length; i++) {
    bytes[i] = binaryStr.charCodeAt(i);
  }
  return bytes;
}

const StreamingMeshViewer: React.FC<StreamingMeshViewerProps> = ({
  voxelData,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const rafRef = useRef<number>(0);
  const instancedMeshRef = useRef<THREE.InstancedMesh | null>(null);
  const initializedRef = useRef(false);
  const cameraFramedRef = useRef(false);

  // ---------- Initialise Three.js scene once ----------
  const initScene = useCallback(() => {
    const container = containerRef.current;
    if (!container || initializedRef.current) return;
    initializedRef.current = true;

    const width = container.clientWidth;
    const height = container.clientHeight;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Scene
    const scene = new THREE.Scene();
    scene.background = null;
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 2000);
    camera.position.set(30, 20, 30);
    cameraRef.current = camera;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 3.0;
    controls.enablePan = false;
    controls.minDistance = 1;
    controls.maxDistance = 500;
    controlsRef.current = controls;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
    dirLight.position.set(5, 8, 4);
    scene.add(dirLight);

    const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
    fillLight.position.set(-3, 2, -4);
    scene.add(fillLight);

    // Animation loop
    const animate = () => {
      rafRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize observer
    const ro = new ResizeObserver(() => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      cancelAnimationFrame(rafRef.current);
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      initializedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const cleanup = initScene();
    return () => cleanup?.();
  }, [initScene]);

  // ---------- Handle voxel data ----------
  useEffect(() => {
    if (!voxelData?.voxel_data || !sceneRef.current) {
      // Reset framing flag when voxelData is cleared (new generation starting)
      if (!voxelData) cameraFramedRef.current = false;
      return;
    }

    try {
      const raw = base64ToUint8Array(voxelData.voxel_data);
      const voxelCount = Math.floor(raw.length / 6); // 6 bytes per voxel: x,y,z,r,g,b

      if (voxelCount === 0) return;

      // Remove previous instanced mesh
      if (instancedMeshRef.current) {
        sceneRef.current.remove(instancedMeshRef.current);
        instancedMeshRef.current.geometry.dispose();
        if (instancedMeshRef.current.material instanceof THREE.Material) {
          instancedMeshRef.current.material.dispose();
        }
        instancedMeshRef.current = null;
      }

      // --- Detect actual grid spacing so cubes fill the gaps ---
      // Collect unique sorted coordinates along each axis to find the
      // most common step between neighbours (mode of deltas).
      const xs = new Set<number>();
      const ys = new Set<number>();
      const zs = new Set<number>();
      for (let i = 0; i < voxelCount; i++) {
        const off = i * 6;
        xs.add(raw[off]);
        ys.add(raw[off + 1]);
        zs.add(raw[off + 2]);
      }

      const modeStep = (vals: Set<number>): number => {
        const sorted = [...vals].sort((a, b) => a - b);
        if (sorted.length < 2) return 1;
        const counts = new Map<number, number>();
        for (let i = 1; i < sorted.length; i++) {
          const d = sorted[i] - sorted[i - 1];
          if (d > 0) counts.set(d, (counts.get(d) || 0) + 1);
        }
        let best = 1;
        let bestCount = 0;
        counts.forEach((c, d) => {
          if (c > bestCount) { bestCount = c; best = d; }
        });
        return best;
      };

      const stepX = modeStep(xs);
      const stepY = modeStep(ys);
      const stepZ = modeStep(zs);

      // Uniform cubic boxes — normalise positions by dividing by each axis step
      // so all axes have unit spacing, then use 1×1×1 cubes.
      const boxGeo = new THREE.BoxGeometry(1, 1, 1);

      const material = new THREE.MeshStandardMaterial({
        roughness: 0.55,
        metalness: 0.05,
      });

      const instMesh = new THREE.InstancedMesh(boxGeo, material, voxelCount);
      instMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

      // Per-instance color
      const colorArr = new Float32Array(voxelCount * 3);
      const dummy = new THREE.Matrix4();
      const color = new THREE.Color();

      // Track bounds for centering (in normalised coords)
      let minX = Infinity, minY = Infinity, minZ = Infinity;
      let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;

      for (let i = 0; i < voxelCount; i++) {
        const offset = i * 6;
        // Normalise raw coords to unit grid
        const x = raw[offset] / stepX;
        const y = raw[offset + 1] / stepY;
        const z = raw[offset + 2] / stepZ;
        const r = raw[offset + 3];
        const g = raw[offset + 4];
        const b = raw[offset + 5];

        // Server uses Z-up; Three.js uses Y-up → swap Y and Z
        dummy.makeTranslation(x, z, y);
        instMesh.setMatrixAt(i, dummy);

        color.setRGB(r / 255, g / 255, b / 255);
        colorArr[i * 3] = color.r;
        colorArr[i * 3 + 1] = color.g;
        colorArr[i * 3 + 2] = color.b;

        if (x < minX) minX = x;
        if (z < minY) minY = z;  // swapped: Three.js Y = server Z
        if (y < minZ) minZ = y;  // swapped: Three.js Z = server Y
        if (x > maxX) maxX = x;
        if (z > maxY) maxY = z;
        if (y > maxZ) maxZ = y;
      }

      instMesh.instanceMatrix.needsUpdate = true;

      const colorAttr = new THREE.InstancedBufferAttribute(colorArr, 3);
      instMesh.instanceColor = colorAttr;

      // Center the instanced mesh at origin
      const cx = (minX + maxX) / 2;
      const cy = (minY + maxY) / 2;
      const cz = (minZ + maxZ) / 2;
      instMesh.position.set(-cx, -cy, -cz);

      sceneRef.current.add(instMesh);
      instancedMeshRef.current = instMesh;

      // Fit camera – reframe on every voxel update so the camera keeps up
      // with the growing model. Preserve the current orbit direction so
      // auto-rotate isn't jarred; only adjust the distance.
      const sizeX = maxX - minX + 1;
      const sizeY = maxY - minY + 1;
      const sizeZ = maxZ - minZ + 1;
      const maxDim = Math.max(sizeX, sizeY, sizeZ);

      if (controlsRef.current && cameraRef.current) {
        const fovRad = cameraRef.current.fov * (Math.PI / 180);
        const idealDist = (maxDim / 2) / Math.tan(fovRad / 2) * 1.5;

        if (!cameraFramedRef.current) {
          // First frame: jump to a good position
          cameraRef.current.position.set(idealDist * 0.7, idealDist * 0.5, idealDist * 0.7);
          controlsRef.current.target.set(0, 0, 0);
          cameraFramedRef.current = true;
        } else {
          // Subsequent frames: scale the camera out along its current direction
          const dir = cameraRef.current.position.clone().sub(controlsRef.current.target);
          const currentDist = dir.length();
          if (currentDist > 0 && idealDist > currentDist) {
            dir.normalize().multiplyScalar(idealDist);
            cameraRef.current.position.copy(controlsRef.current.target).add(dir);
          }
        }
        controlsRef.current.update();
      }

      console.log(`[StreamingMeshViewer] Rendered ${voxelCount} voxels (${voxelData.stage})`);
    } catch (err) {
      console.error('[StreamingMeshViewer] Failed to render voxel data:', err);
    }
  }, [voxelData]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        width: '100%',
        height: '100%',
        minHeight: 280,
        borderRadius: 16,
        overflow: 'hidden',
        background: 'radial-gradient(ellipse at center, #f8fafc 0%, #f1f5f9 100%)',
      }}
    />
  );
};

export default StreamingMeshViewer;
