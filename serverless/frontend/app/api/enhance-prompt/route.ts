import { NextRequest, NextResponse } from "next/server";

const GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions";

// Text-only: enhance prompt for image generation + get segmentation label
const TEXT_SYSTEM_PROMPT = `You are a prompt engineer specializing in text-to-image generation and 3D object segmentation.

When given a user's description, you must return a JSON object with exactly two fields:
1. "imagePrompt": An enhanced, detailed prompt optimized for generating a single, well-lit, centered object image suitable for 3D reconstruction. The object should be on a clean, neutral background. Add details about materials, lighting, and composition. Keep it concise but descriptive.
2. "segmentationPrompt": A simple 1-3 word label identifying the main object in the image (e.g., "car", "wooden chair", "red sneaker"). This will be used for object segmentation.

IMPORTANT: Return ONLY valid JSON, no markdown, no explanation.`;

// Vision: analyze image + user text to get segmentation label
const VISION_SYSTEM_PROMPT = `You are an expert at identifying objects in images for 3D segmentation.

Given an image and optionally a user's description, identify the main object that should be extracted for 3D reconstruction.

Return a JSON object with exactly one field:
1. "segmentationPrompt": A simple 1-3 word label identifying the main object in the image (e.g., "car", "wooden chair", "red sneaker"). Be specific but concise.

If the user provides a description, use it to help identify what they want to segment. If not, identify the most prominent object.

IMPORTANT: Return ONLY valid JSON, no markdown, no explanation.`;

export async function POST(request: NextRequest) {
  const groqApiKey = process.env.GROQ_API_KEY;

  if (!groqApiKey) {
    return NextResponse.json(
      { error: "GROQ_API_KEY not configured" },
      { status: 500 }
    );
  }

  try {
    const { prompt, imageUrl } = await request.json();

    // Vision mode: analyze image to get segmentation prompt
    if (imageUrl) {
      const response = await fetch(GROQ_API_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${groqApiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "meta-llama/llama-4-scout-17b-16e-instruct",
          messages: [
            { role: "system", content: VISION_SYSTEM_PROMPT },
            {
              role: "user",
              content: [
                {
                  type: "text",
                  text: prompt
                    ? `The user wants to extract: "${prompt}". Identify the object.`
                    : "Identify the main object in this image for 3D segmentation.",
                },
                {
                  type: "image_url",
                  image_url: { url: imageUrl },
                },
              ],
            },
          ],
          temperature: 0.3,
          max_tokens: 100,
          response_format: { type: "json_object" },
        }),
      });

      if (!response.ok) {
        const error = await response.text();
        console.error("Groq Vision API error:", error);
        // Fallback to user prompt
        return NextResponse.json({
          segmentationPrompt: prompt || "object",
        });
      }

      const data = await response.json();
      const content = data.choices?.[0]?.message?.content;

      try {
        const parsed = JSON.parse(content);
        return NextResponse.json({
          segmentationPrompt: parsed.segmentationPrompt || prompt || "object",
        });
      } catch {
        return NextResponse.json({
          segmentationPrompt: prompt || "object",
        });
      }
    }

    // Text mode: enhance prompt for image generation
    if (!prompt || typeof prompt !== "string") {
      return NextResponse.json(
        { error: "Missing or invalid prompt" },
        { status: 400 }
      );
    }

    const response = await fetch(GROQ_API_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${groqApiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "llama-3.3-70b-versatile",
        messages: [
          { role: "system", content: TEXT_SYSTEM_PROMPT },
          { role: "user", content: prompt },
        ],
        temperature: 0.7,
        max_tokens: 500,
        response_format: { type: "json_object" },
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: `Groq API error: ${error}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;

    if (!content) {
      return NextResponse.json(
        { error: "No response from Groq" },
        { status: 500 }
      );
    }

    try {
      const parsed = JSON.parse(content);
      return NextResponse.json({
        imagePrompt: parsed.imagePrompt || prompt,
        segmentationPrompt: parsed.segmentationPrompt || prompt,
      });
    } catch {
      return NextResponse.json({
        imagePrompt: prompt,
        segmentationPrompt: prompt,
      });
    }
  } catch (error) {
    console.error("Enhance prompt error:", error);
    return NextResponse.json(
      { error: "Failed to enhance prompt" },
      { status: 500 }
    );
  }
}
