import { Link } from "react-router-dom";
import { ArrowLeft, LayoutDashboard } from "lucide-react";

import { GlbUploadCard } from "../components/GlbUploadCard";
import { ProfileMenu } from "../components/ProfileMenu";
import { SEO } from "../components/SEO";
import { SiteFooter } from "../components/SiteFooter";

const faqs = [
  {
    question: "Can I convert a GLB file to a LEGO-compatible model?",
    answer:
      "Yes. Upload a .glb 3D model and BrickBuilder converts it into a brick model with a preview, parts list, and building files.",
  },
  {
    question: "Can I use this for OBJ to LEGO conversion?",
    answer:
      "This page currently accepts GLB uploads directly. If you have an OBJ file, export or convert it to GLB first, then upload the GLB here.",
  },
  {
    question: "What does 3D model to LEGO conversion include?",
    answer:
      "The converter voxelizes the 3D model, maps colors to available brick colors, optimizes the structure into bricks, and creates downloadable model files.",
  },
  {
    question: "Do I get instructions and a parts list?",
    answer:
      "After conversion, the generated model page can show the 3D brick model, building files, and a parts list for ordering or estimating the build.",
  },
];

const structuredData = [
  {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: "GLB to LEGO Converter",
    alternateName: [
      "3D Model to LEGO Converter",
      "GLB to Brick Model Converter",
      "OBJ to LEGO Converter",
      "3D to LEGO Converter",
    ],
    description:
      "Upload a GLB 3D model and convert it into a LEGO-compatible brick model with preview, parts list, and building files.",
    url: "https://brickbuilder.ai/glb-to-lego",
    applicationCategory: "DesignApplication",
    operatingSystem: "Web Browser",
    creator: {
      "@type": "Organization",
      name: "BrickBuilder AI",
      url: "https://brickbuilder.ai",
    },
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
    featureList: [
      "GLB to LEGO-compatible brick model conversion",
      "3D model to brick model conversion",
      "Brick color mapping",
      "3D brick model preview",
      "Parts list generation",
      "LDR and MPD building file generation",
    ],
  },
  {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  },
];

export default function GlbToLegoPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-white via-slate-50 to-white text-slate-900">
      <SEO
        title="GLB to LEGO Converter | 3D Model to LEGO | BrickBuilder AI"
        description="Convert a GLB 3D model into a LEGO-compatible brick model with preview, building files, and a parts list."
        keywords="glb to lego, glb to lego converter, 3d model to lego, 3d to lego, obj to lego, convert 3d model to lego, lego model converter, brick model generator"
        url="https://brickbuilder.ai/glb-to-lego"
        structuredData={structuredData}
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

        <main className="flex flex-1 flex-col items-center py-10 text-center sm:py-16">
          <div className="w-full max-w-3xl">
            <Link
              to="/"
              className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition-colors hover:text-[#f44336]"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Link>

            <h1 className="text-4xl font-extrabold leading-tight text-slate-900 sm:text-5xl">
              GLB to LEGO Converter
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-slate-600 sm:text-lg">
              Upload a GLB 3D model and convert it into a LEGO-compatible brick
              model. BrickBuilder turns 3D models into buildable brick files with
              a preview, color-mapped parts, and a parts list.
            </p>

            <div className="mx-auto flex justify-center">
              <GlbUploadCard />
            </div>

            <section className="mx-auto mt-12 max-w-3xl text-left">
              <h2 className="text-2xl font-bold text-slate-900">
                Convert 3D Models Into Bricks
              </h2>
              <div className="mt-4 space-y-4 text-sm leading-7 text-slate-600 sm:text-base">
                <p>
                  This GLB to LEGO converter is built for makers who already have
                  a 3D model and want a practical brick version of it. Upload a
                  `.glb` file, preview the source model, then generate a
                  LEGO-compatible build that can be opened on the generated model
                  page.
                </p>
                <p>
                  If you are searching for OBJ to LEGO or 3D model to LEGO tools,
                  export your model as GLB first and use this page as the
                  conversion step. GLB keeps mesh and material data together,
                  which makes it a good format for turning 3D designs into brick
                  models.
                </p>
              </div>
            </section>

            <section className="mx-auto mt-10 grid max-w-3xl gap-4 text-left sm:grid-cols-3">
              {[
                ["Upload GLB", "Choose a .glb model and inspect it in the browser before converting."],
                ["Generate Bricks", "Voxelize the model, map colors, and optimize the result into brick parts."],
                ["Build or Edit", "Open the generated model to view files, instructions, pricing, and parts."],
              ].map(([title, body]) => (
                <article key={title} className="rounded-lg border border-slate-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
                </article>
              ))}
            </section>

            <section className="mx-auto mt-12 max-w-3xl text-left">
              <h2 className="text-2xl font-bold text-slate-900">
                GLB to LEGO FAQ
              </h2>
              <div className="mt-4 divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
                {faqs.map((faq) => (
                  <article key={faq.question} className="p-5">
                    <h3 className="text-base font-semibold text-slate-900">
                      {faq.question}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {faq.answer}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          </div>
        </main>

        <SiteFooter />
      </div>
    </div>
  );
}
