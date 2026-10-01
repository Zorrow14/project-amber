"""HTTP caching for the GET endpoints.

The precomputed responses (``/meta``, ``/counterfactual``, ``/scenarios``) are
serialized to JSON once, at startup, and served as those bytes with a weak ETag
derived from them, so a browser revalidating after ``max-age`` gets a bodiless
304. The query-dependent GETs (``/panel``, ``/index``) get the same
``Cache-Control`` but no ETag: their answer is a pure function of the query and
the snapshot, so the URL is the cache key. ``/health`` is never cached.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import Request, Response
from pydantic import BaseModel

from amber import config

__all__ = ["CACHE_CONTROL", "NO_STORE", "CachedBody", "cacheable", "serve"]

CACHE_CONTROL = f"public, max-age={config.API_CACHE_MAX_AGE_SECONDS}"
NO_STORE = "no-store"


@dataclass(frozen=True, slots=True)
class CachedBody:
    """A response body serialized once, with its ETag.

    Attributes:
        content: The JSON bytes.
        etag: A weak validator over ``content`` (weak because gzip re-encodes it).
    """

    content: bytes
    etag: str

    @classmethod
    def of(cls, model: BaseModel) -> CachedBody:
        """Serialize ``model`` as FastAPI would, and fingerprint the bytes."""
        content = model.model_dump_json().encode()
        digest = hashlib.sha256(content).hexdigest()[:32]
        return cls(content=content, etag=f'W/"{digest}"')


def _matches(request: Request, etag: str) -> bool:
    """Whether the request's ``If-None-Match`` already holds ``etag``."""
    header = request.headers.get("if-none-match")
    if not header:
        return False
    if header.strip() == "*":
        return True
    bare = etag.removeprefix("W/")
    return any(tag.strip().removeprefix("W/") == bare for tag in header.split(","))


def serve(request: Request, body: CachedBody) -> Response:
    """The cached body, or a 304 when the client already has it."""
    headers = {"ETag": body.etag, "Cache-Control": CACHE_CONTROL}
    if _matches(request, body.etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body.content, media_type="application/json", headers=headers)


def cacheable(response: Response) -> None:
    """Dependency: mark a GET response as cacheable for ``max-age``."""
    response.headers["Cache-Control"] = CACHE_CONTROL
