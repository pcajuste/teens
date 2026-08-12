"""Supabase Storage upload service for rep campaign-submission files
(Build Prompt 5 deliverable 11).

Same two-implementation pattern as app/services/supabase_auth_client.py:
an HTTP client that calls the real Supabase Storage REST API in
production, and a local-dev/test stand-in that never leaves the
process (no real Supabase Storage runs locally). Selected the same way,
by Settings.environment.

Access scoping: files are uploaded to a private bucket
(`campaign-submissions`) under a key namespaced by
`{rep_id}/{campaign_id}/{filename}`. The bucket itself is never public;
read access for the rep and the relevant brand is granted via signed
URLs issued elsewhere (Prompt 8/10 -- brand submission viewing), not by
this service, which only ever produces the storage key. This module
does not read files back, only validates and writes them.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings

SUBMISSION_BUCKET = "campaign-submissions"

# Server-side validation (Prompt 5 deliverable 11: "validate file
# type/size server-side"). Deliverable evidence for a campaign is
# photo/video/screenshot proof, never an executable or arbitrary
# document type.
ALLOWED_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "video/mp4",
        "video/quicktime",
    }
)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class SubmissionUploadError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class UploadedFile:
    storage_key: str
    url: str


def _validate(*, content_type: str, size_bytes: int) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise SubmissionUploadError(
            "unsupported_file_type",
            f"'{content_type}' is not an accepted submission file type.",
        )
    if size_bytes <= 0:
        raise SubmissionUploadError("empty_file", "Uploaded file is empty.")
    if size_bytes > MAX_UPLOAD_BYTES:
        raise SubmissionUploadError(
            "file_too_large",
            f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB submission upload limit.",
        )


def _safe_filename(filename: str) -> str:
    cleaned = _SAFE_FILENAME_RE.sub("_", filename.strip()) or "file"
    return f"{uuid.uuid4().hex}_{cleaned}"


class SubmissionStorageClient(Protocol):
    async def upload(
        self, *, rep_id: str, campaign_id: str, filename: str, content_type: str, data: bytes
    ) -> UploadedFile: ...


class HttpSupabaseStorageClient:
    """Production: uploads to Supabase Storage via its REST API using
    the service-role key (server-side only -- never exposed to the
    client, consistent with every other server-side-only credential in
    this codebase)."""

    def __init__(self, settings: Settings):
        self._base_url = settings.next_public_supabase_url.rstrip("/")
        self._service_role_key = settings.supabase_service_role_key

    async def upload(
        self, *, rep_id: str, campaign_id: str, filename: str, content_type: str, data: bytes
    ) -> UploadedFile:
        _validate(content_type=content_type, size_bytes=len(data))
        key = f"{rep_id}/{campaign_id}/{_safe_filename(filename)}"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/storage/v1/object/{SUBMISSION_BUCKET}/{key}",
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                    "Content-Type": content_type,
                },
                content=data,
            )
        response.raise_for_status()
        url = f"{self._base_url}/storage/v1/object/{SUBMISSION_BUCKET}/{key}"
        return UploadedFile(storage_key=key, url=url)


class LocalDevSubmissionStorageClient:
    """Local dev/test only -- no real Supabase Storage runs locally.
    Validates exactly as production would but never performs network
    I/O, returning a deterministic fake URL so tests can assert on
    shape without a storage backend."""

    async def upload(
        self, *, rep_id: str, campaign_id: str, filename: str, content_type: str, data: bytes
    ) -> UploadedFile:
        _validate(content_type=content_type, size_bytes=len(data))
        key = f"{rep_id}/{campaign_id}/{_safe_filename(filename)}"
        return UploadedFile(storage_key=key, url=f"local-dev-storage://{SUBMISSION_BUCKET}/{key}")


def get_storage_client(settings: Settings) -> SubmissionStorageClient:
    if settings.environment in ("development", "test"):
        return LocalDevSubmissionStorageClient()
    return HttpSupabaseStorageClient(settings)
