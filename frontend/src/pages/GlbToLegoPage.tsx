import { Link } from "react-router-dom";
import { ArrowLeft, LayoutDashboard } from "lucide-react";

import { GlbUploadCard } from "../components/GlbUploadCard";
import { ProfileMenu } from "../components/ProfileMenu";
import { SEO } from "../components/SEO";
import { SiteFooter } from "../components/SiteFooter";

export default function GlbToLegoPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-white via-slate-50 to-white text-slate-900">
      <SEO
        title="GLB to LEGO Converter | BrickBuilder AI"
        description="Upload a GLB 3D model and convert it into a buildable brick model with BrickBuilder AI."
        url="https://brickbuilder.ai/glb-to-lego"
      />

      <div className="mx-auto flex min-h-screen w-full max-w-screen-xl flex-col px-4 pb-10 pt-6 sm:px-6 md:px-8 lg:px-10">
        <header className="flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2">
            <img
              src="/brickbuilder-logo.PNG"
              alt="BrickBuilder"
              className="h-8 w-auto object-contain"
            />
            <span className="hidden text-sm font-semibold text-slate-800 sm:inline">
              BrickBuilder
            </span>
          </Link>

          <nav className="flex items-center gap-2">
            <Link
              to="/dashboard"
              className="inline-flex h-10 w-10 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
              aria-label="Dashboard"
              title="Dashboard"
            >
              <LayoutDashboard className="h-5 w-5" />
            </Link>
            <ProfileMenu />
          </nav>
        </header>

        <main className="flex flex-1 flex-col items-center justify-center py-10 text-center sm:py-16">
          <div className="w-full max-w-3xl">
            <Link
              to="/"
              className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition-colors hover:text-[#f44336]"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Link>

            <h1 className="text-4xl font-extrabold leading-tight text-slate-900 sm:text-5xl">
              GLB to LEGO
            </h1>

            <div className="mx-auto flex justify-center">
              <GlbUploadCard />
            </div>
          </div>
        </main>

        <SiteFooter />
      </div>
    </div>
  );
}
