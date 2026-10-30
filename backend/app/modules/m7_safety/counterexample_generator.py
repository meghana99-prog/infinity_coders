from typing import Any


class CounterexampleGenerator:
    """
    Converts safety verification failures and unknown conditions
    into understandable counterexample records.

    These are explanations of detected violations, not formal
    mathematical proofs of system safety.
    """

    def generate(
        self,
        action: str,
        verification_results: dict[str, Any]
    ) -> dict[str, Any]:

        if not isinstance(verification_results, dict):
            return {
                "action": action,
                "counterexamples": [],
                "status": "UNKNOWN",
                "reason": "Invalid verification results",
            }

        counterexamples = []

        components = [
            "invariants",
            "permissions",
            "resources",
            "conflicts",
        ]

        for component in components:
            result = verification_results.get(component)

            if not isinstance(result, dict):
                continue

            for violation in result.get("violations", []):
                counterexamples.append({
                    "component": component,
                    "type": "SAFETY_VIOLATION",
                    "description": str(violation),
                })

            for conflict in result.get("conflicts", []):
                counterexamples.append({
                    "component": component,
                    "type": "ACTION_CONFLICT",
                    "description": conflict.get(
                        "reason", "Action conflict detected"
                    ),
                    "actions": conflict.get("actions", []),
                })

            for unknown in result.get("unknowns", []):
                counterexamples.append({
                    "component": component,
                    "type": "UNVERIFIED_CONDITION",
                    "description": str(unknown),
                })

        if any(
            item["type"] in {"SAFETY_VIOLATION", "ACTION_CONFLICT"}
            for item in counterexamples
        ):
            status = "FAIL"
        elif counterexamples:
            status = "UNKNOWN"
        else:
            status = "NO_COUNTEREXAMPLE_FOUND"

        return {
            "action": action,
            "status": status,
            "counterexample_count": len(counterexamples),
            "counterexamples": counterexamples,
        }