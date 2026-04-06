"""
rag_service.py
--------------
Full LangChain RAG implementation for the Cybersecurity Advisor.

Pipeline:
  1. Load markdown documents from rag/knowledge_base/
  2. Split into chunks (RecursiveCharacterTextSplitter)
  3. Embed with nomic-embed-text via Ollama
  4. Persist embeddings in ChromaDB
  5. On query:
     a. Embed the question
     b. Retrieve top-K relevant chunks from Chroma
     c. Inject system prompt + retrieved context + anomaly context + history
     d. Stream response from Ollama LLM (llama3.2 / mistral-nemo)
     e. Return answer + source document names

Design decisions:
  - ChromaDB is persisted to disk (rag/chroma_db/) so embeddings
    survive server restarts — only re-embedded if docs change.
  - OllamaEmbeddings runs locally — zero API calls, zero cost.
  - The system prompt is engineering-grade: instructs the LLM to act
    as a SOC analyst, cite sources, and give actionable advice.
  - Conversation history is injected as formatted prior turns so the
    LLM maintains context across multi-turn chats.
  - Anomaly context from LSTM prediction is formatted and injected
    so the LLM can give targeted, specific advice about a detected threat.
"""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Tuple

import httpx
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from loguru import logger

from app.core.config import get_settings
from app.core.exceptions import RAGServiceError
from app.schemas.models import ChatMessage, PredictionResult

# ─── System Prompt ────────────────────────────────────────────────────────────
# Engineering-grade prompt: defines role, scope, output format, and constraints.

SYSTEM_PROMPT = """You are CyberGuard, an expert AI cybersecurity analyst and \
Security Operations Center (SOC) advisor with deep knowledge of:
- Network intrusion detection systems (IDS/IPS)
- Network traffic analysis and anomaly detection
- MITRE ATT&CK framework and threat actor TTPs
- Incident response and digital forensics
- Network protocols (TCP/IP, DNS, HTTP, SSH, FTP, etc.)
- Machine learning-based security systems

## Your Behaviour Rules:
1. ALWAYS base your answers primarily on the provided CONTEXT documents.
2. If the context does not contain enough information, say so clearly, then
   use your general cybersecurity knowledge to supplement — but distinguish
   between context-based and general knowledge answers.
3. ALWAYS provide ACTIONABLE advice: specific commands, configurations,
   or steps the analyst can take immediately.
4. When an ANOMALY DETECTION RESULT is provided, prioritise explaining:
   - What the detected anomaly likely means
   - Its severity and potential impact
   - Immediate containment steps
   - Forensic investigation steps
   - Long-term remediation
5. Structure longer answers with clear sections using markdown headers.
6. Cite which source documents informed your answer (e.g. "[Source: ids_alerts_guide.md]").
7. If asked about something outside cybersecurity scope, politely redirect.
8. Do NOT fabricate CVE numbers, IP addresses, or specific threat intelligence
   unless drawn directly from the context.
9. Use technical language appropriate for a security analyst audience.
10. Keep answers concise but complete — prioritise actionability over length.

## Output Format:
- Use markdown formatting (headers, bullet points, code blocks)
- Lead with the most critical information
- End with a "Next Steps" or "Recommended Actions" section for threat-related queries
"""

# ─── Fingerprint helper ───────────────────────────────────────────────────────

def _fingerprint_kb(kb_path: Path) -> str:
    """
    Compute an MD5 hash of all knowledge base file contents + mtimes.
    Used to detect if documents changed since last embedding run,
    so we avoid redundant re-embedding on every server restart.
    """
    h = hashlib.md5()
    for doc_file in sorted(kb_path.glob("**/*.md")):
        h.update(doc_file.name.encode())
        h.update(str(doc_file.stat().st_mtime).encode())
        h.update(doc_file.read_bytes())
    return h.hexdigest()


# ─── RAGService ───────────────────────────────────────────────────────────────

class RAGService:
    """
    Async-compatible RAG service using LangChain + ChromaDB + Ollama.

    Lifecycle:
        svc = RAGService()
        await svc.initialise()   # called once in FastAPI lifespan
        answer, sources = await svc.query(question, history, ctx)
        await svc.close()        # called on FastAPI shutdown
    """

    def __init__(self) -> None:
        self.is_ready:   bool             = False
        self._vectordb:  Optional[Chroma] = None
        self._embeddings: Optional[OllamaEmbeddings] = None
        self._settings   = get_settings()

    # ── Startup ───────────────────────────────────────────────────────────────

    async def initialise(self) -> None:
        """
        Full initialisation pipeline:
          1. Check Ollama is reachable
          2. Create OllamaEmbeddings
          3. Load / re-embed knowledge base into ChromaDB
        """
        logger.info("Initialising RAG service...")

        settings = self._settings

        # ── 1. Check Ollama reachability ──────────────────────────
        await self._check_ollama()

        # ── 2. Setup embeddings ───────────────────────────────────
        logger.info(
            f"Creating OllamaEmbeddings: model={settings.ollama_embed_model} "
            f"base_url={settings.ollama_base_url}"
        )
        self._embeddings = OllamaEmbeddings(
            model=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        )

        # ── 3. Load / build ChromaDB ──────────────────────────────
        await asyncio.get_event_loop().run_in_executor(
            None, self._build_vectorstore
        )

        self.is_ready = True
        logger.success(
            f"RAG service ready — "
            f"collection: cyber_knowledge | "
            f"embed_model: {settings.ollama_embed_model} | "
            f"llm: {settings.ollama_llm_model}"
        )

    async def _check_ollama(self) -> None:
        """Ping Ollama, verify both required models are available."""
        settings = self._settings
        logger.info(f"Checking Ollama at {settings.ollama_base_url} ...")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                resp.raise_for_status()
                available = [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            raise RAGServiceError(
                f"Cannot reach Ollama at {settings.ollama_base_url}. "
                f"Run: ollama serve\nError: {e}"
            ) from e

        logger.info(f"  Available Ollama models: {available}")

        # Check LLM model:
        llm_ok = any(
            settings.ollama_llm_model in m for m in available
        )
        if not llm_ok:
            logger.warning(
                f"  LLM model '{settings.ollama_llm_model}' not found! "
                f"Run: ollama pull {settings.ollama_llm_model}"
            )

        # Check embedding model:
        emb_ok = any(
            settings.ollama_embed_model in m for m in available
        )
        if not emb_ok:
            raise RAGServiceError(
                f"Embedding model '{settings.ollama_embed_model}' not found. "
                f"Run: ollama pull {settings.ollama_embed_model}"
            )

        logger.success("  Ollama model checks passed.")

    def _build_vectorstore(self) -> None:
        """
        Load documents, chunk them, embed, and persist to ChromaDB.
        If the knowledge base fingerprint matches an existing DB,
        reuse the existing embeddings (skip re-embedding).
        """
        settings = self._settings
        kb_path  = Path(settings.knowledge_base_path)
        db_path  = Path(settings.chroma_db_path)

        if not kb_path.exists() or not any(kb_path.glob("*.md")):
            raise RAGServiceError(
                f"Knowledge base empty: {kb_path}\n"
                "Add .md files to rag/knowledge_base/ and restart."
            )

        # ── Fingerprint check ─────────────────────────────────────
        fingerprint     = _fingerprint_kb(kb_path)
        fp_file         = db_path / "kb_fingerprint.txt"
        db_path.mkdir(parents=True, exist_ok=True)

        existing_fp = fp_file.read_text().strip() if fp_file.exists() else ""

        if existing_fp == fingerprint and (db_path / "chroma.sqlite3").exists():
            logger.info("Knowledge base unchanged — loading existing ChromaDB.")
            self._vectordb = Chroma(
                collection_name="cyber_knowledge",
                embedding_function=self._embeddings,
                persist_directory=str(db_path),
            )
            count = self._vectordb._collection.count()
            logger.info(f"  Loaded {count} embedded chunks from disk.")
            return

        # ── Load documents ────────────────────────────────────────
        logger.info(f"Loading documents from: {kb_path}")
        docs: List[Document] = []

        for md_file in sorted(kb_path.glob("*.md")):
            loader = TextLoader(str(md_file), encoding="utf-8")
            loaded = loader.load()
            # Tag each doc with its source filename:
            for doc in loaded:
                doc.metadata["source"] = md_file.name
                doc.metadata["title"]  = md_file.stem.replace("_", " ").title()
            docs.extend(loaded)
            logger.info(f"  Loaded: {md_file.name} ({len(loaded[0].page_content)} chars)")

        if not docs:
            raise RAGServiceError("No documents loaded from knowledge base.")

        # ── Chunk documents ───────────────────────────────────────
        logger.info(
            f"Splitting into chunks: "
            f"size={settings.rag_chunk_size} "
            f"overlap={settings.rag_chunk_overlap}"
        )
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
            separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
            length_function=len,
        )
        chunks = splitter.split_documents(docs)
        logger.info(f"  Total chunks: {len(chunks)}")

        # ── Embed + persist ───────────────────────────────────────
        logger.info(
            f"Embedding {len(chunks)} chunks with "
            f"'{settings.ollama_embed_model}' (this may take a minute)..."
        )

        # Delete existing collection if re-embedding:
        if (db_path / "chroma.sqlite3").exists():
            import shutil
            shutil.rmtree(db_path)
            db_path.mkdir(parents=True, exist_ok=True)
            logger.info("  Cleared stale ChromaDB collection.")

        self._vectordb = Chroma.from_documents(
            documents=chunks,
            embedding=self._embeddings,
            collection_name="cyber_knowledge",
            persist_directory=str(db_path),
        )

        # Save fingerprint so next restart skips re-embedding:
        fp_file.write_text(fingerprint)

        count = self._vectordb._collection.count()
        logger.success(f"  ChromaDB built: {count} vectors persisted to {db_path}")

    # ── Query ─────────────────────────────────────────────────────────────────

    async def query(
        self,
        question:           str,
        history:            Optional[List[ChatMessage]] = None,
        prediction_context: Optional[PredictionResult]  = None,
    ) -> Tuple[str, List[str]]:
        """
        Run a RAG query against the cyber knowledge base.

        Args:
            question:           User's question string
            history:            Prior chat messages (for multi-turn context)
            prediction_context: Optional LSTM anomaly result for targeted advice

        Returns:
            (answer: str, sources: List[str])  where sources are filenames
        """
        if not self.is_ready or self._vectordb is None:
            raise RAGServiceError(
                "RAG service not initialised. Call initialise() first."
            )

        settings = self._settings

        # ── 1. Retrieve relevant chunks ───────────────────────────
        retrieval_query = self._build_retrieval_query(
            question, prediction_context
        )

        logger.debug(f"Retrieval query: {retrieval_query[:100]}...")

        # Run retrieval in a thread (Chroma is synchronous):
        docs_with_scores: List[Tuple[Document, float]] = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._vectordb.similarity_search_with_relevance_scores(
                retrieval_query,
                k=settings.rag_top_k,
            ),
        )

        # Filter low-relevance chunks (score < 0.3):
        relevant_docs = [
            (doc, score)
            for doc, score in docs_with_scores
            if score >= 0.3
        ]

        if not relevant_docs:
            # Fall back to top-K without score filter:
            relevant_docs = docs_with_scores[:3]

        logger.debug(
            f"Retrieved {len(relevant_docs)} chunks | "
            f"scores: {[round(s, 3) for _, s in relevant_docs]}"
        )

        # ── 2. Build context string ───────────────────────────────
        context_str = self._format_context(relevant_docs)
        source_names = list({
            doc.metadata.get("source", "unknown")
            for doc, _ in relevant_docs
        })

        # ── 3. Build full prompt ──────────────────────────────────
        full_prompt = self._build_prompt(
            question=question,
            context=context_str,
            history=history or [],
            prediction_context=prediction_context,
        )

        # ── 4. Call Ollama LLM (async HTTP) ───────────────────────
        answer = await self._call_ollama(full_prompt, settings)

        logger.info(
            f"RAG query complete | "
            f"sources={source_names} | "
            f"answer_len={len(answer)} chars"
        )

        return answer, source_names

    # ── Prompt Building ───────────────────────────────────────────────────────

    def _build_retrieval_query(
        self,
        question:           str,
        prediction_context: Optional[PredictionResult],
    ) -> str:
        """
        Augment the retrieval query with anomaly context so ChromaDB
        retrieves chunks most relevant to the specific detected threat.
        """
        if prediction_context is None or not prediction_context.is_anomaly:
            return question

        # Include anomaly info to bias retrieval toward relevant docs:
        return (
            f"{question} "
            f"anomaly detection probability={prediction_context.probability:.2f} "
            f"severity={prediction_context.severity.value} "
            f"attack detection network intrusion"
        )

    def _format_context(
        self,
        docs_with_scores: List[Tuple[Document, float]],
    ) -> str:
        """Format retrieved chunks into a numbered context block."""
        parts = []
        for i, (doc, score) in enumerate(docs_with_scores, 1):
            source = doc.metadata.get("source", "unknown")
            title  = doc.metadata.get("title",  "Document")
            parts.append(
                f"[Context {i}] Source: {source} | Relevance: {score:.2f}\n"
                f"{doc.page_content.strip()}"
            )
        return "\n\n---\n\n".join(parts)

    def _format_history(self, history: List[ChatMessage]) -> str:
        """Format chat history as a readable conversation block."""
        if not history:
            return ""
        lines = ["## Prior Conversation:"]
        for msg in history[-6:]:   # last 6 messages only (3 turns)
            prefix = "Analyst" if msg.role == "user" else "CyberGuard"
            lines.append(f"**{prefix}:** {msg.content}")
        return "\n".join(lines)

    def _format_anomaly_context(
        self,
        prediction_context: PredictionResult,
    ) -> str:
        """Format an LSTM PredictionResult into a readable alert block."""
        if not prediction_context.is_anomaly:
            return ""

        severity_emoji = {
            "LOW":      "🟡",
            "MEDIUM":   "🟠",
            "HIGH":     "🔴",
            "CRITICAL": "🚨",
        }.get(prediction_context.severity.value, "⚠️")

        return (
            f"## {severity_emoji} ACTIVE ANOMALY ALERT\n"
            f"- **Detection ID:** {prediction_context.prediction_id}\n"
            f"- **Label:** {prediction_context.label.value}\n"
            f"- **Attack Probability:** {prediction_context.probability:.1%}\n"
            f"- **Severity:** {prediction_context.severity.value}\n"
            f"- **Decision Threshold:** {prediction_context.threshold}\n"
            f"- **Detected At:** {prediction_context.timestamp}\n\n"
            "The analyst is asking about this specific detected threat."
        )

    def _build_prompt(
        self,
        question:           str,
        context:            str,
        history:            List[ChatMessage],
        prediction_context: Optional[PredictionResult],
    ) -> str:
        """
        Assemble the complete prompt sent to the Ollama LLM.

        Structure:
          [System Prompt]
          [Anomaly Alert — if present]
          [Conversation History — if any]
          [Retrieved Context Documents]
          [Current Question]
          [Answer Instruction]
        """
        sections: List[str] = [SYSTEM_PROMPT]

        # Anomaly context (highest priority — inject early):
        if prediction_context and prediction_context.is_anomaly:
            sections.append(self._format_anomaly_context(prediction_context))

        # Conversation history:
        history_str = self._format_history(history)
        if history_str:
            sections.append(history_str)

        # Retrieved knowledge base context:
        sections.append(
            f"## Relevant Knowledge Base Context:\n\n{context}"
        )

        # Current question:
        sections.append(
            f"## Analyst Question:\n{question}"
        )

        # Final instruction (reduces hallucination):
        sections.append(
            "## Your Response:\n"
            "Provide a thorough, accurate, and actionable cybersecurity answer. "
            "Reference the context documents where applicable. "
            "If this is about a detected anomaly, start with immediate response actions."
        )

        return "\n\n".join(sections)

    # ── Ollama LLM Call ───────────────────────────────────────────────────────

    async def _call_ollama(self, prompt: str, settings) -> str:
        """
        Call Ollama /api/generate with the assembled prompt.
        Uses non-streaming mode (stream=False) for simplicity.
        For streaming to WebSocket, use stream=True with async iteration.

        Args:
            prompt:   Complete prompt string
            settings: Application settings

        Returns:
            Generated text response from the LLM
        """
        payload = {
            "model":  settings.ollama_llm_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature":   0.3,    # Low temp = more factual, less creative
                "top_p":         0.9,
                "top_k":         40,
                "num_predict":   2048,   # Max output tokens
                "repeat_penalty": 1.1,   # Reduce repetition
                "stop": [
                    "## Analyst Question:",
                    "Human:",
                    "User:",
                ],
            },
        }

        logger.debug(
            f"Calling Ollama: model={settings.ollama_llm_model} "
            f"prompt_len={len(prompt)} chars"
        )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=300.0,    # LLM can take up to 5 min on CPU
                    write=10.0,
                    pool=5.0,
                )
            ) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

        except httpx.TimeoutException as e:
            raise RAGServiceError(
                f"Ollama request timed out after 5 minutes. "
                f"Try a smaller model or add more RAM. Error: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise RAGServiceError(
                f"Ollama returned HTTP {e.response.status_code}: {e.response.text}"
            ) from e
        except Exception as e:
            raise RAGServiceError(
                f"Ollama call failed: {type(e).__name__}: {e}"
            ) from e

        answer = data.get("response", "").strip()

        if not answer:
            raise RAGServiceError(
                "Ollama returned an empty response. "
                "Check that the model is fully loaded: ollama list"
            )

        # Log token usage if available:
        eval_count   = data.get("eval_count", 0)
        prompt_tokens = data.get("prompt_eval_count", 0)
        logger.debug(
            f"Ollama usage: prompt_tokens={prompt_tokens} "
            f"completion_tokens={eval_count}"
        )

        return answer

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Release ChromaDB resources on app shutdown."""
        if self._vectordb is not None:
            try:
                self._vectordb = None
                logger.info("RAG service: ChromaDB connection closed.")
            except Exception as e:
                logger.warning(f"RAG close error: {e}")
        self.is_ready = False

    # ── Admin helpers ─────────────────────────────────────────────────────────

    async def get_collection_stats(self) -> dict:
        """Return stats about the current ChromaDB collection."""
        if not self._vectordb:
            return {"status": "not_loaded"}
        count = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._vectordb._collection.count()
        )
        settings = self._settings
        return {
            "status":          "ready",
            "collection_name": "cyber_knowledge",
            "total_chunks":    count,
            "embed_model":     settings.ollama_embed_model,
            "llm_model":       settings.ollama_llm_model,
            "kb_path":         settings.knowledge_base_path,
            "db_path":         settings.chroma_db_path,
        }
