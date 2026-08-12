"""Field-level encryption for data Section 7's schema comments flag as
"stored encrypted in production" -- currently just brand_profiles.ein
(Build Prompt 8 deliverable 1). Uses Fernet (symmetric, authenticated
encryption -- AES-128-CBC + HMAC, from the `cryptography` package
already a dependency as of Prompt 7's stripe_service.py) rather than
relying on Postgres-level column encryption (pgcrypto), so the
plaintext EIN never round-trips through the database layer at all, and
the encryption key lives only in application config, not in a
DB-accessible secret.

`EIN_ENCRYPTION_KEY` must be a urlsafe-base64-encoded 32-byte key --
generate one with `Fernet.generate_key()`. Rotating this key requires
re-encrypting every stored EIN; no rotation mechanism exists yet
(out of scope for MVP, same as this repo's other single-secret designs
like SUPABASE_JWT_SECRET)."""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings


class EinDecryptionError(Exception):
    pass


@lru_cache
def _fernet(key: str) -> Fernet:
    return Fernet(key.encode())


def encrypt_ein(settings: Settings, ein: str) -> str:
    return _fernet(settings.ein_encryption_key).encrypt(ein.encode()).decode()


def decrypt_ein(settings: Settings, encrypted_ein: str) -> str:
    try:
        return _fernet(settings.ein_encryption_key).decrypt(encrypted_ein.encode()).decode()
    except InvalidToken as exc:
        raise EinDecryptionError("Stored EIN could not be decrypted -- wrong key or corrupted value.") from exc
