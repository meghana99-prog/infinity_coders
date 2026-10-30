from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class DecisionCertificate:
    """
    Generates an auditable machine-readable safety certificate.

    PASS means all configured checks passed. It does not mean
    the industrial system is formally or universally proven safe.
    """

    VALID_STATUSES = {"PASS", "FAIL", "UNKNOWN"}

    def generate(
        self,
        action: str,
        verification_results: dict[str, Any],
        counterexample_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        if not isinstance(verification_results, dict):
            verification_results = {}

        component_statuses = {}
        violations = []
        unknowns = []

        components = [
            "invariants",
            "permissions",
            "resources",
            "conflicts",
        ]

        for component in components:
            result = verification_results.get(component)

            if not isinstance(result, dict):
                component_statuses[component] = "UNKNOWN"
                unknowns.append(
                    f"{component} verification result is missing"
                )
                continue

            status = result.get("status", "UNKNOWN")

            if status not in self.VALID_STATUSES:
                status = "UNKNOWN"

            component_statuses[component] = status

            violations.extend(
                result.get("violations", [])
            )

            for conflict in result.get("conflicts", []):
                violations.append(
                    conflict.get("reason", "Action conflict detected")
                )

            unknowns.extend(result.get("unknowns", []))

        statuses = list(component_statuses.values())

        if "FAIL" in statuses:
            overall_status = "FAIL"
        elif "UNKNOWN" in statuses:
            overall_status = "UNKNOWN"
        else:
            overall_status = "PASS"

        return {
            "certificate_id": str(uuid4()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": overall_status,
            "component_statuses": component_statuses,
            "checked_components": len(components),
            "violations": violations,
            "unknowns": unknowns,
            "counterexamples": (
                counterexample_result.get("counterexamples", [])
                if isinstance(counterexample_result, dict)
                else []
            ),
            "requires_human_approval": overall_status != "PASS",
            "execution_allowed": False,
            "verification_scope": (
                "Configured prototype checks only; "
                "not formal proof of real-world industrial safety."
            ),
        }