import React, { useState } from "react";
import { SEO } from "../components/SEO";
import { SiteFooter } from "../components/SiteFooter";
import { useNavigate, useLocation, useSearchParams } from "react-router-dom";
import { ThreeLDRViewer } from "../components/ThreeLDRViewer";
import type { ExportCaptureApi } from "../components/ThreeLDRViewer";
import { VoxelViewer } from "../components/VoxelViewer";
import modelsMetadata from "../assets/demo-images/models-metadata.json";

const DEMO_MODEL_IDS = new Set(
  Object.values(modelsMetadata).map((m) => m.id)
);

// Mirrors the backend /updateUsername validation: 3-30 chars,
// letters, numbers, underscores, hyphens, or periods.
const USERNAME_PATTERN = /^[A-Za-z0-9_.-]{3,30}$/;
import { GetPriceApiService, GetPriceResponse } from "../services/getPriceApi";
import { ResizeScaler } from "../components/ResizeScaler";
import { ResizeModelApiService } from "../services/resizeModelApi";
import { PromptEditModelApiService } from "../services/promptEditModelApi";
import { GetGenerationApiService, GetGenerationResponse } from "../services/getGenerationApi";
import { LdrToMpdApiService } from "../services/ldrToMpdApi";
import { ToggleIsCommunityApiService } from "../services/toggleIsCommunityApi";
import { UpdateGenerationNameApiService } from "../services/updateGenerationNameApi";
import { UpdateImagePreviewApiService } from "../services/updateImagePreviewApi";
import { supabase } from "../lib/supabase";
import { useAuth } from "../contexts/AuthContext";
import {
  HandCoins,
  Package,
  Hammer,
  Mail,
  Boxes,
  Star,
  Loader2,
  Pencil,
  User,
  Users,
  ChevronDown,
  Github,
  LogOut,
  ArrowLeft,
  Download,
  Image,
  FileText,
  Video,
} from "lucide-react";

function Header() {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [githubStars, setGithubStars] = useState<number | null>(null);

  React.useEffect(() => {
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
      aria-label="View BrickBuilder.AI on GitHub"
      className="inline-flex h-8 min-w-[4.5rem] items-center justify-center gap-1.5 rounded-full bg-slate-100 px-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-200 sm:h-9 sm:min-w-[5.25rem] sm:gap-2 sm:px-3 sm:text-sm"
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-950 text-white sm:h-6 sm:w-6">
        <Github className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
      </span>
      <span>{formattedGithubStars}</span>
    </a>
  );

  return (
    <header className="flex items-center justify-between w-full relative landing-fade-in landing-delay-1" style={{ zIndex: 50 }}>
      <a href="/" className="flex items-center gap-3">
        <img
          src="/logo.svg"
          alt="BRICKBUILDER.AI"
          className="h-7 w-auto"
          onError={(e) => ((e.currentTarget as HTMLImageElement).style.display = "none")}
        />
        <span className="text-xl font-extrabold tracking-tight">
          <span className="text-[#ff4b4b]">BRICK</span>
          <span className="text-slate-900">BUILDER</span>
          <span className="text-slate-900">.</span>
          <span className="text-[#ff4b4b]">AI</span>
        </span>
      </a>

      {/* Login / Sign Up OR Account Menu */}
      <div className="flex items-center gap-3">
        <button
          className="inline-flex items-center gap-1.5 bg-transparent text-slate-700 border-none text-sm px-3 h-9 cursor-pointer transition-all duration-200 hover:text-[#f44336] hover:-translate-y-px"
          onClick={() => navigate("/community")}
        >
          <Users className="h-4 w-4" />
          Community
        </button>
        {githubStarLink}
        {user ? (
          // Logged in: show account dropdown
          <>
            {/* Account dropdown */}
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 rounded-full px-3 h-9 border-none cursor-pointer transition-colors"
              >
                <div className="w-6 h-6 bg-[#f44336] rounded-full flex items-center justify-center">
                  <User className="h-4 w-4 text-white" />
                </div>
                <ChevronDown className={`h-4 w-4 text-slate-600 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              {dropdownOpen && (
                <>
                  {/* Backdrop to close dropdown */}
                  <div 
                    className="fixed inset-0" 
                    style={{ zIndex: 40 }}
                    onClick={() => setDropdownOpen(false)} 
                  />
                  {/* Dropdown menu */}
                  <div 
                    className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-2"
                    style={{ zIndex: 51 }}
                  >
                    <button
                      onClick={() => {
                        setDropdownOpen(false);
                        navigate('/dashboard');
                      }}
                      className="w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2 cursor-pointer bg-transparent border-none"
                    >
                      Dashboard
                    </button>
                    <div className="border-t border-slate-100 my-1" />
                    <button
                      onClick={async () => {
                        setDropdownOpen(false);
                        await signOut();
                        navigate('/');
                      }}
                      className="w-full px-4 py-2.5 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 cursor-pointer bg-transparent border-none"
                    >
                      <LogOut className="h-4 w-4" />
                      Log out
                    </button>
                  </div>
                </>
              )}
            </div>
          </>
        ) : (
          // Not logged in: show login/signup buttons
          <>
            <button
              className="bg-transparent text-slate-600 border-none text-sm px-3 h-9 cursor-pointer transition-all duration-200 hover:text-black hover:-translate-y-px"
              onClick={() => navigate("/login")}
            >
              Login
            </button>

            <button
              className="bg-[#f44336] text-white rounded-full px-4 h-9 border-none text-sm font-medium cursor-pointer transition-all duration-200 hover:bg-[#ff6b6b] hover:-translate-y-px"
              onClick={() => navigate("/signup")}
            >
              Sign Up
            </button>
          </>
        )}
      </div>
      
    </header>
  );
}

type StatCardProps = {
  icon: React.ReactNode;
  title: string;
  sub: string;
};

function StatCard({ icon, title, sub }: StatCardProps) {
  return (
    <div
        className="relative rounded-xl bg-white p-4 shadow-sm flex items-center gap-4 border border-slate-200"
        >
            {/* Red circle behind black icon */}
      <div
        className="h-12 w-12 rounded-full flex items-center justify-center shrink-0"
        style={{ backgroundColor: "#f44336" }}
      >
        <div className="text-black">{icon}</div>
      </div>

      <div className="flex-1">
        <div className="text-sm font-semibold text-slate-800">{title}</div>
        <div className="text-xs text-slate-500">{sub}</div>
      </div>
    </div>
  );
}


export default function GeneratedModel() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const params = new URLSearchParams(location.search);
  const { user: currentUser, userProfile: currentUserProfile, updateUsername } = useAuth();
  
  // Generation fetch state
  const [generationLoading, setGenerationLoading] = React.useState(false);
  const [generationError, setGenerationError] = React.useState<string | null>(null);
  const [currentGenerationId, setCurrentGenerationId] = React.useState<string | null>(null);
  const [screenshots, setScreenshots] = React.useState<{ angle1: string; angle2: string } | null>(null);
  const [priceData, setPriceData] = React.useState<GetPriceResponse | null>(null);
  const [priceLoading, setPriceLoading] = React.useState(false);
  const [priceError, setPriceError] = React.useState<string | null>(null);
  const [priceRefreshCounter, setPriceRefreshCounter] = React.useState(0);
  const [isResizing, setIsResizing] = React.useState(false);
  const [showResizeScaler, setShowResizeScaler] = React.useState(false);
  const [showPriceResize, setShowPriceResize] = React.useState(false);
  const [isPromptEditing, setIsPromptEditing] = React.useState(false);
  const [editPrompt, setEditPrompt] = React.useState("");
  const [editModelQuality, setEditModelQuality] = React.useState<"regular" | "premium">("premium");
  const [editPreviewImageUrl, setEditPreviewImageUrl] = React.useState<string | null>(null);
  const [editPromptError, setEditPromptError] = React.useState<string | null>(null);
  
  // Voxel editor state
  const [showVoxelEditor, setShowVoxelEditor] = React.useState(false);
  const [voxelHasChanges, setVoxelHasChanges] = React.useState(false);
  const [showUnsavedChangesModal, setShowUnsavedChangesModal] = React.useState(false);
  // Action to perform after the user resolves the unsaved-changes modal
  // (Save or Discard). Defaults to simply exiting the editor.
  const pendingExitActionRef = React.useRef<(() => void) | null>(null);
  const voxelSaveRef = React.useRef<(() => Promise<void>) | null>(null);
  const [xyzrgbContent, setXyzrgbContent] = React.useState<string | null>(null);
  const [xyzrgbUrl, setXyzrgbUrl] = React.useState<string | null>(null);
  const [problematicXyzrgbContent, setProblematicXyzrgbContent] = React.useState<string | null>(null);
  const [problematicXyzrgbUrl, setProblematicXyzrgbUrl] = React.useState<string | null>(null);
  const [xyzrgbLoading, setXyzrgbLoading] = React.useState(false);
  const [xyzrgbError, setXyzrgbError] = React.useState<string | null>(null);
  const [accessToken, setAccessToken] = React.useState<string | null>(null);
  const [processedImageUrl, setProcessedImageUrl] = React.useState<string | null>(null);
  const [detailLevel, setDetailLevel] = React.useState<number | null>(null);
  const [currentScaler, setCurrentScaler] = React.useState<number | undefined>(undefined);
  
  // State for reactive model content
  const [mpdContent, setMpdContent] = React.useState<string | null>(null);
  const [ldrContent, setLdrContent] = React.useState<string | null>(null);
  const [modelName, setModelName] = React.useState<string>("Your Model");
  
  // Save polling state (after VoxelViewer save, poll until LDR processing completes)
  const [isSavePolling, setIsSavePolling] = React.useState(false);
  const [savePollingError, setSavePollingError] = React.useState<string | null>(null);
  const savePollingAbortRef = React.useRef<AbortController | null>(null);

  // Community toggle state
  const [isCommunity, setIsCommunity] = React.useState<boolean>(false);
  const [generationOwnerId, setGenerationOwnerId] = React.useState<string | null>(null);
  const [communityToggleLoading, setCommunityToggleLoading] = React.useState<boolean>(false);
  const [communityToggleError, setCommunityToggleError] = React.useState<string | null>(null);
  // Naming modal (shown when posting to community)
  const [showCommunityNameModal, setShowCommunityNameModal] = React.useState<boolean>(false);
  const [communityNameInput, setCommunityNameInput] = React.useState<string>("");
  const [communityNameError, setCommunityNameError] = React.useState<string | null>(null);
  // Username editing within the community modal
  const [isEditingUsername, setIsEditingUsername] = React.useState<boolean>(false);
  const [usernameInput, setUsernameInput] = React.useState<string>("");
  const [usernameSaving, setUsernameSaving] = React.useState<boolean>(false);
  const [usernameError, setUsernameError] = React.useState<string | null>(null);

  // Whether the current generation is missing a preview image and should have
  // one captured + uploaded after the 3D viewer finishes loading.
  const [needsPreviewUpload, setNeedsPreviewUpload] = React.useState<boolean>(false);
  // Tracks generation ids we've already uploaded a preview for in this session
  // so we don't re-upload on every viewer re-render.
  const previewUploadedForRef = React.useRef<Set<string>>(new Set());

  // True once the Three.js scene has finished loading the model. Used to fade
  // in the sections below the 3D preview only after the scene is ready.
  const [sceneReady, setSceneReady] = React.useState<boolean>(false);

  // True once the user has clicked the Edit Model button at least once. Used
  // to permanently stop the attention pulse on that button so it doesn't keep
  // pulsing after the user has discovered the feature (even if they later exit
  // edit mode).
  const [hasClickedEditModel, setHasClickedEditModel] = React.useState<boolean>(false);
  const [previewPngDataUrl, setPreviewPngDataUrl] = React.useState<string | null>(null);
  const [exportMenuOpen, setExportMenuOpen] = React.useState(false);
  const [isExportingVideo, setIsExportingVideo] = React.useState(false);
  const exportCaptureApiRef = React.useRef<ExportCaptureApi | null>(null);
  const exportMenuRef = React.useRef<HTMLDivElement | null>(null);

  const handleExportCaptureReady = React.useCallback((api: ExportCaptureApi | null) => {
    exportCaptureApiRef.current = api;
  }, []);

  // Only the owner of the generation (when logged in) can post / unpost to community
  const canToggleCommunity = Boolean(
    currentUser?.id && generationOwnerId && currentUser.id === generationOwnerId
  );
  
  // Get model data from location state (passed from LandingPage) or localStorage
  const stateData = location.state as { 
    mpdContent?: string,
    ldrContent?: string,
    modelName?: string,
    voxelSize?: number,
    generation_id?: string,
    storageKeys?: {
      LDR_CONTENT: string,
      MPD_CONTENT: string,
      MODEL_NAME: string,
      GENERATED_AT: string,
      GENERATION_ID: string
    }
  } | null;

  const isDemoModel = !!currentGenerationId && DEMO_MODEL_IDS.has(currentGenerationId);
  
  // Function to load model data from various sources
  const getModelData = () => {
    if (stateData?.mpdContent && stateData?.ldrContent) {
      return {
        mpdContent: stateData.mpdContent,
        ldrContent: stateData.ldrContent,
        modelName: stateData.modelName || "Your Model"
      };
    }
    
    // Fallback to localStorage using passed storage keys
    if (stateData?.storageKeys) {
      try {
        const storageKeys = stateData.storageKeys;
        const savedMpdContent = localStorage.getItem(storageKeys.MPD_CONTENT);
        const savedLdrContent = localStorage.getItem(storageKeys.LDR_CONTENT);
        const savedModelName = localStorage.getItem(storageKeys.MODEL_NAME);
        
        return {
          mpdContent: savedMpdContent,
          ldrContent: savedLdrContent,
          modelName: savedModelName || params.get("name") || "Your Model"
        };
      } catch (error) {
        console.error('Error loading model');
      }
    }
    
    // Additional fallback: try standard localStorage keys when no storageKeys provided
    try {
      const savedMpdContent = localStorage.getItem('lastMpdContent');
      const savedLdrContent = localStorage.getItem('lastLdrContent');
      const savedModelName = localStorage.getItem('lastModelName');
      
      if (savedMpdContent) {
        return {
          mpdContent: savedMpdContent,
          ldrContent: savedLdrContent,
          modelName: savedModelName || params.get("name") || "Your Model"
        };
      }
    } catch (error) {
      console.error('Error loading model');
    }
    
    // Final fallback
    return {
      mpdContent: null,
      ldrContent: null,
      modelName: params.get("name") || "Your Model"
    };
  };
  
  // Initialize model data on component mount - check URL id param first, then fetch from backend, fall back to localStorage
  React.useEffect(() => {
    const initializeModelData = async () => {
      // Priority 1: Check for id parameter in URL (e.g., /generated-model?id=abc123)
      const urlGenerationId = searchParams.get('id');
      
      if (urlGenerationId) {
        setGenerationLoading(true);
        setGenerationError(null);
        
        try {
          // First check the current status
          const statusResponse = await GetGenerationApiService.getGeneration(urlGenerationId);
          
          // If still processing, poll until complete
          if (statusResponse.status === 'started' || statusResponse.status === 'processing') {
            // Show preview image if available
            if (statusResponse.external_image_url) {
              setEditPreviewImageUrl(statusResponse.external_image_url);
            }
            
            // Poll until complete
            const generationData = await GetGenerationApiService.pollUntilComplete(
              urlGenerationId,
              (response: GetGenerationResponse) => {
                if (response.external_image_url) {
                  setEditPreviewImageUrl(response.external_image_url);
                }
              }
            );
            
            // Clear preview image after completion
            setEditPreviewImageUrl(null);
            
            // Process completed generation
            await processCompletedGeneration(urlGenerationId, generationData);
            return;
          }
          
          // If failed, show error
          if (statusResponse.status === 'failed') {
            throw new Error(statusResponse.error_message || 'Generation failed');
          }
          
          // If completed, use the data directly
          if (statusResponse.status === 'completed') {
            if (!statusResponse.ldr_content) {
              throw new Error('No LDR content found in generation data');
            }
            
            // Set reference image URL for voxel editor
            if (statusResponse.processed_image_url) {
              setProcessedImageUrl(statusResponse.processed_image_url);
            }
            
            // Set detail level for resize scaler
            if (statusResponse.detail_level) {
              setDetailLevel(statusResponse.detail_level);
              setCurrentScaler(statusResponse.detail_level);
            }
            
            await processCompletedGeneration(urlGenerationId, {
              generation_id: statusResponse.generation_id,
              prompt: statusResponse.prompt || 'Your Model',
              ldr_content: statusResponse.ldr_content,
              mpd_url: statusResponse.mpd_url,
              xyzrgb_url: statusResponse.xyzrgb_url,
              problematic_xyzrgb_url: statusResponse.problematic_xyzrgb_url,
            });
            return;
          }
          
        } catch (error) {
          console.error('Failed to fetch generation data from URL id:', error);
          setGenerationError(`Failed to load generation: ${error instanceof Error ? error.message : 'Unknown error'}`);
          setGenerationLoading(false);
          return;
        }
      }
      
      // Priority 2: Check for generation_id in location state (passed from LandingPage navigation)
      const stateGenerationId = stateData?.generation_id;
      
      if (stateGenerationId) {
        setGenerationLoading(true);
        setGenerationError(null);
        
        try {
          const statusResponse = await GetGenerationApiService.getGeneration(stateGenerationId);
          
          if (statusResponse.status === 'completed' && statusResponse.ldr_content) {
            await processCompletedGeneration(stateGenerationId, {
              generation_id: statusResponse.generation_id,
              prompt: statusResponse.prompt || stateData?.modelName || 'Your Model',
              ldr_content: statusResponse.ldr_content,
              mpd_url: statusResponse.mpd_url,
              xyzrgb_url: statusResponse.xyzrgb_url,
              problematic_xyzrgb_url: statusResponse.problematic_xyzrgb_url,
            });
            return;
          }
          
          if (statusResponse.status === 'failed') {
            throw new Error(statusResponse.error_message || 'Generation failed');
          }
        } catch (error) {
          console.error('Failed to fetch generation data from state:', error);
          setGenerationError(`Failed to load generation: ${error instanceof Error ? error.message : 'Unknown error'}`);
          setGenerationLoading(false);
          return;
        }
      }
      
      // Priority 3: Try localStorage generation ID
      const generationId = localStorage.getItem('lastGenerationId');
      
      // Try to fetch latest data from backend first
      if (generationId) {
        try {
          const statusResponse = await GetGenerationApiService.getGeneration(generationId);
          
          // If completed, use the data
          if (statusResponse.status === 'completed' && statusResponse.ldr_content) {
            // Store generation ID for edit mode
            setCurrentGenerationId(generationId);
            
            // Set reference image URL for voxel editor
            if (statusResponse.processed_image_url) {
              setProcessedImageUrl(statusResponse.processed_image_url);
            }
            
            // Update detail level for resize scaler
            if (statusResponse.detail_level) {
              setDetailLevel(statusResponse.detail_level);
              setCurrentScaler(statusResponse.detail_level);
            }
            
            // Update xyzrgb URL if available
            if (statusResponse.xyzrgb_url) {
              setXyzrgbUrl(statusResponse.xyzrgb_url);
            }
            
            // Update problematic xyzrgb URL if available
            if (statusResponse.problematic_xyzrgb_url) {
              setProblematicXyzrgbUrl(statusResponse.problematic_xyzrgb_url);
            }
            
            // Update LDR content
            localStorage.setItem('lastLdrContent', statusResponse.ldr_content);
            setLdrContent(statusResponse.ldr_content);
            
            // Set model name from backend prompt
            const freshModelName = statusResponse.prompt || localStorage.getItem('lastModelName') || "Your Model";
            setModelName(freshModelName);
            localStorage.setItem('lastModelName', freshModelName);
            
            // Get MPD content from URL or convert LDR to MPD
            let mpdContent: string | null = null;
            if (statusResponse.mpd_url) {
              try {
                const mpdResponse = await fetch(statusResponse.mpd_url);
                if (mpdResponse.ok) {
                  mpdContent = await mpdResponse.text();
                }
              } catch (mpdError) {
                console.warn('Failed to fetch MPD from URL:', mpdError);
              }
            }
            
            if (!mpdContent) {
              try {
                const authToken = (await supabase.auth.getSession()).data.session?.access_token;
                const mpdData = await LdrToMpdApiService.convertLdrToMpd(
                  statusResponse.ldr_content,
                  freshModelName,
                  authToken
                );
                mpdContent = mpdData.mpd_content;
              } catch (mpdError) {
                console.warn('Failed to convert LDR to MPD:', mpdError);
              }
            }
            
            if (mpdContent) {
              localStorage.setItem('lastMpdContent', mpdContent);
              setMpdContent(mpdContent);
            }
            
            return; // Successfully loaded from backend
          }
        } catch (error) {
          console.error('Failed to fetch generation data, falling back to localStorage:', error);
        }
      }
      
      // Priority 3: Fall back to localStorage if backend fetch fails or no generation ID
      const { mpdContent: initialMpdContent, ldrContent: initialLdrContent, modelName: initialName } = getModelData();
      if (initialMpdContent) setMpdContent(initialMpdContent);
      if (initialLdrContent) setLdrContent(initialLdrContent);
      setModelName(initialName);
    };
    
    // Helper function to process completed generation data
    const processCompletedGeneration = async (
      generationId: string,
      data: { 
        generation_id: string; 
        prompt: string; 
        ldr_content: string; 
        mpd_url: string | null;
        xyzrgb_url: string | null; 
        problematic_xyzrgb_url: string | null;
      }
    ) => {
      // Store generation ID for edit mode
      setCurrentGenerationId(generationId);
      
      // Update xyzrgb URL if available
      if (data.xyzrgb_url) {
        setXyzrgbUrl(data.xyzrgb_url);
      }
      
      // Update problematic xyzrgb URL if available
      if (data.problematic_xyzrgb_url) {
        setProblematicXyzrgbUrl(data.problematic_xyzrgb_url);
      }
      
      // Set LDR content
      setLdrContent(data.ldr_content);
      
      // Set model name from prompt
      const fetchedModelName = data.prompt || "Your Model";
      setModelName(fetchedModelName);
      
      // Get MPD content from URL or convert LDR to MPD
      let mpdContent: string | null = null;
      if (data.mpd_url) {
        try {
          const mpdResponse = await fetch(data.mpd_url);
          if (mpdResponse.ok) {
            mpdContent = await mpdResponse.text();
          }
        } catch (mpdError) {
          console.warn('Failed to fetch MPD from URL:', mpdError);
        }
      }
      
      if (!mpdContent) {
        try {
          const authToken = (await supabase.auth.getSession()).data.session?.access_token;
          const mpdData = await LdrToMpdApiService.convertLdrToMpd(
            data.ldr_content,
            fetchedModelName,
            authToken
          );
          mpdContent = mpdData.mpd_content;
        } catch (mpdError) {
          console.warn('Failed to convert LDR to MPD:', mpdError);
        }
      }
      
      if (mpdContent) {
        setMpdContent(mpdContent);
      }
      
      setGenerationLoading(false);
    };
    
    initializeModelData();
  }, [searchParams]);
  
  // Fetch access token on mount
  React.useEffect(() => {
    const fetchToken = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        setAccessToken(session?.access_token || null);
      } catch (error) {
        console.error('Failed to get session token:', error);
      }
    };
    fetchToken();
  }, []);

  // Fetch isCommunity flag for the current generation
  React.useEffect(() => {
    let cancelled = false;

    const fetchIsCommunity = async () => {
      if (!currentGenerationId) {
        setIsCommunity(false);
        setGenerationOwnerId(null);
        setNeedsPreviewUpload(false);
        return;
      }
      try {
        const { data, error } = await supabase
          .from('generations')
          .select('is_community, user_id, preview_image_url')
          .eq('id', currentGenerationId)
          .maybeSingle();

        if (cancelled) return;

        if (error) {
          console.warn('Failed to fetch is_community flag:', error);
          return;
        }

        const row = data as {
          is_community?: boolean;
          user_id?: string | null;
          preview_image_url?: string | null;
        } | null;
        setIsCommunity(Boolean(row?.is_community));
        setGenerationOwnerId(row?.user_id ?? null);
        setNeedsPreviewUpload(!row?.preview_image_url);
      } catch (e) {
        if (!cancelled) {
          console.warn('Failed to fetch is_community flag:', e);
        }
      }
    };

    fetchIsCommunity();
    return () => {
      cancelled = true;
    };
  }, [currentGenerationId]);

  // Whether the signed-in user owns the current generation. Required to
  // upload a preview image (and matches the backend's authorization check).
  const isGenerationOwner = Boolean(
    currentUser?.id && generationOwnerId && currentUser.id === generationOwnerId
  );

  // Called once after ThreeLDRViewer finishes loading the model. Stores the
  // captured PNG so the upload effect below can send it once all async state
  // (auth token, generation ownership, needsPreviewUpload) has resolved.
  const handlePreviewCaptured = React.useCallback((dataUrl: string) => {
    setPreviewPngDataUrl(dataUrl);
  }, []);

  // Upload the captured preview image once every required piece of async state
  // is ready. This effect re-runs whenever any dependency changes, so it
  // correctly handles the race where the 3D viewer fires onPreviewCaptured
  // before the auth token or Supabase generation query have returned (e.g.
  // when navigating from the landing page with in-memory model data).
  React.useEffect(() => {
    if (!previewPngDataUrl) return;
    if (!currentGenerationId) return;
    if (!needsPreviewUpload) return;
    if (!isGenerationOwner) return;
    if (!accessToken) return;
    if (previewUploadedForRef.current.has(currentGenerationId)) return;

    // Mark as uploaded immediately so concurrent renders don't double-fire.
    previewUploadedForRef.current.add(currentGenerationId);

    UpdateImagePreviewApiService.updateImagePreview(
      currentGenerationId,
      previewPngDataUrl,
      accessToken,
    )
      .then(() => {
        setNeedsPreviewUpload(false);
      })
      .catch((err) => {
        // Allow retrying on next mount if the upload fails.
        previewUploadedForRef.current.delete(currentGenerationId);
        console.warn('Failed to upload preview image:', err);
      });
  }, [previewPngDataUrl, currentGenerationId, needsPreviewUpload, isGenerationOwner, accessToken]);

  React.useEffect(() => {
    if (!exportMenuOpen) return;
    const handleDocumentClick = (event: MouseEvent) => {
      if (!exportMenuRef.current) return;
      if (!exportMenuRef.current.contains(event.target as Node)) {
        setExportMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleDocumentClick);
    return () => document.removeEventListener('mousedown', handleDocumentClick);
  }, [exportMenuOpen]);

  const handleToggleCommunity = async () => {
    if (!currentGenerationId || communityToggleLoading) return;

    // When posting (currently not in community), open the naming modal first.
    // The actual toggle happens after the user submits a name.
    if (!isCommunity) {
      setCommunityNameError(null);
      setCommunityToggleError(null);
      setCommunityNameInput("");
      setIsEditingUsername(false);
      setUsernameError(null);
      setShowCommunityNameModal(true);
      return;
    }

    // Removing from community — no modal, toggle directly.
    setCommunityToggleLoading(true);
    setCommunityToggleError(null);
    const previous = isCommunity;
    setIsCommunity(!previous);
    try {
      const response = await ToggleIsCommunityApiService.toggleIsCommunity(
        currentGenerationId,
        accessToken || undefined
      );
      if (typeof response.is_community === 'boolean') {
        setIsCommunity(response.is_community);
      } else if (typeof response.isCommunity === 'boolean') {
        setIsCommunity(response.isCommunity);
      }
    } catch (error) {
      setIsCommunity(previous);
      console.error('Failed to toggle community status:', error);
      setCommunityToggleError(
        error instanceof Error ? error.message : 'Failed to update community status'
      );
    } finally {
      setCommunityToggleLoading(false);
    }
  };

  // Username derived for display: profile username, fallback to email local-part.
  const displayUsername = (currentUserProfile?.username && currentUserProfile.username.trim())
    || currentUser?.email?.split('@')[0]
    || 'builder';

  const handleStartEditUsername = () => {
    setUsernameInput(currentUserProfile?.username?.trim() || displayUsername);
    setUsernameError(null);
    setIsEditingUsername(true);
  };

  const handleCancelEditUsername = () => {
    if (usernameSaving) return;
    setIsEditingUsername(false);
    setUsernameInput("");
    setUsernameError(null);
  };

  const handleSaveUsername = async () => {
    if (usernameSaving) return;
    const trimmed = usernameInput.trim();
    if (!trimmed) {
      setUsernameError('Username cannot be empty.');
      return;
    }
    if (trimmed.length < 3 || trimmed.length > 30) {
      setUsernameError('Username must be 3-30 characters.');
      return;
    }
    if (!USERNAME_PATTERN.test(trimmed)) {
      setUsernameError(
        'Username can only contain letters, numbers, underscores, hyphens, or periods.'
      );
      return;
    }
    setUsernameSaving(true);
    setUsernameError(null);
    try {
      const { error, success } = await updateUsername(trimmed);
      if (!success) {
        setUsernameError(typeof error === 'string' ? error : 'Failed to update username.');
        return;
      }
      setIsEditingUsername(false);
      setUsernameInput("");
    } catch (err) {
      setUsernameError(err instanceof Error ? err.message : 'Failed to update username.');
    } finally {
      setUsernameSaving(false);
    }
  };

  const handleSubmitCommunityName = async () => {
    if (!currentGenerationId || communityToggleLoading) return;
    if (isEditingUsername) {
      setCommunityNameError('Please save or cancel your username change first.');
      return;
    }
    const trimmed = communityNameInput.trim();
    if (!trimmed) {
      setCommunityNameError('Please enter a name for your model.');
      return;
    }
    if (trimmed.length > 200) {
      setCommunityNameError('Name must be 200 characters or fewer.');
      return;
    }

    setCommunityToggleLoading(true);
    setCommunityNameError(null);
    setCommunityToggleError(null);
    const previous = isCommunity;

    try {
      // 1) Save the name first
      await UpdateGenerationNameApiService.updateGenerationName(
        currentGenerationId,
        trimmed,
        accessToken || undefined
      );
      // Reflect the new name locally
      setModelName(trimmed);

      // 2) Optimistic flip then toggle community status
      setIsCommunity(!previous);
      const response = await ToggleIsCommunityApiService.toggleIsCommunity(
        currentGenerationId,
        accessToken || undefined
      );
      if (typeof response.is_community === 'boolean') {
        setIsCommunity(response.is_community);
      } else if (typeof response.isCommunity === 'boolean') {
        setIsCommunity(response.isCommunity);
      }

      setShowCommunityNameModal(false);
      setCommunityNameInput("");
    } catch (error) {
      // Revert optimistic flip if it happened
      setIsCommunity(previous);
      console.error('Failed to post to community:', error);
      setCommunityNameError(
        error instanceof Error ? error.message : 'Failed to post to community'
      );
    } finally {
      setCommunityToggleLoading(false);
    }
  };
  
  // Function to refresh model data from localStorage
  const refreshModelData = () => {
    const { mpdContent: freshMpdContent, ldrContent: freshLdrContent, modelName: freshName } = getModelData();
    if (freshMpdContent) setMpdContent(freshMpdContent);
    if (freshLdrContent) setLdrContent(freshLdrContent);
    setModelName(freshName);
  };
  
  // Fetch price estimate when generation_id is available
  React.useEffect(() => {
    const fetchPriceEstimate = async () => {
      if (!currentGenerationId) {
        return;
      }
      
      setPriceLoading(true);
      setPriceError(null);
      
      try {
        const priceResponse = await GetPriceApiService.getPrice(
          currentGenerationId,
          accessToken || undefined
        );
        setPriceData(priceResponse);
      } catch (error) {
        console.error('GeneratedModel - Price fetch failed');
        setPriceError(error instanceof Error ? error.message : 'Failed to get price');
      } finally {
        setPriceLoading(false);
      }
    };

    fetchPriceEstimate();
  }, [currentGenerationId, priceRefreshCounter, accessToken]);

  // Handle resize model functionality
  const handleResizeModel = React.useCallback(async (detailLevel: number) => {
    if (!mpdContent) {
      console.error('No model content available for resizing');
      return;
    }

    // Use currentGenerationId state (set when loading from URL or localStorage)
    if (!currentGenerationId) {
      console.error('No generation ID found for resizing');
      return;
    }

    console.log('Resize detail_level:', detailLevel);

    setIsResizing(true);
    
    try {      
      const response = await ResizeModelApiService.resizeModel(
        currentGenerationId,
        detailLevel,
        accessToken || undefined
      );
      
      // Update generation ID and URL immediately
      if (response.generation_id) {
        localStorage.setItem('lastGenerationId', response.generation_id);
        localStorage.setItem('GENERATION_ID', response.generation_id);
        setCurrentGenerationId(response.generation_id);
        
        const newUrl = new URL(window.location.href);
        newUrl.searchParams.set('id', response.generation_id);
        window.history.replaceState({}, '', newUrl.toString());
      }
      
      // Update xyzrgb content immediately if returned
      if (response.xyzrgb_content) {
        setXyzrgbContent(response.xyzrgb_content);
      }
      
      // Clear price data while polling
      setPriceData(null);
      
      // Resize API has returned — stop the resize loading indicator
      setIsResizing(false);
      
      // Cancel any previous polling (save or resize)
      if (savePollingAbortRef.current) {
        savePollingAbortRef.current.abort();
      }
      const abortController = new AbortController();
      savePollingAbortRef.current = abortController;
      
      setIsSavePolling(true);
      setSavePollingError(null);
      
      try {
        // Poll until generation completes (LDR processing finishes)
        const completedGeneration = await GetGenerationApiService.pollUntilComplete(
          response.generation_id,
          undefined,
          undefined,
          undefined,
          abortController.signal
        );
        
        console.log('[GeneratedModel] Resize polling completed:', completedGeneration.generation_id);
        
        // Update LDR content
        if (completedGeneration.ldr_content) {
          setLdrContent(completedGeneration.ldr_content);
          localStorage.setItem('LDR_CONTENT', completedGeneration.ldr_content);
          localStorage.setItem('lastLdrContent', completedGeneration.ldr_content);
        }
        
        // Get MPD content from URL or convert LDR to MPD
        let newMpdContent: string | null = null;
        if (completedGeneration.mpd_url) {
          try {
            const mpdResponse = await fetch(completedGeneration.mpd_url);
            if (mpdResponse.ok) {
              newMpdContent = await mpdResponse.text();
            }
          } catch (mpdError) {
            console.warn('Failed to fetch MPD from URL:', mpdError);
          }
        }
        
        if (!newMpdContent && completedGeneration.ldr_content) {
          try {
            const authToken = (await supabase.auth.getSession()).data.session?.access_token;
            const mpdData = await LdrToMpdApiService.convertLdrToMpd(
              completedGeneration.ldr_content,
              modelName,
              authToken
            );
            newMpdContent = mpdData.mpd_content;
          } catch (mpdError) {
            console.warn('Failed to convert LDR to MPD:', mpdError);
          }
        }
        
        if (newMpdContent) {
          setMpdContent(newMpdContent);
          localStorage.setItem('MPD_CONTENT', newMpdContent);
          localStorage.setItem('lastMpdContent', newMpdContent);
        }
        
        // Update xyzrgb URLs and content from completed generation
        if (completedGeneration.xyzrgb_url) {
          setXyzrgbUrl(completedGeneration.xyzrgb_url);
          
          try {
            const xyzrgbResponse = await fetch(completedGeneration.xyzrgb_url);
            if (xyzrgbResponse.ok) {
              const content = await xyzrgbResponse.text();
              setXyzrgbContent(content);
            }
          } catch (err) {
            console.warn('Failed to fetch xyzrgb content:', err);
          }
        }
        
        // Update problematic xyzrgb
        if (completedGeneration.problematic_xyzrgb_url) {
          setProblematicXyzrgbUrl(completedGeneration.problematic_xyzrgb_url);
          
          try {
            const problematicResponse = await fetch(completedGeneration.problematic_xyzrgb_url);
            if (problematicResponse.ok) {
              const problematicContent = await problematicResponse.text();
              setProblematicXyzrgbContent(problematicContent);
            }
          } catch (problematicErr) {
            console.warn('Failed to fetch problematic xyzrgb content:', problematicErr);
          }
        } else {
          setProblematicXyzrgbUrl(null);
          setProblematicXyzrgbContent(null);
        }
        
        // Clear screenshots and re-trigger price fetch
        setScreenshots(null);
        setPriceRefreshCounter(c => c + 1);
        
        console.log(`Resize completed. New generation ID: ${response.generation_id}`);
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          console.log('[GeneratedModel] Resize polling aborted (superseded)');
          return;
        }
        console.error('Resize polling failed:', error);
        setSavePollingError(error instanceof Error ? error.message : 'Failed to process model after resize');
      } finally {
        if (savePollingAbortRef.current === abortController) {
          setIsSavePolling(false);
          savePollingAbortRef.current = null;
        }
      }
    } catch (error) {
      console.error('GeneratedModel - Resize failed');
      setIsResizing(false);
    }
  }, [mpdContent, accessToken, currentGenerationId, modelName]);

  const handlePromptEditModel = React.useCallback(async () => {
    if (!editPrompt.trim()) {
      console.error('No prompt provided for editing');
      return;
    }

    // Use currentGenerationId state (set when loading from URL or localStorage)
    if (!currentGenerationId) {
      console.error('No generation ID found for prompt editing');
      return;
    }

    // Get modelOption based on quality selection
    const modelOption = editModelQuality === 'regular' ? 'a' : 'b';

    console.log('[GeneratedModel] Prompt edit:', editPrompt, 'modelOption:', modelOption);

    setIsPromptEditing(true);
    setEditPromptError(null);
    setEditPreviewImageUrl(null);
    
    try {      
      // Start the async edit operation
      const response = await PromptEditModelApiService.promptEditModel(
        currentGenerationId,
        editPrompt.trim(),
        accessToken || undefined,
        modelOption
      );
      
      const newGenerationId = response.generation_id;
      console.log('[GeneratedModel] Edit started, polling for status:', newGenerationId);
      
      // Poll for completion with status updates
      const completedGeneration = await GetGenerationApiService.pollUntilComplete(
        newGenerationId,
        (statusResponse: GetGenerationResponse) => {
          // Show preview image if available during processing
          if (statusResponse.external_image_url) {
            setEditPreviewImageUrl(statusResponse.external_image_url);
          }
        }
      );
      
      // Clear preview image after completion
      setEditPreviewImageUrl(null);
      
      console.log('[GeneratedModel] Edit completed:', completedGeneration.generation_id);
            
      // Update localStorage with new content
      localStorage.setItem('lastLdrContent', completedGeneration.ldr_content);
      setLdrContent(completedGeneration.ldr_content);
      
      localStorage.setItem('lastGenerationId', completedGeneration.generation_id);
      setCurrentGenerationId(completedGeneration.generation_id);
      
      // Get MPD content from URL or convert LDR to MPD
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
      
      if (!mpdContent) {
        try {
          const authToken = (await supabase.auth.getSession()).data.session?.access_token;
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
      
      if (mpdContent) {
        localStorage.setItem('lastMpdContent', mpdContent);
        setMpdContent(mpdContent);
      }
      
      // Update xyzrgb URLs
      if (completedGeneration.xyzrgb_url) {
        setXyzrgbUrl(completedGeneration.xyzrgb_url);
      }
      if (completedGeneration.problematic_xyzrgb_url) {
        setProblematicXyzrgbUrl(completedGeneration.problematic_xyzrgb_url);
      }
      
      // Clear screenshots to force regeneration with new model
      setScreenshots(null);
      
      // Clear the prompt input after successful edit
      setEditPrompt('');
    } catch (error) {
      console.error('GeneratedModel - Prompt edit failed:', error);
      setEditPromptError(error instanceof Error ? error.message : 'Failed to edit model');
      setEditPreviewImageUrl(null);
    } finally {
      setIsPromptEditing(false);
    }
  }, [editPrompt, editModelQuality, accessToken, modelName, currentGenerationId]);

  // Guard an action (e.g. in-app navigation) behind the unsaved-changes modal.
  // If the voxel editor has unsaved changes, prompt the user; otherwise run immediately.
  const guardUnsavedChanges = (action: () => void) => {
    if (showVoxelEditor && voxelHasChanges) {
      pendingExitActionRef.current = action;
      setShowUnsavedChangesModal(true);
      return;
    }
    action();
  };

  const handleEditModelClick = async () => {
    // Stop the attention pulse permanently once the user has discovered the
    // Edit Model button, so it doesn't keep pulsing after they exit edit mode.
    setHasClickedEditModel(true);

    // If already in edit mode, check for unsaved changes before exiting
    if (showVoxelEditor) {
      if (voxelHasChanges) {
        pendingExitActionRef.current = () => {
          setShowVoxelEditor(false);
          setShowResizeScaler(false);
          setXyzrgbError(null);
        };
        setShowUnsavedChangesModal(true);
        return;
      }
      setShowVoxelEditor(false);
      setShowResizeScaler(false);
      setXyzrgbError(null);
      return;
    }

    // Enter edit mode - fetch xyzrgb content
    if (!xyzrgbUrl) {
      setXyzrgbError('No voxel data available for this model');
      return;
    }

    setXyzrgbLoading(true);
    setXyzrgbError(null);

    try {
      // Fetch the xyzrgb content from the URL
      const response = await fetch(xyzrgbUrl);
      if (!response.ok) {
        throw new Error(`Failed to fetch voxel data: ${response.statusText}`);
      }
      
      const content = await response.text();
      setXyzrgbContent(content);
      
      // Fetch problematic xyzrgb content if URL is available
      if (problematicXyzrgbUrl) {
        try {
          const problematicResponse = await fetch(problematicXyzrgbUrl);
          if (problematicResponse.ok) {
            const problematicContent = await problematicResponse.text();
            setProblematicXyzrgbContent(problematicContent);
          }
        } catch (problematicErr) {
          // Non-fatal - just log and continue without problematic highlighting
          console.warn('Failed to fetch problematic xyzrgb content:', problematicErr);
        }
      }
      
      setShowVoxelEditor(true);
      setShowResizeScaler(true);
    } catch (err) {
      console.error('Failed to fetch xyzrgb content:', err);
      setXyzrgbError(`Failed to load voxel data: ${err}`);
    } finally {
      setXyzrgbLoading(false);
    }
  };

  const angles = [
    { label: "View angle 01", src: "" },
    { label: "View angle 02", src: "" },
    { label: "View angle 03", src: "" },
  ];

    const handleBackClick = React.useCallback(() => {
    navigate("/");
    }, [navigate]);

    const getSafeExportName = React.useCallback(() => {
      return (modelName || 'model')
        .trim()
        .replace(/[^a-zA-Z0-9_-]+/g, '_')
        .replace(/^_+|_+$/g, '') || 'model';
    }, [modelName]);

    const downloadBlob = React.useCallback((blob: Blob, fileName: string) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    }, []);

    const handleExportLdr = React.useCallback(() => {
      if (!ldrContent) return;
      setExportMenuOpen(false);
      const blob = new Blob([ldrContent], { type: 'text/plain;charset=utf-8' });
      downloadBlob(blob, `${getSafeExportName()}.ldr`);
    }, [ldrContent, downloadBlob, getSafeExportName]);

    const handleExportPng = React.useCallback(() => {
      setExportMenuOpen(false);
      const pngDataUrl = previewPngDataUrl ?? exportCaptureApiRef.current?.capturePreviewPng() ?? null;
      if (!pngDataUrl) return;
      fetch(pngDataUrl)
        .then((res) => res.blob())
        .then((blob) => {
          downloadBlob(blob, `${getSafeExportName()}.png`);
        })
        .catch((err) => {
          console.warn('Failed to export PNG:', err);
        });
    }, [downloadBlob, getSafeExportName, previewPngDataUrl]);

    const handleExportVideo = React.useCallback(async () => {
      if (!exportCaptureApiRef.current || isExportingVideo) return;
      setExportMenuOpen(false);
      setIsExportingVideo(true);
      try {
        const result = await exportCaptureApiRef.current.capturePreviewVideo();
        if (!result) return;
        downloadBlob(result.blob, `${getSafeExportName()}.${result.extension}`);
      } catch (err) {
        console.warn('Failed to export video:', err);
      } finally {
        setIsExportingVideo(false);
      }
    }, [downloadBlob, getSafeExportName, isExportingVideo]);


  return (
    <div className="min-h-screen text-slate-900" style={{ backgroundColor: "#ffffff" }}>
      <SEO
        title={`Generated Model — ${modelName}`}
        description="View your generated model, pricing, steps, and pieces."
        url="https://brickbuilder.ai/generated-model"
      />

      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-4 sm:px-6 md:px-8 lg:px-10 pb-16 pt-3">
        <Header />
        
        {/* Generate Another Button */}
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mt-4 mb-2 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Generate Another
        </button>

        {/* Loading state when fetching generation by ID */}
        {generationLoading && (
          <div className="flex flex-col items-center justify-center py-32">
            {/* Preview image during loading */}
            {editPreviewImageUrl && (
              <div className="relative w-full max-w-md mb-6">
                <img
                  src={editPreviewImageUrl}
                  alt="Generation preview"
                  className="w-full rounded-xl shadow-lg border border-slate-200"
                />
                <div className="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded-full">
                  Processing...
                </div>
              </div>
            )}
            <Loader2 className="h-12 w-12 animate-spin text-[#f44336] mb-4" />
            <p className="text-slate-600">Loading model...</p>
          </div>
        )}

        {/* Error state when generation fetch fails */}
        {generationError && !generationLoading && (
          <div className="flex flex-col items-center justify-center py-32">
            <div className="text-red-500 text-lg font-semibold mb-4">Failed to Load Model</div>
            <p className="text-slate-600 mb-6">{generationError}</p>
            <button
              onClick={() => navigate("/")}
              className="px-6 py-2 bg-[#f44336] text-white rounded-full hover:bg-[#ff6b6b] transition-all"
            >
              Go Back Home
            </button>
          </div>
        )}

        {/* Main content - only show when not loading and no error */}
        {!generationLoading && !generationError && (
          <>
        {/* Centered Title - hide when in edit mode */}
        {!showVoxelEditor && (
          <section className="relative mt-2 mb-2 md:mb-3 landing-fade-in landing-delay-2">
            <h2 className="text-lg sm:text-xl lg:text-2xl font-semibold text-center break-words px-4">
              Successfully Generated Model
            </h2>
            {currentGenerationId && (
              <p className="text-xs text-slate-400 text-center mt-1">
                id: {currentGenerationId}
              </p>
            )}
            {/* <p className="text-sm text-slate-500 text-center italic mt-3 px-4">
              Generations offer a starting point, but it's up to you to resize, recolor, and reshape your model to perfection!
            </p> */}
          </section>
        )}

{/* Voxel Editor - shown when edit mode is active */}
{showVoxelEditor && xyzrgbContent ? (
  <section className="mt-6 md:mt-8 lg:mt-10">
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-[#f44336]">Edit Mode</h2>
        <p className="text-sm text-slate-500">Select blocks to change color or add/remove</p>
      </div>
      {/* Voxel editor */}
      <div className="border border-slate-200 rounded-2xl overflow-hidden bg-white shadow-sm" style={{ height: '700px' }}>
        <VoxelViewer 
            xyzrgbContent={xyzrgbContent}
            problematicXyzrgbContent={problematicXyzrgbContent || undefined}
            generationId={currentGenerationId || undefined}
            accessToken={accessToken || undefined}
            referenceImageUrl={isDemoModel ? undefined : (processedImageUrl || undefined)}
            isProcessingSave={isSavePolling}
            onHasChangesChange={setVoxelHasChanges}
            saveRef={voxelSaveRef}
            showResizeScaler={!isDemoModel && showResizeScaler && !!mpdContent}
            onResize={handleResizeModel}
            isResizing={isResizing}
            resizeScaler={currentScaler}
            onResizeScalerChange={setCurrentScaler}
            onSaveSuccess={async (response) => {
            // Store new generation ID in localStorage immediately
            localStorage.setItem('lastGenerationId', response.generation_id);
            if (response.generation_id) {
              localStorage.setItem('GENERATION_ID', response.generation_id);
            }
            
            // Update the displayed generation ID and URL immediately
            setCurrentGenerationId(response.generation_id);
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.set('id', response.generation_id);
            window.history.replaceState({}, '', newUrl.toString());
            
            // Start polling — backend is now processing LDR asynchronously
            
            // Cancel any previous save polling
            if (savePollingAbortRef.current) {
              savePollingAbortRef.current.abort();
            }
            const abortController = new AbortController();
            savePollingAbortRef.current = abortController;
            
            setIsSavePolling(true);
            setSavePollingError(null);
            
            try {
              // Poll until generation completes (LDR processing finishes)
              const completedGeneration = await GetGenerationApiService.pollUntilComplete(
                response.generation_id,
                undefined,
                undefined,
                undefined,
                abortController.signal
              );
              
              console.log('[GeneratedModel] Save polling completed:', completedGeneration.generation_id);
              
              // Update LDR content
              if (completedGeneration.ldr_content) {
                setLdrContent(completedGeneration.ldr_content);
                localStorage.setItem('LDR_CONTENT', completedGeneration.ldr_content);
                localStorage.setItem('lastLdrContent', completedGeneration.ldr_content);
              }
              
              // Get MPD content from URL or convert LDR to MPD
              let newMpdContent: string | null = null;
              if (completedGeneration.mpd_url) {
                try {
                  const mpdResponse = await fetch(completedGeneration.mpd_url);
                  if (mpdResponse.ok) {
                    newMpdContent = await mpdResponse.text();
                  }
                } catch (mpdError) {
                  console.warn('Failed to fetch MPD from URL:', mpdError);
                }
              }
              
              if (!newMpdContent && completedGeneration.ldr_content) {
                try {
                  const authToken = (await supabase.auth.getSession()).data.session?.access_token;
                  const mpdData = await LdrToMpdApiService.convertLdrToMpd(
                    completedGeneration.ldr_content,
                    modelName,
                    authToken
                  );
                  newMpdContent = mpdData.mpd_content;
                } catch (mpdError) {
                  console.warn('Failed to convert LDR to MPD:', mpdError);
                }
              }
              
              if (newMpdContent) {
                setMpdContent(newMpdContent);
                localStorage.setItem('MPD_CONTENT', newMpdContent);
                localStorage.setItem('lastMpdContent', newMpdContent);
              }
              
              // Update xyzrgb URLs and content
              if (completedGeneration.xyzrgb_url) {
                setXyzrgbUrl(completedGeneration.xyzrgb_url);
                
                // Only update xyzrgb content if the voxel editor is NOT open.
                // When the editor is open, it already holds the correct voxel state
                // (the user's edits). Overwriting it would reset the editor and
                // lose in-progress work. We still update problematic overlay below.
                if (!showVoxelEditor) {
                  try {
                    const xyzrgbResponse = await fetch(completedGeneration.xyzrgb_url);
                    if (xyzrgbResponse.ok) {
                      const content = await xyzrgbResponse.text();
                      setXyzrgbContent(content);
                    }
                  } catch (err) {
                    console.warn('Failed to fetch xyzrgb content:', err);
                  }
                }
              }
              
              // Update problematic xyzrgb URL and content
              if (completedGeneration.problematic_xyzrgb_url) {
                setProblematicXyzrgbUrl(completedGeneration.problematic_xyzrgb_url);
                
                try {
                  const problematicResponse = await fetch(completedGeneration.problematic_xyzrgb_url);
                  if (problematicResponse.ok) {
                    const problematicContent = await problematicResponse.text();
                    setProblematicXyzrgbContent(problematicContent);
                  }
                } catch (problematicErr) {
                  console.warn('Failed to fetch problematic xyzrgb content:', problematicErr);
                }
              } else {
                // Clear problematic content if no URL is returned
                setProblematicXyzrgbUrl(null);
                setProblematicXyzrgbContent(null);
              }
              
              // Clear screenshots to regenerate with new model
              setScreenshots(null);
              
              // Re-trigger price fetch now that the generation is complete
              setPriceRefreshCounter(c => c + 1);
              
              console.log(`Model saved successfully. New generation ID: ${response.generation_id}`);
            } catch (error) {
              // Ignore abort errors — means a newer save superseded this one
              if (error instanceof DOMException && error.name === 'AbortError') {
                console.log('[GeneratedModel] Save polling aborted (superseded by newer save)');
                return;
              }
              console.error('Save polling failed:', error);
              setSavePollingError(error instanceof Error ? error.message : 'Failed to process model after save');
            } finally {
              // Only clear polling state if this controller wasn't replaced
              if (savePollingAbortRef.current === abortController) {
                setIsSavePolling(false);
                savePollingAbortRef.current = null;
              }
            }
          }}
        />
      </div>
    </div>
  </section>
) : (
  /* Angle gallery with extra vertical spacing - hidden when voxel editor is shown */
  <section className="mt-2 md:mt-3">
    <div className="grid grid-cols-1 gap-4">
      {/* View angle screenshots disabled
      {angles.slice(0, 2).map((a, idx) => {
        const screenshotSrc = screenshots ? (idx === 0 ? screenshots.angle1 : screenshots.angle2) : null;
        const showSpinner = isSavePolling || (mpdContent && !screenshots);
        
        return (
          <figure
            key={idx}
            className="hidden md:block rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <div
              className="relative w-full overflow-hidden rounded-xl bg-slate-50"
              style={{ paddingTop: "66%" }}
            >
              <div className="absolute inset-0">
                {showSpinner ? (
                  <div className="flex items-center justify-center h-full bg-slate-50">
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-8 h-8 border-[3px] border-gray-300 border-t-black rounded-full animate-spin"></div>
                    </div>
                  </div>
                ) : (
                  <img
                    src={screenshotSrc || a.src}
                    alt={a.label}
                    className="absolute inset-0 h-full w-full object-contain"
                  />
                )}
              </div>
            </div>
            <figcaption className="mt-3 text-xs text-slate-500 text-center">
              {a.label}
            </figcaption>
          </figure>
        );
      })}
      */}

      {/* 3D viewer - always visible */}
      <figure className="rounded-2xl border border-slate-200 bg-white p-2 shadow-sm">
        <div
          className="relative w-full overflow-hidden rounded-xl bg-slate-50"
          style={{ aspectRatio: '3 / 2', maxHeight: '50vh' }}
        >
          <div ref={exportMenuRef} className="absolute right-3 top-3 z-20">
            <button
              type="button"
              aria-label="Export model"
                disabled={isSavePolling || isExportingVideo || (!ldrContent && !previewPngDataUrl)}
              onClick={() => setExportMenuOpen((prev) => !prev)}
              className="inline-flex items-center gap-2 rounded-full border border-slate-700/40 bg-slate-900/85 px-2.5 py-2 sm:px-4 text-xs font-semibold tracking-wide text-white shadow-lg shadow-black/30 backdrop-blur-sm transition-all duration-150 hover:bg-slate-800 hover:scale-[1.03] disabled:cursor-not-allowed disabled:opacity-45"
            >
                {isExportingVideo ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
              <span className="hidden sm:inline">Export</span>
            </button>

            {exportMenuOpen && (
              <div className="absolute right-0 mt-2 w-44 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl">
                <button
                  type="button"
                  onClick={handleExportLdr}
                  disabled={!ldrContent}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <FileText size={14} />
                  LDraw (.ldr)
                </button>
                <button
                  type="button"
                  onClick={handleExportPng}
                  disabled={!previewPngDataUrl && !exportCaptureApiRef.current}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <Image size={14} />
                  Image (.png)
                </button>
                <button
                  type="button"
                  onClick={() => { void handleExportVideo(); }}
                  disabled={!exportCaptureApiRef.current || isExportingVideo}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {isExportingVideo ? <Loader2 size={14} className="animate-spin" /> : <Video size={14} />}
                  Video (.mp4)
                </button>
              </div>
            )}
          </div>
          <div className="absolute inset-0">
            {isSavePolling ? (
              <div className="flex items-center justify-center h-full bg-slate-50">
                <div className="flex flex-col items-center gap-3">
                  <div className="w-8 h-8 border-[3px] border-gray-300 border-t-black rounded-full animate-spin"></div>
                  <span className="text-xs text-slate-500">Processing build...</span>
                </div>
              </div>
            ) : mpdContent ? (
              <ThreeLDRViewer
                key={mpdContent.length}
                modelContent={mpdContent}
                modelName={modelName}
                onPreviewCaptured={handlePreviewCaptured}
                onModelLoaded={() => setSceneReady(true)}
                onExportCaptureReady={handleExportCaptureReady}
                animateModelBuild
                /* onScreenshotsReady={setScreenshots} — disabled */
              />
            ) : (
              <div className="w-full h-full bg-slate-50"></div>
            )}
          </div>
        </div>
        <figcaption className="mt-1 text-xs text-slate-500 text-center">
          {/* Click/touch and drag to rotate, scroll/pinch to zoom */}
        </figcaption>
      </figure>
    </div>
  </section>
)}

        {/* Sections below the 3D preview fade in once the scene is ready */}
        <div
          className={sceneReady ? "below-preview-sequence" : ""}
          style={sceneReady ? undefined : { opacity: 0 }}
        >
        {/* Resize Scaler - shown outside edit mode */}
        {!showVoxelEditor && showResizeScaler && mpdContent && (
          <section className="mt-12 max-w-md mx-auto space-y-6">
            <ResizeScaler
              onResize={handleResizeModel}
              disabled={!mpdContent}
              isResizing={isResizing}
              scaler={currentScaler}
              onScalerChange={setCurrentScaler}
            />
          </section>
        )}

        {/* Centered dual buttons: Edit Model + Order My Kit */}
        <section className="mt-4 mb-4 flex flex-col items-center gap-3 px-4">
          {/* Tip nudging users toward the Block Editor (hidden in edit mode) */}
          {!showVoxelEditor && (
            <p className="text-sm text-slate-500 text-center mb-2 max-w-2xl">
              Not what you were expecting? Try coloring and shaping using the Block Editor!
            </p>
          )}
          <div className="flex flex-col sm:flex-row justify-center gap-3 sm:gap-6 w-full sm:w-auto">
            {/* Edit Model button — white with grey border, turns red on hover */}
            <button
                type="button"
                aria-label="Edit model"
                onClick={handleEditModelClick}
                disabled={xyzrgbLoading}
                className={`inline-flex items-center justify-center gap-2 h-12 rounded-full px-7 w-full sm:w-auto sm:min-w-44 bg-white text-black font-semibold border-2 border-gray-300 transition-all duration-150 ${
                  xyzrgbLoading 
                    ? 'cursor-not-allowed opacity-70' 
                    : 'cursor-pointer hover:border-[#f44336] hover:text-[#f44336] hover:scale-[1.03] hover:shadow-lg'
                } ${!xyzrgbLoading && !hasClickedEditModel ? 'attention-pulse' : ''}`}
            >
                {xyzrgbLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Loading...
                  </>
                ) : (
                  <>
                    {/* <Pencil size={16} /> */}
                    {showVoxelEditor ? 'Exit Block Editor' : 'Edit Model'}
                  </>
                )}
            </button>

            {/* Instructions button — white with grey border, turns red on hover */}
            <button
                type="button"
                aria-label="View instructions"
                onClick={() => guardUnsavedChanges(() => navigate(`/instructions?id=${currentGenerationId}`))}
                disabled={!currentGenerationId || isSavePolling}
                className="inline-flex items-center justify-center gap-2 h-12 rounded-full px-7 w-full sm:w-auto sm:min-w-44 bg-white text-black font-semibold border-2 border-gray-300 cursor-pointer transition-all duration-150 hover:border-[#f44336] hover:text-[#f44336] hover:scale-[1.03] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50"
            >
                {isSavePolling ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Processing...
                  </>
                ) : (
                  'View Instructions'
                )}
            </button>

            {/* Order My Kit button — red with hover lighten */}
            <button
            type="button"
            aria-label="Order my kit"
            disabled={priceLoading || isSavePolling}
            onClick={() => guardUnsavedChanges(() => navigate("/order", { 
              state: { 
                name: modelName,
                parts_list: priceData?.parts_breakdown || [],
                screenshots: screenshots,
                generation_id: currentGenerationId,
                priceData: priceData
              }
            }))}
            className={`inline-flex items-center justify-center h-12 rounded-full px-7 w-full sm:w-auto sm:min-w-44 text-white font-semibold transition-all duration-150 shadow-lg ${
              priceLoading || isSavePolling
                ? 'bg-gray-400 cursor-not-allowed' 
                : 'bg-[#f44336] cursor-pointer shadow-[#f44336]/25 hover:bg-[#ff6b6b] hover:scale-[1.03]'
            }`}
          >
            {priceLoading || isSavePolling ? (
              <>
                <div className="w-4 h-4 border-2 border-gray-300 border-t-black rounded-full animate-spin mr-2"></div>
                Order my Kit!
              </>
            ) : (
              'Order my Kit!'
            )}
          </button>

          {/* Post / Remove from Community button — only the owner can toggle */}
          {canToggleCommunity && (
          <button
            type="button"
            aria-label={isCommunity ? 'Remove from community' : 'Post to community'}
            disabled={!currentGenerationId || communityToggleLoading || isSavePolling}
            onClick={handleToggleCommunity}
            className={`inline-flex items-center justify-center gap-2 h-12 rounded-full px-7 w-full sm:w-auto sm:min-w-44 font-semibold transition-all duration-150 border-2 ${
              !currentGenerationId || communityToggleLoading || isSavePolling
                ? 'bg-white text-gray-400 border-gray-200 cursor-not-allowed'
                : isCommunity
                  ? 'bg-white text-[#f44336] border-[#f44336] cursor-pointer hover:bg-[#f44336] hover:text-white hover:scale-[1.03] hover:shadow-lg'
                  : 'bg-white text-black border-gray-300 cursor-pointer hover:border-[#f44336] hover:text-[#f44336] hover:scale-[1.03] hover:shadow-lg'
            }`}
          >
            {communityToggleLoading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                {isCommunity ? 'Removing...' : 'Posting...'}
              </>
            ) : (
              <>
                <Users size={16} />
                {isCommunity ? 'Remove from Community' : 'Post to Community'}
              </>
            )}
          </button>
          )}
          </div>
          
          {/* Error message for voxel editor */}
          {xyzrgbError && (
            <p className="text-red-500 text-sm">{xyzrgbError}</p>
          )}
          {savePollingError && (
            <p className="text-red-500 text-sm">{savePollingError}</p>
          )}
          {communityToggleError && (
            <p className="text-red-500 text-sm">{communityToggleError}</p>
          )}
        </section>

        {/* Congrats line */}
        <section className="mt-12">
          <p className="text-base text-center md:text-left">
            <span className="font-semibold">Congratulations:</span>{" "}
            <span className="text-slate-700">your model is generated.</span>
          </p>
        </section>

        {/* Stats grid with hover animation */}
        <section className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
          <div className="flex flex-col">
            <StatCard
              icon={(priceLoading || isSavePolling) ? (
                <div className="w-5 h-5 border-2 border-gray-300 border-t-black rounded-full animate-spin"></div>
              ) : (
                <HandCoins className="h-5 w-5 text-black" />
              )}
              title={
                (priceLoading || isSavePolling)
                  ? "Estimating Price..." 
                  : priceError 
                    ? "Price Unavailable"
                    : priceData 
                      ? `$${priceData.total_price} ${priceData.currency}`
                      : ""
              }
              sub={
                (priceLoading || isSavePolling)
                  ? "Loading price estimate..."
                  : priceError
                    ? "Unable to calculate pricing"
                    : priceData
                      ? "Total cost + shipping"
                      : ""
              }
            />
            {/* Too expensive? Try resizing! */}
            {priceData && !priceLoading && !isSavePolling && !isDemoModel && (
              <div className="mt-2 text-center">
                <p className="text-sm text-slate-500">
                  Too expensive?{' '}
                  <button
                    type="button"
                    onClick={() => setShowPriceResize(prev => !prev)}
                    className="text-[#f44336] font-semibold hover:underline cursor-pointer bg-transparent border-none p-0 text-sm"
                  >
                    Try resizing!
                  </button>
                </p>
                {showPriceResize && (
                  <div className="mt-3 max-w-xs mx-auto">
                    <ResizeScaler
                      onResize={handleResizeModel}
                      disabled={!mpdContent}
                      isResizing={isResizing}
                      scaler={currentScaler}
                      onScalerChange={setCurrentScaler}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
          <StatCard
            icon={(priceLoading || isSavePolling) ? (
              <div className="w-5 h-5 border-2 border-gray-300 border-t-black rounded-full animate-spin"></div>
            ) : (
              <Package className="h-5 w-5 text-black" />
            )}
            title={
              (priceLoading || isSavePolling)
                ? "Counting Pieces..."
                : priceData 
                  ? `${priceData.total_parts} Pieces`
                  : ""
            }
            sub={
              (priceLoading || isSavePolling)
                ? "Loading piece count..."
                : priceData 
                  ? ""
                  : ""
            }
          />
          <StatCard
            icon={(priceLoading || isSavePolling) ? (
              <div className="w-5 h-5 border-2 border-gray-300 border-t-black rounded-full animate-spin"></div>
            ) : (
              <Boxes className="h-5 w-5 text-black" />
            )}
            title={
              (priceLoading || isSavePolling)
                ? "Calculating Weight..."
                : priceData
                  ? `${priceData.total_weight.toFixed(2)} kg`
                  : ""
            }
            sub={
              (priceLoading || isSavePolling)
                ? "Loading weight..."
                : priceData
                  ? "Total weight"
                  : ""
            }
          />
        </section>

        {/* Footer action bar */}
        <section className="mt-12 flex items-center justify-between">
          <div className="flex items-center gap-3">
          </div>
        </section>
        </div>
          </>
        )}

      {/* Unsaved changes confirmation modal */}
      {showUnsavedChangesModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
          onClick={() => {
            pendingExitActionRef.current = null;
            setShowUnsavedChangesModal(false);
          }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-[90%] relative"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-slate-800 mb-2">Save your changes?</h3>
            <p className="text-sm text-slate-500 mb-6">
              You have unsaved edits. Would you like to save before exiting edit mode?
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  pendingExitActionRef.current = null;
                  setShowUnsavedChangesModal(false);
                }}
                className="px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowUnsavedChangesModal(false);
                  setShowVoxelEditor(false);
                  setShowResizeScaler(false);
                  setXyzrgbError(null);
                  setVoxelHasChanges(false);
                  const action = pendingExitActionRef.current;
                  pendingExitActionRef.current = null;
                  if (action) action();
                }}
                className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors cursor-pointer"
              >
                Discard
              </button>
              <button
                onClick={async () => {
                  setShowUnsavedChangesModal(false);
                  if (voxelSaveRef.current) {
                    await voxelSaveRef.current();
                  }
                  setShowVoxelEditor(false);
                  setShowResizeScaler(false);
                  setXyzrgbError(null);
                  setVoxelHasChanges(false);
                  const action = pendingExitActionRef.current;
                  pendingExitActionRef.current = null;
                  if (action) action();
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-[#10B981] rounded-lg hover:bg-[#059669] transition-colors cursor-pointer"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Community name modal — shown when posting to community */}
      {showCommunityNameModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
          onClick={() => {
            if (communityToggleLoading) return;
            setShowCommunityNameModal(false);
            setCommunityNameError(null);
          }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl p-6 max-w-md w-[90%] relative"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-slate-800 mb-2">Name your model</h3>
            <p className="text-sm text-slate-500 mb-4">
              Give your model a name before sharing it with the community.
            </p>
            <input
              type="text"
              autoFocus
              value={communityNameInput}
              onChange={(e) => {
                setCommunityNameInput(e.target.value);
                if (communityNameError) setCommunityNameError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSubmitCommunityName();
                } else if (e.key === 'Escape' && !communityToggleLoading) {
                  setShowCommunityNameModal(false);
                  setCommunityNameError(null);
                }
              }}
              placeholder="Enter model name"
              maxLength={200}
              disabled={communityToggleLoading}
              className="w-full px-4 py-2.5 text-sm rounded-lg border-2 border-slate-200 focus:border-[#f44336] focus:outline-none transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            />
            {communityNameError && (
              <p className="mt-2 text-sm text-red-500">{communityNameError}</p>
            )}

            {/* Username section — shows the username that will appear on the post */}
            <div className="mt-5 pt-4 border-t border-slate-100">
              {!isEditingUsername ? (
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm text-slate-600">
                    Posting as{' '}
                    <span className="font-semibold text-slate-800">{displayUsername}</span>
                  </p>
                  <button
                    type="button"
                    onClick={handleStartEditUsername}
                    disabled={communityToggleLoading || !currentUserProfile}
                    className="text-sm font-medium text-[#f44336] hover:text-[#ff6b6b] transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Edit
                  </button>
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">
                    Username
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      autoFocus
                      value={usernameInput}
                      onChange={(e) => {
                        setUsernameInput(e.target.value);
                        if (usernameError) setUsernameError(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleSaveUsername();
                        } else if (e.key === 'Escape' && !usernameSaving) {
                          handleCancelEditUsername();
                        }
                      }}
                      placeholder="Enter a username"
                      maxLength={30}
                      disabled={usernameSaving}
                      className="flex-1 px-3 py-2 text-sm rounded-lg border-2 border-slate-200 focus:border-[#f44336] focus:outline-none transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                    />
                    <button
                      type="button"
                      onClick={handleSaveUsername}
                      disabled={usernameSaving || !usernameInput.trim()}
                      className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-[#f44336] rounded-lg hover:bg-[#ff6b6b] transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {usernameSaving ? <Loader2 size={14} className="animate-spin" /> : 'Save'}
                    </button>
                    <button
                      type="button"
                      onClick={handleCancelEditUsername}
                      disabled={usernameSaving}
                      className="px-3 py-2 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Cancel
                    </button>
                  </div>
                  <p className="mt-1.5 text-xs text-slate-500">
                    3-30 characters. Letters, numbers, underscores, hyphens, or periods.
                  </p>
                  {usernameError && (
                    <p className="mt-2 text-sm text-red-500">{usernameError}</p>
                  )}
                </div>
              )}
            </div>
            <div className="flex gap-3 justify-end mt-6">
              <button
                onClick={() => {
                  if (communityToggleLoading) return;
                  setShowCommunityNameModal(false);
                  setCommunityNameError(null);
                }}
                disabled={communityToggleLoading}
                className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitCommunityName}
                disabled={communityToggleLoading || !communityNameInput.trim() || isEditingUsername}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#f44336] rounded-lg hover:bg-[#ff6b6b] transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {communityToggleLoading ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Posting...
                  </>
                ) : (
                  'Post to Community'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      </div>

      <SiteFooter />
    </div>
  );
}
