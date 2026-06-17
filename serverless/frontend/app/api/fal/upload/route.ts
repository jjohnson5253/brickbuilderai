import { NextRequest, NextResponse } from "next/server";

const FAL_STORAGE_URL = "https://rest.alpha.fal.ai/storage/upload/initiate";

export async function POST(request: NextRequest) {
  const falKey = process.env.FAL_KEY;

  if (!falKey) {
    return NextResponse.json(
      { error: "FAL_KEY not configured" },
      { status: 500 }
    );
  }

  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return NextResponse.json(
        { error: "No file provided" },
        { status: 400 }
      );
    }

    // Step 1: Initiate upload to get a pre-signed URL
    const initiateResponse = await fetch(
      `${FAL_STORAGE_URL}?storage_type=fal-cdn-v3`,
      {
        method: "POST",
        headers: {
          Authorization: `Key ${falKey}`,
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          content_type: file.type || "application/octet-stream",
          file_name: file.name,
        }),
      }
    );

    if (!initiateResponse.ok) {
      const errorText = await initiateResponse.text();
      return NextResponse.json(
        { error: `Upload initiation failed: ${errorText}` },
        { status: initiateResponse.status }
      );
    }

    const { upload_url, file_url } = await initiateResponse.json();

    // Step 2: Upload the file to the pre-signed URL
    const arrayBuffer = await file.arrayBuffer();
    const uploadResponse = await fetch(upload_url, {
      method: "PUT",
      headers: {
        "Content-Type": file.type || "application/octet-stream",
      },
      body: arrayBuffer,
    });

    if (!uploadResponse.ok) {
      const errorText = await uploadResponse.text();
      return NextResponse.json(
        { error: `File upload failed: ${errorText}` },
        { status: uploadResponse.status }
      );
    }

    return NextResponse.json({ url: file_url });
  } catch (error) {
    console.error("Upload error:", error);
    return NextResponse.json(
      { error: "Failed to upload file" },
      { status: 500 }
    );
  }
}
