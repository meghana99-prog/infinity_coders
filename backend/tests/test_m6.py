import pytest

from backend.app.modules.m6_defense.provenance import (
    ProvenanceValidator,
)


@pytest.fixture
def validator():
    return ProvenanceValidator()


@pytest.fixture
def valid_event():
    return {
        "event_id": "EVT-001",
        "event_type": "TEMPERATURE_READING",
        "source": "SENSOR-01",
        "trust_score": 0.95,
        "timestamp_confidence": 0.98,
        "signature_valid": True,
    }


def test_valid_event_passes(validator, valid_event):
    result = validator.validate(valid_event)

    assert result["status"] == "PASS"


def test_invalid_signature_fails(validator, valid_event):
    valid_event["signature_valid"] = False

    result = validator.validate(valid_event)

    assert result["status"] == "FAIL"


def test_low_trust_score_fails(validator, valid_event):
    valid_event["trust_score"] = 0.2

    result = validator.validate(valid_event)

    assert result["status"] == "FAIL"


def test_low_timestamp_confidence_fails(validator, valid_event):
    valid_event["timestamp_confidence"] = 0.2

    result = validator.validate(valid_event)

    assert result["status"] == "FAIL"


def test_missing_signature_returns_unknown(validator, valid_event):
    valid_event["signature_valid"] = None

    result = validator.validate(valid_event)

    assert result["status"] == "UNKNOWN"


def test_missing_trust_score_returns_unknown(validator, valid_event):
    del valid_event["trust_score"]

    result = validator.validate(valid_event)

    assert result["status"] == "UNKNOWN"


def test_nested_event_record_passes(validator, valid_event):
    record = {"event": valid_event}

    result = validator.validate(record)

    assert result["status"] == "PASS"


def test_invalid_event_input_raises_error(validator):
    with pytest.raises(TypeError):
        validator.validate("invalid event")


def test_invalid_threshold_raises_error():
    with pytest.raises(ValueError):
        ProvenanceValidator(minimum_trust_score=1.5)
        
from backend.app.modules.m6_defense.replay_detector import (
    ReplayDetector,
)


def test_new_event_is_accepted():
    detector = ReplayDetector()

    event = {"event_id": "EVT-101", "value": 85.5}

    result = detector.inspect(event)

    assert result["status"] == "NEW"
    assert result["accept"] is True


def test_exact_replay_is_rejected():
    detector = ReplayDetector()

    event = {"event_id": "EVT-102", "value": 90}

    detector.inspect(event)
    result = detector.inspect(event)

    assert result["status"] == "REPLAY"
    assert result["accept"] is False


def test_reused_id_with_different_payload_is_rejected():
    detector = ReplayDetector()

    detector.inspect({
        "event_id": "EVT-103",
        "value": 90,
    })

    result = detector.inspect({
        "event_id": "EVT-103",
        "value": 110,
    })

    assert result["status"] == "ID_COLLISION"
    assert result["accept"] is False


def test_distinct_event_ids_are_accepted():
    detector = ReplayDetector()

    first = detector.inspect({
        "event_id": "EVT-104",
        "value": 90,
    })

    second = detector.inspect({
        "event_id": "EVT-105",
        "value": 90,
    })

    assert first["accept"] is True
    assert second["accept"] is True


def test_missing_event_id_returns_unknown():
    detector = ReplayDetector()

    result = detector.inspect({"value": 90})

    assert result["status"] == "UNKNOWN"
    assert result["accept"] is False


def test_invalid_input_raises_error():
    detector = ReplayDetector()

    with pytest.raises(TypeError):
        detector.inspect("invalid")


def test_reset_clears_replay_history():
    detector = ReplayDetector()

    event = {"event_id": "EVT-106", "value": 90}

    detector.inspect(event)
    detector.reset()

    result = detector.inspect(event)

    assert result["status"] == "NEW"
    assert result["accept"] is True
    
from backend.app.modules.m6_defense.anomaly_detector import (
    AnomalyDetector,
)


def test_normal_sensor_reading():
    detector = AnomalyDetector()

    result = detector.inspect({
        "event_id": "E1",
        "source": "SENSOR-1",
        "metric": "temperature",
        "value": 85,
    })

    assert result["status"] == "NORMAL"


def test_temperature_limit_exceeded():
    detector = AnomalyDetector()

    result = detector.inspect({
        "event_id": "E2",
        "source": "SENSOR-1",
        "metric": "temperature",
        "value": 150,
    })

    assert result["status"] == "SUSPICIOUS"
    assert "OPERATING_LIMIT_EXCEEDED" in result["anomalies"]


def test_sudden_temperature_change():
    detector = AnomalyDetector()

    detector.inspect({
        "event_id": "E3",
        "source": "SENSOR-1",
        "metric": "temperature",
        "value": 85,
    })

    result = detector.inspect({
        "event_id": "E4",
        "source": "SENSOR-1",
        "metric": "temperature",
        "value": 115,
    })

    assert "SUDDEN_VALUE_CHANGE" in result["anomalies"]


def test_different_sensors_have_independent_history():
    detector = AnomalyDetector()

    detector.inspect({
        "event_id": "E5",
        "source": "SENSOR-1",
        "metric": "temperature",
        "value": 85,
    })

    result = detector.inspect({
        "event_id": "E6",
        "source": "SENSOR-2",
        "metric": "temperature",
        "value": 115,
    })

    assert result["status"] == "NORMAL"


def test_non_numeric_reading_returns_unknown():
    detector = AnomalyDetector()

    result = detector.inspect({
        "event_id": "E7",
        "source": "SENSOR-1",
        "metric": "temperature",
        "value": "invalid",
    })

    assert result["status"] == "UNKNOWN"


def test_missing_sensor_metadata_returns_unknown():
    detector = AnomalyDetector()

    result = detector.inspect({
        "event_id": "E8",
        "value": 85,
    })

    assert result["status"] == "UNKNOWN"


def test_reset_clears_sensor_history():
    detector = AnomalyDetector()

    detector.inspect({
        "event_id": "E9",
        "source": "SENSOR-1",
        "metric": "temperature",
        "value": 85,
    })

    detector.reset()

    result = detector.inspect({
        "event_id": "E10",
        "source": "SENSOR-1",
        "metric": "temperature",
        "value": 115,
    })

    assert result["status"] == "NORMAL"
    
from backend.app.modules.m6_defense.consistency_checker import (
    ConsistencyChecker,
)


def test_consistent_sources():
    checker = ConsistencyChecker(tolerance=5)

    result = checker.inspect([
        {"source": "S1", "component_id": "R1",
         "metric": "temperature", "value": 85},
        {"source": "S2", "component_id": "R1",
         "metric": "temperature", "value": 87},
    ])

    assert result["status"] == "CONSISTENT"


def test_conflicting_sources():
    checker = ConsistencyChecker(tolerance=5)

    result = checker.inspect([
        {"source": "S1", "component_id": "R1",
         "metric": "temperature", "value": 85},
        {"source": "S2", "component_id": "R1",
         "metric": "temperature", "value": 160},
    ])

    assert result["status"] == "CONFLICT"


def test_single_source_returns_unknown():
    checker = ConsistencyChecker()

    result = checker.inspect([
        {"source": "S1", "component_id": "R1",
         "metric": "temperature", "value": 85},
    ])

    assert result["status"] == "UNKNOWN"


def test_different_components_are_separate():
    checker = ConsistencyChecker()

    result = checker.inspect([
        {"source": "S1", "component_id": "R1",
         "metric": "temperature", "value": 85},
        {"source": "S2", "component_id": "R2",
         "metric": "temperature", "value": 160},
    ])

    assert result["status"] == "UNKNOWN"
    assert result["groups_checked"] == 2


def test_duplicate_records_from_same_source():
    checker = ConsistencyChecker()

    result = checker.inspect([
        {"source": "S1", "component_id": "R1",
         "metric": "temperature", "value": 85},
        {"source": "S1", "component_id": "R1",
         "metric": "temperature", "value": 86},
        {"source": "S2", "component_id": "R1",
         "metric": "temperature", "value": 87},
    ])

    assert result["results"][0]["source_count"] == 2
    assert result["status"] == "CONSISTENT"


def test_invalid_input_raises_error():
    checker = ConsistencyChecker()

    with pytest.raises(TypeError):
        checker.inspect("invalid")
        
from backend.app.modules.m6_defense.agent_guard import (
    AgentRecommendationGuard,
)


def test_valid_recommendation_passes():
    guard = AgentRecommendationGuard()

    result = guard.inspect(
        {
            "action": "inspect_component",
            "confidence": 0.90,
            "evidence_ids": ["EV-001"],
            "safety_status": "PASS",
        },
        known_evidence_ids=["EV-001"],
    )

    assert result["status"] == "PASS"
    assert result["execution_allowed"] is False
    assert result["requires_human_approval"] is True


def test_blocked_action_is_rejected():
    guard = AgentRecommendationGuard()

    result = guard.inspect(
        {
            "action": "delete_safety_logs",
            "confidence": 0.95,
            "evidence_ids": ["EV-001"],
            "safety_status": "PASS",
        },
        ["EV-001"],
    )

    assert result["status"] == "REJECT"


def test_failed_safety_check_is_rejected():
    guard = AgentRecommendationGuard()

    result = guard.inspect(
        {
            "action": "reduce_load",
            "confidence": 0.90,
            "evidence_ids": ["EV-001"],
            "safety_status": "FAIL",
        },
        ["EV-001"],
    )

    assert result["status"] == "REJECT"


def test_unknown_safety_status_is_not_approved():
    guard = AgentRecommendationGuard()

    result = guard.inspect(
        {
            "action": "inspect_component",
            "confidence": 0.90,
            "evidence_ids": ["EV-001"],
            "safety_status": "UNKNOWN",
        },
        ["EV-001"],
    )

    assert result["status"] == "UNKNOWN"


def test_missing_evidence_is_unknown():
    guard = AgentRecommendationGuard()

    result = guard.inspect(
        {
            "action": "inspect_component",
            "confidence": 0.90,
            "evidence_ids": [],
            "safety_status": "PASS",
        },
        ["EV-001"],
    )

    assert result["status"] == "UNKNOWN"


def test_unknown_evidence_reference_is_rejected():
    guard = AgentRecommendationGuard()

    result = guard.inspect(
        {
            "action": "inspect_component",
            "confidence": 0.90,
            "evidence_ids": ["EV-999"],
            "safety_status": "PASS",
        },
        ["EV-001"],
    )

    assert result["status"] == "REJECT"


def test_invalid_confidence_is_rejected():
    guard = AgentRecommendationGuard()

    result = guard.inspect(
        {
            "action": "inspect_component",
            "confidence": 1.5,
            "evidence_ids": ["EV-001"],
            "safety_status": "PASS",
        },
        ["EV-001"],
    )

    assert result["status"] == "REJECT"


def test_invalid_recommendation_input_raises_error():
    guard = AgentRecommendationGuard()

    import pytest

    with pytest.raises(TypeError):
        guard.inspect("invalid", ["EV-001"])