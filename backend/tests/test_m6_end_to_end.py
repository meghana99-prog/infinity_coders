import pytest

from backend.app.modules.m6_defense.integration import (
    M6DefensePipeline,
)


@pytest.fixture
def pipeline():
    return M6DefensePipeline()


def make_event(event_id, value, source="sensor_A",
               signature_valid=True):
    return {
        "event_id": event_id,
        "source": source,
        "metric": "temperature",
        "value": value,
        "component_id": "COMP-01",
        "trust_score": 0.95,
        "timestamp_confidence": 0.98,
        "signature_valid": signature_valid,
    }


def test_combined_invalid_provenance_and_replay(pipeline):
    invalid = make_event(
        "ATTACK-001", 70, signature_valid=False
    )

    first = pipeline.inspect_event(invalid)
    second = pipeline.inspect_event(invalid)

    assert first["status"] == "BLOCKED"
    assert first["stage"] == "PROVENANCE"

    # Provenance rejection occurs before replay inspection.
    assert second["status"] == "BLOCKED"
    assert second["stage"] == "PROVENANCE"


def test_combined_replay_and_anomaly_detection(pipeline):
    normal = make_event("EVENT-001", 60)
    suspicious = make_event("EVENT-002", 100)

    first = pipeline.inspect_event(normal)
    second = pipeline.inspect_event(suspicious)
    replay = pipeline.inspect_event(suspicious)

    assert first["status"] == "ACCEPTED"
    assert second["status"] == "REVIEW_REQUIRED"
    assert second["anomaly"]["status"] == "SUSPICIOUS"
    assert replay["status"] == "BLOCKED"
    assert replay["stage"] == "REPLAY"


def test_conflicting_sources_are_detected(pipeline):
    observations = [
        {
            "source": "sensor_A",
            "component_id": "COMP-01",
            "metric": "temperature",
            "value": 85,
        },
        {
            "source": "sensor_B",
            "component_id": "COMP-01",
            "metric": "temperature",
            "value": 160,
        },
    ]

    result = pipeline.inspect_consistency(observations)

    assert result["status"] == "CONFLICT"


def test_emergency_event_is_preserved_for_review(pipeline):
    emergency = make_event("EMERGENCY-001", 130)

    result = pipeline.inspect_event(emergency)

    assert result["accepted"] is True
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["review_required"] is True
    assert result["execution_allowed"] is False


def test_pipeline_reset_allows_new_event(pipeline):
    event = make_event("RESET-001", 70)

    first = pipeline.inspect_event(event)
    assert first["accepted"] is True

    pipeline.reset()

    second = pipeline.inspect_event(event)
    assert second["accepted"] is True