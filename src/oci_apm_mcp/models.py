"""Stable public response models for MCP tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ResponseStatus = Literal[
    "success",
    "no_data",
    "needs_clarification",
    "invalid_request",
    "unauthorized",
    "not_found",
    "rate_limited",
    "partial",
    "error",
]


class Scope(BaseModel):
    """Effective OCI scope, with sensitive identifiers masked."""

    model_config = ConfigDict(extra="forbid")

    region: str | None = None
    compartment_id: str | None = None
    apm_domain_id: str | None = None


class TimeWindow(BaseModel):
    """Normalized UTC time bounds used for an APM query or trace lookup."""

    model_config = ConfigDict(extra="forbid")

    start: str
    end: str


class Pagination(BaseModel):
    """Opaque OCI pagination state and server-side truncation metadata."""

    model_config = ConfigDict(extra="forbid")

    next_page: str | None = None
    truncated: bool = False


class ToolResponse(BaseModel):
    """Common response envelope for every public tool."""

    model_config = ConfigDict(extra="forbid")

    status: ResponseStatus
    request_id: str | None = None
    scope: Scope
    time_window: TimeWindow | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    pagination: Pagination | None = None
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    partial: bool = False
    timing_ms: int = Field(ge=0)

    def as_dict(self) -> dict[str, Any]:
        """Serialize using JSON-safe values for structured MCP output."""
        return self.model_dump(mode="json")
