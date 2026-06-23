import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";

const ROTATION_INTERVAL_MS = 3500;

export function AnnouncementBanner() {
  const [visible, setVisible] = useState(true);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setIndex((prev) => (prev === 0 ? 1 : 0));
    }, ROTATION_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  if (!visible) return null;

  return (
    <div className="relative w-full bg-[#0a1733] text-white">
      <div className="grid">
        <div
          className={`col-start-1 row-start-1 block w-full py-2.5 px-10 text-center text-sm font-semibold text-white transition-opacity duration-700 ease-in-out ${
            index === 0 ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
        >
          <span aria-hidden="true" className="mr-2">✦</span>
          Summer sale: 50% off all orders! (June 22 - July 22)
          <span aria-hidden="true" className="ml-2">✦</span>
        </div>
        <Link
          to="/competitions"
          aria-hidden={index !== 1}
          className={`col-start-1 row-start-1 block w-full py-2.5 px-10 text-center text-sm font-semibold text-white hover:text-blue-200 transition-opacity duration-700 ease-in-out no-underline ${
            index === 1 ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
        >
          <span aria-hidden="true" className="mr-2">✦</span>
          Congrats to our Brickworld Competition Winners!
          <span aria-hidden="true" className="ml-2">✦</span>
        </Link>
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
