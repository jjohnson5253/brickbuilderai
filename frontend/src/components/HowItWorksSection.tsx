import React from "react";
import { MessageSquare, Wand2, Package } from "lucide-react";
import { BRICKBUILDER_GITHUB_REPO_URL } from "../constants/urls";

export function HowItWorksSection() {
  const stepDelayClasses = ["landing-delay-2", "landing-delay-3", "landing-delay-4"];
  const steps = [
    {
      icon: MessageSquare,
      title: "Describe or upload",
      description: "Type a prompt like \"a pink elephant\" or drop in any image you want to build.",
    },
    {
      icon: Wand2,
      title: "BrickBuilder generates your model",
      description: "Our generative pipeline turns your idea into a buildable 3D brick model in seconds.",
    },
    {
      icon: Package,
      title: "Preview, edit, and order",
      description: "Make your edits, grab the instructions, and we'll ship the parts to your door in 8 days.",
    },
  ];

  return (
    <section
      id="how-it-works"
      className="w-full mt-24 mb-16 relative"
      style={{ zIndex: 15 }}
    >
      <div className="mx-auto max-w-5xl px-2">
        <div className="text-center landing-fade-in landing-delay-1">
          {/* <span className="inline-block rounded-full bg-slate-100 px-3 py-1 text-xs font-medium tracking-wide text-slate-600 uppercase">
            How it works
          </span> */}
          <h2 className="mt-4 text-3xl font-bold text-slate-900 sm:text-4xl">
            How It Works
          </h2>
          <p className="mt-3 text-base text-slate-600 max-w-2xl mx-auto">
            Turn images and text into custom 3D brick models. Edit freely, get instant instructions, and have the parts on your doorstep in 8 days.
          </p>
          <p className="mt-3 text-sm text-slate-600 max-w-2xl mx-auto">
            Want to learn the magic? See how BrickBuilder works and try running it yourself by exploring the code on{" "}
            <a
              href={BRICKBUILDER_GITHUB_REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-[#f44336] hover:text-[#d9372d] underline decoration-[#f44336]/30 underline-offset-2"
            >
              GitHub
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
            .
          </p>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3 md:gap-8 relative">
          {/* Connecting line behind cards on md+ */}
          <div
            aria-hidden
            className="hidden md:block absolute left-0 right-0 top-12 h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent"
          />

          {steps.map((step, i) => {
            const Icon = step.icon;
            return (
              <div
                key={step.title}
                className={`relative flex flex-col items-center text-center rounded-2xl border border-slate-200 bg-white/80 backdrop-blur-sm p-6 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 landing-fade-in ${stepDelayClasses[i] ?? "landing-delay-4"}`}
              >
                <div className="relative">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-[#f44336] to-[#ff6b6b] text-white shadow-md">
                    <Icon className="h-7 w-7" />
                  </div>
                  <span className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-white border border-slate-200 text-xs font-bold text-slate-700 shadow-sm">
                    {i + 1}
                  </span>
                </div>
                <h3 className="mt-5 text-lg font-semibold text-slate-900">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">
                  {step.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
