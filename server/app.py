"""
JobLens Scam Detection API - Main Entry Point.

This module provides backward compatibility and serves as the main entry point.
The application has been refactored into a modular structure under the `api/` package.

Endpoints:
- POST /scoring/url: Scrape a job posting URL and score it
- POST /scoring/text: Score a job posting using plain text body
- POST /resume/match: Match resume against JD (JSON with base64 PDF)
- DELETE /resume/cache: Clear resume parsing cache
- GET /health: Health check endpoint
- GET /rules: List all configured detection rules
- POST /summarize: Summarize a scoring result using Groq
"""

from __future__ import annotations

import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from api.app import app, create_app

__all__ = ["app", "create_app"]

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run("app:app", host=host, port=port, reload=True)
