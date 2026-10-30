from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Event(BaseModel):
    """Validated event received by the CHRONOS-X system."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    event_time: datetime
    arrival_time: datetime

    source: str = Field(min_length=1)
    event_type: str = Field(min_length=1)

    value: Any
    unit: str | None = None

    trust_score: float = Field(ge=0.0, le=1.0)
    timestamp_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    component_id: str = Field(min_length=1)
    signature_valid: bool | None = None

    @field_validator("event_time", "arrival_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamps must include a timezone.")
        return value

    @property
    def evidence_score(self) -> float:
        """
        A ranking score for evidence quality.
        This is not a probability that the event is true.
        """

        signature_factor = (
            1.0 if self.signature_valid is True
            else 0.5 if self.signature_valid is None
            else 0.0
        )

        return round(
            self.trust_score
            * self.timestamp_confidence
            * signature_factor,
            4,
        )

    def to_record(self) -> dict:
        """Return a JSON-compatible representation."""
        return self.model_dump(mode="json")