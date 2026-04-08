"""
FastAPI application factory for JobLens API.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
import httpx
import asyncio

from api.config import DEFAULT_MODEL_PATH
from api.routes import scoring_router, resume_router, system_router, config_router

logger = logging.getLogger(__name__)


async def _keep_alive():
    """I have written this as a keep-alive function for Render spin-down."""
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not render_url:
        logger.warning("RENDER_EXTERNAL_URL not set, keep-alive disabled.")
        return
    
    await asyncio.sleep(60) 
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.get(f"{render_url}/health")
                logger.info("Keep-alive ping sent ✓")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")
        await asyncio.sleep(10 * 60) 

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload the model on startup."""
    from core.scoring import get_model, clear_model_cache

    logger.info("Starting JobLens API...")
    try:
        logger.info(f"Preloading model from {DEFAULT_MODEL_PATH}...")
        get_model(DEFAULT_MODEL_PATH)
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.warning(
            f"Could not preload model: {e}. Will attempt to load on first request."
        )

    keep_alive_task = asyncio.create_task(_keep_alive())
    yield

    logger.info("Shutting down JobLens API...")
    keep_alive_task.cancel()
    try:
        await keep_alive_task
    except asyncio.CancelledError:
        pass
    clear_model_cache()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="JobLens Scam Detection API",
        description=(
            "Gate-based ensemble for detecting fraudulent job postings "
            "using ML + rule-based analysis, with resume matching capabilities."
        ),
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(scoring_router)
    app.include_router(resume_router)
    app.include_router(system_router)
    app.include_router(config_router)

    return app


app = create_app()
