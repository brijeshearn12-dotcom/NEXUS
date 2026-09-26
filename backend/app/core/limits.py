"""Input size limits and safe error messages shared by the API layer (Task 8.2 hardening).

Limits are generous multiples of the real corpus so legitimate requests are never rejected:
the largest curated judgment is ~366,000 characters of cleaned text and the longest title
is 94 characters. Judgment text itself keeps its existing endpoint check
(cases.MAX_INGEST_TEXT_LENGTH = 5,000,000 characters -> 413).
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Receive, Scope, Send

# ── Field limits ──────────────────────────────────────────────────────────────
MAX_TITLE_CHARS = 500
MAX_SOURCE_REF_CHARS = 1_000
MAX_NOTES_CHARS = 2_000
MAX_ID_CHARS = 200
MAX_ANALYST_ID_CHARS = 128
MAX_STATUS_CHARS = 32
MAX_QUERY_TEXT_CHARS = 200
MAX_ID_LIST_ITEMS = 1_000

# ── Transport limits (checked before the body is read) ────────────────────────
# Above the ingest endpoint's own 5,000,000-character check for plain text, so that check
# (and its clear message) still applies; ~20x the largest real judgment.
MAX_REQUEST_BODY_BYTES = 8 * 1024 * 1024
MAX_URL_PATH_CHARS = 2_048


def safe_error_detail(action: str, err: BaseException) -> str:
    """Client-facing 500 message without internal details (hosts, paths, query text).

    The full exception is logged server-side by each endpoint.
    """
    return f"{action} ({type(err).__name__}). Details were recorded in the server log."


class RequestSizeLimitMiddleware:
    """Reject oversized requests with a clean 413/414 before any body is buffered."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if len(scope.get("path", "")) > MAX_URL_PATH_CHARS:
            await _reject(send, 414, "Request URL is too long.")
            return

        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                size = int(declared)
            except ValueError:
                await _reject(send, 400, "Invalid Content-Length header.")
                return
            if size > MAX_REQUEST_BODY_BYTES:
                await _reject(send, 413, _too_large())
                return
            await self.app(scope, receive, send)
            return

        # No Content-Length (e.g. chunked): read the body here, up to the limit, and replay it.
        # (Raising from inside the app's body read would surface as a generic 400 instead.)
        buffered: list[dict] = []
        received = 0
        while True:
            message = await receive()
            buffered.append(message)
            if message["type"] != "http.request":
                break
            received += len(message.get("body", b""))
            if received > MAX_REQUEST_BODY_BYTES:
                await _reject(send, 413, _too_large())
                return
            if not message.get("more_body", False):
                break

        async def replay() -> dict:
            if buffered:
                return buffered.pop(0)
            return await receive()

        await self.app(scope, replay, send)


def _too_large() -> str:
    return f"Request body exceeds the {MAX_REQUEST_BODY_BYTES // (1024 * 1024)} MB limit."


async def _reject(send: Send, status_code: int, message: str) -> None:
    body = json.dumps({"detail": message}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})
