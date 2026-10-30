import pytest

from backend.app.modules.m6_defense.integration import (
    M6DefensePipeline,
)


@pytest.fixture
def pipeline():
    """Create a fresh M6 pipeline for each test."""
    return M6DefensePipeline()


def make_event(
    event_id,
    value=70,
    source="sensor_A",
    metric="temperature",
    signature_valid=True,
    event_type="telemetry",
):
    """Generate synthetic industrial telemetry."""

    return {
        "event_id": event_id,
        "source": source,
        "metric": metric,
        "value": value,
        "component_id": "COMP-01",
        "trust_score": 0.95,
        "timestamp_confidence": 0.98,
        "signature_valid": signature_valid,
        "event_type": event_type,
    }


# --------------------------------------------------
# TEST 1: VALID EVENT
# --------------------------------------------------

def test_valid_event_passes_complete_pipeline(pipeline):
    event = make_event("EV-001")

    result = pipeline.inspect_event(event)

    assert result["accepted"] is True
    assert result["status"] == "ACCEPTED"
    assert result["provenance"]["status"] == "PASS"
    assert result["replay"]["accept"] is True
    assert result["anomaly"]["status"] == "NORMAL"
    assert result["execution_allowed"] is False


# --------------------------------------------------
# TEST 2: INVALID PROVENANCE
# --------------------------------------------------

def test_invalid_provenance_blocks_event(pipeline):
    event = make_event(
        "EV-002",
        signature_valid=False,
    )

    result = pipeline.inspect_event(event)

    assert result["accepted"] is False
    assert result["status"] == "BLOCKED"
    assert result["stage"] == "PROVENANCE"


# --------------------------------------------------
# TEST 3: REPLAY DETECTION
# --------------------------------------------------

def test_replayed_event_is_blocked(pipeline):
    event = make_event("EV-003")

    first_result = pipeline.inspect_event(event)
    second_result = pipeline.inspect_event(event)

    assert first_result["accepted"] is True
    assert second_result["accepted"] is False
    assert second_result["status"] == "BLOCKED"
    assert second_result["stage"] == "REPLAY"


# --------------------------------------------------
# TEST 4: SUSPICIOUS TELEMETRY
# --------------------------------------------------

def test_suspicious_telemetry_flagged_for_review(pipeline):
    first_event = make_event(
        "EV-004",
        value=60,
    )

    second_event = make_event(
        "EV-005",
        value=100,
    )

    pipeline.inspect_event(first_event)

    result = pipeline.inspect_event(second_event)

    assert result["accepted"] is True
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["anomaly"]["status"] == "SUSPICIOUS"
    assert result["review_required"] is True


# --------------------------------------------------
# TEST 5: CROSS-SOURCE CONFLICT
# --------------------------------------------------

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


# --------------------------------------------------
# TEST 6: ADVERSARIAL AGENT RECOMMENDATION
# --------------------------------------------------

def test_adversarial_agent_recommendation_rejected(pipeline):
    recommendation = {
        "action": "delete_safety_logs",
        "confidence": 0.99,
        "evidence_ids": ["EV-006"],
        "safety_status": "PASS",
    }

    result = pipeline.inspect_recommendation(
        recommendation,
        known_evidence_ids=["EV-006"],
    )

    assert result["status"] == "REJECT"
    assert result["execution_allowed"] is False


# --------------------------------------------------
# TEST 7: VALID AGENT RECOMMENDATION
# --------------------------------------------------

def test_valid_agent_recommendation_requires_approval(pipeline):
    recommendation = {
        "action": "inspect_component",
        "confidence": 0.90,
        "evidence_ids": ["EV-007"],
        "safety_status": "PASS",
    }

    result = pipeline.inspect_recommendation(
        recommendation,
        known_evidence_ids=["EV-007"],
    )

    assert result["status"] == "PASS"
    assert result["execution_allowed"] is False
    assert result["requires_human_approval"] is True


# --------------------------------------------------
# TEST 8: LEGITIMATE EMERGENCY ALERT
# --------------------------------------------------

def test_legitimate_emergency_alert_is_preserved(pipeline):
    emergency_event = make_event(
        "EV-008",
        value=130,
        event_type="emergency_alert",
    )

    result = pipeline.inspect_event(emergency_event)

    # Suspicious emergency telemetry is retained for review.
    assert result["accepted"] is True
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["anomaly"]["status"] == "SUSPICIOUS"
    assert result["execution_allowed"] is False


# --------------------------------------------------
# TEST 9: INVALID INPUT
# --------------------------------------------------

def test_invalid_event_input_raises_error(pipeline):
    with pytest.raises(TypeError):
        pipeline.inspect_event("invalid-event")


# --------------------------------------------------
# TEST 10: PIPELINE RESET
# --------------------------------------------------

def test_reset_clears_pipeline_histories(pipeline):
    event = make_event("EV-009")

    first_result = pipeline.inspect_event(event)

    assert first_result["accepted"] is True

    pipeline.reset()

    second_result = pipeline.inspect_event(event)

    assert second_result["accepted"] is True
    assert second_result["status"] == "ACCEPTED"