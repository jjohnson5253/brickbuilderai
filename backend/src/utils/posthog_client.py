"""
PostHog client configuration and event tracking utilities for BrickAI API.
"""

import os
import logging
from typing import Optional, Dict, Any
from posthog import Posthog
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class PostHogClient:
    """PostHog client wrapper for tracking API events."""
    
    def __init__(self):
        self.api_key = os.getenv("POSTHOG_API_KEY")
        self.host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")
        self.enabled = False  # PostHog tracking disabled
        
        if self.enabled:
            self.client = Posthog(
                project_api_key=self.api_key,
                host=self.host
            )
            # PostHog client initialized
        else:
            self.client = None
            logger.warning("PostHog client disabled - API key not configured")
    
    def track_event(self, event_name: str, user_id: Optional[str] = None, properties: Optional[Dict[str, Any]] = None):
        """Track an event with PostHog."""
        if not self.enabled:
            logger.debug(f"PostHog disabled - would track event: {event_name}")
            return
        
        try:
            # Use a default user_id if none provided
            if user_id is None:
                user_id = "anonymous"
            
            # Add default properties
            event_properties = {
                "service": "brickai-api",
                "environment": os.getenv("ENVIRONMENT", "development"),
                **(properties or {})
            }
            
            self.client.capture(
                distinct_id=user_id,
                event=event_name,
                properties=event_properties
            )
            
            # Event tracked
            
        except Exception as e:
            logger.error(f"Failed to track PostHog event '{event_name}': {e}")
    
    def identify_user(self, user_id: str, properties: Optional[Dict[str, Any]] = None):
        """Identify a user with PostHog."""
        if not self.enabled:
            logger.debug(f"PostHog disabled - would identify user: {user_id}")
            return
        
        try:
            self.client.identify(
                distinct_id=user_id,
                properties=properties or {}
            )
            logger.info(f"👤 Identified user: {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to identify user '{user_id}': {e}")
    
    def close(self):
        """Close the PostHog client connection."""
        if self.enabled and self.client:
            self.client.shutdown()
            logger.info("🔌 PostHog client connection closed")

# Global PostHog client instance
posthog_client = PostHogClient()

# Convenience functions for easy usage
def track_api_call(endpoint: str, user_id: Optional[str] = None, **properties):
    """Track an API call event."""
    posthog_client.track_event(
        event_name="api_call",
        user_id=user_id,
        properties={
            "endpoint": endpoint,
            **properties
        }
    )

def track_image_conversion(user_id: Optional[str] = None, **properties):
    """Track an image to brick conversion event."""
    posthog_client.track_event(
        event_name="image_to_bricks_conversion",
        user_id=user_id,
        properties=properties
    )

def track_error(error_type: str, error_message: str, endpoint: str, user_id: Optional[str] = None):
    """Track an error event."""
    posthog_client.track_event(
        event_name="api_error",
        user_id=user_id,
        properties={
            "error_type": error_type,
            "error_message": error_message,
            "endpoint": endpoint
        }
    )