from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ActionType = Literal["issue_credit", "send_marketing", "schedule_callback", "resolve_case"]


class DecisionContract(BaseModel):
    """Typed, bounded contract submitted by an autonomous business agent."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=3, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=96)
    agent_id: str = Field(min_length=3, max_length=64)
    customer_id: str = Field(min_length=3, max_length=64)
    action_type: ActionType
    amount_mad: float = Field(default=0, ge=0, le=100_000)
    channel: Literal["email", "sms", "phone", "internal", "none"] = "none"
    priority: int = Field(default=3, ge=1, le=5)
    utility: int = Field(default=50, ge=1, le=100)
    allow_partial: bool = False
    reversible: bool = True
    requires_human: bool = False
    proposed_at: datetime
    expires_at: datetime | None = None
    expected_state_version: int | None = Field(default=None, ge=1)
    evidence: list[str] = Field(default_factory=list, max_length=8)
    rationale: str = Field(default="", max_length=500)
    context_note: str = Field(default="", max_length=500)

    @field_validator("proposal_id", "idempotency_key", "agent_id", "customer_id")
    @classmethod
    def safe_identifiers(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", value):
            raise ValueError("Identifiers may contain only letters, digits, dot, underscore, colon and hyphen")
        return value

    @field_validator("proposed_at", "expires_at")
    @classmethod
    def timezone_aware_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def action_shape_is_valid(self) -> "DecisionContract":
        if self.action_type == "issue_credit" and self.amount_mad <= 0:
            raise ValueError("Credit proposals must have a positive amount")
        if self.action_type != "issue_credit" and self.amount_mad != 0:
            raise ValueError("Only credit proposals may carry an amount")
        if self.action_type == "send_marketing" and self.channel not in ("email", "sms"):
            raise ValueError("Marketing requires email or SMS channel")
        if self.expires_at is not None and self.expires_at <= self.proposed_at:
            raise ValueError("expires_at must be later than proposed_at")
        return self

    def public_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DecisionBatch(BaseModel):
    """External adapter envelope for one coordinated multi-agent decision."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=3, max_length=64)
    customer_id: str = Field(min_length=3, max_length=64)
    proposals: list[DecisionContract] = Field(min_length=1, max_length=20)
