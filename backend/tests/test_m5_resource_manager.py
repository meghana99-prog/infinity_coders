import pytest

from app.modules.m5_stochastic_simulation.resource_manager import (
    validate_resource_plan,
)


@pytest.fixture
def inventory():
    return {
        "capacities": {
            "power": {"capacity": 1},
            "operators": {"capacity": 2},
            "authorization": {"capacity": 0},
        },
        "current_availability": {
            "power": 1,
            "operators": 2,
            "authorization": 0,
        },
    }


def test_valid_resource_plan_passes(inventory):
    actions = [
        {"action": "COOLING", "resources": {"power": 1}},
        {"action": "ISOLATION", "resources": {"operators": 1}},
    ]

    result = validate_resource_plan(inventory, actions)

    assert result["status"] == "PASS"
    assert result["feasible"] is True
    assert result["remaining_resources"]["power"] == 0
    assert result["remaining_resources"]["operators"] == 1
    assert result["execution_authorized"] is False


def test_resource_overallocation_fails(inventory):
    actions = [
        {"action": "ACTION_A", "resources": {"operators": 2}},
        {"action": "ACTION_B", "resources": {"operators": 1}},
    ]

    result = validate_resource_plan(inventory, actions)

    assert result["status"] == "FAIL"
    assert result["feasible"] is False
    assert len(result["violations"]) > 0


def test_unknown_resource_returns_unknown(inventory):
    actions = [
        {"action": "ACTION_A", "resources": {"unknown_resource": 1}},
    ]

    result = validate_resource_plan(inventory, actions)

    assert result["status"] == "UNKNOWN"
    assert result["feasible"] is False


def test_qualitative_resource_values_are_rejected(inventory):
    actions = [
        {"action": "COOLING", "resources": {"power": "medium"}},
    ]

    result = validate_resource_plan(inventory, actions)

    assert result["status"] == "UNKNOWN"
    assert result["feasible"] is False


def test_empty_plan_returns_unknown(inventory):
    result = validate_resource_plan(inventory, [])

    assert result["status"] == "UNKNOWN"
    assert result["feasible"] is False