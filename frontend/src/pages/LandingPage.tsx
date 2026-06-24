
import React, { useEffect, useLayoutEffect, useRef, useState, memo } from "react";
import { Sparkles, Image as ImageIcon, Users, Calendar, Eye, X, Settings, MessageSquare, Wand2, Package, Github, LayoutDashboard } from "lucide-react";
import { SEO } from "../components/SEO";
import FallingBricks from "../components/FallingBricks";
import LoginModal from "../components/LoginModal";
import { useNavigate } from "react-router-dom";
import { TextToBricksApiService } from "../services/textToBricksApi";
import { ImageToBricksApiService, StreamEvent, VoxelDataEvent, PipelineEvent } from "../services/imageToBricksApi";
import { GetGenerationApiService, GetGenerationResponse } from "../services/getGenerationApi";
import { recordAnonymousGeneration } from "../utils/anonGenerations";
import StreamingMeshViewer from "../components/StreamingMeshViewer";
import { LdrToMpdApiService } from "../services/ldrToMpdApi";
import { useAuth } from "../contexts/AuthContext";
import modelsMetadata from "../assets/demo-images/models-metadata.json";
import { SiteFooter } from "../components/SiteFooter";
import { GlbUploadCard } from "../components/GlbUploadCard";
import { ProfileMenu } from "../components/ProfileMenu";

// Check if 3D streaming (SAM3D) is enabled by default via environment variable
// Note: Image generation always uses flux-2 streaming regardless of this setting
const STREAMING_ENABLED_BY_DEFAULT = import.meta.env.VITE_ENABLE_STREAMING !== 'false';

// Toggle whether users must be logged in before starting a generation.
const REQUIRE_LOGIN_FOR_GENERATION = false;

// LocalStorage keys for persisting generated models
const STORAGE_KEYS = {
  LDR_CONTENT: 'lastLdrContent',
  MPD_CONTENT: 'lastMpdContent',
  MODEL_NAME: 'lastModelName',
  GENERATED_AT: 'lastGeneratedAt',
  GENERATION_ID: 'lastGenerationId'
};

// SessionStorage key for persisting landing form state across login redirects
const PENDING_LANDING_STATE_KEY = 'pendingLandingState';

type SizeValue = "tiny" | "medium" | "big";
const SIZE_PRESETS: { label: string; value: SizeValue }[] = [
  { label: "Tiny", value: "tiny" },
  { label: "Medium", value: "medium" },
  { label: "Big", value: "big" },
];

type ModelQuality = "regular" | "premium";
const MODEL_QUALITY_PRESETS: { label: string; value: ModelQuality; modelOption: string }[] = [
  { label: "Regular", value: "regular", modelOption: "a" },
  { label: "Premium", value: "premium", modelOption: "b" },
];

type StyleOption = "videogame" | "plush" | "voxel";
const STYLE_PRESETS: { label: string; value: StyleOption; promptOption: string }[] = [
  { label: "Videogame", value: "videogame", promptOption: "a" },
  { label: "Plush", value: "plush", promptOption: "b" },
  { label: "Block", value: "voxel", promptOption: "c" },
];

type GenerationType = "streaming" | "non-streaming";
const GENERATION_TYPE_PRESETS: { label: string; value: GenerationType; description?: string }[] = [
  { label: "Streaming", value: "streaming", description: "SAM3D with live 3D preview" },
  { label: "Standard", value: "non-streaming", description: "Trellis (faster, no preview)" },
];

type VoxelizerOption = "trimesh" | "obj2voxel";
const VOXELIZER_PRESETS: { label: string; value: VoxelizerOption; description?: string }[] = [
  { label: "Trimesh", value: "trimesh", description: "Python voxelizer with texture color sampling" },
  { label: "obj2voxel", value: "obj2voxel", description: "Legacy C++ voxelizer" },
];

const NAV_LINKS = [
  { label: "Products", href: "#products" },
  { label: "Models", href: "#models" },
  { label: "Created", href: "#created" },
  { label: "Today", href: "#today" },
];

type ModelMetadata = {
  id: string;
  cost: number;
  pieces: number;
  weight: number;
  img_url: string;
};

type FeaturedItem = {
  title: string;
  metadata: ModelMetadata;
};

// Generate FEATURED array from metadata
const FEATURED: FeaturedItem[] = Object.entries(modelsMetadata).map(([title, metadata]) => ({
  title,
  metadata: metadata as ModelMetadata
}));

// ---- Typewriter placeholder logic ----
const EXAMPLE_PHRASES = [
  "a unicorn",
  "a red fire hydrant",
  "a 3‑story lakeside cabin",
  "baby yoda with a scarf",
  "a retro space rover",
  "a dachshund in sunglasses",
];

function useTypewriter(enabled: boolean) {
  const [idx, setIdx] = useState(0);
  const [text, setText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [pause, setPause] = useState(false);
  const [showCaret, setShowCaret] = useState(true);

  // Caret blinking - separate from text updates
  useEffect(() => {
    if (!enabled) return;
    const interval = setInterval(() => {
      setShowCaret(prev => !prev);
    }, 400);
    return () => clearInterval(interval);
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;               // stop updating when user is typing/focused
    if (pause) {
      const t = setTimeout(() => setPause(false), 900);
      return () => clearTimeout(t);
    }

    const phrase = EXAMPLE_PHRASES[idx % EXAMPLE_PHRASES.length];
    const speed = deleting ? 35 : 70;   // typing speed
    const nextTimer = setTimeout(() => {
      const nextLen = deleting ? text.length - 1 : text.length + 1;
      const next = phrase.slice(0, Math.max(0, nextLen));
      setText(next);
      if (!deleting && next === phrase) {
        setPause(true);
        setDeleting(true);
      } else if (deleting && next.length === 0) {
        setDeleting(false);
        setIdx((i) => (i + 1) % EXAMPLE_PHRASES.length);
      }
    }, speed);

    return () => clearTimeout(nextTimer);
  }, [enabled, text, deleting, pause, idx]);

  const caret = enabled && showCaret ? "|" : "";
  return (text + caret).trim();
}

// ---- In‑place loading: progress + messages ----
const LOADING_BEATS: Array<{ dur: number; text: string }> = [
  { dur: 2000, text: "Spinning up turbo hamsters..." },
  { dur: 2000, text: "Asking the AI nicely to imagine for you..." },
  { dur: 2000, text: "Translating dreams ➜ bricks..." },
  { dur: 2000, text: "Checking your vibe alignment coefficients..." },
  { dur: 2000, text: "Picking only the tastiest studs..." },
  { dur: 2000, text: "Hunting for the best brick deals (coupon ninja mode)" },
  { dur: 2000, text: "Making sure gravity will cooperate..." },
  { dur: 2000, text: "Polishing your pixels till they reflect the soul..." },
  { dur: 2000, text: "Applying secret sauce (proprietary™)" },
  { dur: 2000, text: "Snapping bricks with great satisfaction..." },
];

function useBeatText(active: boolean) {
  const [i, setI] = useState(0);
  const [fade, setFade] = useState(1);
  useEffect(() => {
    if (!active) {
      setI(0);
      setFade(1);
      return;
    }
    let alive = true;
    let currentIndex = 0;
    const loop = async () => {
      while (alive) {
        const beat = LOADING_BEATS[currentIndex % LOADING_BEATS.length];
        setI(currentIndex);
        setFade(1);
        await new Promise((r) => setTimeout(r, beat.dur));
        if (!alive) break;
        setFade(0.4);
        await new Promise((r) => setTimeout(r, 220));
        if (!alive) break;
        currentIndex++;
      }
    };
    loop();
    return () => { alive = false; };
  }, [active]);
  const text = LOADING_BEATS[i % LOADING_BEATS.length]?.text ?? "";
  return { text, fade };
}

export default function LandingPage() {
  const { session, loading: authLoading } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState<SizeValue>("big");
  const [modelQuality, setModelQuality] = useState<ModelQuality>("regular");
  const [styleOption, setStyleOption] = useState<StyleOption>("videogame");
  const [generationType, setGenerationType] = useState<GenerationType>(
    STREAMING_ENABLED_BY_DEFAULT ? "streaming" : "non-streaming"
  );
  const [voxelizer, setVoxelizer] = useState<VoxelizerOption>("trimesh");
  const [imgFile, setImgFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [focused, setFocused] = useState(false);
  const showTypewriter = !focused && prompt.length === 0;
  const typedPlaceholder = useTypewriter(showTypewriter);

  // NEW: in‑place loading state
  const [loading, setLoading] = useState(false);
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [generationStatus, setGenerationStatus] = useState<string | null>(null);
  const { text: beatText, fade: beatFade } = useBeatText(loading);

  // Generated model state
  const [generatedMpdContent, setGeneratedMpdContent] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);

  // Streaming 3D preview state
  const [voxelData, setVoxelData] = useState<VoxelDataEvent | null>(null);
  
  // Last completed generation (shown as a row)
  const [lastGeneration, setLastGeneration] = useState<GetGenerationResponse | null>(null);

  const navigate = useNavigate();
  const [isCardHidden, setIsCardHidden] = useState(true);
  const [areOptionsHidden, setAreOptionsHidden] = useState(true);

  // Login modal state
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [pendingGenerateAfterLogin, setPendingGenerateAfterLogin] = useState(false);

  // Check for in-progress generations on page load
  useEffect(() => {
    const checkProcessingGenerations = async () => {
      // Wait for auth to finish loading before checking for processing generations
      if (authLoading) return;
      
      try {
        // Priority 1: Check for recently prompted generation ID
        const recentlyPromptedId = localStorage.getItem('recently_prompted_generation_id');
        
        if (recentlyPromptedId) {
          console.log('Found recently prompted generation, ID:', recentlyPromptedId);
          
          try {
            const statusResponse = await GetGenerationApiService.getGeneration(recentlyPromptedId);
            console.log('Recently prompted generation status:', statusResponse.status);
            
            if (statusResponse.status === 'processing' || statusResponse.status === 'started' || statusResponse.status === 'queued') {
              // Resume polling
              console.log('Resuming polling for recently prompted generation:', recentlyPromptedId);
              setLoading(true);
              setGenerationStatus(statusResponse.status);
              if (statusResponse.external_image_url) {
                setPreviewImageUrl(statusResponse.external_image_url);
              }
              
              try {
                const completedGeneration = await GetGenerationApiService.pollUntilComplete(
                  recentlyPromptedId,
                  (response: GetGenerationResponse) => {
                    setGenerationStatus(response.status);
                    if (response.external_image_url) {
                      setPreviewImageUrl(response.external_image_url);
                    }
                  }
                );
                
                setLoading(false);
                setPreviewImageUrl(null);
                setGenerationStatus(null);
                
                // Refetch to get full response with all fields
                const fullResponse = await GetGenerationApiService.getGeneration(recentlyPromptedId);
                
                // Navigate to generated model page since this completed from loading state
                if (!session) recordAnonymousGeneration(fullResponse.generation_id);
                navigate(`/generated-model?id=${fullResponse.generation_id}`);
              } catch (error) {
                console.error('Generation failed during resume:', error);
                setLoading(false);
                setGenerationError("Generation failed. Please try again");
                setPreviewImageUrl(null);
                setGenerationStatus(null);
                // Only clear if polling explicitly failed, keep for next reload attempt
              }
              
              return; // Exit early, don't check other processing generations
            } else if (statusResponse.status === 'completed') {
              // Show it as last generation (keep localStorage for future visits)
              console.log('Recently prompted generation already completed, displaying in card');
              setLastGeneration(statusResponse);
              return; // Exit early
            } else if (statusResponse.status === 'failed') {
              // Clear the failed generation ID only if explicitly failed
              console.log('Recently prompted generation failed, clearing from storage');
              localStorage.removeItem('recently_prompted_generation_id');
              setGenerationError("Generation failed. Please try again");
              return; // Exit early
            }
            // If status is unknown, don't clear - just continue to check other generations
            console.warn('Unknown status for recently prompted generation:', statusResponse.status);
          } catch (error) {
            // If GET request fails (network error, etc), don't clear the ID - keep it for retry
            console.warn('Failed to check recently prompted generation status, will retry on next load:', error);
          }
        }
        
        // Priority 2: Check for other processing generations
        // Get processing generations for the current user (works for both authenticated and anonymous)
        const { GetUserGenerationsApiService } = await import('../services/getUserGenerationsApi');
        const processingGens = await GetUserGenerationsApiService.getUserGenerations(
          session?.access_token || undefined, // undefined for anonymous users
          1, // Only need the most recent one
          0, // offset
          true // Only get processing generations
        );
        
        if (processingGens.generations.length === 0) {
          console.log('No processing generations found');
          return;
        }
        
        const lastGenerationId = processingGens.generations[0].id;
        console.log('Found in-progress generation, ID:', lastGenerationId);
        
        const statusResponse = await GetGenerationApiService.getGeneration(lastGenerationId);
        console.log('Generation status:', statusResponse.status);
        
        if (statusResponse.status === 'processing' || statusResponse.status === 'started' || statusResponse.status === 'queued') {
          // Resume polling
          console.log('Found in-progress generation, resuming polling:', lastGenerationId);
          setLoading(true);
          setGenerationStatus(statusResponse.status);
          if (statusResponse.external_image_url) {
            setPreviewImageUrl(statusResponse.external_image_url);
          }
          
          try {
            const completedGeneration = await GetGenerationApiService.pollUntilComplete(
              lastGenerationId,
              (response: GetGenerationResponse) => {
                setGenerationStatus(response.status);
                if (response.external_image_url) {
                  setPreviewImageUrl(response.external_image_url);
                }
              }
            );
            
            setLoading(false);
            // Refetch to get full response with all fields
            const fullResponse = await GetGenerationApiService.getGeneration(lastGenerationId);
            
            // Navigate to generated model page
            if (!session) recordAnonymousGeneration(fullResponse.generation_id);
            navigate(`/generated-model?id=${fullResponse.generation_id}`);
          } catch (error) {
            console.error('Generation failed during resume:', error);
            setLoading(false);
            setGenerationError("Generation failed. Please try again");
            setPreviewImageUrl(null);
            setGenerationStatus(null);
          }
          
        } else if (statusResponse.status === 'completed') {
          setLastGeneration(statusResponse);
        } else if (statusResponse.status === 'failed') {
          setGenerationError("Generation failed. Please try again");
        }
      } catch (error) {
        console.warn('Failed to check last generation:', error);
      }
    };
    
    checkProcessingGenerations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading]);

  // Generate preview URL for uploaded image
  useEffect(() => {
    if (imgFile) {
      const url = URL.createObjectURL(imgFile);
      setImagePreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setImagePreviewUrl(null);
    }
  }, [imgFile]);

  // Restore pending form state after returning from a login redirect
  useEffect(() => {
    const raw = sessionStorage.getItem(PENDING_LANDING_STATE_KEY);
    if (!raw) return;
    sessionStorage.removeItem(PENDING_LANDING_STATE_KEY);
    try {
      const payload = JSON.parse(raw) as {
        prompt?: string;
        size?: SizeValue;
        modelQuality?: ModelQuality;
        styleOption?: StyleOption;
        generationType?: GenerationType;
        voxelizer?: VoxelizerOption;
        areOptionsHidden?: boolean;
        image?: { name: string; type: string; base64: string } | null;
      };
      if (typeof payload.prompt === 'string') setPrompt(payload.prompt);
      if (payload.size) setSize(payload.size);
      if (payload.modelQuality) setModelQuality(payload.modelQuality);
      if (payload.styleOption) setStyleOption(payload.styleOption);
      if (payload.generationType) setGenerationType(payload.generationType);
      if (payload.voxelizer) setVoxelizer(payload.voxelizer);
      if (typeof payload.areOptionsHidden === 'boolean') setAreOptionsHidden(payload.areOptionsHidden);
      if (payload.image && payload.image.base64) {
        try {
          const binary = atob(payload.image.base64);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
          }
          const restored = new File([bytes], payload.image.name, { type: payload.image.type });
          setImgFile(restored);
        } catch (decodeErr) {
          console.warn('Failed to restore uploaded image after login:', decodeErr);
        }
      }
    } catch (err) {
      console.warn('Failed to parse pending landing state:', err);
    }
  }, []);

  // Function to save model to localStorage (same as BrickBuilder)
  const saveModelToStorage = (ldrContent?: string, mpdContent?: string, modelName?: string, generationId?: string) => {
    try {
      if (ldrContent) {
        localStorage.setItem(STORAGE_KEYS.LDR_CONTENT, ldrContent);
      }
      if (mpdContent) {
        localStorage.setItem(STORAGE_KEYS.MPD_CONTENT, mpdContent);
      }
      if (modelName) {
        localStorage.setItem(STORAGE_KEYS.MODEL_NAME, modelName);
      }
      if (generationId && generationId.trim()) {
        localStorage.setItem(STORAGE_KEYS.GENERATION_ID, generationId);
      } else {
        localStorage.removeItem(STORAGE_KEYS.GENERATION_ID);
      }
      localStorage.setItem(STORAGE_KEYS.GENERATED_AT, new Date().toISOString());
      console.log('Model saved to localStorage');
    } catch (error) {
      console.error('Error saving model to localStorage:', error);
    }
  };

  const onPickImage = () => fileInputRef.current?.click();
  const onFileChange: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const file = e.target.files?.[0] ?? null;
    setImgFile(file);
  };

  // Drag-and-drop state & handlers
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) {
      setIsDragging(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    dragCounter.current = 0;
    if (loading) return;
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) {
      setImgFile(file);
    }
  };

  // Helper function to convert File to base64
  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        if (typeof reader.result === 'string') {
          // Remove the data URL prefix (e.g., "data:image/png;base64,")
          const base64 = reader.result.split(',')[1];
          resolve(base64);
        } else {
          reject(new Error('Failed to read file as base64'));
        }
      };
      reader.onerror = (error) => reject(error);
    });
  };

  // Persist current form state so it can be restored after a login redirect.
  const savePendingLandingState = async (): Promise<void> => {
    try {
      let imageData: { name: string; type: string; base64: string } | null = null;
      if (imgFile) {
        const base64 = await fileToBase64(imgFile);
        imageData = { name: imgFile.name, type: imgFile.type, base64 };
      }
      const payload = {
        prompt,
        size,
        modelQuality,
        styleOption,
        generationType,
        voxelizer,
        areOptionsHidden,
        image: imageData,
      };
      sessionStorage.setItem(PENDING_LANDING_STATE_KEY, JSON.stringify(payload));
    } catch (err) {
      console.warn('Failed to persist landing state before login redirect:', err);
    }
  };

  const onGenerate = async () => {
    // Prevent multiple simultaneous calls
    if (loading) return;

    // Validate input: either text prompt or image required
    if (!imgFile && !prompt.trim()) {
      setGenerationError("Please enter a text prompt or upload an image");
      return;
    }

    if (REQUIRE_LOGIN_FOR_GENERATION && authLoading) {
      return;
    }

    if (REQUIRE_LOGIN_FOR_GENERATION && !session) {
      setShowLoginModal(true);
      setPendingGenerateAfterLogin(true);
      return;
    }

    // Clear previous results and errors
    setGeneratedMpdContent(null);
    setGenerationError(null);
    setPreviewImageUrl(null);
    setGenerationStatus(null);
    setLastGeneration(null); // Clear previous generation card
    setVoxelData(null);
    
    // Clear old recently prompted generation ID before starting new one
    localStorage.removeItem('recently_prompted_generation_id');
    
    // Start loading
    setLoading(true);
    
    try {
      // Convert size to voxelSize (similar to BrickBuilder component)
      // scale conversion from: https://chatgpt.com/share/690f88ae-7234-8006-bca8-a56e991721fb
      const getVoxelSize = (size: SizeValue): number => {
        switch (size) {
          case 'tiny': return Math.round((40 + 199) / 18.333);
          case 'medium': return Math.round((125 + 199) / 18.333);
          case 'big': return 40;
          default: return Math.round((125 + 199) / 18.333);
        }
      };
      
      let postResponse;
      let modelName: string;
      
      // Get modelOption based on quality selection
      const modelOption = MODEL_QUALITY_PRESETS.find(q => q.value === modelQuality)?.modelOption || 'b';
      
      // Get promptOption based on style selection
      const promptOption = STYLE_PRESETS.find(st => st.value === styleOption)?.promptOption || 'a';
      
      // Get auth token if user is logged in
      const authToken = session?.access_token;
      
      // Shared stream-event handler used by both image and text streaming calls.
      const handleStreamEvent = (event: StreamEvent) => {
        // Update UI based on streaming events
        if ('type' in event && event.type === 'pipeline') {
          const pe = event as PipelineEvent;
          if (pe.stage === 'image_generation') {
            const queueInfo = pe.queue_position != null ? ` (position ${pe.queue_position})` : '';
            setGenerationStatus(pe.message ? `${pe.message}${queueInfo}` : `Generating…${queueInfo}`);
            // Show live diffusion frames as they stream in
            if (pe.image_url) {
              setPreviewImageUrl(pe.image_url);
            }
          } else if (pe.stage === 'background_removal') {
            setGenerationStatus(pe.message || 'Processing input…');
            if (pe.progress === 100 && pe.image_url) {
              setPreviewImageUrl(pe.image_url);
            }
          } else if (pe.stage === 'input_processed') {
            setGenerationStatus(pe.message || 'Server booting up... (3-45 seconds)');
            if (pe.image_url) {
              setPreviewImageUrl(pe.image_url);
            }
          } else if (pe.stage === 'brick_conversion') {
            // Trellis (non-streamed) 3D step. Backend message looks like
            // "Generating 3D model... (queued)". Normalize to a clean status
            // keyword so the badge can show the right timing hint.
            const match = pe.message?.match(/\(([^)]+)\)/);
            const rawStatus = match?.[1]?.toLowerCase();
            if (rawStatus === 'queued') {
              setGenerationStatus('queued');
            } else if (rawStatus === 'processing' || rawStatus === 'started' || rawStatus === 'in_progress') {
              setGenerationStatus('processing');
            } else {
              setGenerationStatus('processing');
            }
          } else if (pe.message) {
            setGenerationStatus(pe.message);
          } else {
            setGenerationStatus(pe.stage);
          }
        } else if ('stage' in event && ((event as Record<string, unknown>).stage === 'geometry' || (event as Record<string, unknown>).stage === 'appearance')) {
          const vd = event as unknown as VoxelDataEvent;
          setVoxelData(vd);
          const label = vd.stage === 'appearance' ? 'Coloring bricks' : 'Generating shape';
          const pct = vd.progress != null ? ` ${Math.round(vd.progress * 100)}%` : '';
          setGenerationStatus(`${label}…${pct}`);
        }
      };

      // Image generation always streams via the SSE endpoint. The 3D Mode
      // toggle only decides how the 3D step runs: SAM3D (streamed live voxels)
      // when streaming, or Trellis (non-streamed) when standard.
      const stream3d = generationType === 'streaming';

      // Use image API if image is uploaded, otherwise use text API
      if (imgFile) {
        console.log(`Generating from image (3D ${stream3d ? 'streaming' : 'standard'}):`, imgFile.name);
        const imageBase64 = await fileToBase64(imgFile);
        postResponse = await ImageToBricksApiService.generateBricksFromImageStream(
          imageBase64,
          getVoxelSize(size),
          authToken,
          modelOption,
          promptOption,
          handleStreamEvent,
          stream3d,
          voxelizer,
        );
        modelName = imgFile.name.replace(/\.[^/.]+$/, ''); // Remove file extension
      } else {
        console.log(`Generating from text prompt (3D ${stream3d ? 'streaming' : 'standard'}):`, prompt.trim());
        postResponse = await TextToBricksApiService.generateBricksFromTextStream(
          prompt.trim(),
          getVoxelSize(size),
          authToken,
          modelOption,
          promptOption,
          handleStreamEvent,
          stream3d,
          voxelizer,
        );
        modelName = prompt.trim();
      }
      
      const generationId = postResponse.generation_id;
      console.log('Generation started, polling for status:', generationId);
      
      // Save generation ID immediately so page reload can resume polling
      localStorage.setItem(STORAGE_KEYS.GENERATION_ID, generationId);
      // Save as recently prompted generation for priority checking on page load
      localStorage.setItem('recently_prompted_generation_id', generationId);
      // If created while logged out, remember it so it can be claimed on login.
      if (!session) recordAnonymousGeneration(generationId);
      
      // Poll for completion with status updates
      const completedGeneration = await GetGenerationApiService.pollUntilComplete(
        generationId,
        (statusResponse: GetGenerationResponse) => {
          // Update status display
          setGenerationStatus(statusResponse.status);
          
          // Show preview image if available during processing
          if (statusResponse.external_image_url) {
            setPreviewImageUrl(statusResponse.external_image_url);
          }
        }
      );
      
      console.log('Generation completed:', completedGeneration.generation_id);
      
      // Get MPD content - either from URL or convert LDR to MPD
      let mpdContent: string | null = null;
      if (completedGeneration.mpd_url) {
        try {
          const mpdResponse = await fetch(completedGeneration.mpd_url);
          if (mpdResponse.ok) {
            mpdContent = await mpdResponse.text();
          }
        } catch (mpdError) {
          console.warn('Failed to fetch MPD from URL:', mpdError);
        }
      }
      
      // Fallback: convert LDR to MPD if MPD URL wasn't available or failed
      if (!mpdContent && completedGeneration.ldr_content) {
        try {
          const mpdData = await LdrToMpdApiService.convertLdrToMpd(
            completedGeneration.ldr_content,
            modelName,
            authToken
          );
          mpdContent = mpdData.mpd_content;
        } catch (mpdError) {
          console.warn('Failed to convert LDR to MPD:', mpdError);
        }
      }
      
      setGeneratedMpdContent(mpdContent);
      setLoading(false);
      setPreviewImageUrl(null);
      setGenerationStatus(null);
      
      // Save to localStorage for persistence across browser refreshes
      saveModelToStorage(
        completedGeneration.ldr_content,
        mpdContent || undefined,
        modelName,
        completedGeneration.generation_id
      );
      
      // Navigate to generated model page since this completed from loading state
      if (!session) recordAnonymousGeneration(completedGeneration.generation_id);
      navigate(`/generated-model?id=${completedGeneration.generation_id}`);
      
    } catch (error) {
      console.error('Generation failed:', error);
      // Check if error is a network error - if user is online but fetch failed, backend is likely not running
      const isNetworkError = error instanceof TypeError && error.message === 'Failed to fetch';
      const errorMsg = error instanceof Error ? error.message : '';
      
      let errorMessage = 'Generation failed. Please try again';
      if (isNetworkError) {
        errorMessage = navigator.onLine 
          ? 'Backend services not running. Check terminal for errors.' 
          : 'No internet connection';
      } else if (errorMsg.includes('FAL_KEY')) {
        // Backend is running but FAL_KEY is not configured
        errorMessage = 'FAL_KEY not configured. Set FAL_KEY in .env file and restart the backend server.';
      } else if (errorMsg) {
        // Use the error message from the backend
        errorMessage = errorMsg;
      }
      setGenerationError(errorMessage);
      setLoading(false);
      setPreviewImageUrl(null);
      setGenerationStatus(null);
      // Clear the recently prompted ID on failure
      localStorage.removeItem('recently_prompted_generation_id');
    }
  };

  // After a successful login from the modal, automatically continue generation
  useEffect(() => {
    if (pendingGenerateAfterLogin && session && !authLoading && !loading) {
      setPendingGenerateAfterLogin(false);
      onGenerate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingGenerateAfterLogin, session, authLoading]);

  return (
    <div
      className="min-h-screen text-slate-900 relative"
      style={{ backgroundColor: "#fbfbfd" }}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Drag-and-drop overlay */}
      {isDragging && (
        <div
          className="fixed inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          style={{ zIndex: 9999, pointerEvents: 'none' }}
        >
          <div className="rounded-2xl border-4 border-dashed border-white bg-white/20 px-12 py-10 text-center">
            <ImageIcon className="mx-auto mb-3 h-12 w-12 text-white" />
            <p className="text-xl font-semibold text-white">Drop image to upload</p>
          </div>
        </div>
      )}
      <SEO
        title="BrickBuilder - Turn Images into 3D LEGO-Compatible Brick Models"
        description="Build brick models from text prompts or images. Experimental demo — results may vary."
        url="https://brickbuilder.ai/landing"
      />

      <FallingBricks density={22} opacity={0.25} zIndex={0} />

      <LoginModal
        open={showLoginModal}
        onClose={() => {
          setShowLoginModal(false);
          setPendingGenerateAfterLogin(false);
        }}
        onSuccess={() => setShowLoginModal(false)}
        redirectTo="/"
        onBeforeOAuthRedirect={savePendingLandingState}
      />

      <div className="mx-auto flex min-h-screen w-full max-w-screen-xl flex-col px-4 sm:px-6 md:px-8 lg:px-10 pb-16 pt-6 relative" style={{ zIndex: 10 }}>
        <LandingHeader onLoginClick={() => setShowLoginModal(true)} />

        <main className="flex flex-1 flex-col items-center text-center w-full">
          <div className="mt-4 flex w-full max-w-3xl flex-col items-center gap-6 sm:mt-8">
            <h1 className="text-4xl font-extrabold leading-tight sm:text-5xl text-slate-900 landing-fade-in landing-delay-2">
              Imagine. Customize. Build.
            </h1>

            <p className="text-lg text-slate-600 landing-fade-in landing-delay-2">Turn images or text into buildable 3D brick models in seconds</p>

            <div className="w-full relative z-20 landing-fade-in landing-delay-3">
              <div className="w-full" style={{ position: 'relative' }}>
                <input
                  value={prompt}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPrompt(e.target.value)}
                  placeholder={imgFile ? "Image uploaded - text prompt disabled" : (showTypewriter ? typedPlaceholder : "")}
                  className="input w-full h-12 rounded-full pr-40 pl-4 text-base shadow-sm border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  disabled={loading || !!imgFile}
                />
                <button
                  type="button"
                  onClick={onPickImage}
                  className="flex items-center gap-1.5 rounded-full border border-gray-200 bg-white hover:bg-slate-100 px-3 py-1.5 text-sm text-slate-600 transition-colors"
                  style={{
                    position: 'absolute',
                    right: '6px',
                    left: 'auto',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    zIndex: 2,
                  }}
                  aria-label="Upload image"
                  title="Upload image"
                  disabled={loading}
                >
                  <ImageIcon className="h-4 w-4" />
                  Upload Image
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={onFileChange}
                  disabled={loading}
                />
              </div>

              {!loading && (
              <div className="flex items-center justify-center gap-2 mt-3 landing-fade-in landing-delay-3">
                <button
                  type="button"
                  onClick={onGenerate}
                  className="inline-flex items-center justify-center h-12 rounded-full px-6 min-w-36 text-white transition-colors bg-[#f44336] cursor-pointer hover:bg-[#ff6b6b]"
                >
                  <Sparkles className="mr-2 h-5 w-5" />
                  Generate
                </button>
                <button
                  type="button"
                  onClick={() => setAreOptionsHidden(prev => !prev)}
                  className="inline-flex items-center justify-center h-10 w-10 rounded-full text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
                  aria-label="Toggle settings"
                >
                  <Settings className="h-5 w-5" />
                </button>
              </div>
              )}
            </div>

            {/* Image thumbnail preview */}
            {imagePreviewUrl && (
              <div className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 shadow-sm">
                <img
                  src={imagePreviewUrl}
                  alt="Uploaded preview"
                  className="w-20 h-20 object-cover rounded-md"
                />
                <div className="flex-1 text-left">
                  <p className="text-sm font-medium text-slate-700">{imgFile?.name}</p>
                  <p className="text-xs text-slate-500 mt-1">
                    {imgFile && (imgFile.size / 1024).toFixed(1)} KB
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setImgFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = '';
                  }}
                  className="text-slate-400 hover:text-red-500 transition-colors"
                  aria-label="Remove image"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            )}

            {/* Size chips - hidden during loading */}
            {/* {!loading && !areOptionsHidden && (
              <div className="flex items-center gap-3 relative" style={{ zIndex: 25 }}>
                <span className="text-sm text-slate-500">Size:</span>
                {SIZE_PRESETS.map((s) => {
                  const active = s.value === size;
                  return (
                    <button
                      key={s.value}
                      onClick={() => !loading && setSize(s.value)}
                      className={`rounded-full px-4 py-1 text-sm transition-all duration-150 ${
                        active
                          ? "bg-[#f44336] text-white border border-transparent"
                          : "bg-white text-slate-700 border border-slate-300 hover:opacity-70"
                      } ${loading ? "cursor-not-allowed" : "cursor-pointer"}`}
                      disabled={loading}
                    >
                      {s.label}
                    </button>
                  );
                })}
                <button
                  onClick={() => setAreOptionsHidden(true)}
                  className="ml-2 p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
                  aria-label="Hide options"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )} */}

            {/* Style chips - hidden during loading */}
            {!loading && !areOptionsHidden && (
              <div className="flex items-center gap-3 relative" style={{ zIndex: 25 }}>
                <span className="text-sm text-slate-500">Style:</span>
                {STYLE_PRESETS.map((st) => {
                  const active = st.value === styleOption;
                  return (
                    <button
                      key={st.value}
                      onClick={() => !loading && setStyleOption(st.value)}
                      className={`rounded-full px-4 py-1 text-sm transition-all duration-150 ${
                        active
                          ? "bg-[#f44336] text-white border border-transparent"
                          : "bg-white text-slate-700 border border-slate-300 hover:opacity-70"
                      } ${loading ? "cursor-not-allowed" : "cursor-pointer"}`}
                      disabled={loading}
                    >
                      {st.label}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Generation Mode chips - hidden during loading */}
            {!loading && !areOptionsHidden && (
              <div className="flex items-center gap-3 relative" style={{ zIndex: 25 }}>
                <span className="text-sm text-slate-500">3D Mode:</span>
                {GENERATION_TYPE_PRESETS.map((gt) => {
                  const active = gt.value === generationType;
                  return (
                    <button
                      key={gt.value}
                      onClick={() => !loading && setGenerationType(gt.value)}
                      className={`rounded-full px-4 py-1 text-sm transition-all duration-150 ${
                        active
                          ? "bg-[#f44336] text-white border border-transparent"
                          : "bg-white text-slate-700 border border-slate-300 hover:opacity-70"
                      } ${loading ? "cursor-not-allowed" : "cursor-pointer"}`}
                      disabled={loading}
                      title={gt.description}
                    >
                      {gt.label}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Voxelizer chips - only relevant for the Standard (Trellis) 3D mode */}
            {!loading && !areOptionsHidden && generationType === "non-streaming" && (
              <div className="flex items-center gap-3 relative" style={{ zIndex: 25 }}>
                <span className="text-sm text-slate-500">Voxelizer:</span>
                {VOXELIZER_PRESETS.map((vx) => {
                  const active = vx.value === voxelizer;
                  return (
                    <button
                      key={vx.value}
                      onClick={() => !loading && setVoxelizer(vx.value)}
                      className={`rounded-full px-4 py-1 text-sm transition-all duration-150 ${
                        active
                          ? "bg-[#f44336] text-white border border-transparent"
                          : "bg-white text-slate-700 border border-slate-300 hover:opacity-70"
                      } ${loading ? "cursor-not-allowed" : "cursor-pointer"}`}
                      disabled={loading}
                      title={vx.description}
                    >
                      {vx.label}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Upload GLB - convert your own model through glb2brick */}
            {!loading && !areOptionsHidden && (
              <div className="w-full max-w-xl" style={{ zIndex: 25 }}>
                <GlbUploadCard />
              </div>
            )}

            {!loading && (
              <>
                {/* <p className="mt-2 text-sm text-slate-500 landing-fade-in landing-delay-3">
                  This app uses generative AI to create brick models. Results may vary.
                </p> */}

                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 shadow-sm transition-all hover:-translate-y-px hover:border-[#f44336]/30 hover:bg-red-50 hover:text-[#f44336] landing-fade-in landing-delay-3"
                  onClick={() => navigate("/community")}
                >
                  <Users className="h-4 w-4" />
                  View Community Models
                </button>
                
                {/* Last completed generation */}
                {lastGeneration && !isCardHidden && (
                  <div className="mt-4 w-full max-w-xl rounded-xl border border-slate-200 bg-white shadow-sm relative">
                    <button
                      onClick={() => setIsCardHidden(true)}
                      className="absolute top-3 right-3 p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
                      aria-label="Hide card"
                    >
                      <X className="w-4 h-4" />
                    </button>
                    <div className="p-4 flex gap-4">
                      <div className="w-20 h-20 rounded-lg overflow-hidden bg-slate-100 border flex items-center justify-center">
                        {lastGeneration.external_image_url ? (
                          <img src={lastGeneration.external_image_url} alt={lastGeneration.generation_id} className="w-full h-full object-cover" />
                        ) : (
                          <Sparkles className="w-6 h-6 text-slate-300" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-sm text-slate-900 truncate">id: {lastGeneration.generation_id}</h3>
                        <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3"/> Recently created
                          </span>
                        </div>
                        <button 
                          onClick={() => navigate(`/generated-model?id=${lastGeneration.generation_id}`)}
                          className="mt-2 inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs hover:bg-slate-50 cursor-pointer"
                        >
                          <Eye className="w-3.5 h-3.5"/> View Model
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Featured horizontal marquee OR in‑place progress UI */}
          <section className="mt-4 w-full relative landing-fade-in landing-delay-4" style={{ zIndex: 15 }}>
            {loading && (
              <div className="flex w-full flex-col items-center gap-4 mb-4">
                {/* Preview container with overlaid status + beat text */}
                <div className="relative w-full max-w-md overflow-hidden rounded-xl shadow-lg border border-slate-200" style={{ height: 340 }}>
                  {/* Content layer */}
                  {voxelData ? (
                    <div style={{ height: 340 }}>
                      <StreamingMeshViewer voxelData={voxelData} />
                    </div>
                  ) : previewImageUrl ? (
                    <>
                      {/* <svg width="0" height="0" style={{ position: 'absolute' }}>
                        <filter id="wavy-edge">
                          <feTurbulence type="turbulence" baseFrequency="0.02" numOctaves="3" result="noise" seed="1">
                            <animate attributeName="seed" dur="0.5s" values="1;2;3;4;5" repeatCount="indefinite" />
                          </feTurbulence>
                          <feDisplacementMap in="SourceGraphic" in2="noise" scale="8" xChannelSelector="R" yChannelSelector="G" />
                        </filter>
                      </svg> */}
                      <img
                        src={previewImageUrl}
                        alt="Generation preview"
                        className="w-full h-full object-contain"
                        // style={{ filter: 'blur(4px) grayscale(100%) url(#wavy-edge)', transform: 'scale(1.05)' }}
                      />
                    </>
                  ) : (
                    <div className="w-full flex items-center justify-center bg-slate-50" style={{ height: 340 }}>
                      <div className="text-slate-300 text-sm">Preparing preview…</div>
                    </div>
                  )}

                  {/* Status badge — overlayed on top center */}
                  <div className="absolute top-3 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1" style={{ zIndex: 10 }}>
                    <div className="text-xs text-slate-600 font-mono bg-white/80 backdrop-blur-sm px-3 py-1 rounded-full shadow-sm whitespace-nowrap">
                      Status: {generationStatus === 'queued'
                        ? 'Queued'
                        : (generationStatus === 'processing' || generationStatus === 'started')
                          ? 'Generating 3D model'
                          : (generationStatus || 'Starting')}
                    </div>
                    {generationStatus === 'queued' && (
                      <div className="text-xs text-slate-500 bg-white/80 backdrop-blur-sm px-3 py-1 rounded-full shadow-sm whitespace-nowrap">
                        This will take about 1-2 minutes
                      </div>
                    )}
                    {(generationStatus === 'processing' || generationStatus === 'started') && (
                      <div className="text-xs text-slate-500 bg-white/80 backdrop-blur-sm px-3 py-1 rounded-full shadow-sm whitespace-nowrap">
                        This will take about 30-60 seconds
                      </div>
                    )}
                  </div>

                  {/* Rotating beat text — overlayed on bottom center */}
                  <div className="absolute bottom-3 left-1/2 -translate-x-1/2 max-w-[90%]" style={{ zIndex: 10 }}>
                    <div
                      className="text-xs sm:text-sm text-center bg-white/80 backdrop-blur-sm px-3 py-1.5 rounded-full shadow-sm whitespace-nowrap"
                      style={{ color: `rgba(30, 41, 59, ${beatFade})`, transition: 'color 250ms ease' }}
                    >
                      {beatText}
                    </div>
                  </div>
                </div>
              </div>
            )}
            {generationError && (
              <div className="flex flex-col items-center gap-4 mb-4">
                <div className="text-red-600 text-center">
                  <h3 className="text-lg font-semibold mb-2">Generation Failed</h3>
                  <p>{generationError}</p>
                </div>
                <button
                  onClick={() => {
                    setGenerationError(null);
                  }}
                  className="px-4 py-2 border border-slate-300 text-slate-700 rounded-full hover:bg-slate-50 transition-colors"
                >
                  Try Again
                </button>
              </div>
            )}
            <div className="w-screen relative left-1/2 -translate-x-1/2">
              <FeaturedStrip items={FEATURED} />
            </div>
          </section>

          <HowItWorks />
        </main>

        <SiteFooter />
      </div>
    </div>
  );
}

function HowItWorks() {
  const steps = [
    {
      icon: MessageSquare,
      title: "Describe or upload",
      description: "Type a prompt like \"a pink elephant\" or drop in any image you want to build.",
    },
    {
      icon: Wand2,
      title: "AI builds your model",
      description: "Our generative pipeline turns your idea into a buildable 3D brick model in seconds.",
    },
    {
      icon: Package,
      title: "Preview, edit, and order",
      description: "Make your edits, grab the instructions, and we'll ship the parts to your door in 8 days.",
    },
  ];

  return (
    <section
      id="how-it-works"
      className="w-full mt-24 mb-16 relative"
      style={{ zIndex: 15 }}
    >
      <div className="mx-auto max-w-5xl px-2">
        <div className="text-center landing-fade-in landing-delay-1">
          {/* <span className="inline-block rounded-full bg-slate-100 px-3 py-1 text-xs font-medium tracking-wide text-slate-600 uppercase">
            How it works
          </span> */}
          <h2 className="mt-4 text-3xl font-bold text-slate-900 sm:text-4xl">
            How It Works
          </h2>
          <p className="mt-3 text-base text-slate-600 max-w-2xl mx-auto">
            Turn images and text into custom 3D brick models. Edit freely, get instant instructions, and have the parts on your doorstep in 8 days.
          </p>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3 md:gap-8 relative">
          {/* Connecting line behind cards on md+ */}
          <div
            aria-hidden
            className="hidden md:block absolute left-0 right-0 top-12 h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent"
          />

          {steps.map((step, i) => {
            const Icon = step.icon;
            return (
              <div
                key={step.title}
                className={`relative flex flex-col items-center text-center rounded-2xl border border-slate-200 bg-white/80 backdrop-blur-sm p-6 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 landing-fade-in landing-delay-${i + 2}`}
              >
                <div className="relative">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-[#f44336] to-[#ff6b6b] text-white shadow-md">
                    <Icon className="h-7 w-7" />
                  </div>
                  <span className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-white border border-slate-200 text-xs font-bold text-slate-700 shadow-sm">
                    {i + 1}
                  </span>
                </div>
                <h3 className="mt-5 text-lg font-semibold text-slate-900">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">
                  {step.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function LandingHeader({ onLoginClick }: { onLoginClick: () => void }) {
  const navigate = useNavigate();
  const { user, isSupabaseConfigured } = useAuth();
  const [githubStars, setGithubStars] = useState<number | null>(null);

  // Show profile menu if user is logged in OR if Supabase is not configured
  const showProfileMenu = user || !isSupabaseConfigured;

  useEffect(() => {
    let cancelled = false;

    fetch("https://api.github.com/repos/jjohnson5253/brickbuilderai", {
      headers: { Accept: "application/vnd.github+json" },
    })
      .then((response) => {
        if (!response.ok) throw new Error("Failed to load GitHub stars");
        return response.json();
      })
      .then((repo: { stargazers_count?: number }) => {
        if (!cancelled && typeof repo.stargazers_count === "number") {
          setGithubStars(repo.stargazers_count);
        }
      })
      .catch(() => {
        if (!cancelled) setGithubStars(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const formattedGithubStars = githubStars === null
    ? "..."
    : new Intl.NumberFormat("en", {
        notation: "compact",
        maximumFractionDigits: 1,
      }).format(githubStars);

  const githubStarLink = (
    <a
      href="https://github.com/jjohnson5253/brickbuilderai"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="View BrickBuilder on GitHub"
      className="inline-flex h-8 min-w-[4.5rem] items-center justify-center gap-1.5 rounded-full bg-slate-100 px-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-200 sm:h-9 sm:min-w-[5.25rem] sm:gap-2 sm:px-3 sm:text-sm"
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-950 text-white sm:h-6 sm:w-6">
        <Github className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
      </span>
      <span>{formattedGithubStars}</span>
    </a>
  );

  return (
    <header className="flex w-full flex-wrap items-center justify-between gap-y-2 relative landing-fade-in landing-delay-1" style={{ zIndex: 50 }}>
      <a href="/" className="flex min-w-0 items-center gap-2 sm:gap-3">
        <img
          src="/logo.svg"
          alt="BrickBuilder"
          className="h-6 w-auto sm:h-7"
          onError={(e) => {
            const el = e.currentTarget as HTMLImageElement;
            el.style.display = "none";
          }}
        />
        <span className="truncate text-lg font-extrabold tracking-tight sm:text-xl">
          <span className="text-[#ff4b4b]">BRICK</span>
          <span className="text-slate-900">BUILDER</span>
        </span>
      </a>

      <nav className="absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 sm:flex">
        <button
          className="inline-flex items-center gap-1.5 bg-transparent text-slate-700 border-none text-sm px-3 h-9 cursor-pointer transition-all duration-200 hover:text-[#f44336] hover:-translate-y-px"
          onClick={() => navigate("/community")}
        >
          <Users className="h-4 w-4" />
          Community
        </button>
      </nav>

      {/* Login / Sign Up OR Account Menu */}
      <div className="flex items-center gap-2 sm:gap-3">
        {showProfileMenu ? (
          // Logged in or no Supabase: show GitHub stars and account dropdown
          <>
            {githubStarLink}

            {/* Dashboard button */}
            <button
              className="inline-flex items-center gap-1.5 bg-transparent text-slate-700 border-none text-sm px-2 h-8 cursor-pointer transition-all duration-200 hover:text-[#f44336] hover:-translate-y-px sm:px-3 sm:h-9"
              onClick={() => navigate('/dashboard')}
            >
              <LayoutDashboard className="h-4 w-4" />
              Dashboard
            </button>

            {/* Account dropdown */}
            <ProfileMenu />
          </>
        ) : (
          // Not logged in: show login button
          <>
            {githubStarLink}
            <button
              className="h-8 rounded-full border-none bg-[#f44336] px-3 text-xs font-medium text-white cursor-pointer transition-all duration-200 hover:-translate-y-px hover:bg-[#ff6b6b] sm:h-9 sm:px-4 sm:text-sm"
              onClick={onLoginClick}
            >
              Login
            </button>
          </>
        )}
      </div>

    </header>
  );
}

/** TranslateX marquee (no user scroll). Cards remain 1:1 squares. */
const FeaturedStrip = memo(function FeaturedStrip({ items }: { items: FeaturedItem[] }) {
  const navigate = useNavigate();
  const trackRef = useRef<HTMLDivElement>(null);
  const runRef = useRef<HTMLDivElement>(null);
  const xRef = useRef(0);
  const lastRef = useRef(0);
  const rafRef = useRef<number>(0);
  const [runWidth, setRunWidth] = useState(0);
  
  const isDraggingRef = useRef(false);
  const dragStartXRef = useRef(0);
  const dragStartPosRef = useRef(0);
  const hasDraggedRef = useRef(false);

  useLayoutEffect(() => {
    const measure = () => {
      if (!runRef.current) return;
      setRunWidth(runRef.current.offsetWidth);
      xRef.current = 0;
      if (trackRef.current) trackRef.current.style.transform = `translate3d(0,0,0)`;
    };
    const onResize = () => requestAnimationFrame(measure);
    measure();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    const track = trackRef.current;
    if (!track || !runWidth) return;

    const speed = 37; // px/sec

    const step = (ts: number) => {
      if (isDraggingRef.current) {
        rafRef.current = requestAnimationFrame(step);
        return;
      }

      if (!lastRef.current) lastRef.current = ts;
      const dt = (ts - lastRef.current) / 1000;
      lastRef.current = ts;

      xRef.current -= speed * dt;
      if (-xRef.current >= runWidth) xRef.current += runWidth;

      track.style.transform = `translate3d(${Math.round(xRef.current)}px,0,0)`; // snap to int px
      rafRef.current = requestAnimationFrame(step);
    };

    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [runWidth]);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;

    const handlePointerDown = (e: PointerEvent) => {
      isDraggingRef.current = true;
      hasDraggedRef.current = false;
      dragStartXRef.current = e.clientX;
      dragStartPosRef.current = xRef.current;
      track.style.cursor = 'grabbing';
    };

    const handlePointerMove = (e: PointerEvent) => {
      if (!isDraggingRef.current) return;
      const delta = e.clientX - dragStartXRef.current;
      
      // Mark as dragged if moved more than 5 pixels
      if (Math.abs(delta) > 5) {
        hasDraggedRef.current = true;
      }
      
      xRef.current = dragStartPosRef.current + delta;
      
      // Normalize position to stay within bounds
      while (-xRef.current >= runWidth) xRef.current += runWidth;
      while (xRef.current > 0) xRef.current -= runWidth;
      
      track.style.transform = `translate3d(${Math.round(xRef.current)}px,0,0)`;
    };

    const handlePointerUp = () => {
      if (isDraggingRef.current) {
        isDraggingRef.current = false;
        lastRef.current = 0; // Reset for smooth resumption
        track.style.cursor = 'grab';
        
        // Reset hasDragged after a brief delay to allow click prevention
        setTimeout(() => {
          hasDraggedRef.current = false;
        }, 100);
      }
    };

    const handleClick = (e: MouseEvent) => {
      if (hasDraggedRef.current) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    track.addEventListener('pointerdown', handlePointerDown);
    track.addEventListener('click', handleClick, true);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    window.addEventListener('pointercancel', handlePointerUp);

    return () => {
      track.removeEventListener('pointerdown', handlePointerDown);
      track.removeEventListener('click', handleClick, true);
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      window.removeEventListener('pointercancel', handlePointerUp);
    };
  }, [runWidth]);

  const Row = () => (
    <div ref={runRef} className="flex w-max gap-6 py-1" style={{ willChange: "transform" }}>
      {items.map((m, i) => (
        <article
          key={`card-${i}`}
          className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm"
          style={{
            width: "clamp(10rem, 18vw, 17rem)",
            flex: "0 0 clamp(10rem, 18vw, 17rem)",
            backfaceVisibility: "hidden",
            transform: "translateZ(0)",
          }}
        >
          <div
            className="relative w-full overflow-hidden rounded-xl bg-slate-50"
            style={{ paddingTop: "100%" }}
          >
            <img
              src={m.metadata.img_url}
              alt={m.title}
              className="absolute left-0 top-0 h-full w-full object-contain"
              style={{ transform: "translateZ(0)" }}
              draggable="false"
              onDragStart={(e) => e.preventDefault()}
            />
          </div>
          <div className="mt-3 text-center">
            <h3 className="text-sm font-semibold text-slate-800 mb-1">{m.title}</h3>
            <p className="text-xs text-slate-600">{m.metadata.pieces} pieces</p>
            <p className="text-xs text-slate-600">${m.metadata.cost} USD</p>
            <button
              onClick={() => navigate(`/generated-model?id=${m.metadata.id}`)}
              className="mt-2 inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 h-9 text-xs hover:bg-slate-50 cursor-pointer"
            >
              <Eye className="w-4 h-4"/> View Model
            </button>
          </div>
        </article>
      ))}
    </div>
  );

  return (
    <div className="relative w-full overflow-hidden select-none">
      <div
        ref={trackRef}
        className="flex w-max gap-6"
        style={{ transform: "translate3d(0,0,0)", willChange: "transform", backfaceVisibility: "hidden", cursor: "grab", touchAction: "none" }}
      >
        <Row />
        <Row />
      </div>
    </div>
  );
});


