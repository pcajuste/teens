from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

SignupRole = Literal["talent", "brand", "recruiter"]


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: SignupRole
    date_of_birth: date
    parent_email: EmailStr | None = None

    @model_validator(mode="after")
    def _parent_email_not_self(self) -> "SignupRequest":
        if self.parent_email is not None and self.parent_email == self.email:
            raise ValueError("parent_email must differ from the signup email")
        return self


class SignupResponse(BaseModel):
    id: str
    email: str
    role: str
    account_status: str


class ParentVerifyResponse(BaseModel):
    account_status: str
    parent_verified_at: datetime


class ResendConsentRequest(BaseModel):
    email: EmailStr


class ResendConsentResponse(BaseModel):
    status: Literal["sent"]


class MeResponse(BaseModel):
    id: str
    email: str
    role: str
    account_status: str
    # Enough detail for the frontend to pick the right waiting screen
    # without exposing anything beyond account state. One of:
    # "awaiting_parental_consent" (under-16 talent, consent not yet given),
    # "pending_admin_approval" (brand/recruiter awaiting review), or
    # None (active, or rejected/suspended -- account_status alone covers those).
    pending_reason: Literal["awaiting_parental_consent", "pending_admin_approval"] | None = None
