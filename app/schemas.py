from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class WeightEntry(BaseModel):
    weight: float
    unit: str
    date: str
    source: str

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("date must be ISO 8601 format") from exc
        return v


class WeightResponse(BaseModel):
    id: int
    weight: float
    unit: str
    date: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GripGainsLogResponse(BaseModel):
    id: int
    weight_record_id: int | None
    date: str
    weight_lbs: float
    source: str
    success: bool
    response: Any
    created_at: datetime

    model_config = {"from_attributes": True}
