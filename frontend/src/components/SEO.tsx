import { Helmet } from 'react-helmet-async';

interface SEOProps {
  title?: string;
  description?: string;
  keywords?: string;
  image?: string;
  url?: string;
  type?: string;
  noIndex?: boolean;
}

export function SEO({
  title = "BrickBuilder AI",
  description = "Turn images and text into LEGO compatible brick models. Get building instructions instantly!",
  keywords = "use ai to build legos, image to lego, how to convert image to legos, lego ai, brick ai, brickai, brickbuilder, brickbuilder.ai, lego building ai, ai building lego, turn images into lego, AI lego converter, brick model generator, turn images into actual legos, lego building software, lego generator, lego instruction generator, lego ai agent",
  image = "https://brickbuilder.ai/twitter-preview.png",
  url = "https://brickbuilder.ai/",
  type = "website",
  noIndex = false
}: SEOProps) {
  const structuredData = {
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
      {/* Primary Meta Tags */}
      <title>{title}</title>
      <meta name="title" content={title} />
      <meta name="description" content={description} />
      <meta name="keywords" content={keywords} />
      {noIndex && <meta name="robots" content="noindex, nofollow" />}
      
      {/* Open Graph / Facebook */}
      <meta property="og:type" content={type} />
      <meta property="og:url" content={url} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={image} />
      <meta property="og:site_name" content="BrickBuilder AI" />
      
      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:url" content={url} />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={image} />
      
      {/* Canonical URL */}
      <link rel="canonical" href={url} />
      
      {/* Structured Data */}
      <script type="application/ld+json">
        {JSON.stringify(structuredData, null, 2)}
      </script>
    </Helmet>
  );
}