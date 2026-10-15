import random
from datetime import UTC, datetime

from .config import MACHINES, METRICS
from .models import Reading


class Simulator:
    def __init__(self, seed=2026):
        self.rng = random.Random(seed)
        self.pending = {}

    def inject(self, machine_id, metric):
        if machine_id in self.pending:
            raise ValueError("An injection is already running for this machine")
        self.pending[machine_id] = (metric, 8)

    def sample(self, machine_id, timestamp=None):
        spec = MACHINES[machine_id]
        values = {
            metric: self.rng.gauss(mean, std)
            for metric, mean, std in zip(METRICS, spec["mean"], spec["std"], strict=True)
        }
        if machine_id in self.pending:
            metric, remaining = self.pending[machine_id]
            # A clearly visible positive step, not a learned failure signature.
            values[metric] += 8 * spec["std"][list(METRICS).index(metric)]
            if remaining == 1:
                del self.pending[machine_id]
            else:
                self.pending[machine_id] = (metric, remaining - 1)
        return Reading(machine_id=machine_id, timestamp=timestamp or datetime.now(UTC), **values)
