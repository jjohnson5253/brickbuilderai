import { useState } from "react";
import { X } from "lucide-react";

export function AnnouncementBanner() {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <div className="relative w-full bg-[#0a1733] text-white">
      <div className="block w-full py-2.5 px-10 text-center text-sm font-semibold text-white">
        <span aria-hidden="true" className="mr-2">✦</span>
        Summer sale: 50% off all orders! (June 22 - July 22)
        <span aria-hidden="true" className="ml-2">✦</span>
      </div>
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
