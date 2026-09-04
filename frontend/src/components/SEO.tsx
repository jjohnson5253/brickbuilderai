import { useEffect } from 'react';
import { Helmet } from 'react-helmet-async';

interface SEOProps {
  title?: string;
  description?: string;
  keywords?: string;
  image?: string;
  url?: string;
  type?: string;
  noIndex?: boolean;
  structuredData?: Record<string, unknown> | Record<string, unknown>[];
}

export function SEO({
  title = "BrickBuilder AI",
  description = "Turn images and text into LEGO compatible brick models. Get building instructions instantly!",
  keywords = "use ai to build legos, image to lego, how to convert image to legos, lego ai, brick ai, brickai, brickbuilder, brickbuilder.ai, lego building ai, ai building lego, turn images into lego, AI lego converter, brick model generator, turn images into actual legos, lego building software, lego generator, lego instruction generator, lego ai agent",
  image = "https://brickbuilder.ai/twitter-preview.png",
  url = "https://brickbuilder.ai/",
  type = "website",
  noIndex = false,
  structuredData
}: SEOProps) {
  useEffect(() => {
    const upsertMeta = (selector: string, attributes: Record<string, string>) => {
      const existing = Array.from(document.head.querySelectorAll<HTMLMetaElement>(selector));
      const primary = existing[0] ?? document.createElement('meta');

      Object.entries(attributes).forEach(([key, value]) => {
        primary.setAttribute(key, value);
      });

      if (!primary.parentElement) {
        document.head.appendChild(primary);
      }

      existing.slice(1).forEach((element) => element.remove());
    };

    document.title = title;
    upsertMeta('meta[name="title"]', { name: 'title', content: title });
    upsertMeta('meta[name="description"]', { name: 'description', content: description });
    upsertMeta('meta[name="keywords"]', { name: 'keywords', content: keywords });
    upsertMeta('meta[property="og:type"]', { property: 'og:type', content: type });
    upsertMeta('meta[property="og:url"]', { property: 'og:url', content: url });
    upsertMeta('meta[property="og:title"]', { property: 'og:title', content: title });
    upsertMeta('meta[property="og:description"]', { property: 'og:description', content: description });
    upsertMeta('meta[property="og:image"]', { property: 'og:image', content: image });
    upsertMeta('meta[property="og:site_name"]', { property: 'og:site_name', content: 'BrickBuilder AI' });
    upsertMeta('meta[name="twitter:card"]', { name: 'twitter:card', content: 'summary_large_image' });
    upsertMeta('meta[name="twitter:url"]', { name: 'twitter:url', content: url });
    upsertMeta('meta[name="twitter:title"]', { name: 'twitter:title', content: title });
    upsertMeta('meta[name="twitter:description"]', { name: 'twitter:description', content: description });
    upsertMeta('meta[name="twitter:image"]', { name: 'twitter:image', content: image });

    const canonicals = Array.from(document.head.querySelectorAll<HTMLLinkElement>('link[rel="canonical"]'));
    const canonical = canonicals[0] ?? document.createElement('link');
    canonical.setAttribute('rel', 'canonical');
    canonical.setAttribute('href', url);
    if (!canonical.parentElement) {
      document.head.appendChild(canonical);
    }
    canonicals.slice(1).forEach((element) => element.remove());

    const robots = document.head.querySelector<HTMLMetaElement>('meta[name="robots"]');
    if (noIndex) {
      upsertMeta('meta[name="robots"]', { name: 'robots', content: 'noindex, nofollow' });
    } else if (robots?.getAttribute('content') === 'noindex, nofollow') {
      robots.remove();
    }
  }, [description, image, keywords, noIndex, title, type, url]);

  const defaultStructuredData = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    "name": "BrickBuilder AI",
    "alternateName": ["Image to LEGO Brick Converter", "LEGO AI", "Brick AI", "BrickAI", "AI LEGO Builder", "Turn Images Into LEGO"],
    "description": description,
    "url": url,
    "applicationCategory": "DesignApplication",
    "operatingSystem": "Web Browser",
    "offers": {
      "@type": "Offer",
      "price": "0",
      "priceCurrency": "USD",
      "availability": "https://schema.org/InStock"
    },
    "creator": {
      "@type": "Organization",
      "name": "BrickBuilder AI",
      "url": "https://brickbuilder.ai"
    },
    "featureList": [
        "AI-powered LEGO brick conversion",
        "Turn images into actual LEGO models",
        "Brick AI building assistant",
        "3D LEGO model visualization",
        "Building instructions generation",
        "LDR file download",
        "Real-time AI processing"
      ],
    "screenshot": image,
    "softwareVersion": "Beta 1.0",
    "datePublished": "2025-10-06",
    "inLanguage": "en-US"
  };

  return (
    <Helmet>
      {/* Structured Data */}
      <script type="application/ld+json">
        {JSON.stringify(structuredData ?? defaultStructuredData, null, 2)}
      </script>
    </Helmet>
  );
}
