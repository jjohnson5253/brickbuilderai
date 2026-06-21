import { Link } from "react-router-dom";
import { ChevronLeft, Trophy, Gift, Mail } from "lucide-react";
import { SEO } from "../components/SEO";
import { SiteFooter } from "../components/SiteFooter";

export default function CompetitionsPage() {
  return (
    <>
      <SEO
        title="Competition | BrickBuilder AI"
        description="Enter the BrickBuilder Competition for a chance to win a $60 custom LEGO model. Submit your build to the Community Page by Sunday night!"
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

          <div className="flex items-center gap-3 mb-6">
            <Trophy className="h-8 w-8 text-[#f44336]" />
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
              BrickBuilder Competition
            </h1>
          </div>

          {/* Giveaway */}
          <div className="rounded-2xl bg-amber-50 border border-amber-200 p-6 mb-6">
            <div className="flex items-center gap-2 mb-1">
              <Gift className="h-6 w-6 text-amber-600" />
              <h2 className="text-xl font-extrabold text-amber-700">
                Giveaway! 🎉
              </h2>
            </div>
            <p className="text-2xl font-bold text-slate-900">
              Win a $60 Custom LEGO Model
            </p>
          </div>

          {/* Featured builds */}
          <div className="flex items-end justify-center gap-4 sm:gap-8 mb-8">
            <img
              src="/assets/mario.png"
              alt="LEGO Mario build"
              className="h-28 sm:h-40 w-auto object-contain drop-shadow-md"
            />
            <img
              src="/assets/pikachu.png"
              alt="LEGO Pikachu build"
              className="h-24 sm:h-36 w-auto object-contain drop-shadow-md"
            />
            <img
              src="/assets/goomba.png"
              alt="LEGO Goomba build"
              className="h-24 sm:h-36 w-auto object-contain drop-shadow-md"
            />
          </div>

          {/* Rules */}
          <div className="rounded-2xl bg-slate-50 border border-slate-200 p-6 mb-6">
            <h2 className="text-xl font-extrabold mb-4">Rules</h2>
            <ul className="space-y-3 text-lg text-slate-700">
              <li className="flex gap-3">
                <span className="text-[#f44336] font-bold">•</span>
                <span>
                  Post to the{" "}
                  <Link
                    to="/community"
                    className="text-[#f44336] font-semibold hover:underline"
                  >
                    Community Page
                  </Link>{" "}
                  by Sunday night June 21 11:59 PM CST
                </span>
              </li>
              <li className="flex gap-3">
                <span className="text-[#f44336] font-bold">•</span>
                <span>
                  Must scale down to{" "}
                  <span className="bg-yellow-200 font-bold px-1 rounded">
                    &lt; 600 bricks
                  </span>
                </span>
              </li>
              <li className="flex gap-3">
                <span className="text-[#f44336] font-bold">•</span>
                <span>Unlimited submissions allowed!</span>
              </li>
            </ul>
          </div>

          {/* Winners */}
          <div className="rounded-2xl bg-amber-50 border border-amber-200 p-6 flex items-center gap-3">
            <Mail className="h-6 w-6 text-amber-600 shrink-0" />
            <p className="text-lg font-bold text-amber-700">
              Top 3 models will receive an email Monday
            </p>
          </div>
        </div>
        <SiteFooter />
      </div>
    </>
  );
}
