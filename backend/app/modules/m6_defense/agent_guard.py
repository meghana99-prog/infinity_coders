class AgentRecommendationGuard:
    """
    Validates agent recommendations before they can be considered
    for human review.

    This prototype does not execute industrial actions.
    """

    def __init__(self, allowed_actions=None):
        self.allowed_actions = set(
            allowed_actions or {
                "inspect_component",
                "increase_monitoring",
                "notify_operator",
                "schedule_maintenance",
                "reduce_load",
                "shutdown_equipment",
            }
        )

    def inspect(self, recommendation, known_evidence_ids):
        if not isinstance(recommendation, dict):
            raise TypeError("recommendation must be a dictionary")

        if not isinstance(known_evidence_ids, (list, set, tuple)):
            raise TypeError("known_evidence_ids must be a list, set, or tuple")

        action = recommendation.get("action")
        confidence = recommendation.get("confidence")
        evidence_ids = recommendation.get("evidence_ids")
        safety_status = recommendation.get("safety_status")

        reasons = []

        if not isinstance(action, str) or not action.strip():
            return self._result("UNKNOWN", ["Missing or invalid action"])

        if action not in self.allowed_actions:
            return self._result("REJECT", ["Action is not allowlisted"])

        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            return self._result("REJECT", ["Invalid confidence value"])

        if not isinstance(evidence_ids, list) or not evidence_ids:
            return self._result("UNKNOWN", ["Evidence IDs are missing"])

        if any(not isinstance(item, str) or not item.strip()
               for item in evidence_ids):
            return self._result("UNKNOWN", ["Evidence IDs are invalid"])

        unknown_ids = [
            item for item in evidence_ids
            if item not in known_evidence_ids
        ]

        if unknown_ids:
            return self._result(
                "REJECT",
                ["Recommendation references unknown evidence IDs"]
            )

        if safety_status == "FAIL":
            return self._result("REJECT", ["Safety validation failed"])

        if safety_status != "PASS":
            return self._result(
                "UNKNOWN",
                ["Safety validation is missing or inconclusive"]
            )

        reasons.append("Action is allowlisted")
        reasons.append("Evidence references are recognised")
        reasons.append("Safety validation passed")

        return {
            "status": "PASS",
            "reasons": reasons,
            "action": action,
            "confidence": confidence,
            "evidence_ids": evidence_ids,
            "execution_allowed": False,
            "requires_human_approval": True,
        }

    @staticmethod
    def _result(status, reasons):
        return {
            "status": status,
            "reasons": reasons,
            "execution_allowed": False,
            "requires_human_approval": True,
        }