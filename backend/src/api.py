import os
import logging

# Configure headless mode for Open3D before any imports
os.environ["DISPLAY"] = ":99"
os.environ["OPEN3D_HEADLESS"] = "1" 
os.environ["PYOPENGL_PLATFORM"] = "egl"

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from .requests.imageToBricks import image_to_bricks, image_to_bricks_stream, ImageToBricksRequest, ImageToBricksResponse
from .requests.textToBricks import text_to_bricks, text_to_bricks_stream, TextToBricksRequest
from .requests.ldrToBrickOwl import ldr_to_brickowl, LdrToBrickOwlRequest, LdrToBrickOwlResponse
from .requests.estimatePrice import estimate_price, EstimatePriceRequest, EstimatePriceResponse
from .requests.getPrice import get_price, GetPriceRequest, GetPriceResponse
from .requests.partToMpd import part_to_mpd, PartToMpdRequest, PartToMpdResponse
from .requests.ldrToMpd import ldr_to_mpd, LdrToMpdRequest, LdrToMpdResponse
from .requests.resizeModel import resize_model, ResizeModelRequest, ResizeModelResponse
from .requests.promptEditModel import prompt_edit_model, PromptEditModelRequest
from .requests.createCheckoutSession import create_checkout_session, CreateCheckoutSessionRequest, CreateCheckoutSessionResponse
from .requests.stripeWebhook import stripe_webhook, StripeWebhookRequest, StripeWebhookResponse
from .requests.getGeneration import get_generation, GetGenerationRequest, GetGenerationResponse
from .requests.getUserGenerations import get_user_generations, GetUserGenerationsRequest, GetUserGenerationsResponse
from .requests.getGenerationsByImage import get_generations_by_image, GetGenerationsByImageRequest, GetGenerationsByImageResponse
from .requests.getCommunityGenerations import get_community_generations, GetCommunityGenerationsRequest, GetCommunityGenerationsResponse
from .requests.updateModel import update_model, UpdateModelRequest, UpdateModelResponse
from .requests.updateLdrAndPartsList import update_ldr_and_parts_list, UpdateLdrAndPartsListRequest, UpdateLdrAndPartsListResponse
from .requests.sendWaitlistEmail import send_waitlist_email, SendWaitlistEmailRequest, SendWaitlistEmailResponse
from .requests.toggleIsCommunity import toggle_is_community, ToggleIsCommunityRequest, ToggleIsCommunityResponse
from .requests.claimGeneration import claim_generation, ClaimGenerationRequest, ClaimGenerationResponse
from .requests.updateGenerationName import update_generation_name, UpdateGenerationNameRequest, UpdateGenerationNameResponse
from .requests.updateImagePreview import update_image_preview, UpdateImagePreviewRequest, UpdateImagePreviewResponse
from .requests.updateUsername import update_username, UpdateUsernameRequest, UpdateUsernameResponse

# Import utilities
from .utils.pack_ldraw_model import LDrawPacker
from .utils.posthog_client import track_api_call
from .utils.auth import get_user_with_optional_auth, require_paid_auth

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress verbose httpx logs from fal.ai API requests
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(
    title="Image2Brick API",
    description="Convert text or images to brick building instructions",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:5174",  # Vite dev server (fallback port)
        "http://127.0.0.1:5174",
        "http://localhost:4173",  # Vite preview
        "http://127.0.0.1:4173",
        "https://brickai.frlabs.dev",  # Production Vercel domain
        "https://brickai-backend-production.up.railway.app",  # Railway production domain
        "https://brickai-backend-staging.up.railway.app",  # Railway staging domain
        "https://image2brick.com",  # New domain
        "https://img2brick.com",  # New domain
        "https://imagetobrick.com",  # New domain
        "https://prompt2brick.com",  # New domain
        "https://brickai-generations-viewer.vercel.app",  # Vercel viewer app
        "https://prompt2bricks.com",  # New domain
        "https://brickai-new-ui.vercel.app",  # New UI domain
        "https://brickbuilder.ai",
        "https://brickai-frontend.vercel.app",  # New UI domain
        "https://brickbuilderai-staging.vercel.app",
        "https://trybrickbuilder.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FAL_KEY = os.getenv("FAL_KEY")
if not FAL_KEY:
    raise ValueError("FAL_KEY environment variable is required")

# Set the FAL API key
os.environ["FAL_KEY"] = FAL_KEY

# Validate authentication configuration at startup
from .utils.auth import supabase_client, SUPABASE_ENABLED
if not SUPABASE_ENABLED:
    logger.warning(
        "Supabase is not configured. Running in anonymous mode without "
        "authentication. Set SUPABASE_URL and keys to enable it."
    )
else:
    pass  # Authentication system validated


@app.get("/")
async def health_check():
    """Health check endpoint"""
    track_api_call(endpoint="/", user_id="anonymous")
    return {"message": "brickai API is running"}


@app.get("/local-storage/{bucket}/{file_path:path}")
async def serve_local_storage(bucket: str, file_path: str):
    """Serve files stored by the local embedded storage fallback.

    Only relevant when Supabase is not configured (LOCAL_DB_ENABLED). Returns
    404 when local storage is not in use or the file does not exist.
    """
    from .utils import local_db

    root = local_db.STORAGE_ROOT
    if root is None:
        raise HTTPException(status_code=404, detail="Local storage not enabled")

    safe = os.path.normpath(file_path).lstrip("/")
    target = (root / bucket / safe).resolve()
    bucket_root = (root / bucket).resolve()
    if not str(target).startswith(str(bucket_root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(target)

@app.post("/imageToBricks")
async def imageToBricks_endpoint(
    request: ImageToBricksRequest = ImageToBricksRequest(),
    auth_info: dict = Depends(get_user_with_optional_auth)
):
    """
    Start image to brick conversion.
    If stream=True, returns an SSE stream with real-time SAM3D events + brick pipeline.
    Otherwise returns generation_id immediately for polling.
    """
    if request.stream:
        return await image_to_bricks_stream(request, auth_info)
    return await image_to_bricks(request, auth_info)


@app.post("/textToBricks")
async def textToBricks_endpoint(
    request: TextToBricksRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
):
    """
    Start text to brick conversion.
    If stream=True, returns an SSE stream with real-time SAM3D events + brick pipeline.
    Otherwise returns generation_id immediately for polling.
    """
    if request.stream:
        return await text_to_bricks_stream(request, auth_info)
    return await text_to_bricks(request, auth_info)


@app.post("/ldrToMpd", response_model=LdrToMpdResponse)
async def ldr_to_mpd_endpoint(
    request: LdrToMpdRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> LdrToMpdResponse:
    """Convert an LDR file to MPD format with all dependencies packed"""
    return await ldr_to_mpd(request, auth_info)


@app.post("/partToMpd", response_model=PartToMpdResponse)
async def part_to_mpd_endpoint(
    request: PartToMpdRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> PartToMpdResponse:
    """Convert an LDraw part number to MPD format with all dependencies packed"""
    return await part_to_mpd(request, auth_info)


@app.post("/ldrToBrickOwl", response_model=LdrToBrickOwlResponse)
async def ldr_to_brickowl_endpoint(
    request: LdrToBrickOwlRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
):
    """Create a BrickOwl wishlist from an LDR file"""
    return await ldr_to_brickowl(request, auth_info)


@app.post("/estimatePrice", response_model=EstimatePriceResponse)
async def estimate_price_endpoint(
    request: EstimatePriceRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
):
    """Estimate price for an LDR file using BrickOwl catalog prices"""
    return await estimate_price(request, auth_info)


@app.post("/getPrice", response_model=GetPriceResponse)
async def get_price_endpoint(
    request: GetPriceRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> GetPriceResponse:
    """Get price for a generation based on its parts list CSV"""
    return await get_price(request, auth_info)


@app.post("/resizeModel", response_model=ResizeModelResponse)
async def resize_model_endpoint(
    request: ResizeModelRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> ResizeModelResponse:
    """Resize an existing model by changing its voxel size"""
    return await resize_model(request, auth_info)


@app.post("/promptEditModel", response_model=ImageToBricksResponse)
async def prompt_edit_model_endpoint(
    request: PromptEditModelRequest,
    auth_info: dict = Depends(require_paid_auth)
) -> ImageToBricksResponse:
    """
    Start editing a model with a prompt. Returns new generation_id immediately.
    Poll GET /generation/{generation_id} for status and results.
    """
    return await prompt_edit_model(request, auth_info)


@app.post("/createCheckoutSession", response_model=CreateCheckoutSessionResponse)
async def create_checkout_session_endpoint(
    request: CreateCheckoutSessionRequest,
    auth_info: dict = Depends(get_user_with_optional_auth),
) -> CreateCheckoutSessionResponse:
    """Create a Stripe Checkout Session (mirrors api/create-checkout-session.js)

    This delegates to the `create_checkout_session` handler implemented in
    `src/components/requests/create_checkout_session.py` so you can drop that
    file into your backend and avoid running the Node server for checkout.
    """
    return await create_checkout_session(request, auth_info)


@app.post("/stripeWebhook", response_model=StripeWebhookResponse)
async def stripe_webhook_endpoint(
    request: Request,
    # Note: Stripe webhooks don't use authentication, they use signature verification
) -> StripeWebhookResponse:
    """Handle Stripe webhook events
    
    This endpoint receives webhook events from Stripe and processes them.
    No authentication is required as Stripe uses signature verification.
    """
    # Pass empty auth_info since webhooks don't use user authentication
    return await stripe_webhook(request, {})


@app.post("/getGeneration", response_model=GetGenerationResponse)
async def get_generation_endpoint(
    request: GetGenerationRequest
) -> GetGenerationResponse:
    """Get generation status and data by generation ID (POST version)"""
    return await get_generation(request)


@app.get("/generation/{generation_id}", response_model=GetGenerationResponse)
async def get_generation_by_id_endpoint(
    generation_id: str
) -> GetGenerationResponse:
    """Get generation status and data by generation ID (GET version for polling)"""
    request = GetGenerationRequest(generation_id=generation_id)
    return await get_generation(request)


@app.post("/getUserGenerations", response_model=GetUserGenerationsResponse)
async def get_user_generations_endpoint(
    request_body: GetUserGenerationsRequest = GetUserGenerationsRequest(),
    request: Request = None,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> GetUserGenerationsResponse:
    """Get all generations for the authenticated or anonymous user
    
    This endpoint retrieves all generations for the authenticated or anonymous user
    along with any associated orders from the orders table.
    
    If an authenticated user has anonymous generations from their current IP,
    those generations will be migrated to their authenticated account.
    """
    return await get_user_generations(request_body, auth_info, request)


@app.post("/getGenerationsByImage", response_model=GetGenerationsByImageResponse)
async def get_generations_by_image_endpoint(
    request_body: GetGenerationsByImageRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> GetGenerationsByImageResponse:
    """Get all generations for a specific processed_image_url and user_id
    
    This endpoint retrieves all edit iterations for a specific model by finding
    all generations that share the same processed_image_url.
    
    Useful for viewing edit history of a model.
    """
    return await get_generations_by_image(request_body, auth_info)


@app.post("/getCommunityGenerations", response_model=GetCommunityGenerationsResponse)
async def get_community_generations_endpoint(
    request_body: GetCommunityGenerationsRequest = GetCommunityGenerationsRequest(),
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> GetCommunityGenerationsResponse:
    """Get all generations flagged as community (is_community = true)

    Mirrors the pagination behavior of /getUserGenerations: results are
    deduplicated by processed_image_url (keeping the most recent per image),
    and support `limit`, `offset`, and `has_more` for paging.
    """
    return await get_community_generations(request_body, auth_info)


@app.post("/updateModel", response_model=UpdateModelResponse)
async def update_model_endpoint(
    request: UpdateModelRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> UpdateModelResponse:
    """Update a generation's xyzrgb file
    
    This endpoint uploads new xyzrgb content to Supabase storage
    and updates the xyzrgb_url for the given generation ID.
    """
    return await update_model(request, auth_info)


@app.post("/updateLdrAndPartsList", response_model=UpdateLdrAndPartsListResponse)
async def update_ldr_and_parts_list_endpoint(
    request: UpdateLdrAndPartsListRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> UpdateLdrAndPartsListResponse:
    """Update a generation's LDR file and parts list CSV
    
    This endpoint uploads new LDR content to Supabase storage,
    updates the ldr_url, generates a new parts list CSV,
    and updates the parts_list_csv_url for the given generation ID.
    """
    return await update_ldr_and_parts_list(request, auth_info)


@app.post("/sendWaitlistEmail", response_model=SendWaitlistEmailResponse)
async def send_waitlist_email_endpoint(
    request: SendWaitlistEmailRequest
) -> SendWaitlistEmailResponse:
    """Send a welcome email to a waitlist subscriber
    
    This endpoint sends a welcome email using Resend to users who join the waitlist.
    No authentication required.
    """
    return await send_waitlist_email(request)


@app.post("/toggleIsCommunity", response_model=ToggleIsCommunityResponse)
async def toggle_is_community_endpoint(
    request: ToggleIsCommunityRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> ToggleIsCommunityResponse:
    """Toggle the is_community flag for a generation

    Reads the current is_community value for the given generation_id from
    Supabase and flips it (true <-> false). A null/missing value is treated
    as false, so the first toggle will set it to true.
    """
    return await toggle_is_community(request, auth_info)


@app.post("/claimGeneration", response_model=ClaimGenerationResponse)
async def claim_generation_endpoint(
    request: ClaimGenerationRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> ClaimGenerationResponse:
    """Claim ownership of an anonymous generation for the authenticated user.

    Used after a logged-out visitor signs in to take ownership of a generation
    they created while anonymous (identified by generation_id), without relying
    on a fragile IP-hash match. Already-owned generations are a no-op; rows
    owned by a different authenticated user return 403.
    """
    return await claim_generation(request, auth_info)


@app.post("/updateGenerationName", response_model=UpdateGenerationNameResponse)
async def update_generation_name_endpoint(
    request: UpdateGenerationNameRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> UpdateGenerationNameResponse:
    """Update the name of a generation

    Requires the authenticated user to be the owner (user_id) of the
    generation row. Anonymous users are rejected with 401, and users who
    do not own the row receive 403.
    """
    return await update_generation_name(request, auth_info)


@app.post("/updateImagePreview", response_model=UpdateImagePreviewResponse)
async def update_image_preview_endpoint(
    request: UpdateImagePreviewRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> UpdateImagePreviewResponse:
    """Upload a preview image for a generation

    Stores the provided base64 image in Supabase Storage (same bucket as
    processed_image_url) and saves the resulting URL into the
    `preview_image_url` column on the generation row.

    Requires the authenticated user to be the owner (user_id) of the
    generation row. Anonymous users are rejected with 401, and users who
    do not own the row receive 403.
    """
    return await update_image_preview(request, auth_info)


@app.post("/updateUsername", response_model=UpdateUsernameResponse)
async def update_username_endpoint(
    request: UpdateUsernameRequest,
    auth_info: dict = Depends(get_user_with_optional_auth)
) -> UpdateUsernameResponse:
    """Update the username for the authenticated user

    Updates the `username` column on the authenticated user's row in the
    `user_profiles` table. Rejects anonymous users (401) and rejects
    usernames already taken by another user (409).
    """
    return await update_username(request, auth_info)


def main():
    """Main entry point for running the API server"""
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    main()