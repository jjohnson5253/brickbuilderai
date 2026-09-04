import { describe, expect, it } from "vitest";

import { blogPosts } from "../src/content/blogPosts";

describe("blog posts", () => {
  it("provides unique, indexable article metadata", () => {
    expect(blogPosts.length).toBeGreaterThan(0);
    expect(new Set(blogPosts.map((post) => post.slug)).size).toBe(blogPosts.length);

    for (const post of blogPosts) {
      expect(post.slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
      expect(post.description.length).toBeGreaterThanOrEqual(120);
      expect(post.keywords).toContain("BrickBuilder AI");
      expect(post.sections.length).toBeGreaterThanOrEqual(5);
      expect(post.faq.length).toBeGreaterThanOrEqual(3);
    }
  });
});
