import { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { useNavigate } from 'react-router-dom';
import { Upload, Loader2, Box, AlertTriangle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { GlbToBricksApiService } from '../services/glbToBricksApi';
import { GetGenerationApiService } from '../services/getGenerationApi';

type VoxelizerOption = 'trimesh' | 'obj2voxel';

const VOXELIZER_PRESETS: { label: string; value: VoxelizerOption; description: string }[] = [
  { label: 'Trimesh', value: 'trimesh', description: 'Python voxelizer with texture color sampling' },
  { label: 'obj2voxel', value: 'obj2voxel', description: 'Legacy C++ voxelizer' },
];

const ACCEPTED = '.glb,.obj,.mtl,.png,.jpg,.jpeg,.bmp,.tga';
const VALID_EXTS = ['.glb', '.obj', '.mtl', '.png', '.jpg', '.jpeg', '.bmp', '.tga'];

const basename = (s: string) => s.split(/[\\/]/).pop() || s;
const lower = (s: string) => s.toLowerCase();
const isGlb = (f: File) => lower(f.name).endsWith('.glb');
const isObj = (f: File) => lower(f.name).endsWith('.obj');
const isMtl = (f: File) => lower(f.name).endsWith('.mtl');

/** Interactive viewer for GLB or OBJ (with MTL/textures) using raw three.js. */
function ModelViewer({ files, mainName }: { files: File[]; mainName: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    let renderer: THREE.WebGLRenderer | null = null;
    let animationId = 0;
    let resizeObserver: ResizeObserver | null = null;
    let controls: { dispose: () => void; update: () => void } | null = null;
    const blobUrls: string[] = [];

    const container = containerRef.current;
    if (!container) return;

    const setup = async () => {
      try {
        setLoading(true);
        setError(null);

        const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
        const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
        const { OBJLoader } = await import('three/examples/jsm/loaders/OBJLoader.js');
        const { MTLLoader } = await import('three/examples/jsm/loaders/MTLLoader.js');
        const { RoomEnvironment } = await import('three/examples/jsm/environments/RoomEnvironment.js');
        if (disposed || !container) return;

        const width = container.clientWidth || 400;
        const height = container.clientHeight || 320;

        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0xeef2f5);
        const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 1000);

        renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.setSize(width, height);
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        container.appendChild(renderer.domElement);

        const pmrem = new THREE.PMREMGenerator(renderer);
        scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

        const orbit = new OrbitControls(camera, renderer.domElement);
        orbit.enableDamping = true;
        controls = orbit;

        // Map every uploaded file's basename -> blob URL so loaders can resolve
        // OBJ -> MTL -> texture references regardless of the original paths.
        const blobByName = new Map<string, string>();
        for (const f of files) {
          const url = URL.createObjectURL(f);
          blobUrls.push(url);
          blobByName.set(lower(f.name), url);
        }

        const manager = new THREE.LoadingManager();
        manager.setURLModifier((url) => {
          if (url.startsWith('blob:') || url.startsWith('data:')) return url;
          const mapped = blobByName.get(lower(basename(url)));
          return mapped || url;
        });

        const frame = (object: THREE.Object3D) => {
          const bbox = new THREE.Box3().setFromObject(object);
          const size = bbox.getSize(new THREE.Vector3());
          const center = bbox.getCenter(new THREE.Vector3());
          const radius = Math.max(size.x, size.y, size.z) * 0.5 || 1;
          orbit.target.copy(center);
          camera.position.copy(center).add(new THREE.Vector3(1, 0.7, 1).multiplyScalar(radius * 2.4));
          camera.near = radius / 100;
          camera.far = radius * 100;
          camera.updateProjectionMatrix();
          orbit.update();
          setLoading(false);
        };

        const onLoadError = (err: unknown) => {
          if (disposed) return;
          console.error('Failed to load model:', err);
          setError('Failed to load model preview');
          setLoading(false);
        };

        const mainUrl = blobByName.get(lower(mainName));
        if (!mainUrl) {
          onLoadError(new Error('Main file not found'));
          return;
        }

        if (lower(mainName).endsWith('.glb')) {
          const loader = new GLTFLoader(manager);
          loader.load(mainUrl, (gltf: { scene: THREE.Group }) => {
            if (disposed) return;
            scene.add(gltf.scene);
            frame(gltf.scene);
          }, undefined, onLoadError);
        } else {
          // OBJ — load its MTL first (if uploaded) for materials/textures.
          const mtlFile = files.find(isMtl);
          const loadObj = (materials?: { preload: () => void }) => {
            const objLoader = new OBJLoader(manager);
            if (materials) {
              materials.preload();
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              objLoader.setMaterials(materials as any);
            }
            objLoader.load(mainUrl, (obj: THREE.Group) => {
              if (disposed) return;
              scene.add(obj);
              frame(obj);
            }, undefined, onLoadError);
          };

          if (mtlFile) {
            const mtlUrl = blobByName.get(lower(mtlFile.name))!;
            const mtlLoader = new MTLLoader(manager);
            mtlLoader.load(mtlUrl, (materials: { preload: () => void }) => {
              if (disposed) return;
              loadObj(materials);
            }, undefined, () => loadObj());
          } else {
            loadObj();
          }
        }

        const animate = () => {
          animationId = requestAnimationFrame(animate);
          orbit.update();
          renderer!.render(scene, camera);
        };
        animate();

        resizeObserver = new ResizeObserver(() => {
          if (!renderer || !container) return;
          const w = container.clientWidth;
          const h = container.clientHeight;
          if (w === 0 || h === 0) return;
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
          renderer.setSize(w, h);
        });
        resizeObserver.observe(container);
      } catch (err) {
        console.error('Model viewer setup failed:', err);
        setError('Failed to initialize 3D viewer');
        setLoading(false);
      }
    };

    setup();

    return () => {
      disposed = true;
      if (animationId) cancelAnimationFrame(animationId);
      if (resizeObserver) resizeObserver.disconnect();
      if (controls) controls.dispose();
      blobUrls.forEach((u) => URL.revokeObjectURL(u));
      if (renderer) {
        renderer.dispose();
        renderer.forceContextLoss();
        if (renderer.domElement.parentNode) {
          renderer.domElement.parentNode.removeChild(renderer.domElement);
        }
      }
    };
  }, [files, mainName]);

  return (
    <div className="relative w-full h-72 rounded-lg overflow-hidden border border-slate-200 bg-slate-100">
      <div ref={containerRef} className="absolute inset-0" />
      {loading && !error && (
        <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading model…
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center text-red-500 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}

/** Settings card: upload a GLB or OBJ(+MTL), preview it, pick the voxelizer, and convert. */
export function GlbUploadCard({ autoOpen = false }: { autoOpen?: boolean } = {}) {
  const { session } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [mainName, setMainName] = useState<string | null>(null);
  const [missingMtl, setMissingMtl] = useState<string[]>([]);
  const [voxelizer, setVoxelizer] = useState<VoxelizerOption>('trimesh');
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Open the file browser automatically when requested by the parent.
  useEffect(() => {
    if (autoOpen) fileInputRef.current?.click();
  }, [autoOpen]);

  // Merge newly selected files with existing ones (replacing same-name files).
  const addFiles = useCallback((selected: FileList | null) => {
    if (!selected || selected.length === 0) return;
    const valid = Array.from(selected).filter((f) =>
      VALID_EXTS.some((e) => lower(f.name).endsWith(e)),
    );
    if (valid.length === 0) {
      setError('Please select a .glb, or a .obj plus its .mtl/textures');
      return;
    }
    setError(null);
    setStatus(null);
    setFiles((prev) => {
      const byName = new Map<string, File>();
      for (const f of prev) byName.set(lower(f.name), f);
      for (const f of valid) byName.set(lower(f.name), f);
      return Array.from(byName.values());
    });
  }, []);

  // Recompute the main model file + any missing MTL references when files change.
  useEffect(() => {
    let cancelled = false;
    const compute = async () => {
      const glb = files.find(isGlb);
      const obj = files.find(isObj);
      const main = glb || obj || null;
      if (cancelled) return;
      setMainName(main ? main.name : null);

      if (main && isObj(main)) {
        try {
          const text = await main.text();
          const refs: string[] = [];
          for (const line of text.split(/\r?\n/)) {
            if (lower(line).startsWith('mtllib')) {
              refs.push(...line.trim().split(/\s+/).slice(1).map(basename));
            }
          }
          const have = new Set(files.map((f) => lower(f.name)));
          const missing = refs.filter((r) => !have.has(lower(r)));
          if (!cancelled) setMissingMtl(missing);
        } catch {
          if (!cancelled) setMissingMtl([]);
        }
      } else if (!cancelled) {
        setMissingMtl([]);
      }
    };
    compute();
    return () => {
      cancelled = true;
    };
  }, [files]);

  const handleConvert = async () => {
    if (!mainName || submitting || missingMtl.length > 0) return;
    setSubmitting(true);
    setError(null);
    setStatus('Uploading…');
    try {
      const { generation_id } = await GlbToBricksApiService.uploadModel(
        files,
        voxelizer,
        40,
        session?.access_token,
      );
      setStatus('Processing…');
      await GetGenerationApiService.pollUntilComplete(generation_id, (res) => {
        if (res.status) setStatus(`Status: ${res.status}`);
      });
      navigate(`/generated-model?id=${generation_id}`);
    } catch (err) {
      console.error('Model conversion failed:', err);
      setError(err instanceof Error ? err.message : 'Conversion failed');
      setStatus(null);
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setFiles([]);
    setMainName(null);
    setMissingMtl([]);
    setStatus(null);
    setError(null);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 sm:p-6 max-w-2xl mt-6">
      <h2 className="text-lg font-semibold text-slate-900 mb-1 flex items-center gap-2">
        <Box className="w-5 h-5 text-[#f44336]" />
        Upload model
      </h2>
      <p className="text-sm text-slate-500 mb-5">
        Upload a <span className="font-medium">.glb</span>, or a{' '}
        <span className="font-medium">.obj</span> together with its{' '}
        <span className="font-medium">.mtl</span> and texture files, then choose a voxelizer and
        convert it into a brick model.
      </p>

      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED}
        multiple
        className="hidden"
        onChange={(e) => {
          addFiles(e.target.files);
          e.target.value = '';
        }}
      />

      {!mainName ? (
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#f44336] rounded-lg hover:bg-[#ff6b6b] transition-colors cursor-pointer"
        >
          <Upload className="w-4 h-4" />
          Choose files (.glb or .obj + .mtl)
        </button>
      ) : (
        <div className="space-y-4">
          <ModelViewer files={files} mainName={mainName} />

          {/* File summary + actions */}
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm text-slate-600 truncate">
              <span className="font-medium">{mainName}</span>
              {files.length > 1 && (
                <span className="text-slate-400"> +{files.length - 1} file(s)</span>
              )}
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={submitting}
                className="text-sm font-medium text-[#f44336] hover:text-[#ff6b6b] transition-colors cursor-pointer disabled:opacity-50"
              >
                Add files
              </button>
              <button
                type="button"
                onClick={reset}
                disabled={submitting}
                className="text-sm font-medium text-slate-500 hover:text-slate-700 transition-colors cursor-pointer disabled:opacity-50"
              >
                Clear
              </button>
            </div>
          </div>

          {/* Missing MTL warning */}
          {missingMtl.length > 0 && (
            <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-800">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>
                This OBJ needs material file(s):{' '}
                <span className="font-medium">{missingMtl.join(', ')}</span>. Click “Add files” to
                upload the .mtl (and any textures).
              </span>
            </div>
          )}

          {/* Voxelizer selection */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm text-slate-500">Voxelizer:</span>
            {VOXELIZER_PRESETS.map((vx) => {
              const active = vx.value === voxelizer;
              return (
                <button
                  key={vx.value}
                  type="button"
                  onClick={() => !submitting && setVoxelizer(vx.value)}
                  disabled={submitting}
                  title={vx.description}
                  className={`rounded-full px-4 py-1 text-sm transition-all duration-150 ${
                    active
                      ? 'bg-[#f44336] text-white border border-transparent'
                      : 'bg-white text-slate-700 border border-slate-300 hover:opacity-70'
                  } ${submitting ? 'cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  {vx.label}
                </button>
              );
            })}
          </div>

          <div className="flex flex-col items-start gap-3">
            <button
              type="button"
              onClick={handleConvert}
              disabled={submitting || missingMtl.length > 0}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#f44336] rounded-lg hover:bg-[#ff6b6b] transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Box className="w-4 h-4" />}
              Convert to bricks
            </button>
            {status && <span className="text-sm text-slate-500">{status}</span>}
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-500">{error}</p>}
    </div>
  );
}

export default GlbUploadCard;
