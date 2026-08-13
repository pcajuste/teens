"""Build Prompt 8I pseudonym system: one persistent, brand-facing handle
per talent, generated once and never regenerated or resolvable back to
identity through any code path (spec: "no path from pseudonym to real
identity, ever -- not on request, not through an escalation, not even
through Teenure staff acting as a go-between").

Deliberately not exposed through any admin lookup-by-handle route --
that door does not exist by omission, not by a permission check that
could be misconfigured.
"""
from __future__ import annotations

import secrets
import string

import asyncpg

from app.repositories import talent_pseudonyms_repository

_ALPHABET = string.ascii_uppercase + string.digits
_HANDLE_SUFFIX_LEN = 3
_MAX_ATTEMPTS = 10


def _random_handle() -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(_HANDLE_SUFFIX_LEN))
    return f"Contributor_{suffix}"


async def get_or_create_pseudonym(conn: asyncpg.Connection, talent_id: str) -> talent_pseudonyms_repository.TalentPseudonym:
    existing = await talent_pseudonyms_repository.get_by_talent_id(conn, talent_id)
    if existing is not None:
        return existing

    for _ in range(_MAX_ATTEMPTS):
        handle = _random_handle()
        if not await talent_pseudonyms_repository.handle_exists(conn, handle):
            return await talent_pseudonyms_repository.create(conn, talent_id=talent_id, handle=handle)

    raise RuntimeError("Could not generate a unique pseudonym handle after several attempts.")
