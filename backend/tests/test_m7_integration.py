import pytest
from app.modules.m7_safety import SafetyVerificationEngine


@pytest.fixture
def engine():
    return SafetyVerificationEngine()


@pytest.fixture
def safe_state():
    return {
        "temperature": 90,
        "pressure": 100,
        "cooling_capacity": 80
    }


def test_complete_pipeline_pass(engine, safe_state):
    result = engine.verify(
        action="ACTIVATE_BACKUP_COOLING",
        state=safe_state,
        approvals={
            "backup_cooling_approval": True
        },
        available_resources={
            "cooling_capacity": 60
        }
    )

    assert result["status"] == "PASS"
    assert result["execution_allowed"] is False


def test_pipeline_rejects_unsafe_temperature(engine):
    result = engine.verify(
        action="ACTIVATE_BACKUP_COOLING",
        state={
            "temperature": 150,
            "pressure": 100,
            "cooling_capacity": 80
        },
        approvals={
            "backup_cooling_approval": True
        },
        available_resources={
            "cooling_capacity": 60
        }
    )

    assert result["status"] == "FAIL"


def test_pipeline_rejects_missing_permission(engine, safe_state):
    result = engine.verify(
        action="SHUTDOWN_REACTOR",
        state=safe_state,
        approvals={},
        available_resources={
            "shutdown_resources": 1
        }
    )

    assert result["status"] == "UNKNOWN"


def test_pipeline_rejects_insufficient_resources(engine, safe_state):
    result = engine.verify(
        action="ACTIVATE_BACKUP_COOLING",
        state=safe_state,
        approvals={
            "backup_cooling_approval": True
        },
        available_resources={
            "cooling_capacity": 10
        }
    )

    assert result["status"] == "FAIL"


def test_pipeline_detects_conflicting_actions(engine, safe_state):
    result = engine.verify(
        action="SHUTDOWN_REACTOR",
        state=safe_state,
        approvals={
            "shutdown_permission": True
        },
        available_resources={
            "shutdown_resources": 1
        },
        proposed_actions=[
            "SHUTDOWN_REACTOR",
            "CONTINUE_MONITORING"
        ]
    )

    assert result["status"] == "FAIL"


def test_pipeline_generates_counterexample(engine):
    result = engine.verify(
        action="ACTIVATE_BACKUP_COOLING",
        state={
            "temperature": 150,
            "pressure": 100,
            "cooling_capacity": 80
        },
        approvals={
            "backup_cooling_approval": True
        },
        available_resources={
            "cooling_capacity": 60
        }
    )

    counterexample = result["counterexample_result"]

    assert counterexample["status"] == "FAIL"
    assert counterexample["counterexample_count"] > 0


def test_pipeline_generates_certificate(engine, safe_state):
    result = engine.verify(
        action="ACTIVATE_BACKUP_COOLING",
        state=safe_state,
        approvals={
            "backup_cooling_approval": True
        },
        available_resources={
            "cooling_capacity": 60
        }
    )

    certificate = result["decision_certificate"]

    assert certificate["certificate_id"]
    assert certificate["status"] == "PASS"
    assert certificate["checked_components"] == 4
    assert certificate["execution_allowed"] is False


def test_unknown_state_does_not_pass(engine):
    result = engine.verify(
        action="ACTIVATE_BACKUP_COOLING",
        state={
            "temperature": 90,
            "pressure": 100
        },
        approvals={
            "backup_cooling_approval": True
        },
        available_resources={
            "cooling_capacity": 60
        }
    )

    assert result["status"] == "UNKNOWN"
    assert result["requires_human_approval"] is True