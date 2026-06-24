#!/usr/bin/env python3
"""
Local development server script
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

if __name__ == "__main__":
    import uvicorn
    from src.api import app
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        reload=False,  # Disable reload to avoid subprocess issues
        log_level="info"
    )