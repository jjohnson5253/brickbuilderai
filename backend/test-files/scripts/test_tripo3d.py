#!/usr/bin/env python3
"""
Test script for Tripo3D API - Image to Model generation
Uploads batman.png and generates a 3D model using Turbo-v1.0-20250506
"""

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.getenv("TRIPO3D_API_KEY")
if not API_KEY:
    raise ValueError("TRIPO3D_API_KEY environment variable not set")

BASE_URL = "https://api.tripo3d.ai/v2/openapi"
IMAGE_PATH = "./test-files/png/batman.png"

# Headers for API requests
headers = {
    "Authorization": f"Bearer {API_KEY}",
}


def upload_image(image_path: str) -> str:
    """
    Upload an image to Tripo3D and return the file_token.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        file_token: Token to reference the uploaded file
    """
    print(f"📤 Uploading image: {image_path}")
    
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    upload_url = f"{BASE_URL}/upload"
    
    with open(image_path, "rb") as f:
        files = {"file": (Path(image_path).name, f, "image/png")}
        response = requests.post(upload_url, headers=headers, files=files)
    
    response.raise_for_status()
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Upload failed: {data}")
    
    file_token = data["data"]["image_token"]
    print(f"✅ Upload successful! File token: {file_token}")
    return file_token


def create_image_to_model_task(file_token: str) -> str:
    """
    Create an image-to-model generation task.
    
    Args:
        file_token: Token from the uploaded image
        
    Returns:
        task_id: ID of the generation task
    """
    print(f"\n🚀 Creating image-to-model task...")
    
    task_url = f"{BASE_URL}/task"
    
    payload = {
        "type": "image_to_model",
        "model_version": "Turbo-v1.0-20250506",
        "file": {
            "type": "png",
            "file_token": file_token
        }
    }
    
    response = requests.post(
        task_url,
        headers={**headers, "Content-Type": "application/json"},
        json=payload
    )
    
    # Try to get JSON response even on error
    try:
        data = response.json()
        print(f"   Response: {data}")
    except:
        data = None
    
    if response.status_code != 200:
        error_msg = f"HTTP {response.status_code}: {response.reason}"
        if data:
            error_msg += f"\n   API Response: {data}"
        raise Exception(error_msg)
    
    if data and data.get("code") != 0:
        raise Exception(f"Task creation failed: {data}")
    
    task_id = data["data"]["task_id"]
    print(f"✅ Task created! Task ID: {task_id}")
    return task_id


def get_task_status(task_id: str) -> dict:
    """
    Get the status of a task.
    
    Args:
        task_id: ID of the task to check
        
    Returns:
        Task status data
    """
    status_url = f"{BASE_URL}/task/{task_id}"
    response = requests.get(status_url, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Failed to get task status: {data}")
    
    return data["data"]


def wait_for_task_completion(task_id: str, max_wait_time: int = 300) -> dict:
    """
    Poll the task status until it completes or times out.
    
    Args:
        task_id: ID of the task to monitor
        max_wait_time: Maximum time to wait in seconds
        
    Returns:
        Final task data
    """
    print(f"\n⏳ Waiting for task completion...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        task_data = get_task_status(task_id)
        status = task_data.get("status")
        
        print(f"   Status: {status}", end="\r")
        
        if status == "success":
            print(f"\n✅ Task completed successfully!")
            return task_data
        elif status == "failed":
            print(f"\n❌ Task failed!")
            print(f"   Error: {task_data.get('error', 'Unknown error')}")
            return task_data
        elif status in ["queued", "running"]:
            time.sleep(2)  # Poll every 2 seconds
        else:
            print(f"\n⚠️  Unknown status: {status}")
            time.sleep(2)
    
    print(f"\n⏱️  Timeout after {max_wait_time} seconds")
    return get_task_status(task_id)


def download_model(task_data: dict, output_dir: str = "./output") -> None:
    """
    Download the generated model files.
    
    Args:
        task_data: Task data containing output information
        output_dir: Directory to save the downloaded files
    """
    output = task_data.get("output", {})
    
    if not output:
        print("⚠️  No output data available")
        return
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Download model file (GLB)
    model_url = output.get("model")
    if model_url:
        print(f"\n📥 Downloading model...")
        response = requests.get(model_url)
        response.raise_for_status()
        
        output_path = Path(output_dir) / "batman_tripo3d.glb"
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Model saved to: {output_path}")
    
    # Download rendered image if available
    rendered_image_url = output.get("rendered_image")
    if rendered_image_url:
        print(f"\n📥 Downloading rendered image...")
        response = requests.get(rendered_image_url)
        response.raise_for_status()
        
        output_path = Path(output_dir) / "batman_tripo3d_render.png"
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Rendered image saved to: {output_path}")


def main():
    """Main execution flow."""
    print("=" * 60)
    print("Tripo3D API Test - Image to Model")
    print("=" * 60)
    
    try:
        # Step 1: Upload image
        file_token = upload_image(IMAGE_PATH)
        
        # Step 2: Create generation task
        task_id = create_image_to_model_task(file_token)
        
        # Step 3: Wait for completion
        task_data = wait_for_task_completion(task_id)
        
        # Step 4: Download results if successful
        if task_data.get("status") == "success":
            download_model(task_data)
            
            print("\n" + "=" * 60)
            print("✅ SUCCESS - Model generated and downloaded!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print(f"❌ Task ended with status: {task_data.get('status')}")
            print("=" * 60)
        
        # Print full task data for reference
        print("\n📋 Full task data:")
        import json
        print(json.dumps(task_data, indent=2))
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
