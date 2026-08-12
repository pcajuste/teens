"""Supabase Storage signed uploads for submission evidence (Prompt 5,
deliverable 10).

Not one of Section 8's literally-enumerated routes -- the spec's
POST /campaigns/:id/submit body already expects `submission_file_urls`
as strings, implying the client uploads first and submits URLs after.
This module (plus the /campaigns/:id/upload-url route in
app/routers/campaigns.py) is the missing "how do those URLs get
created" step, flagged as an addition beyond the spec's literal route
list and justified by deliverable 10's explicit requirement.

Requires a live Supabase project to exercise for real (same caveat as
app.services.supabase_admin) -- validation logic (file type/size,
campaign eligibility) is unit-testable without one; the signed-URL
call itself is not covered by this prompt's pytest suite.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.core.constants import ALLOWED_UPLOAD_CONTENT_TYPES, MAX_UPLOAD_BYTES

SUBMISSIONS_BUCKET = "submission-files"


class UploadValidationError(Exception):
    pass


class StorageError(RuntimeError):
    pass


def validate_upload(*, content_type: str, file_size_bytes: int) -> None:
    if content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise UploadValidationError(f"Unsupported file type: {content_type}")
    if file_size_bytes > MAX_UPLOAD_BYTES:
        raise UploadValidationError(f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit")


def create_signed_upload_url(
    *, campaign_id: str, rep_id: str, file_name: str, content_type: str, file_size_bytes: int, settings: Settings
) -> dict:
    """Returns {"upload_url": ..., "object_path": ...}.

    Object path is scoped to `{campaign_id}/{rep_id}/{file_name}` inside
    a private (non-public) bucket -- only the submitting rep and the
    campaign's brand should be able to read it, enforced via a Supabase
    Storage RLS policy on storage.objects (not written here; belongs
    with the other RLS migrations, out of scope for this service call).
    """
    validate_upload(content_type=content_type, file_size_bytes=file_size_bytes)

    object_path = f"{campaign_id}/{rep_id}/{file_name}"
    resp = httpx.post(
        f"{settings.next_public_supabase_url}/storage/v1/object/upload/sign/{SUBMISSIONS_BUCKET}/{object_path}",
        headers={
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        },
        timeout=10.0,
    )
    if resp.status_code >= 400:
        raise StorageError(f"Failed to create signed upload URL: {resp.status_code} {resp.text}")

    return {"upload_url": resp.json()["url"], "object_path": object_path}
