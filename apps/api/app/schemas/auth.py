from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    role: Literal["rep", "brand", "recruiter"]
    date_of_birth: date
    parent_email: EmailStr | None = None


class SignupResponse(BaseModel):
    user_id: str
    email: str
    role: str
    account_status: str


class ResendConsentRequest(BaseModel):
    email: EmailStr


class MeResponse(BaseModel):
    id: str
    email: str
    role: str
    account_status: str
    pending_reason: str | None = None
