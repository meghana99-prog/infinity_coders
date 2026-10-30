import pytest

from app.modules.m7_safety.invariant_checker import InvariantChecker
from app.modules.m7_safety.permission_checker import PermissionChecker
from app.modules.m7_safety.resource_checker import ResourceChecker
from app.modules.m7_safety.conflict_checker import ConflictChecker
from app.modules.m7_safety.counterexample_generator import CounterexampleGenerator
from app.modules.m7_safety.decision_certificate import DecisionCertificate


def test_invariant_pass():
    checker = InvariantChecker()

    result = checker.check({
        "temperature": 90,
        "pressure": 100,
        "cooling_capacity": 80
    })

    assert result["status"] == "PASS"


def test_invariant_fail_high_temperature():
    checker = InvariantChecker()

    result = checker.check({
        "temperature": 150,
        "pressure": 100,
        "cooling_capacity": 80
    })

    assert result["status"] == "FAIL"
    assert len(result["violations"]) > 0


def test_invariant_unknown_missing_metric():
    checker = InvariantChecker()

    result = checker.check({
        "temperature": 90,
        "pressure": 100
    })

    assert result["status"] == "UNKNOWN"


def test_permission_pass():
    checker = PermissionChecker()

    result = checker.check(
        "SHUTDOWN_REACTOR",
        {"shutdown_permission": True}
    )

    assert result["status"] == "PASS"


def test_permission_fail():
    checker = PermissionChecker()

    result = checker.check(
        "SHUTDOWN_REACTOR",
        {"shutdown_permission": False}
    )

    assert result["status"] == "FAIL"


def test_permission_unknown():
    checker = PermissionChecker()

    result = checker.check(
        "SHUTDOWN_REACTOR",
        {}
    )

    assert result["status"] == "UNKNOWN"


def test_resource_pass():
    checker = ResourceChecker()

    result = checker.check(
        "ACTIVATE_BACKUP_COOLING",
        {"cooling_capacity": 60}
    )

    assert result["status"] == "PASS"


def test_resource_fail():
    checker = ResourceChecker()

    result = checker.check(
        "ACTIVATE_BACKUP_COOLING",
        {"cooling_capacity": 20}
    )

    assert result["status"] == "FAIL"


def test_resource_unknown():
    checker = ResourceChecker()

    result = checker.check(
        "ACTIVATE_BACKUP_COOLING",
        {}
    )

    assert result["status"] == "UNKNOWN"


def test_conflict_detection():
    checker = ConflictChecker()

    result = checker.check([
        "SHUTDOWN_REACTOR",
        "CONTINUE_MONITORING"
    ])

    assert result["status"] == "FAIL"


def test_duplicate_action_detection():
    checker = ConflictChecker()

    result = checker.check([
        "ACTIVATE_BACKUP_COOLING",
        "ACTIVATE_BACKUP_COOLING"
    ])

    assert result["status"] == "FAIL"


def test_valid_action_combination():
    checker = ConflictChecker()

    result = checker.check([
        "ACTIVATE_BACKUP_COOLING",
        "ISOLATE_NETWORK"
    ])

    assert result["status"] == "PASS"


def test_counterexample_generation():
    generator = CounterexampleGenerator()

    results = {
        "invariants": {
            "status": "FAIL",
            "violations": ["Temperature exceeds maximum"],
            "unknowns": []
        }
    }

    result = generator.generate(
        "SHUTDOWN_REACTOR",
        results
    )

    assert result["status"] == "FAIL"
    assert result["counterexample_count"] == 1


def test_decision_certificate_fail():
    generator = DecisionCertificate()

    results = {
        "invariants": {
            "status": "FAIL",
            "violations": ["Temperature too high"],
            "unknowns": []
        },
        "permissions": {
            "status": "PASS",
            "violations": [],
            "unknowns": []
        },
        "resources": {
            "status": "PASS",
            "violations": [],
            "unknowns": []
        },
        "conflicts": {
            "status": "PASS",
            "conflicts": [],
            "unknowns": []
        }
    }

    certificate = generator.generate(
        "SHUTDOWN_REACTOR",
        results
    )

    assert certificate["status"] == "FAIL"
    assert certificate["execution_allowed"] is False
    assert certificate["requires_human_approval"] is True