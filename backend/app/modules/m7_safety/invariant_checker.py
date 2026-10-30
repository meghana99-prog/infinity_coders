from typing import Any


class InvariantChecker:
    """
    Checks equipment states against configured safety invariants.

    This is a deterministic prototype checker.
    Limits must be supplied by the scenario or validated configuration.
    """

    DEFAULT_INVARIANTS = {
        "temperature": {"min": 0.0, "max": 120.0},
        "pressure": {"min": 0.0, "max": 200.0},
        "cooling_capacity": {"min": 20.0, "max": 100.0},
    }

    def __init__(self, invariants=None):
        self.invariants = invariants or self.DEFAULT_INVARIANTS

    def check(self, state: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(state, dict):
            return {
                "status": "UNKNOWN",
                "violations": [],
                "reason": "Invalid state input",
            }

        violations = []
        unknowns = []

        for metric, limits in self.invariants.items():
            if metric not in state or state[metric] is None:
                unknowns.append(f"Missing value for {metric}")
                continue

            try:
                value = float(state[metric])
                minimum = float(limits["min"])
                maximum = float(limits["max"])
            except (TypeError, ValueError, KeyError):
                unknowns.append(f"Invalid value or limits for {metric}")
                continue

            if minimum > maximum:
                unknowns.append(f"Invalid invariant configuration for {metric}")
                continue

            if value < minimum:
                violations.append(
                    f"{metric}={value} is below minimum {minimum}"
                )

            elif value > maximum:
                violations.append(
                    f"{metric}={value} exceeds maximum {maximum}"
                )

        if violations:
            status = "FAIL"
        elif unknowns:
            status = "UNKNOWN"
        else:
            status = "PASS"

        return {
            "status": status,
            "violations": violations,
            "unknowns": unknowns,
            "checked_invariants": len(self.invariants),
        }