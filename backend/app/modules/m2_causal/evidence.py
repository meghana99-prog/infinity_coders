from collections import defaultdict

class EvidenceExtractor:
    """Extract structured observations from M1 reconstruction output."""

    def extract(self, reconstruction: dict) -> dict:
        if not isinstance(reconstruction, dict):
            raise TypeError("Reconstruction must be a dictionary.")

        ledger = reconstruction.get("event_ledger")

        if not isinstance(ledger, list):
            raise ValueError("M1 event_ledger must be a list.")

        observations = defaultdict(list)
        evidence_records = []
        excluded_records = []

        for record in ledger:
            if not isinstance(record, dict):
                excluded_records.append({
                    "reason": "invalid_ledger_record"
                })
                continue

            event = record.get("event")

            # Support both flat and nested M1 event records
            if not isinstance(event, dict):
                event = record

            required = [
                "event_id",
                "event_time",
                "source",
                "event_type",
                "component_id",
                "value",
            ]

            missing = [
                field for field in required
                if field not in event
            ]

            if missing:
                excluded_records.append({
                    "event_id": event.get("event_id"),
                    "reason": "missing_required_fields",
                    "fields": missing,
                })
                continue

            value = event["value"]

            if not isinstance(value, (int, float)) or isinstance(value, bool):
                excluded_records.append({
                    "event_id": event["event_id"],
                    "reason": "non_numeric_observation",
                })
                continue

            status = record.get(
                "reconciliation_status",
                 event.get("reconciliation_status", "unknown"),
           )

            evidence_score = record.get(
                "evidence_score",
                event.get("evidence_score", 0.0),
            )

            try:
                evidence_score = float(evidence_score)
            except (TypeError, ValueError):
                evidence_score = 0.0

            if not 0.0 <= evidence_score <= 1.0:
                evidence_score = 0.0

            evidence = {
                "event_id": event["event_id"],
                "event_time": event["event_time"],
                "arrival_time": event.get(
                   "arrival_time",
                   record.get("arrival_time"),
               ),
                "source": event["source"],
                "component_id": event["component_id"],
                "event_type": event["event_type"],
                "value": value,
                "unit": event.get("unit"),
                "evidence_score": evidence_score,
                "reconciliation_status": status,
                "anomalies": record.get(
                  "anomalies",
                  event.get("anomalies", []),
                ),
            }

            evidence_records.append(evidence)

            observations[event["component_id"]].append(
                evidence
            )

        for component_id in observations:
            observations[component_id].sort(
                key=lambda item: (
                    item["event_time"],
                    item["event_id"],
                )
            )

        evidence_records.sort(
            key=lambda item: (
                item["event_time"],
                item["event_id"],
            )
        )

        return {
            "total_ledger_records": len(ledger),
            "extracted_observations": len(evidence_records),
            "excluded_observations": len(excluded_records),
            "observations_by_component": dict(observations),
            "evidence_records": evidence_records,
            "excluded_records": excluded_records,
        }