"""Server-side age calculation. Never trust a client-computed age
(Section 9) -- every caller must supply `today` explicitly (the
router passes `date.today()`), so this stays a pure, unit-testable
function rather than reaching for the clock itself."""
from __future__ import annotations

from datetime import date


def compute_age(date_of_birth: date, *, today: date) -> int:
    age = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age
