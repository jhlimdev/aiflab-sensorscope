"""Frozen per-machine univariate z-scores fitted on separate synthetic data."""

import math
import random
import statistics

from .config import MACHINES, METRICS


class Detector:
    def __init__(self, threshold: float = 3.5):
        self.threshold = threshold
        rng = random.Random(1729)  # Independent from the live simulator seed.
        self.baselines = {}
        for machine_id, spec in MACHINES.items():
            baseline = {}
            for metric, mean, std in zip(METRICS, spec["mean"], spec["std"], strict=True):
                reference = [rng.gauss(mean, std) for _ in range(240)]
                baseline[metric] = {
                    "mean": statistics.mean(reference),
                    "std": max(statistics.stdev(reference), METRICS[metric]["floor"]),
                    "samples": len(reference),
                }
            self.baselines[machine_id] = baseline

    def evaluate(self, machine_id: str, values: dict) -> dict:
        scores = {}
        for metric, reference in self.baselines[machine_id].items():
            value = values[metric]
            if not math.isfinite(value):
                raise ValueError("Sensor values must be finite")
            scores[metric] = abs(value - reference["mean"]) / reference["std"]
        anomalies = [metric for metric, score in scores.items() if score >= self.threshold]
        return {
            "status": "anomaly" if anomalies else "normal",
            "scores": scores,
            "anomalies": anomalies,
            "threshold": self.threshold,
        }
