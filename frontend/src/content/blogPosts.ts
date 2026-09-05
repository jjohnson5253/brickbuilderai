import generatedPosts from "./blog-posts.json";

export interface BlogPost {
  slug: string;
  title: string;
  description: string;
  date: string;
  dateDisplay: string;
  keywords: string[];
  category: string;
  intro: string;
  image: string;
  imageAlt: string;
  sections: Array<{
    heading: string;
    paragraphs: string[];
  }>;
  faq: Array<{
    question: string;
    answer: string;
  }>;
}

export const blogPosts = generatedPosts satisfies BlogPost[];
