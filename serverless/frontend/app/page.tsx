"use client";

import { useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { useSAM3DStream } from "./hooks/useSAM3DStream";
import BottomToolbar from "./components/BottomToolbar";
import LogPanel from "./components/LogPanel";

// Dynamic import to avoid SSR issues with Three.js
const VoxelViewer = dynamic(() => import("./components/VoxelViewer"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center text-zinc-500">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-zinc-600 border-t-cyan-500 rounded-full animate-spin mx-auto mb-3" />
        <span className="text-sm">Loading 3D viewer...</span>
      </div>
    </div>
  ),
});

const ViewCube = dynamic(() => import("./components/ViewCube"), {
  ssr: false,
  loading: () => (
    <div className="w-32 h-32 flex items-center justify-center">
      <div className="w-4 h-4 border-2 border-zinc-600 border-t-zinc-400 rounded-full animate-spin" />
    </div>
  ),
});

export default function Home() {
  const [isLogPanelOpen, setIsLogPanelOpen] = useState(false);
  const [targetCameraPosition, setTargetCameraPosition] = useState<[number, number, number] | null>(null);
  const [targetSpherical, setTargetSpherical] = useState<{ theta: number; phi: number } | null>(null);
  const [cameraRotation, setCameraRotation] = useState({ theta: 0, phi: Math.PI / 2 });
  const [showAxes, setShowAxes] = useState(false);
  const [showGrid, setShowGrid] = useState(true);
  const [showViewCube, setShowViewCube] = useState(true);
  const [autoRotate, setAutoRotate] = useState(false);
  const [autoRotateSpeed, setAutoRotateSpeed] = useState(1);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  
  const handleViewChange = useCallback((position: [number, number, number]) => {
    setTargetCameraPosition(position);
    setTimeout(() => setTargetCameraPosition(null), 100);
  }, []);

  const handleDragRotate = useCallback((spherical: { theta: number; phi: number }) => {
    setTargetSpherical(spherical);
  }, []);
  
  const {
    isStreaming,
    voxels,
    meshData,
    glbData,
    logs,
    currentStage,
    progress,
    glbUrl,
    startStream,
    cancelStream,
  } = useSAM3DStream();

  return (
    <div className="h-screen bg-[#0a0a0a] text-zinc-100 relative overflow-hidden">
      {/* 3D Viewer - takes full screen */}
      <div className="absolute inset-0">
        <VoxelViewer
          voxels={voxels}
          meshData={meshData}
          glbData={glbData}
          autoRotate={autoRotate}
          autoRotateSpeed={autoRotateSpeed}
          targetCameraPosition={targetCameraPosition}
          targetSpherical={targetSpherical}
          onCameraRotationChange={setCameraRotation}
          showAxes={showAxes}
          showGrid={showGrid}
        />
      </div>

      {/* Header - floating */}
      <header className="absolute top-0 left-0 right-0 px-4 py-3 flex items-center justify-between pointer-events-none">
        {/* Hamburger Menu */}
        <div className="relative pointer-events-auto">
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="p-1.5 rounded-md bg-zinc-900/80 backdrop-blur border border-zinc-700/50 hover:bg-zinc-800/80 transition-colors"
          >
            <svg className="w-4 h-4 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          
          {/* Dropdown Menu */}
          {isMenuOpen && (
            <div className="absolute top-full left-0 mt-1 w-36 bg-zinc-900/95 backdrop-blur-xl border border-zinc-700/50 rounded-lg shadow-xl overflow-hidden">
              <div className="p-1.5 space-y-0.5">
                <button
                  onClick={() => setShowAxes(!showAxes)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800/80 transition-colors text-xs"
                >
                  <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${showAxes ? 'bg-green-500 border-green-500' : 'border-zinc-600'}`}>
                    {showAxes && <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                  </div>
                  <span className="text-zinc-300">Show Axes</span>
                </button>
                <button
                  onClick={() => setShowGrid(!showGrid)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800/80 transition-colors text-xs"
                >
                  <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${showGrid ? 'bg-green-500 border-green-500' : 'border-zinc-600'}`}>
                    {showGrid && <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                  </div>
                  <span className="text-zinc-300">Show Grid</span>
                </button>
                <button
                  onClick={() => setShowViewCube(!showViewCube)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800/80 transition-colors text-xs"
                >
                  <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${showViewCube ? 'bg-green-500 border-green-500' : 'border-zinc-600'}`}>
                    {showViewCube && <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                  </div>
                  <span className="text-zinc-300">View Cube</span>
                </button>
                
                {/* Divider */}
                <div className="h-px bg-zinc-700/50 my-1" />
                
                {/* Auto Rotate Toggle */}
                <button
                  onClick={() => setAutoRotate(!autoRotate)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800/80 transition-colors text-xs"
                >
                  <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${autoRotate ? 'bg-green-500 border-green-500' : 'border-zinc-600'}`}>
                    {autoRotate && <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                  </div>
                  <span className="text-zinc-300">Auto Rotate</span>
                </button>
                
                {/* Speed Slider - only visible when auto-rotate is on */}
                {autoRotate && (
                  <div className="px-2 py-1.5">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-zinc-500">Speed</span>
                      <span className="text-[10px] text-zinc-400 tabular-nums">{autoRotateSpeed.toFixed(1)}x</span>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="5"
                      step="0.1"
                      value={autoRotateSpeed}
                      onChange={(e) => setAutoRotateSpeed(parseFloat(e.target.value))}
                      className="w-full h-1 bg-zinc-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-zinc-300 [&::-webkit-slider-thumb]:hover:bg-white [&::-webkit-slider-thumb]:transition-colors"
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Logo */}
        <div className="pointer-events-auto absolute left-1/2 -translate-x-1/2">
          <img 
            src="/logo.png" 
            alt="Manifold" 
            className="h-10 w-44 rounded-lg"
          />
        </div>

        {/* Spacer for flex balance */}
        <div className="w-7" />
      </header>

      {/* Top Right Controls - ViewCube */}
      {showViewCube && (
        <div className="absolute top-3 right-4 pointer-events-auto">
          <ViewCube 
            onViewChange={handleViewChange} 
            cameraRotation={cameraRotation}
            onDragRotate={handleDragRotate}
            showAxes={showAxes}
          />
        </div>
      )}

      {/* Empty state */}
      {voxels.length === 0 && !meshData && !glbData && !isStreaming && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center -mt-20">
            <div className="w-3 h-3 mx-auto mb-4 rounded-full bg-zinc-700 shadow-[0_0_20px_4px_rgba(82,82,91,0.3)]" />
            <p className="text-xs text-zinc-600 tracking-widest uppercase">
              Upload an image or describe what you want...
            </p>
          </div>
        </div>
      )}

      {/* Bottom Toolbar - floating */}
      <BottomToolbar
        isStreaming={isStreaming}
        progress={progress}
        currentStage={currentStage}
        glbUrl={glbUrl}
        onStart={startStream}
        onCancel={cancelStream}
        onOpenLogs={() => setIsLogPanelOpen(true)}
        logCount={logs.length}
      />

      {/* Log Panel (slide-out drawer) */}
      <LogPanel
        logs={logs}
        isOpen={isLogPanelOpen}
        onClose={() => setIsLogPanelOpen(false)}
      />

      {/* Built with fal badge */}
      <a
        href="https://fal.ai"
        target="_blank"
        rel="noopener noreferrer"
        className="absolute bottom-4 right-4 px-2.5 py-1.5 rounded-md bg-zinc-900/80 backdrop-blur border border-zinc-700/50 text-xs text-zinc-500 hover:text-zinc-300 transition-colors pointer-events-auto"
      >
        Built with <span className="font-semibold text-zinc-400">fal</span>
      </a>
    </div>
  );
}
