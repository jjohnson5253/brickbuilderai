import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

interface MpdImageRendererProps {
  mpdContent: string;
  width?: number;
  height?: number;
  className?: string;
}

export function MpdImageRenderer({ mpdContent, width = 400, height = 300, className = '' }: MpdImageRendererProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Track renderer for cleanup
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const pmremRef = useRef<THREE.PMREMGenerator | null>(null);

  useEffect(() => {
    let isMounted = true;
    
    // Dispose previous renderer if exists
    if (rendererRef.current) {
      rendererRef.current.dispose();
      rendererRef.current.forceContextLoss();
      rendererRef.current = null;
    }
    if (pmremRef.current) {
      pmremRef.current.dispose();
      pmremRef.current = null;
    }

    const renderMpdToImage = async () => {
      try {
        setLoading(true);
        setError(null);

        // Dynamic imports for Three.js
        const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
        const { RoomEnvironment } = await import('three/examples/jsm/environments/RoomEnvironment.js');
        const { LDrawLoader } = await import('three/examples/jsm/loaders/LDrawLoader.js');
        const { LDrawConditionalLineMaterial } = await import('three/examples/jsm/materials/LDrawConditionalLineMaterial.js');

        if (!isMounted) return;

        // Create scene, camera, renderer
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0xdeebed);

        const camera = new THREE.PerspectiveCamera(45, width / height, 1, 10000);
        const renderer = new THREE.WebGLRenderer({ 
          antialias: true, 
          preserveDrawingBuffer: true
        });
        
        // Store in ref for cleanup
        rendererRef.current = renderer;
        
        renderer.setSize(width, height);
        renderer.toneMapping = THREE.ACESFilmicToneMapping;

        // Environment setup
        const pmremGenerator = new THREE.PMREMGenerator(renderer);
        pmremRef.current = pmremGenerator;
        scene.environment = pmremGenerator.fromScene(new RoomEnvironment()).texture;

        // Controls for calculating good camera position
        const controls = new OrbitControls(camera, renderer.domElement);

        // Load the MPD model
        const loader = new LDrawLoader();
        loader.setConditionalLineMaterial(LDrawConditionalLineMaterial);
        loader.smoothNormals = false;

        // Create blob URL for the MPD content
        const blob = new Blob([mpdContent], { type: 'text/plain' });
        const objectUrl = URL.createObjectURL(blob);

        loader.load(
          objectUrl,
          (model: THREE.Group) => {
            if (!isMounted) {
              URL.revokeObjectURL(objectUrl);
              return;
            }

            // Rotate the model to match the original implementation
            model.rotation.x = Math.PI;
            scene.add(model);

            // Calculate bounding box and adjust camera
            const bbox = new THREE.Box3().setFromObject(model);
            const size = bbox.getSize(new THREE.Vector3());
            const radius = Math.max(size.x, Math.max(size.y, size.z)) * 0.5;

            // Set camera position based on model size
            const center = bbox.getCenter(new THREE.Vector3());
            controls.target.copy(center);
            camera.position.set(-2.3, 1, 2).multiplyScalar(radius * 1.3).add(center);
            controls.update();

            // Render the scene
            renderer.render(scene, camera);

            // Convert to image URL
            const canvas = renderer.domElement;
            const dataUrl = canvas.toDataURL('image/png');
            setImageUrl(dataUrl);
            setLoading(false);

            // Cleanup - free the WebGL context immediately after capturing
            URL.revokeObjectURL(objectUrl);
            pmremGenerator.dispose();
            renderer.dispose();
            renderer.forceContextLoss();
            rendererRef.current = null;
            pmremRef.current = null;
          },
          undefined,
          (error) => {
            if (!isMounted) {
              URL.revokeObjectURL(objectUrl);
              return;
            }
            console.error('Image generation failed:', error);
            setError('Failed to render image');
            setLoading(false);
            URL.revokeObjectURL(objectUrl);
            renderer.dispose();
            renderer.forceContextLoss();
            rendererRef.current = null;
          }
        );

      } catch (err) {
        if (!isMounted) return;
        console.error('Error rendering MPD to image:', err);
        setError('Render error');
        setLoading(false);
      }
    };

    if (mpdContent) {
      renderMpdToImage();
    }

    return () => {
      isMounted = false;
      // Cleanup on unmount
      if (rendererRef.current) {
        rendererRef.current.dispose();
        rendererRef.current.forceContextLoss();
        rendererRef.current = null;
      }
      if (pmremRef.current) {
        pmremRef.current.dispose();
        pmremRef.current = null;
      }
    };
  }, [mpdContent, width, height]);

  if (loading) {
    return (
      <div className={`w-full h-full ${className}`} style={{ backgroundColor: '#deebed' }} />
    );
  }

  if (error || !imageUrl) {
    return (
      <div className={`flex items-center justify-center w-full h-full ${className}`} style={{ backgroundColor: '#deebed' }}>
        <p className="text-sm text-slate-500">Failed to render</p>
      </div>
    );
  }

  return (
    <img 
      src={imageUrl} 
      alt="Step preview"
      className={`block object-contain w-full h-full max-w-full max-h-full ${className}`}
    />
  );
}