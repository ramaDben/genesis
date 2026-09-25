"""Shared value objects for genesis hooks."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GuardOutcome(BaseModel):
    """Result of a validation gate.

    Attributes:
        exit_code: 0 = allow, 2 = deny/block.
        stderr: Optional human-readable reason (written to stderr for debug).
    """

    exit_code: int = Field(default=0, ge=0, le=2, description="0 = allow, 2 = deny/block")
    stderr: str = Field(default="", description="Debug/reason message for stderr")
