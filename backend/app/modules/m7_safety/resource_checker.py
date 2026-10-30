from typing import Any


class ResourceChecker:
    """
    Validates resource availability for proposed interventions.

    Resource requirements are configurable and represent synthetic
    prototype values, not certified industrial requirements.
    """

    DEFAULT_REQUIREMENTS = {
        "ACTIVATE_BACKUP_COOLING": {
            "cooling_capacity": 40.0
        },
        "ISOLATE_NETWORK": {
            "network_capacity": 10.0
        },
        "REDUCE_LOAD": {
            "power_capacity": 20.0
        },
        "SHUTDOWN_REACTOR": {
            "shutdown_resources": 1.0
        },
    }

    def __init__(self, requirements=None):
        self.requirements = (
            requirements
            if requirements is not None
            else self.DEFAULT_REQUIREMENTS
        )

    def check(
        self,
        action: str,
        available_resources: dict[str, Any]
    ) -> dict[str, Any]:

        if not isinstance(action, str) or not action.strip():
            return {
                "status": "UNKNOWN",
                "violations": [],
                "unknowns": ["Action is missing or invalid"],
            }

        if not isinstance(available_resources, dict):
            return {
                "status": "UNKNOWN",
                "violations": [],
                "unknowns": ["Resource information is invalid"],
            }

        action = action.upper().strip()

        if action not in self.requirements:
            return {
                "status": "UNKNOWN",
                "action": action,
                "violations": [],
                "unknowns": [
                    f"No resource requirements defined for {action}"
                ],
            }

        violations = []
        unknowns = []

        required = self.requirements[action]

        for resource, required_amount in required.items():

            if (
                resource not in available_resources
                or available_resources[resource] is None
            ):
                unknowns.append(
                    f"Available quantity missing for {resource}"
                )
                continue

            try:
                available = float(available_resources[resource])
                required_amount = float(required_amount)

                if available < 0 or required_amount < 0:
                    raise ValueError

            except (TypeError, ValueError):
                unknowns.append(
                    f"Invalid resource quantity for {resource}"
                )
                continue

            if available < required_amount:
                violations.append(
                    f"Insufficient {resource}: "
                    f"required {required_amount}, available {available}"
                )

        if violations:
            status = "FAIL"
        elif unknowns:
            status = "UNKNOWN"
        else:
            status = "PASS"

        return {
            "status": status,
            "action": action,
            "requirements": required,
            "violations": violations,
            "unknowns": unknowns,
        }