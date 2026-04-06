"""
main.py
-------
FastAPI application factory.

Startup (lifespan):
  1. Setup structured logging (Loguru)
  2. Load LSTM model + scaler (LSTMService.load)
  3. Initialise RAG service (LangChain + ChromaDB + Ollama)

Shutdown (lifespan):
  1. Unload LSTM model from GPU/CPU memory
  2. Close RAG / ChromaDB connections

Middleware:
  - CORS (origins from .env)
  - Request timing header (X-Process-Time)
  - Rate limiting via SlowAPI

Routes mounted:
  /health, /model-info  → health.router
  /predict, /chat       → predict.router
  /upload               → upload.router
  /reports              → reports.router
  /ws                   → websocket.router (WebSocket)
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging

# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Async context manager for startup / shutdown logic.
    Everything before `yield` runs on startup.
    Everything after `yield` runs on shutdown.
    """
    settings = get_settings()

    # ── Startup ───────────────────────────────────────────────────
    setup_logging()
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info("=" * 60)

    # Load LSTM model:
    from app.services.lstm_service import lstm_service
    try:
        lstm_service.load()
        app.state.lstm_service = lstm_service
        logger.success("LSTM service ready.")
    except Exception as e:
        logger.error(f"LSTM service failed to load: {e}")
        logger.warning("Running without LSTM — /predict endpoints will return 503.")
        app.state.lstm_service = None

    # Load RAG service (imported lazily to avoid circular imports):
    try:
        from app.services.rag_service import RAGService
        rag = RAGService()
        await rag.initialise()
        app.state.rag_service = rag
        logger.success("RAG service ready.")
    except Exception as e:
        logger.error(f"RAG service failed to load: {e}")
        logger.warning("Running without RAG — /chat endpoint will return 503.")
        app.state.rag_service = None

    logger.info(f"API listening on http://{settings.host}:{settings.port}")
    logger.info("Docs available at: http://localhost:8000/docs")

    yield   # ← App is running here

    # ── Shutdown ──────────────────────────────────────────────────
    logger.info("Shutting down...")

    if app.state.lstm_service:
        app.state.lstm_service.unload()

    if app.state.rag_service:
        await app.state.rag_service.close()

    logger.info("Shutdown complete.")


# ─── App Factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    # Rate limiter:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "## Local LLM Cyber RAG Advisor + ML Intrusion Detection System\n\n"
            "### Features\n"
            "- **LSTM IDS**: Real-time network anomaly detection (NSL-KDD trained)\n"
            "- **RAG Advisor**: LangChain + ChromaDB + Ollama cybersecurity Q&A\n"
            "- **Upload**: CSV / PCAP batch analysis\n"
            "- **WebSocket**: Live packet stream predictions\n"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Rate limiting ─────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── CORS ──────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ─────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(
        request: Request, call_next
    ):
        import time
        t0       = time.perf_counter()
        response = await call_next(request)
        elapsed  = (time.perf_counter() - t0) * 1000
        response.headers["X-Process-Time"] = f"{elapsed:.2f}ms"
        return response

    # ── Custom exception handlers ─────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────
    from app.api.routes.health    import router as health_router
    from app.api.routes.predict   import router as predict_router
    from app.api.routes.upload    import router as upload_router
    from app.api.routes.reports   import router as reports_router
    from app.api.routes.websocket import router as ws_router

    app.include_router(health_router,  prefix="")        # /health, /model-info
    app.include_router(predict_router, prefix="")        # /predict, /chat
    app.include_router(upload_router,  prefix="")        # /upload/csv, /upload/pcap
    app.include_router(reports_router, prefix="")        # /reports
    app.include_router(ws_router,      prefix="")        # /ws/live-stream

    # ── Root ──────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "app":     settings.app_name,
            "version": settings.app_version,
            "docs":    "/docs",
            "health":  "/health",
        }

    return app


# ─── App Instance ─────────────────────────────────────────────────────────────
app = create_app()
