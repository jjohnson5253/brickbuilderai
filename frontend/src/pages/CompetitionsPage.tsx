import { Link } from "react-router-dom";
import { ChevronLeft, Trophy } from "lucide-react";
import { SEO } from "../components/SEO";
import { SiteFooter } from "../components/SiteFooter";

export default function CompetitionsPage() {
  return (
    <>
      <SEO
        title="Competitions | BrickBuilder AI"
        description="Join the BrickBuilder Brickworld 2026 competition and build with AI."
        url="https://brickbuilder.ai/competitions"
      />
      <div className="min-h-screen flex flex-col bg-white text-slate-900">
        <div className="flex-1 w-full max-w-3xl mx-auto px-6 py-8">
          <Link to="/" className="inline-flex items-center gap-2 group mb-8">
            <ChevronLeft className="h-5 w-5 text-slate-500 group-hover:text-[#f44336] group-hover:-translate-x-0.5 transition-all" />
            <span className="text-xl font-extrabold tracking-tight">
              <span className="text-[#ff4b4b]">BRICK</span>
              <span className="text-slate-900">BUILDER</span>
            </span>
          </Link>

          <div className="flex items-center gap-3 mb-4">
            <Trophy className="h-8 w-8 text-[#f44336]" />
            <h1 className="text-3xl font-extrabold tracking-tight">
              Brickworld 2026 Competition
            </h1>
          </div>

          <p className="text-lg text-slate-600 mb-6">
            The BrickBuilder Brickworld 2026 competition is now live! Build your
            best creation with BrickBuilder AI and enter for a chance to win.
          </p>

          <p className="text-slate-500">
            More details coming soon.
          </p>
        </div>
        <SiteFooter />
      </div>
    </>
  );
}
