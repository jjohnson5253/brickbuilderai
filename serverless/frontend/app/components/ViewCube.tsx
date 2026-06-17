"use client";

import { useRef, useState, useCallback } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

// Camera positions for each view (normalized direction vectors scaled to distance 2)
export const CAMERA_VIEWS = {
  // Faces
  front: { position: [0, 0, 2], name: "Front" },
  back: { position: [0, 0, -2], name: "Back" },
  top: { position: [0, 2, 0.001], name: "Top" },
  bottom: { position: [0, -2, 0.001], name: "Bottom" },
  left: { position: [-2, 0, 0], name: "Left" },
  right: { position: [2, 0, 0], name: "Right" },
  // Edges (12 edges)
  frontTop: { position: [0, 1.4, 1.4], name: "Front Top" },
  frontBottom: { position: [0, -1.4, 1.4], name: "Front Bottom" },
  frontLeft: { position: [-1.4, 0, 1.4], name: "Front Left" },
  frontRight: { position: [1.4, 0, 1.4], name: "Front Right" },
  backTop: { position: [0, 1.4, -1.4], name: "Back Top" },
  backBottom: { position: [0, -1.4, -1.4], name: "Back Bottom" },
  backLeft: { position: [-1.4, 0, -1.4], name: "Back Left" },
  backRight: { position: [1.4, 0, -1.4], name: "Back Right" },
  topLeft: { position: [-1.4, 1.4, 0], name: "Top Left" },
  topRight: { position: [1.4, 1.4, 0], name: "Top Right" },
  bottomLeft: { position: [-1.4, -1.4, 0], name: "Bottom Left" },
  bottomRight: { position: [1.4, -1.4, 0], name: "Bottom Right" },
  // Corners (8 corners)
  frontTopRight: { position: [1.15, 1.15, 1.15], name: "Front Top Right" },
  frontTopLeft: { position: [-1.15, 1.15, 1.15], name: "Front Top Left" },
  frontBottomRight: { position: [1.15, -1.15, 1.15], name: "Front Bottom Right" },
  frontBottomLeft: { position: [-1.15, -1.15, 1.15], name: "Front Bottom Left" },
  backTopRight: { position: [1.15, 1.15, -1.15], name: "Back Top Right" },
  backTopLeft: { position: [-1.15, 1.15, -1.15], name: "Back Top Left" },
  backBottomRight: { position: [1.15, -1.15, -1.15], name: "Back Bottom Right" },
  backBottomLeft: { position: [-1.15, -1.15, -1.15], name: "Back Bottom Left" },
} as const;

export type CameraView = keyof typeof CAMERA_VIEWS;

// Chamfered cube geometry builder
function createChamferedCubeGeometry(size: number, chamfer: number): THREE.BufferGeometry {
  const s = size / 2;
  const sc = s - chamfer;

  const vertices: number[] = [];
  const indices: number[] = [];
  const normals: number[] = [];

  const addFace = (v1: number[], v2: number[], v3: number[], v4: number[], normal: number[]) => {
    const baseIndex = vertices.length / 3;
    vertices.push(...v1, ...v2, ...v3, ...v4);
    normals.push(...normal, ...normal, ...normal, ...normal);
    indices.push(baseIndex, baseIndex + 1, baseIndex + 2, baseIndex, baseIndex + 2, baseIndex + 3);
  };

  // Main faces
  addFace([-sc, -sc, s], [sc, -sc, s], [sc, sc, s], [-sc, sc, s], [0, 0, 1]);
  addFace([sc, -sc, -s], [-sc, -sc, -s], [-sc, sc, -s], [sc, sc, -s], [0, 0, -1]);
  addFace([-sc, s, sc], [sc, s, sc], [sc, s, -sc], [-sc, s, -sc], [0, 1, 0]);
  addFace([-sc, -s, -sc], [sc, -s, -sc], [sc, -s, sc], [-sc, -s, sc], [0, -1, 0]);
  addFace([s, -sc, sc], [s, -sc, -sc], [s, sc, -sc], [s, sc, sc], [1, 0, 0]);
  addFace([-s, -sc, -sc], [-s, -sc, sc], [-s, sc, sc], [-s, sc, -sc], [-1, 0, 0]);

  // Chamfer edges
  const n = 1 / Math.sqrt(2);
  addFace([-sc, sc, s], [sc, sc, s], [sc, s, sc], [-sc, s, sc], [0, n, n]);
  addFace([sc, -sc, s], [-sc, -sc, s], [-sc, -s, sc], [sc, -s, sc], [0, -n, n]);
  addFace([-s, -sc, sc], [-s, sc, sc], [-sc, sc, s], [-sc, -sc, s], [-n, 0, n]);
  addFace([sc, sc, s], [sc, -sc, s], [s, -sc, sc], [s, sc, sc], [n, 0, n]);
  addFace([sc, sc, -s], [-sc, sc, -s], [-sc, s, -sc], [sc, s, -sc], [0, n, -n]);
  addFace([-sc, -sc, -s], [sc, -sc, -s], [sc, -s, -sc], [-sc, -s, -sc], [0, -n, -n]);
  addFace([-sc, sc, -s], [-sc, -sc, -s], [-s, -sc, -sc], [-s, sc, -sc], [-n, 0, -n]);
  addFace([sc, -sc, -s], [sc, sc, -s], [s, sc, -sc], [s, -sc, -sc], [n, 0, -n]);
  addFace([-s, sc, sc], [-s, sc, -sc], [-sc, s, -sc], [-sc, s, sc], [-n, n, 0]);
  addFace([s, sc, -sc], [s, sc, sc], [sc, s, sc], [sc, s, -sc], [n, n, 0]);
  addFace([-s, -sc, -sc], [-s, -sc, sc], [-sc, -s, sc], [-sc, -s, -sc], [-n, -n, 0]);
  addFace([s, -sc, sc], [s, -sc, -sc], [sc, -s, -sc], [sc, -s, sc], [n, -n, 0]);

  // Corner chamfers
  const n3 = 1 / Math.sqrt(3);
  const addTriangle = (v1: number[], v2: number[], v3: number[], normal: number[]) => {
    const baseIndex = vertices.length / 3;
    vertices.push(...v1, ...v2, ...v3);
    normals.push(...normal, ...normal, ...normal);
    indices.push(baseIndex, baseIndex + 1, baseIndex + 2);
  };

  addTriangle([sc, s, sc], [s, sc, sc], [sc, sc, s], [n3, n3, n3]);
  addTriangle([-sc, s, sc], [-sc, sc, s], [-s, sc, sc], [-n3, n3, n3]);
  addTriangle([s, -sc, sc], [sc, -s, sc], [sc, -sc, s], [n3, -n3, n3]);
  addTriangle([-sc, -sc, s], [-sc, -s, sc], [-s, -sc, sc], [-n3, -n3, n3]);
  addTriangle([s, sc, -sc], [sc, s, -sc], [sc, sc, -s], [n3, n3, -n3]);
  addTriangle([-sc, sc, -s], [-sc, s, -sc], [-s, sc, -sc], [-n3, n3, -n3]);
  addTriangle([sc, -sc, -s], [sc, -s, -sc], [s, -sc, -sc], [n3, -n3, -n3]);
  addTriangle([-s, -sc, -sc], [-sc, -s, -sc], [-sc, -sc, -s], [-n3, -n3, -n3]);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geometry.setIndex(indices);
  return geometry;
}

interface InteractivePartProps {
  position: [number, number, number];
  size: [number, number, number];
  onClick: () => void;
  isHovered: boolean;
  onHover: (hovered: boolean) => void;
}

function InteractivePart({ position, size, onClick, isHovered, onHover }: InteractivePartProps) {
  return (
    <mesh
      position={position}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      onPointerEnter={(e) => { e.stopPropagation(); onHover(true); document.body.style.cursor = "pointer"; }}
      onPointerLeave={(e) => { e.stopPropagation(); onHover(false); document.body.style.cursor = "auto"; }}
    >
      <boxGeometry args={size} />
      <meshBasicMaterial transparent opacity={isHovered ? 0.4 : 0} color="#a1a1aa" />
    </mesh>
  );
}

interface ViewCubeSceneProps {
  onViewChange: (view: CameraView) => void;
  cameraSpherical: { theta: number; phi: number };
  onDragRotate: (spherical: { theta: number; phi: number }) => void;
  showAxes: boolean;
}

function ViewCubeScene({ onViewChange, cameraSpherical, onDragRotate, showAxes }: ViewCubeSceneProps) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const [hoveredPart, setHoveredPart] = useState<string | null>(null);
  const { camera } = useThree();
  const lastSyncRef = useRef({ theta: 0, phi: 0 });
  const isUserDragging = useRef(false);

  const s = 0.5;
  const chamfer = 0.12;
  const sc = s - chamfer;
  const cameraDistance = 2.5;

  const geometry = useRef(createChamferedCubeGeometry(1, chamfer)).current;

  // Sync ViewCube camera with main camera's spherical position
  useFrame(() => {
    if (isUserDragging.current) {
      // When user is dragging the ViewCube, report back to main view
      const spherical = new THREE.Spherical().setFromVector3(camera.position);
      if (Math.abs(spherical.theta - lastSyncRef.current.theta) > 0.01 ||
          Math.abs(spherical.phi - lastSyncRef.current.phi) > 0.01) {
        onDragRotate({ theta: spherical.theta, phi: spherical.phi });
        lastSyncRef.current = { theta: spherical.theta, phi: spherical.phi };
      }
    } else {
      // Sync camera position from main view's spherical coords
      const targetPos = new THREE.Vector3().setFromSphericalCoords(
        cameraDistance,
        cameraSpherical.phi,
        cameraSpherical.theta
      );
      camera.position.lerp(targetPos, 0.3);
      camera.lookAt(0, 0, 0);
      controlsRef.current?.update();
    }
  });

  // Face hit zones
  const faces = [
    { pos: [0, 0, s] as [number, number, number], size: [sc * 2, sc * 2, 0.01] as [number, number, number], view: "front" as CameraView },
    { pos: [0, 0, -s] as [number, number, number], size: [sc * 2, sc * 2, 0.01] as [number, number, number], view: "back" as CameraView },
    { pos: [0, s, 0] as [number, number, number], size: [sc * 2, 0.01, sc * 2] as [number, number, number], view: "top" as CameraView },
    { pos: [0, -s, 0] as [number, number, number], size: [sc * 2, 0.01, sc * 2] as [number, number, number], view: "bottom" as CameraView },
    { pos: [s, 0, 0] as [number, number, number], size: [0.01, sc * 2, sc * 2] as [number, number, number], view: "right" as CameraView },
    { pos: [-s, 0, 0] as [number, number, number], size: [0.01, sc * 2, sc * 2] as [number, number, number], view: "left" as CameraView },
  ];

  // Edge hit zones
  const edgeThickness = chamfer;
  const edgeLength = sc * 2;
  const edgeOffset = s - chamfer / 2;

  const edges = [
    { pos: [0, edgeOffset, edgeOffset] as [number, number, number], size: [edgeLength, edgeThickness, edgeThickness] as [number, number, number], view: "frontTop" as CameraView },
    { pos: [0, -edgeOffset, edgeOffset] as [number, number, number], size: [edgeLength, edgeThickness, edgeThickness] as [number, number, number], view: "frontBottom" as CameraView },
    { pos: [-edgeOffset, 0, edgeOffset] as [number, number, number], size: [edgeThickness, edgeLength, edgeThickness] as [number, number, number], view: "frontLeft" as CameraView },
    { pos: [edgeOffset, 0, edgeOffset] as [number, number, number], size: [edgeThickness, edgeLength, edgeThickness] as [number, number, number], view: "frontRight" as CameraView },
    { pos: [0, edgeOffset, -edgeOffset] as [number, number, number], size: [edgeLength, edgeThickness, edgeThickness] as [number, number, number], view: "backTop" as CameraView },
    { pos: [0, -edgeOffset, -edgeOffset] as [number, number, number], size: [edgeLength, edgeThickness, edgeThickness] as [number, number, number], view: "backBottom" as CameraView },
    { pos: [-edgeOffset, 0, -edgeOffset] as [number, number, number], size: [edgeThickness, edgeLength, edgeThickness] as [number, number, number], view: "backLeft" as CameraView },
    { pos: [edgeOffset, 0, -edgeOffset] as [number, number, number], size: [edgeThickness, edgeLength, edgeThickness] as [number, number, number], view: "backRight" as CameraView },
    { pos: [-edgeOffset, edgeOffset, 0] as [number, number, number], size: [edgeThickness, edgeThickness, edgeLength] as [number, number, number], view: "topLeft" as CameraView },
    { pos: [edgeOffset, edgeOffset, 0] as [number, number, number], size: [edgeThickness, edgeThickness, edgeLength] as [number, number, number], view: "topRight" as CameraView },
    { pos: [-edgeOffset, -edgeOffset, 0] as [number, number, number], size: [edgeThickness, edgeThickness, edgeLength] as [number, number, number], view: "bottomLeft" as CameraView },
    { pos: [edgeOffset, -edgeOffset, 0] as [number, number, number], size: [edgeThickness, edgeThickness, edgeLength] as [number, number, number], view: "bottomRight" as CameraView },
  ];

  // Corner hit zones
  const cornerOffset = s - chamfer / 2;
  const cornerSize = chamfer;

  const corners = [
    { pos: [cornerOffset, cornerOffset, cornerOffset] as [number, number, number], view: "frontTopRight" as CameraView },
    { pos: [-cornerOffset, cornerOffset, cornerOffset] as [number, number, number], view: "frontTopLeft" as CameraView },
    { pos: [cornerOffset, -cornerOffset, cornerOffset] as [number, number, number], view: "frontBottomRight" as CameraView },
    { pos: [-cornerOffset, -cornerOffset, cornerOffset] as [number, number, number], view: "frontBottomLeft" as CameraView },
    { pos: [cornerOffset, cornerOffset, -cornerOffset] as [number, number, number], view: "backTopRight" as CameraView },
    { pos: [-cornerOffset, cornerOffset, -cornerOffset] as [number, number, number], view: "backTopLeft" as CameraView },
    { pos: [cornerOffset, -cornerOffset, -cornerOffset] as [number, number, number], view: "backBottomRight" as CameraView },
    { pos: [-cornerOffset, -cornerOffset, -cornerOffset] as [number, number, number], view: "backBottomLeft" as CameraView },
  ];

  return (
    <>
      {/* Fixed cube - camera orbits around it */}
      <group>
        {/* Main chamfered cube */}
        <mesh geometry={geometry}>
          <meshStandardMaterial color="#52525b" roughness={0.6} metalness={0.1} transparent opacity={0.5} />
        </mesh>

        {/* Wireframe */}
        <lineSegments>
          <edgesGeometry args={[geometry]} />
          <lineBasicMaterial color="#a1a1aa" transparent opacity={0.8} />
        </lineSegments>

        {/* XYZ Axis Helper */}
        {showAxes && <axesHelper args={[0.7]} />}

        {/* Face zones */}
        {faces.map((face) => (
          <InteractivePart
            key={face.view}
            position={face.pos}
            size={face.size}
            onClick={() => onViewChange(face.view)}
            isHovered={hoveredPart === face.view}
            onHover={(h) => setHoveredPart(h ? face.view : null)}
          />
        ))}

        {/* Edge zones */}
        {edges.map((edge) => (
          <InteractivePart
            key={edge.view}
            position={edge.pos}
            size={edge.size}
            onClick={() => onViewChange(edge.view)}
            isHovered={hoveredPart === edge.view}
            onHover={(h) => setHoveredPart(h ? edge.view : null)}
          />
        ))}

        {/* Corner zones */}
        {corners.map((corner) => (
          <mesh
            key={corner.view}
            position={corner.pos}
            onClick={(e) => { e.stopPropagation(); onViewChange(corner.view); }}
            onPointerEnter={(e) => { e.stopPropagation(); setHoveredPart(corner.view); document.body.style.cursor = "pointer"; }}
            onPointerLeave={(e) => { e.stopPropagation(); setHoveredPart(null); document.body.style.cursor = "auto"; }}
          >
            <sphereGeometry args={[cornerSize, 8, 8]} />
            <meshBasicMaterial transparent opacity={hoveredPart === corner.view ? 0.5 : 0} color="#a1a1aa" />
          </mesh>
        ))}
      </group>

      {/* OrbitControls - camera orbits around the fixed cube */}
      <OrbitControls
        ref={controlsRef}
        enableZoom={false}
        enablePan={false}
        rotateSpeed={0.5}
        onStart={() => { isUserDragging.current = true; }}
        onEnd={() => { isUserDragging.current = false; }}
      />
    </>
  );
}

interface ViewCubeProps {
  onViewChange: (position: [number, number, number]) => void;
  cameraRotation: { theta: number; phi: number };
  onDragRotate?: (spherical: { theta: number; phi: number }) => void;
  showAxes?: boolean;
}

export default function ViewCube({ onViewChange, cameraRotation, onDragRotate, showAxes = true }: ViewCubeProps) {
  const handleViewChange = useCallback((view: CameraView) => {
    const viewData = CAMERA_VIEWS[view];
    onViewChange(viewData.position as [number, number, number]);
  }, [onViewChange]);

  const handleDragRotate = useCallback((spherical: { theta: number; phi: number }) => {
    onDragRotate?.(spherical);
  }, [onDragRotate]);

  return (
    <div className="w-32 h-32">
      <Canvas
        camera={{ position: [0, 0, 2.5], fov: 40 }}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.7} />
        <directionalLight position={[3, 3, 3]} intensity={0.5} />
        <directionalLight position={[-3, -3, -3]} intensity={0.2} />
        <ViewCubeScene
          onViewChange={handleViewChange}
          cameraSpherical={cameraRotation}
          onDragRotate={handleDragRotate}
          showAxes={showAxes}
        />
      </Canvas>
    </div>
  );
}
