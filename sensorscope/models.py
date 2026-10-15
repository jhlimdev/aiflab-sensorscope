from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MachineId = Literal["press-01", "motor-02", "pump-03"]
Metric = Literal["temperature", "vibration", "current"]


class Reading(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    machine_id: MachineId
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    temperature: float = Field(ge=-50, le=250)
    vibration: float = Field(ge=0, le=100)
    current: float = Field(ge=0, le=500)

    @field_validator("timestamp")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        value = value.astimezone(UTC)
        if value > datetime.now(UTC) + timedelta(seconds=5):
            raise ValueError("timestamp cannot be more than 5 seconds in the future")
        return value


class Injection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine_id: MachineId
    metric: Metric = "vibration"
