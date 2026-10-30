from typing import Any


class ConflictChecker:
    """
    Detects mutually exclusive and duplicate interventions.

    Conflict rules are configurable for the synthetic CHRONOS-X
    prototype. They must be validated against the simulator contract.
    """

    DEFAULT_CONFLICTS = [
        {"SHUTDOWN_REACTOR", "CONTINUE_MONITORING"},
        {"SHUTDOWN_REACTOR", "REDUCE_LOAD"},
    ]

    def __init__(self, conflicts=None):
        self.conflicts = (
            conflicts
            if conflicts is not None
            else self.DEFAULT_CONFLICTS
        )

    def check(self, actions: list[str]) -> dict[str, Any]:

        if not isinstance(actions, list):
            return {
                "status": "UNKNOWN",
                "conflicts": [],
                "unknowns": ["Actions must be provided as a list"],
            }

        normalized = []

        for action in actions:
            if not isinstance(action, str) or not action.strip():
                return {
                    "status": "UNKNOWN",
                    "conflicts": [],
                    "unknowns": ["An action is missing or invalid"],
                }

            normalized.append(action.upper().strip())

        conflicts_found = []
        unknowns = []

        # Detect duplicate actions.
        if len(normalized) != len(set(normalized)):
            duplicates = sorted({
                action for action in normalized
                if normalized.count(action) > 1
            })

            conflicts_found.append({
                "type": "DUPLICATE_ACTION",
                "actions": duplicates,
                "reason": "The same action appears more than once",
            })

        # Detect mutually exclusive action pairs.
        selected = set(normalized)

        for conflict_pair in self.conflicts:
            if conflict_pair.issubset(selected):
                conflicts_found.append({
                    "type": "MUTUALLY_EXCLUSIVE",
                    "actions": sorted(conflict_pair),
                    "reason": "These actions cannot be selected together",
                })

        if conflicts_found:
            status = "FAIL"
        elif unknowns:
            status = "UNKNOWN"
        else:
            status = "PASS"

        return {
            "status": status,
            "checked_actions": normalized,
            "conflicts": conflicts_found,
            "unknowns": unknowns,
        }