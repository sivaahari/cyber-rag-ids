"""
security.py
-----------
Security utilities for the FastAPI backend:

  1. InputSanitizer     — strips/validates user-supplied strings before
                          they reach the LLM prompt (prompt injection defence)
  2. SecurityHeaders    — adds hardening HTTP headers to every response
  3. request_size_limit — middleware factory to reject oversized bodies
  4. validate_file_ext  — allowlist-based file extension checker
  5. mask_sensitive     — redacts secrets from log strings

None of these replace TLS, WAF, or network-level controls —
they are application-layer hardening only.
"""

import re
import unicodedata
from typing import Callable

from fastapi import FastAPI, Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


# ─── 1. Input Sanitizer ───────────────────────────────────────────────────────

# Patterns that indicate prompt-injection or jailbreak attempts:
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"you\s+are\s+now\s+(a\s+)?(?!CyberGuard)",   # "you are now DAN"
    r"jailbreak",
    r"act\s+as\s+if\s+you\s+(have\s+no|are\s+without)\s+restrictions?",
    r"disregard\s+(your\s+)?(prior|previous|all)\s+(instructions?|rules?|guidelines?)",
    r"repeat\s+after\s+me",
    r"sudo\s+mode",
    r"developer\s+mode",
    r"<\|.*?\|>",          # special token injection
    r"\[INST\]",           # Mistral instruction tokens
    r"\[\/INST\]",
    r"<<SYS>>",            # Llama system tokens
    r"<</SYS>>",
]

_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS),
    re.IGNORECASE | re.DOTALL,
)

# Characters that should never appear in questions:
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class InputSanitizer:
    """
    Sanitize user-supplied text before it reaches the LLM prompt.

    Usage:
        sanitizer = InputSanitizer()
        clean = sanitizer.sanitize(raw_input)   # raises ValueError on attack
    """

    MAX_LEN = 4_000   # characters (mirrors Pydantic schema max_length)

    def sanitize(self, text: str) -> str:
        """
        Clean and validate a user input string.

        Steps:
          1. Trim leading/trailing whitespace
          2. Enforce maximum length
          3. Strip Unicode control characters
          4. Normalize to NFC (prevents homoglyph attacks)
          5. Detect prompt-injection patterns → raise ValueError
          6. Return cleaned string

        Args:
            text: Raw user input

        Returns:
            Sanitized string safe for inclusion in an LLM prompt

        Raises:
            ValueError: If the input contains injection patterns
        """
        if not text or not isinstance(text, str):
            raise ValueError("Input must be a non-empty string.")

        # Step 1 — trim:
        text = text.strip()

        # Step 2 — length:
        if len(text) > self.MAX_LEN:
            raise ValueError(
                f"Input too long: {len(text)} chars (max {self.MAX_LEN})."
            )

        # Step 3 — strip control characters:
        text = _CONTROL_CHARS_RE.sub("", text)

        # Step 4 — Unicode normalize:
        text = unicodedata.normalize("NFC", text)

        # Step 5 — injection detection:
        match = _INJECTION_RE.search(text)
        if match:
            logger.warning(
                f"Prompt injection attempt blocked: "
                f"pattern='{match.group()[:30]}…'"
            )
            raise ValueError(
                "Input contains disallowed content. "
                "Please ask a genuine cybersecurity question."
            )

        return text

    def sanitize_history(self, history: list) -> list:
        """Sanitize each message in a chat history list."""
        clean = []
        for msg in history:
            try:
                content = self.sanitize(msg.content if hasattr(msg, "content") else msg.get("content", ""))
                if hasattr(msg, "model_copy"):
                    clean.append(msg.model_copy(update={"content": content}))
                else:
                    clean.append({**msg, "content": content})
            except ValueError:
                # Skip injected history messages silently:
                logger.warning("Skipped injected history message.")
        return clean


# Module-level singleton:
sanitizer = InputSanitizer()


# ─── 2. Security Headers Middleware ───────────────────────────────────────────

SECURITY_HEADERS = {
    # Prevent MIME sniffing:
    "X-Content-Type-Options": "nosniff",
    # Deny framing (clickjacking):
    "X-Frame-Options": "DENY",
    # XSS protection (legacy browsers):
    "X-XSS-Protection": "1; mode=block",
    # Referrer policy:
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # No caching for API responses:
    "Cache-Control": "no-store, no-cache, must-revalidate",
    # Permissions policy (disable unneeded browser features):
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security hardening headers to every HTTP response.
    Does NOT add HSTS (that belongs at the reverse-proxy / TLS layer).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


# ─── 3. Request Size Limiter ──────────────────────────────────────────────────

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Reject requests whose Content-Length exceeds max_bytes.
    Protects against large-body DoS attacks before body is read.

    Args:
        max_bytes: Maximum allowed body size in bytes (default 100 MB)
    """

    def __init__(self, app: ASGIApp, max_bytes: int = 100 * 1024 * 1024) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_bytes:
            logger.warning(
                f"Request body too large: {content_length} bytes "
                f"(max {self.max_bytes}) from {request.client}"
            )
            return Response(
                content='{"error":"request_too_large","message":"Body exceeds size limit."}',
                status_code=413,
                media_type="application/json",
            )
        return await call_next(request)


# ─── 4. File Extension Validator ──────────────────────────────────────────────

ALLOWED_EXTENSIONS = {
    "csv":    {".csv"},
    "pcap":   {".pcap", ".pcapng"},
    "any":    {".csv", ".pcap", ".pcapng"},
}


def validate_file_extension(filename: str, file_type: str = "any") -> bool:
    """
    Check that a filename has an allowed extension.

    Args:
        filename:  Original filename from upload
        file_type: One of 'csv', 'pcap', 'any'

    Returns:
        True if extension is allowed

    Raises:
        ValueError: If extension is not in the allowlist
    """
    if not filename:
        raise ValueError("Filename is empty.")

    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = ALLOWED_EXTENSIONS.get(file_type, ALLOWED_EXTENSIONS["any"])

    if suffix not in allowed:
        raise ValueError(
            f"File type '{suffix}' not allowed. "
            f"Allowed types: {', '.join(sorted(allowed))}"
        )
    return True


# ─── 5. Sensitive Data Masker ─────────────────────────────────────────────────

_SECRET_PATTERNS = [
    (re.compile(r"(api[_-]?key\s*[=:]\s*)[^\s&\"']+", re.I), r"\1[REDACTED]"),
    (re.compile(r"(password\s*[=:]\s*)[^\s&\"']+",    re.I), r"\1[REDACTED]"),
    (re.compile(r"(token\s*[=:]\s*)[^\s&\"']+",       re.I), r"\1[REDACTED]"),
    (re.compile(r"(secret\s*[=:]\s*)[^\s&\"']+",      re.I), r"\1[REDACTED]"),
]


def mask_sensitive(text: str) -> str:
    """
    Replace credential-like patterns in a string with [REDACTED].
    Use before logging any user-supplied data that might include secrets.
    """
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ─── 6. Register all security middleware on app ───────────────────────────────

def register_security_middleware(app: FastAPI) -> None:
    """
    Attach all security middleware to the FastAPI app.
    Call this in create_app() BEFORE adding routes.
    Order matters — middlewares execute in reverse registration order.
    """
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_bytes=105 * 1024 * 1024,   # 105 MB (slightly above max upload)
    )
    logger.info("Security middleware registered.")
