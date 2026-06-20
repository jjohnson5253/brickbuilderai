import React, { useState, useRef } from 'react';
import { Loader2 } from 'lucide-react';

interface ResizeScalerProps {
  onResize: (detailLevel: number) => Promise<void>;
  disabled?: boolean;
  isResizing?: boolean;
  scaler?: number;
  onScalerChange?: (value: number) => void;
  hideHeader?: boolean;
}

export function ResizeScaler({ 
  onResize, 
  disabled = false, 
  isResizing = false, 
  scaler: externalScaler,
  onScalerChange,
  hideHeader = false
}: ResizeScalerProps) {
  const MIN = 10;
  const MAX = 60;
  const DEFAULT = 25;

  // The slider is presented to the user on a 1-100 scale, but the underlying
  // value passed around stays within [MIN, MAX]. These helpers convert between
  // the displayed (1-100) value and the actual scaler value.
  const DISPLAY_MIN = 1;
  const DISPLAY_MAX = 100;

  const toDisplay = (actual: number) =>
    Math.round(
      DISPLAY_MIN + ((actual - MIN) / (MAX - MIN)) * (DISPLAY_MAX - DISPLAY_MIN)
    );

  const toActual = (display: number) =>
    Math.round(
      MIN + ((display - DISPLAY_MIN) / (DISPLAY_MAX - DISPLAY_MIN)) * (MAX - MIN)
    );

  const [internalScaler, setInternalScaler] = useState<number>(DEFAULT);
  const trackRef = useRef<HTMLInputElement | null>(null);
  
  // Use external scaler if provided, otherwise use internal state
  const scaler = externalScaler !== undefined ? externalScaler : internalScaler;
  const displayScaler = toDisplay(scaler);

  const handleResize = async () => {
    if (disabled || isResizing) return;
    await onResize(scaler);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = toActual(parseInt(e.target.value, 10));
    if (onScalerChange) {
      onScalerChange(newValue);
    } else {
      setInternalScaler(newValue);
    }
  };

  return (
    <div className="w-full bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="p-4">
        <div className="space-y-4">
          {!hideHeader && (
            <div className="text-center">
              <h4 className="text-sm font-medium text-gray-700 mb-3">Resize Model</h4>
              <h6 className="text-xs font-medium text-gray-700 mb-3">Increase size to increase resolution</h6>
            </div>
          )}
          {/* Scaler line with draggable thumb (native range input for accessibility) */}
          <div className="px-4">
            <input
              aria-label="Model scaler"
              type="range"
              min={DISPLAY_MIN}
              max={DISPLAY_MAX}
              step={1}
              value={displayScaler}
              onChange={handleInputChange}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider:bg-red-500 slider:rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              ref={trackRef}
              disabled={disabled || isResizing}
            />
            <div className="flex justify-between text-xs text-gray-400 mt-2">
              <span>{DISPLAY_MIN}</span>
              <span className="text-sm font-medium text-gray-500">{displayScaler}</span>
              <span>{DISPLAY_MAX}</span>
            </div>

          </div>

          {/* Resize Action Button */}
          <div className="flex justify-center">
            <button
              onClick={handleResize}
              disabled={disabled || isResizing}
              className="inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-red-500 hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:bg-gray-400 disabled:cursor-not-allowed disabled:hover:bg-gray-400 transition-colors"
            >
              {isResizing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Resizing...
                </>
              ) : (
                'Resize'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}