"use client";

import { useRef, useMemo, useEffect, useState, useCallback } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, PerspectiveCamera } from "@react-three/drei";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

interface Voxel {
  x: number;
  y: number;
  z: number;
  r: number;
  g: number;
  b: number;
}

interface MeshData {
  vertices: Float32Array;
  faces: Uint32Array;
  vertexColors: Uint8Array;
}

interface VoxelPointsProps {
  voxels: Voxel[];
}

function VoxelPoints({ voxels }: VoxelPointsProps) {
  const pointsRef = useRef<THREE.Points>(null);

  const { positions, colors } = useMemo(() => {
    if (voxels.length === 0) {
      return {
        positions: new Float32Array(0),
        colors: new Float32Array(0),
      };
    }

    const positions = new Float32Array(voxels.length * 3);
    const colors = new Float32Array(voxels.length * 3);

    // Calculate bounding box
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    
    for (const v of voxels) {
      minX = Math.min(minX, v.x);
      minY = Math.min(minY, v.y);
      minZ = Math.min(minZ, v.z);
      maxX = Math.max(maxX, v.x);
      maxY = Math.max(maxY, v.y);
      maxZ = Math.max(maxZ, v.z);
    }

    // Calculate center and scale to fit in unit cube
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const centerZ = (minZ + maxZ) / 2;
    
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const rangeZ = maxZ - minZ || 1;
    const maxRange = Math.max(rangeX, rangeY, rangeZ);
    
    // Normalize to fit within [-0.5, 0.5] range (unit cube)
    const scale = 1 / maxRange;

    // First pass: compute positions and find minY after transformation
    let minYAfterTransform = Infinity;
    for (let i = 0; i < voxels.length; i++) {
      const v = voxels[i];
      // Convert from Z-up (SAM-3D) to Y-up (Three.js): X stays, Z becomes Y, -Y becomes Z
      positions[i * 3] = (v.x - centerX) * scale;
      positions[i * 3 + 1] = (v.z - centerZ) * scale;  // Z -> Y (up)
      positions[i * 3 + 2] = -(v.y - centerY) * scale; // -Y -> Z (forward)
      minYAfterTransform = Math.min(minYAfterTransform, positions[i * 3 + 1]);
      
      // Normalize colors to 0-1, fallback to white if color is black/missing
      const isBlack = v.r === 0 && v.g === 0 && v.b === 0;
      colors[i * 3] = isBlack ? 1.0 : v.r / 255;
      colors[i * 3 + 1] = isBlack ? 1.0 : v.g / 255;
      colors[i * 3 + 2] = isBlack ? 1.0 : v.b / 255;
    }

    // Second pass: shift Y so the bottom sits on the platform
    for (let i = 0; i < voxels.length; i++) {
      positions[i * 3 + 1] -= minYAfterTransform - PLATFORM_Y;
    }

    return { positions, colors };
  }, [voxels]);

  if (voxels.length === 0) return null;

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
        <bufferAttribute
          attach="attributes-color"
          args={[colors, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        vertexColors
        sizeAttenuation
        transparent
        opacity={0.9}
      />
    </points>
  );
}

interface MeshPreviewProps {
  meshData: MeshData;
}

function MeshPreview({ meshData }: MeshPreviewProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    
    // Set vertices
    geo.setAttribute("position", new THREE.Float32BufferAttribute(meshData.vertices, 3));
    
    // Set faces (indices)
    geo.setIndex(new THREE.Uint32BufferAttribute(meshData.faces, 1));
    
    // Set vertex colors (normalized)
    const normalizedColors = new Float32Array(meshData.vertexColors.length);
    for (let i = 0; i < meshData.vertexColors.length; i++) {
      normalizedColors[i] = meshData.vertexColors[i] / 255;
    }
    geo.setAttribute("color", new THREE.Float32BufferAttribute(normalizedColors, 3));
    
    // Compute normals for proper lighting
    geo.computeVertexNormals();
    
    // Center and normalize
    geo.computeBoundingBox();
    const box = geo.boundingBox!;
    const center = new THREE.Vector3();
    box.getCenter(center);
    
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    const scale = 1 / maxDim;
    
    // First pass: transform vertices and find minY
    const positions = geo.getAttribute("position");
    let minY = Infinity;
    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i);
      const y = positions.getY(i);
      const z = positions.getZ(i);
      
      // Center, scale, and convert Z-up to Y-up
      const newY = (z - center.z) * scale;  // Z -> Y
      positions.setXYZ(
        i,
        (x - center.x) * scale,
        newY,
        -(y - center.y) * scale  // -Y -> Z
      );
      minY = Math.min(minY, newY);
    }
    
    // Second pass: shift so bottom sits on the platform
    for (let i = 0; i < positions.count; i++) {
      positions.setY(i, positions.getY(i) - minY + PLATFORM_Y);
    }
    
    positions.needsUpdate = true;
    geo.computeVertexNormals();
    
    return geo;
  }, [meshData]);

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        vertexColors
        side={THREE.DoubleSide}
        roughness={0.7}
        metalness={0.1}
      />
    </mesh>
  );
}

interface GLBViewerProps {
  glbData: ArrayBuffer;
}

function GLBViewer({ glbData }: GLBViewerProps) {
  const [scene, setScene] = useState<THREE.Group | null>(null);

  useEffect(() => {
    const loader = new GLTFLoader();
    loader.parse(glbData, "", (gltf) => {
      // GLB is already in Y-up format (glTF standard)
      // Just center and scale - no coordinate conversion needed
      
      // Enable shadows on all meshes and improve materials
      gltf.scene.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.castShadow = true;
          child.receiveShadow = true;
          
          // Enhance material if it's a standard material
          if (child.material instanceof THREE.MeshStandardMaterial) {
            child.material.envMapIntensity = 0.5;
            child.material.needsUpdate = true;
          }
        }
      });
      
      // Center and scale the model
      const box = new THREE.Box3().setFromObject(gltf.scene);
      const center = new THREE.Vector3();
      box.getCenter(center);
      
      const size = new THREE.Vector3();
      box.getSize(size);
      const maxDim = Math.max(size.x, size.y, size.z) || 1;
      const scale = 1 / maxDim;
      
      // Create wrapper for centering and scaling
      const wrapper = new THREE.Group();
      wrapper.add(gltf.scene);
      gltf.scene.position.set(-center.x, -center.y, -center.z);
      wrapper.scale.setScalar(scale);
      
      // Calculate scaled bounding box to find where bottom is
      const scaledMinY = (box.min.y - center.y) * scale;
      // Shift so bottom sits on the platform
      wrapper.position.y = -scaledMinY + PLATFORM_Y;
      
      setScene(wrapper);
    }, (error) => {
      console.error("Error loading GLB:", error);
    });
  }, [glbData]);

  if (!scene) return null;

  return <primitive object={scene} />;
}

function SceneSetup() {
  const { gl } = useThree();
  
  useEffect(() => {
    gl.setClearColor(new THREE.Color("#0a0a0a"), 1);
  }, [gl]);

  return null;
}

interface CameraControllerProps {
  targetPosition: [number, number, number] | null;
  targetSpherical?: { theta: number; phi: number } | null;
  onRotationChange?: (rotation: { theta: number; phi: number }) => void;
  autoRotate: boolean;
  controlsRef: React.RefObject<OrbitControlsImpl | null>;
}

function CameraController({ 
  targetPosition, 
  targetSpherical,
  onRotationChange, 
  autoRotate,
  controlsRef 
}: CameraControllerProps) {
  const { camera } = useThree();
  const animatingRef = useRef(false);
  const targetRef = useRef<THREE.Vector3 | null>(null);
  const startPosRef = useRef<THREE.Vector3 | null>(null);
  const progressRef = useRef(0);

  // Animate camera to target position (from clicking ViewCube faces/edges/corners)
  useEffect(() => {
    if (targetPosition) {
      const distance = camera.position.length();
      const normalizedTarget = new THREE.Vector3(...targetPosition).normalize().multiplyScalar(distance);
      
      startPosRef.current = camera.position.clone();
      targetRef.current = normalizedTarget;
      progressRef.current = 0;
      animatingRef.current = true;
    }
  }, [targetPosition, camera]);

  // Apply spherical rotation from ViewCube drag
  useEffect(() => {
    if (targetSpherical && controlsRef.current) {
      const distance = camera.position.length();
      const spherical = new THREE.Spherical(distance, targetSpherical.phi, targetSpherical.theta);
      camera.position.setFromSpherical(spherical);
      camera.lookAt(0, 0, 0);
      controlsRef.current.update();
    }
  }, [targetSpherical, camera, controlsRef]);

  useFrame(() => {
    // Animate camera
    if (animatingRef.current && targetRef.current && startPosRef.current) {
      progressRef.current += 0.05;
      
      if (progressRef.current >= 1) {
        camera.position.copy(targetRef.current);
        animatingRef.current = false;
      } else {
        // Smooth interpolation
        const t = 1 - Math.pow(1 - progressRef.current, 3); // ease-out cubic
        camera.position.lerpVectors(startPosRef.current, targetRef.current, t);
      }
      
      camera.lookAt(0, 0, 0);
      controlsRef.current?.update();
    }

    // Report camera spherical coordinates for ViewCube sync
    if (onRotationChange) {
      const spherical = new THREE.Spherical().setFromVector3(camera.position);
      onRotationChange({
        theta: spherical.theta,
        phi: spherical.phi,
      });
    }
  });

  return null;
}

// Platform height - lower value = more room for tall models
const PLATFORM_Y = -0.3;

interface VoxelViewerProps {
  voxels: Voxel[];
  meshData?: MeshData | null;
  glbData?: ArrayBuffer | null;
  autoRotate?: boolean;
  autoRotateSpeed?: number;
  targetCameraPosition?: [number, number, number] | null;
  targetSpherical?: { theta: number; phi: number } | null;
  onCameraRotationChange?: (rotation: { theta: number; phi: number }) => void;
  showAxes?: boolean;
  showGrid?: boolean;
}

export default function VoxelViewer({ 
  voxels, 
  meshData = null, 
  glbData = null, 
  autoRotate = false,
  autoRotateSpeed = 1,
  targetCameraPosition = null,
  targetSpherical = null,
  onCameraRotationChange,
  showAxes = true,
  showGrid = true,
}: VoxelViewerProps) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  
  // Priority: GLB > Mesh > Voxels
  const showGLB = glbData !== null;
  const showMesh = !showGLB && meshData !== null;
  const showVoxels = !showGLB && !showMesh && voxels.length > 0;

  return (
    <div className="w-full h-full">
      <Canvas shadows>
        <SceneSetup />
        <PerspectiveCamera makeDefault position={[1.5, 1, 1.5]} fov={50} />
        
        {/* Ambient base lighting */}
        <ambientLight intensity={0.4} />
        
        {/* Hemisphere light for natural sky/ground gradient */}
        <hemisphereLight 
          args={["#87CEEB", "#362312", 0.5]} 
        />
        
        {/* Key light - main directional light with shadows */}
        <directionalLight 
          position={[5, 8, 5]} 
          intensity={1.2} 
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-far={20}
          shadow-camera-left={-3}
          shadow-camera-right={3}
          shadow-camera-top={3}
          shadow-camera-bottom={-3}
          shadow-bias={-0.0001}
        />
        
        {/* Fill light - softer, from opposite side */}
        <directionalLight 
          position={[-4, 4, -4]} 
          intensity={0.4} 
        />
        
        {/* Rim/back light - highlights edges */}
        <directionalLight 
          position={[0, 2, -6]} 
          intensity={0.3} 
        />
        
        {/* Front fill for better face visibility */}
        <pointLight position={[0, 1, 4]} intensity={0.3} />
        
        <CameraController
          targetPosition={targetCameraPosition}
          targetSpherical={targetSpherical}
          onRotationChange={onCameraRotationChange}
          autoRotate={autoRotate}
          controlsRef={controlsRef}
        />
        
        {showGLB && glbData && (
          <GLBViewer glbData={glbData} />
        )}
        {showMesh && meshData && (
          <MeshPreview meshData={meshData} />
        )}
        {showVoxels && (
          <VoxelPoints voxels={voxels} />
        )}
        
        <OrbitControls
          ref={controlsRef}
          enableDamping
          dampingFactor={0.05}
          enablePan={false}
          minDistance={0.5}
          maxDistance={10}
          autoRotate={autoRotate}
          autoRotateSpeed={autoRotateSpeed}
        />
        {showGrid && <gridHelper args={[2, 20, "#333", "#222"]} position={[0, PLATFORM_Y - 0.01, 0]} />}
        
        {/* XYZ Axis Helper - Red=X, Green=Y, Blue=Z */}
        {showAxes && <axesHelper args={[0.5]} position={[0, PLATFORM_Y, 0]} />}
      </Canvas>
    </div>
  );
}

export type { Voxel, MeshData };
