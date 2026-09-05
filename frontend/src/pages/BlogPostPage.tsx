import posthog from "posthog-js";
import { ArrowLeft, LayoutDashboard } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";

import { ProfileMenu } from "../components/ProfileMenu";
import { SEO } from "../components/SEO";
import { SiteFooter } from "../components/SiteFooter";
import { blogPosts } from "../content/blogPosts";

const siteUrl = "https://brickbuilder.ai";

export default function BlogPostPage() {
  const { slug } = useParams();
  const post = blogPosts.find((candidate) => candidate.slug === slug);

  if (!post) {
    return <Navigate to="/blog" replace />;
  }

  const articleUrl = `${siteUrl}/blog/${post.slug}`;
  const imageUrl = `${siteUrl}${post.image}`;
  const structuredData = [
    {
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      headline: post.title,
      description: post.description,
      image: imageUrl,
      datePublished: post.date,
      dateModified: post.date,
      author: {
        "@type": "Organization",
        name: "BrickBuilder AI",
        url: siteUrl,
      },
      publisher: {
        "@type": "Organization",
        name: "BrickBuilder AI",
        logo: {
          "@type": "ImageObject",
          url: `${siteUrl}/brickbuilder-logo.PNG`,
        },
      },
      mainEntityOfPage: {
        "@type": "WebPage",
        "@id": articleUrl,
      },
    },
    {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: post.faq.map((item) => ({
        "@type": "Question",
        name: item.question,
        acceptedAnswer: {
          "@type": "Answer",
          text: item.answer,
        },
      })),
    },
  ];

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <SEO
        title={`${post.title} | BrickBuilder AI`}
        description={post.description}
        keywords={post.keywords.join(", ")}
        image={imageUrl}
        url={articleUrl}
        type="article"
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

        <main className="flex-1 py-10 sm:py-14">
          <article className="mx-auto max-w-3xl">
            <Link
              to="/blog"
              className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition-colors hover:text-[#f44336]"
            >
              <ArrowLeft className="h-4 w-4" />
              Blog
            </Link>

            <header className="mt-8 border-b border-slate-200 pb-9">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#f44336]">
                {post.category}
              </p>
              <h1 className="mt-3 text-4xl font-extrabold leading-tight text-slate-950 sm:text-5xl">
                {post.title}
              </h1>
              <p className="mt-5 text-lg leading-8 text-slate-600">{post.intro}</p>
              <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-500">
                <span>BrickBuilder AI</span>
                <span aria-hidden="true">/</span>
                <time dateTime={post.date}>{post.dateDisplay}</time>
              </div>
            </header>

            <figure className="my-8">
              <img
                src={post.image}
                alt={post.imageAlt}
                className="aspect-[16/9] w-full rounded-lg border border-slate-200 object-cover"
              />
            </figure>

            <div className="mt-10 space-y-11">
              {post.sections.map((section) => (
                <section key={section.heading}>
                  <h2 className="text-2xl font-bold leading-tight text-slate-950">
                    {section.heading}
                  </h2>
                  <div className="mt-4 space-y-4 text-base leading-8 text-slate-700">
                    {section.paragraphs.map((paragraph) => (
                      <p key={paragraph}>{paragraph}</p>
                    ))}
                  </div>
                </section>
              ))}
            </div>

            <section className="mt-12 border-t border-slate-200 pt-9">
              <h2 className="text-2xl font-bold leading-tight text-slate-950">
                Frequently asked questions
              </h2>
              <div className="mt-6 space-y-7">
                {post.faq.map((item) => (
                  <div key={item.question}>
                    <h3 className="text-lg font-bold text-slate-950">{item.question}</h3>
                    <p className="mt-2 text-base leading-7 text-slate-700">{item.answer}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-12 rounded-xl bg-slate-50 p-6 sm:p-8">
              <h2 className="text-2xl font-bold text-slate-950">
                Create your own brick model
              </h2>
              <p className="mt-3 leading-7 text-slate-700">
                Turn an image or prompt into a LEGO-compatible model with BrickBuilder AI.
              </p>
              <Link
                to="/"
                onClick={() =>
                  posthog.capture("blog_generate_model_clicked", { blog_slug: post.slug })
                }
                className="mt-5 inline-flex h-11 items-center justify-center rounded-md bg-[#f44336] px-5 text-sm font-semibold text-white transition-colors hover:bg-red-600"
              >
                Generate a model
              </Link>
            </section>

            <p className="mt-10 text-sm leading-6 text-slate-500">
              LEGO is a trademark of the LEGO Group, which does not sponsor,
              authorize, or endorse this site.
            </p>
          </article>
        </main>
        <SiteFooter />
      </div>
    </div>
  );
}
