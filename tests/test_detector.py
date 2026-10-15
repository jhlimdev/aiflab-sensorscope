import copy
import math

import pytest

from factorypulse.config import MACHINES, METRICS, Settings
from factorypulse.detector import Detector
from factorypulse.simulator import Simulator


@pytest.mark.parametrize("machine_id", MACHINES)
def test_reference_mean_is_normal_and_large_shift_detected(machine_id):
    detector = Detector()
    reference = detector.baselines[machine_id]
    values = {metric: reference[metric]["mean"] for metric in METRICS}
    assert detector.evaluate(machine_id, values)["status"] == "normal"
    values["vibration"] += 8 * reference["vibration"]["std"]
    result = detector.evaluate(machine_id, values)
    assert result["anomalies"] == ["vibration"]
    assert result["scores"]["vibration"] == pytest.approx(8)


def test_repeated_anomalies_do_not_contaminate_baseline():
    detector = Detector()
    before = copy.deepcopy(detector.baselines)
    for _ in range(300):
        assert (
            detector.evaluate("press-01", {"temperature": 100, "vibration": 4, "current": 30})[
                "status"
            ]
            == "anomaly"
        )
    assert detector.baselines == before


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_nonfinite_rejected(value):
    with pytest.raises(ValueError):
        Detector().evaluate("press-01", {"temperature": value, "vibration": 0.45, "current": 12})


def test_negative_deviation_and_threshold_change():
    strict, relaxed = Detector(3), Detector(5)
    ref = strict.baselines["press-01"]
    values = {metric: ref[metric]["mean"] for metric in METRICS}
    values["temperature"] -= 4 * ref["temperature"]["std"]
    assert strict.evaluate("press-01", values)["anomalies"] == ["temperature"]
    assert relaxed.evaluate("press-01", values)["status"] == "normal"


def test_injection_lasts_eight_samples_and_does_not_change_other_machines():
    normal, injected = Simulator(456), Simulator(456)
    injected.inject("press-01", "current")
    with pytest.raises(ValueError):
        injected.inject("press-01", "vibration")
    for i in range(10):
        a, b = normal.sample("press-01"), injected.sample("press-01")
        assert b.current - a.current == pytest.approx(2.8 if i < 8 else 0)
        assert a.temperature == b.temperature
        assert a.vibration == b.vibration
        a, b = normal.sample("motor-02"), injected.sample("motor-02")
        assert a.current == b.current


@pytest.mark.parametrize(
    "kwargs",
    [
        {"interval": 0},
        {"interval": math.nan},
        {"threshold": math.inf},
        {"threshold": 0},
        {"event_limit": 0},
    ],
)
def test_invalid_settings_fail_fast(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)
