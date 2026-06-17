import os
import logging
from typing import Optional
from datetime import datetime
from fastapi import HTTPException
from pydantic import BaseModel, EmailStr
import resend

# Import Supabase client
from ..utils.auth import supabase_client

# Configure logging
logger = logging.getLogger(__name__)


class SendWaitlistEmailRequest(BaseModel):
    email: EmailStr


class SendWaitlistEmailResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    email_sent: bool = False
    already_on_waitlist: bool = False


async def send_waitlist_email(
    request: SendWaitlistEmailRequest
) -> SendWaitlistEmailResponse:
    """
    Add email to waitlist in Supabase and send a welcome email using Resend
    
    Args:
        request: SendWaitlistEmailRequest containing the user's email
        
    Returns:
        SendWaitlistEmailResponse with success status and data
    """
    # Validate Supabase client
    if not supabase_client:
        logger.error("Supabase client is not initialized")
        raise HTTPException(
            status_code=500,
            detail="Database service is not properly configured"
        )
    
    # Validate Resend API key
    resend_api_key = os.getenv("RESEND_API_KEY")
    if not resend_api_key:
        logger.error("RESEND_API_KEY environment variable is not set")
        raise HTTPException(
            status_code=500,
            detail="Email service is not properly configured"
        )
    
    # Set the Resend API key
    resend.api_key = resend_api_key
    
    # Normalize email
    email = request.email.lower().strip()
    
    # Try to insert email into waitlist_emails table
    try:
        result = supabase_client.table('waitlist_emails').insert({
            'email': email,
            'created_at': datetime.utcnow().isoformat()
        }).execute()
        
        logger.info(f"Successfully added {email} to waitlist")
        
    except Exception as db_error:
        error_str = str(db_error)
        
        # Check if it's a duplicate email error (PostgreSQL unique constraint violation)
        if '23505' in error_str or 'duplicate' in error_str.lower() or 'unique' in error_str.lower():
            logger.info(f"Email {email} is already on the waitlist")
            return SendWaitlistEmailResponse(
                success=True,
                message="This email is already on the waitlist! You should receive updates from frlabs.dev - please check your promotions, spam, or other inbox sections.",
                already_on_waitlist=True,
                email_sent=False
            )
        else:
            # Some other database error occurred
            logger.error(f"Database error adding {email} to waitlist: {error_str}")
            raise HTTPException(
                status_code=500,
                detail="Failed to add email to waitlist. Please try again."
            )
    
    # Email successfully added to database, now send welcome email
    # Email HTML content
    email_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <div style="text-align: center; margin-bottom: 32px;">
            <div style="display: inline-flex; align-items: center; gap: 0px;">
              <span style="font-size: 32px; font-weight: 800; color: #ef4444; letter-spacing: -0.5px;">BRICK</span>
              <span style="font-size: 32px; font-weight: 800; color: #1e293b; letter-spacing: -0.5px;">BUILDER</span>
              <span style="font-size: 32px; font-weight: 800; color: #ef4444; letter-spacing: -0.5px;">.AI</span>
            </div>
          </div>
          
          <h2 style="color: #1e293b; margin-bottom: 16px;">Thanks for joining the BrickBuilder Waitlist!</h2>
          
          <div style="background-color: #f8fafc; padding: 24px; border-radius: 8px; margin-bottom: 24px;">
            <h3 style="color: #1e293b; margin-bottom: 12px;">What's coming:</h3>
            <ul style="color: #475569; line-height: 1.6;">
              <li>Generate 3D LEGO compatible models with text or image prompts</li>
              <li>Interactive building instructions</li>
              <li>Simple one-click parts purchasing</li>
            </ul>
          </div>
          
          <p style="color: #475569; line-height: 1.6; margin-bottom: 24px;">
            You'll be the first to know when we launch! Coming Q1 2026.
          </p>
          
          <p style="color: #475569; line-height: 1.6;">
            Best regards,<br>
            The BrickBuilder Team
          </p>
          
          <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 32px 0;">
          
          <p style="color: #94a3b8; font-size: 12px; text-align: center;">
            This email was sent to {email} because you signed up for the BrickBuilder waitlist.
          </p>
        </div>
    """
    
    try:
        params = {
            "from": "BrickBuilder <no-reply@info.brickbuilder.ai>",
            "to": [email],
            "subject": "Welcome to the BrickBuilder Waitlist!",
            "html": email_html,
        }
        
        email_response = resend.Emails.send(params)
        
        logger.info(f"Successfully sent waitlist email to {email}")
        
        return SendWaitlistEmailResponse(
            success=True,
            message="Successfully added to waitlist and welcome email sent!",
            email_sent=True,
            already_on_waitlist=False,
            data={"id": email_response.get("id") if isinstance(email_response, dict) else None}
        )
        
    except Exception as error:
        # Email failed to send, but they're still on the waitlist
        logger.error(f"Failed to send waitlist email to {email}: {str(error)}")
        
        return SendWaitlistEmailResponse(
            success=True,
            message="Successfully added to waitlist, but welcome email failed to send. You're still on the list!",
            email_sent=False,
            already_on_waitlist=False
        )
