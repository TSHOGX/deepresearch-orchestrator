"""FastAPI application for the deep research API."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deep_research.api.routes import config, health, research
from deep_research.config import get_settings
from deep_research.services.session_manager import get_session_manager, reset_session_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Deep Research API")
    settings = get_settings()
    settings.ensure_directories()

    # Initialize session manager
    await get_session_manager()

    yield

    # Shutdown
    logger.info("Shutting down Deep Research API")
    await reset_session_manager()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application.
    """
    settings = get_settings()

    app = FastAPI(
        title="Deep Research API",
        description="Multi-agent deep research system powered by Codex CLI",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(research.router, prefix="/api/research", tags=["Research"])
    app.include_router(config.router, prefix="/api/config", tags=["Config"])

    return app


# Application instance
app = create_app()


def run_server() -> None:
    """Run the API server."""
    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    uvicorn.run(
        "deep_research.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run_server()
