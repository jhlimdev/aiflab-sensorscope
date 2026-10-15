"""Explicit synthetic assumptions; these are not industrial safety limits."""

import math
import os
from dataclasses import dataclass
from pathlib import Path

METRICS = {
    "temperature": {"label": "온도", "unit": "°C", "floor": 0.1},
    "vibration": {"label": "진동", "unit": "mm/s", "floor": 0.01},
    "current": {"label": "전류", "unit": "A", "floor": 0.05},
}
MACHINES = {
    "press-01": {
        "name": "프레스 01",
        "type": "Hydraulic press",
        "location": "LINE A · STATION 01",
        "mean": (55.0, 0.45, 12.0),
        "std": (1.2, 0.04, 0.35),
    },
    "motor-02": {
        "name": "모터 02",
        "type": "Drive motor",
        "location": "LINE A · STATION 02",
        "mean": (42.0, 0.30, 8.0),
        "std": (0.9, 0.03, 0.25),
    },
    "pump-03": {
        "name": "펌프 03",
        "type": "Circulation pump",
        "location": "LINE B · STATION 01",
        "mean": (38.0, 0.22, 5.5),
        "std": (0.8, 0.02, 0.20),
    },
}


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/factorypulse.sqlite3")
    simulator: bool = True
    interval: float = 1.0
    threshold: float = 3.5
    seed: int = 2026
    reading_limit: int = 3000  # Per machine.
    event_limit: int = 1000  # Global; one event per anomalous reading.

    def __post_init__(self):
        if not math.isfinite(self.interval) or not 0.1 <= self.interval <= 60:
            raise ValueError("FP_INTERVAL must be finite and between 0.1 and 60 seconds")
        if not math.isfinite(self.threshold) or not 1 <= self.threshold <= 10:
            raise ValueError("FP_THRESHOLD must be finite and between 1 and 10")
        if self.reading_limit < 1 or self.event_limit < 1:
            raise ValueError("Retention limits must be positive")

    @classmethod
    def from_env(cls):
        mode = os.getenv("FP_SIMULATOR", "true").lower()
        if mode not in {"true", "false"}:
            raise ValueError("FP_SIMULATOR must be true or false")
        return cls(
            db_path=Path(os.getenv("FP_DB_PATH", "data/factorypulse.sqlite3")),
            simulator=mode == "true",
            interval=float(os.getenv("FP_INTERVAL", "1")),
            threshold=float(os.getenv("FP_THRESHOLD", "3.5")),
            seed=int(os.getenv("FP_SEED", "2026")),
        )
