from datetime import datetime

import pytest

from backend.app.models.event import Event
from backend.app.modules.m1_temporal.recon import TemporalReconstructor


def make_event(
    event_id,
    event_time,
    arrival_time,
    value,
    source="sensor_A",
    trust=0.9,
    signature=True,
    timestamp_confidence=1.0,
):
    return Event(
        event_id=event_id,
        event_time=datetime.fromisoformat(event_time),
        arrival_time=datetime.fromisoformat(arrival_time),
        source=source,
        event_type="temperature",
        value=value,
        unit="C",
        trust_score=trust,
        timestamp_confidence=timestamp_confidence,
        component_id="reactor_01",
        signature_valid=signature,
    )


def test_out_of_order_events():
    events = [
        make_event(
            "E2",
            "2026-10-30T08:02:00+00:00",
            "2026-10-30T08:03:00+00:00",
            90,
        ),
        make_event(
            "E1",
            "2026-10-30T08:01:00+00:00",
            "2026-10-30T08:05:00+00:00",
            85,
        ),
    ]

    result = TemporalReconstructor().reconstruct(events)

    ordered_ids = [
        item["event"]["event_id"]
        for item in result["event_ledger"]
    ]

    assert ordered_ids == ["E1", "E2"]


def test_duplicate_detection():
    event = make_event(
        "E1",
        "2026-10-30T08:01:00+00:00",
        "2026-10-30T08:02:00+00:00",
        85,
    )

    repeated_delivery = make_event(
        "E1",
        "2026-10-30T08:01:00+00:00",
        "2026-10-30T08:06:00+00:00",
        85,
    )

    result = TemporalReconstructor().reconstruct(
        [event, repeated_delivery]
    )

    assert result["unique_events"] == 1
    assert result["duplicate_count"] == 1


def test_conflicting_evidence():
    events = [
        make_event(
            "E1",
            "2026-10-30T08:01:00+00:00",
            "2026-10-30T08:02:00+00:00",
            85,
            source="sensor_A",
        ),
        make_event(
            "E2",
            "2026-10-30T08:01:00+00:00",
            "2026-10-30T08:03:00+00:00",
            120,
            source="sensor_B",
        ),
    ]

    result = TemporalReconstructor().reconstruct(events)

    assert result["conflict_count"] == 1
    assert result["history_count"] == 2
    assert result["conflicts"][0]["status"] == "unresolved_conflict"


def test_invalid_signature_is_preserved():
    event = make_event(
        "E1",
        "2026-10-30T08:01:00+00:00",
        "2026-10-30T08:02:00+00:00",
        95,
        signature=False,
    )

    result = TemporalReconstructor().reconstruct([event])

    assert result["unique_events"] == 1
    assert (
        result["event_ledger"][0]["reconciliation_status"]
        == "unverified_signature"
    )


def test_timezone_is_required():
    with pytest.raises(ValueError):
        make_event(
            "E1",
            "2026-10-30T08:01:00",
            "2026-10-30T08:02:00+00:00",
            85,
        )


def test_deterministic_replay():
    events = [
        make_event(
            "E2",
            "2026-10-30T08:02:00+00:00",
            "2026-10-30T08:03:00+00:00",
            90,
        ),
        make_event(
            "E1",
            "2026-10-30T08:01:00+00:00",
            "2026-10-30T08:02:00+00:00",
            85,
        ),
    ]

    engine = TemporalReconstructor()

    first = engine.reconstruct(events)
    second = engine.reconstruct(events)

    assert first == second


def test_timestamp_confidence_is_preserved():
    event = make_event(
        "E1",
        "2026-10-30T08:01:00+00:00",
        "2026-10-30T08:02:00+00:00",
        85,
        timestamp_confidence=0.3,
    )

    result = TemporalReconstructor().reconstruct([event])

    record = result["event_ledger"][0]

    assert record["timestamp_confidence"] == 0.3
    assert record["reconciliation_status"] == "requires_review"


def test_delayed_delivery_is_flagged():
    event = make_event(
        "E1",
        "2026-10-30T08:01:00+00:00",
        "2026-10-30T08:15:00+00:00",
        85,
    )

    result = TemporalReconstructor().reconstruct([event])

    anomalies = result["event_ledger"][0]["anomalies"]

    assert any(
        item["type"] == "delayed_delivery"
        for item in anomalies
    )


def test_event_id_collision_is_preserved():
    first = make_event(
        "E1",
        "2026-10-30T08:01:00+00:00",
        "2026-10-30T08:02:00+00:00",
        85,
    )

    second = make_event(
        "E1",
        "2026-10-30T08:02:00+00:00",
        "2026-10-30T08:03:00+00:00",
        95,
    )

    result = TemporalReconstructor().reconstruct([first, second])

    assert result["unique_events"] == 2
    assert len(result["event_id_collisions"]) == 1
    assert result["event_id_collisions"][0]["status"] == "event_id_collision"


def test_alternative_history_limit():
    events = []

    for index in range(4):
        events.append(
            make_event(
                f"E{index}",
                "2026-10-30T08:01:00+00:00",
                f"2026-10-30T08:0{index + 2}:00+00:00",
                80 + index * 10,
                source=f"sensor_{index}",
            )
        )

    engine = TemporalReconstructor(max_histories=2)
    result = engine.reconstruct(events)

    assert result["conflict_count"] == 1
    assert result["history_count"] == 2
    assert result["history_generation_limited"] is True


def test_invalid_configuration():
    with pytest.raises(ValueError):
        TemporalReconstructor(max_histories=0)