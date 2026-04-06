"""
rag_service.py  — STUB (full implementation in Batch 4)
Allows the app to start without the RAG/Ollama stack.
"""

from loguru import logger


class RAGService:
    """Stub RAG service — replaced with full LangChain implementation in Batch 4."""

    def __init__(self) -> None:
        self.is_ready = False

    async def initialise(self) -> None:
        logger.warning(
            "RAGService stub: /chat endpoint is unavailable. "
            "Full RAG implemented in Batch 4."
        )

    async def query(self, question: str, history=None, prediction_context=None):
        return (
            "RAG service not yet configured. Please complete Batch 4.",
            [],
        )

    async def close(self) -> None:
        pass
