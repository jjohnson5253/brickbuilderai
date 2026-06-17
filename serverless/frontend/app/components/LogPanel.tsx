"use client";

import { useEffect, useRef } from "react";
import type { LogEntry } from "../lib/types";
import { STAGE_COLORS } from "../lib/constants";

interface LogPanelProps {
  logs: LogEntry[];
  isOpen: boolean;
  onClose: () => void;
}

export default function LogPanel({ logs, isOpen, onClose }: LogPanelProps) {
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (isOpen && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, isOpen]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 bottom-0 w-96 bg-zinc-900 border-l border-zinc-800 z-50 flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <h2 className="text-sm font-semibold text-zinc-200">Stream Logs</h2>
          <button
            onClick={onClose}
            className="p-1.5 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 rounded-md transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Logs */}
        <div className="flex-1 overflow-y-auto p-4 space-y-1 text-xs font-mono">
          {logs.length === 0 ? (
            <div className="text-zinc-600 text-center py-8">
              No logs yet...
            </div>
          ) : (
            logs.map((log) => (
              <div
                key={log.id}
                className={`py-1.5 px-2 rounded ${
                  log.type === "error"
                    ? "bg-red-500/10 text-red-400"
                    : log.type === "success"
                    ? "bg-emerald-500/10 text-emerald-400"
                    : log.type === "data"
                    ? "bg-cyan-500/10 text-cyan-300"
                    : "text-zinc-400"
                }`}
              >
                <span className="text-zinc-600">
                  [{log.timestamp.toLocaleTimeString()}]
                </span>{" "}
                <span className={STAGE_COLORS[log.stage] || "text-zinc-500"}>
                  [{log.stage}]
                </span>{" "}
                {log.message}
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-zinc-800 text-xs text-zinc-500">
          {logs.length} log entries
        </div>
      </div>
    </>
  );
}

