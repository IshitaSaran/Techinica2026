"""Shared Finding model — every forensic result in Sift is returned as one of these.

The frontend renders Findings generically, so any new pipeline only needs to
produce Findings to show up in the UI (and get plain-language explanations).
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"


Stage = Literal["search", "stego", "crypto", "metadata"]


class Education(BaseModel):
    what: str = ""
    why: str = ""
    how: str = ""


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    stage: Stage
    # `kind` is an internal key (e.g. "stego.lsb_payload") used to pick the
    # templated explanation; it's harmless extra data for the frontend.
    kind: str = ""
    title: str
    severity: Severity = Severity.info
    summary: str
    technical: str = ""
    education: Education = Field(default_factory=Education)
    data: dict[str, Any] = Field(default_factory=dict)
