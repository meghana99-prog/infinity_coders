from typing import Any


class ProvenanceValidator:
    """
    Evaluates the provenance quality of industrial event records.

    This checks supplied validation metadata; it does not perform
    cryptographic signature verification.
    """

    def __init__(
        self,
        minimum_trust_score: float = 0.5,
        minimum_timestamp_confidence: float = 0.5,
    ):
        if not 0 <= minimum_trust_score <= 1:
            raise ValueError("Invalid minimum trust score.")

        if not 0 <= minimum_timestamp_confidence <= 1:
            raise ValueError("Invalid timestamp confidence.")

        self.minimum_trust_score = minimum_trust_score
        self.minimum_timestamp_confidence = (
            minimum_timestamp_confidence
        )

    def validate(self, event: dict[str, Any]) -> dict:
        if not isinstance(event, dict):
            raise TypeError("Event must be a dictionary.")

        event_data = event.get("event", event)

        if not isinstance(event_data, dict):
            raise ValueError("Invalid event structure.")

        event_id = event_data.get("event_id")

        if not event_id:
            return {
                "event_id": None,
                "status": "UNKNOWN",
                "reasons": ["Missing event ID."],
            }

        reasons = []
        failures = []
        unknowns = []

        signature_valid = event_data.get("signature_valid")

        if signature_valid is False:
            failures.append("Event signature is marked invalid.")
        elif signature_valid is None:
            unknowns.append("Signature validity is unknown.")

        trust_score = event_data.get("trust_score")

        if trust_score is None:
            unknowns.append("Trust score is missing.")
        elif not isinstance(trust_score, (int, float)) or isinstance(trust_score, bool) or not 0 <= trust_score <= 1:
            failures.append("Trust score is invalid.")
        elif trust_score < self.minimum_trust_score:
            failures.append("Trust score is below the required threshold.")

        timestamp_confidence = event_data.get(
            "timestamp_confidence"
        )

        if timestamp_confidence is None:
            unknowns.append("Timestamp confidence is missing.")
        elif (
            not isinstance(timestamp_confidence, (int, float))
            or isinstance(timestamp_confidence, bool)
            or not 0 <= timestamp_confidence <= 1
        ):
            failures.append("Timestamp confidence is invalid.")
        elif timestamp_confidence < self.minimum_timestamp_confidence:
            failures.append("Timestamp confidence is too low.")

        if failures:
            status = "FAIL"
            reasons.extend(failures)
            reasons.extend(unknowns)
        elif unknowns:
            status = "UNKNOWN"
            reasons.extend(unknowns)
        else:
            status = "PASS"

        return {
            "event_id": event_id,
            "status": status,
            "reasons": reasons,
        }