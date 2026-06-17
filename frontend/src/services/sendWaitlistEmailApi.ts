/// <reference types="vite/client" />

export interface SendWaitlistEmailResponse {
  success: boolean;
  message: string;
  email_sent: boolean;
  already_on_waitlist: boolean;
  data?: {
    id: string;
  };
  error?: string;
}

// API Configuration
const API_MODE = import.meta.env.VITE_API_MODE || 'railway';
const LOCAL_API_URL = import.meta.env.VITE_LOCAL_API_URL || 'http://127.0.0.1:8002';
const RAILWAY_API_URL = import.meta.env.VITE_RAILWAY_API_URL || 'https://brickai-backend-production.up.railway.app';
const RAILWAY_API_URL_STAGING = import.meta.env.VITE_RAILWAY_API_URL_STAGING || 'https://brickai-backend-staging.up.railway.app';

// Determine API URLs based on mode
const getApiUrls = () => {
  if (API_MODE === 'local') {
    return {
      sendWaitlistEmail: `${LOCAL_API_URL}/sendWaitlistEmail`,
    };
  } else if (API_MODE === 'railway_staging') {
    return {
      sendWaitlistEmail: `${RAILWAY_API_URL_STAGING}/sendWaitlistEmail`,
    };
  } else {
    return {
      sendWaitlistEmail: `${RAILWAY_API_URL}/sendWaitlistEmail`,
    };
  }
};

const API_URLS = getApiUrls();

/**
 * API service for sending waitlist welcome emails.
 * This service calls the Railway backend endpoint.
 */
export class SendWaitlistEmailApiService {
  /**
   * Send a welcome email to a new waitlist subscriber
   * @param email - The email address to send the welcome email to
   * @returns Promise with success status and optional error message
   */
  static async sendWaitlistEmail(email: string): Promise<SendWaitlistEmailResponse> {
    if (!email) {
      throw new Error('Email is required');
    }

    try {
      const response = await fetch(API_URLS.sendWaitlistEmail, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email.toLowerCase().trim() }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Waitlist email API error:', errorText);
        
        let errorMessage = 'Failed to send welcome email';
        try {
          const errorData = JSON.parse(errorText);
          errorMessage = errorData.error || errorData.message || `API error: ${response.status} ${response.statusText}`;
        } catch {
          errorMessage = errorText || `${response.status} ${response.statusText}`;
        }
        
        return {
          success: false,
          error: errorMessage
        };
      }

      const responseData: SendWaitlistEmailResponse = await response.json();
      return responseData;

    } catch (error) {
      console.error('Failed to send welcome email:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred'
      };
    }
  }
}
