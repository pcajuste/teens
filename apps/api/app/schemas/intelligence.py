"""Response schemas for the Intelligence Layer trend-report endpoints
(Build Prompt 14 deliverable 4)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

InsufficientSampleSize = Literal["insufficient sample size"]


class TrendBucketResponse(BaseModel):
    group: str
    # int when the group has >=10 underlying events; otherwise the
    # explicit marker string -- never a real number below 10, never
    # empty/null (Build Prompt 14 acceptance criterion).
    sample_size: int | InsufficientSampleSize
    completed_share: float | InsufficientSampleSize
