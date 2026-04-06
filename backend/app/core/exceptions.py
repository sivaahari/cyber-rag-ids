"""
exceptions.py
-------------
Custom exception classes and FastAPI exception handlers.
Registered on the app in main.py so all errors return consistent JSON.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from loguru import logger


# ─── Custom Exception Classes ─────────────────────────────────────────────────

class ModelNotLoadedError(Exception):
    """Raised when LSTM model has not been initialised yet."""
    pass


class FeatureExtractionError(Exception):
    """Raised when feature extraction from packet/CSV fails."""
    pass


class RAGServiceError(Exception):
    """Raised when the LangChain RAG chain encounters an error."""
    pass


class FileTooLargeError(Exception):
    """Raised when an uploaded file exceeds the size limit."""
    pass


class UnsupportedFileTypeError(Exception):
    """Raised when an uploaded file has an unsupported extension."""
    pass


# ─── Handler Registration ─────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to the FastAPI app."""

    @app.exception_handler(ModelNotLoadedError)
    async def model_not_loaded_handler(
        request: Request, exc: ModelNotLoadedError
    ) -> JSONResponse:
        logger.error(f"ModelNotLoadedError: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error":   "model_not_loaded",
                "message": "LSTM model is not yet loaded. "
                           "Check server logs and ensure lstm_ids.pt exists.",
                "detail":  str(exc),
            },
        )

    @app.exception_handler(FeatureExtractionError)
    async def feature_extraction_handler(
        request: Request, exc: FeatureExtractionError
    ) -> JSONResponse:
        logger.warning(f"FeatureExtractionError: {exc}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error":   "feature_extraction_failed",
                "message": "Could not extract features from the provided data.",
                "detail":  str(exc),
            },
        )

    @app.exception_handler(RAGServiceError)
    async def rag_service_handler(
        request: Request, exc: RAGServiceError
    ) -> JSONResponse:
        logger.error(f"RAGServiceError: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error":   "rag_service_error",
                "message": "RAG advisor is unavailable. "
                           "Ensure Ollama is running: ollama serve",
                "detail":  str(exc),
            },
        )

    @app.exception_handler(FileTooLargeError)
    async def file_too_large_handler(
        request: Request, exc: FileTooLargeError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "error":   "file_too_large",
                "message": str(exc),
            },
        )

    @app.exception_handler(UnsupportedFileTypeError)
    async def unsupported_file_handler(
        request: Request, exc: UnsupportedFileTypeError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content={
                "error":   "unsupported_file_type",
                "message": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def generic_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(f"Unhandled exception on {request.method} {request.url}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error":   "internal_server_error",
                "message": "An unexpected error occurred. Check server logs.",
            },
        )
