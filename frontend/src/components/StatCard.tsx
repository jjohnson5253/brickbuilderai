import React from 'react';

interface StatCardProps {
  actionLabel?: string;
  disabled?: boolean;
  icon: React.ReactNode;
  onClick?: () => void;
  sub: string;
  title: React.ReactNode;
}

export function StatCard({
  actionLabel,
  disabled = false,
  icon,
  onClick,
  sub,
  title,
}: StatCardProps) {
  const content = (
    <>
      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[#f44336]">
        <div className="text-black">{icon}</div>
      </div>

      <div className="min-w-0 flex-1 text-left">
        <div className="text-sm font-semibold text-slate-800">{title}</div>
        {sub && <div className="text-xs text-slate-500">{sub}</div>}
      </div>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        aria-label={actionLabel}
        disabled={disabled}
        onClick={onClick}
        className="relative flex w-full items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-150 hover:-translate-y-0.5 hover:border-[#f44336] hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-[#f44336] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0 disabled:hover:border-slate-200 disabled:hover:shadow-sm"
      >
        {content}
      </button>
    );
  }

  return (
    <div className="relative flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      {content}
    </div>
  );
}
