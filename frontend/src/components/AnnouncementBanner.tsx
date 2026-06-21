import { useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";

export function AnnouncementBanner() {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <div className="relative w-full bg-[#0a1733] text-white">
      <Link
        to="/competitions"
        className="block w-full py-2.5 px-10 text-center text-sm font-semibold text-white hover:text-blue-200 transition-colors no-underline"
      >
        <span aria-hidden="true" className="mr-2">✦</span>
        BrickBuilder Brickworld 2026 competition live!
        <span aria-hidden="true" className="ml-2">✦</span>
      </Link>
      <button
        type="button"
        onClick={() => setVisible(false)}
        aria-label="Dismiss announcement"
        className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center justify-center text-white/70 hover:text-white transition-colors bg-transparent border-none cursor-pointer p-1"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export default AnnouncementBanner;
