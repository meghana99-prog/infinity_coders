from typing import Any


class PermissionChecker:
    """
    Verifies whether proposed interventions have the required approvals.

    Missing authorization information is treated as UNKNOWN,
    never automatically as permission granted.
    """

    ACTION_REQUIREMENTS = {
        "SHUTDOWN_REACTOR": ["shutdown_permission"],
        "ACTIVATE_BACKUP_COOLING": ["backup_cooling_approval"],
        "ISOLATE_NETWORK": ["network_isolation_approval"],
        "REDUCE_LOAD": ["load_reduction_approval"],
        "SCHEDULE_MAINTENANCE": ["maintenance_approval"],
    }

    def check(
        self,
        action: str,
        approvals: dict[str, Any]
    ) -> dict[str, Any]:

        if not isinstance(action, str) or not action.strip():
            return {
                "status": "UNKNOWN",
                "action": action,
                "violations": [],
                "unknowns": ["Action is missing or invalid"],
            }

        if not isinstance(approvals, dict):
            return {
                "status": "UNKNOWN",
                "action": action,
                "violations": [],
                "unknowns": ["Approval information is invalid"],
            }

        action = action.upper().strip()

        if action not in self.ACTION_REQUIREMENTS:
            return {
                "status": "UNKNOWN",
                "action": action,
                "violations": [],
                "unknowns": [f"No approval policy defined for {action}"],
            }

        violations = []
        unknowns = []

        required_permissions = self.ACTION_REQUIREMENTS[action]

        for permission in required_permissions:
            if permission not in approvals or approvals[permission] is None:
                unknowns.append(
                    f"Approval information missing: {permission}"
                )

            elif approvals[permission] is not True:
                violations.append(
                    f"Required approval not granted: {permission}"
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
            "required_permissions": required_permissions,
            "violations": violations,
            "unknowns": unknowns,
        }