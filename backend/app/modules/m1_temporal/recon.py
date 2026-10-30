from collections import defaultdict
from itertools import islice, product
from typing import Iterable

from backend.app.models.event import Event


class TemporalReconstructor:
    """
    Reconstructs event history while preserving:
    - Event-time and arrival-time differences
    - Duplicate deliveries
    - Event-ID collisions
    - Contradictory evidence
    - Source provenance
    - Timestamp confidence
    - Alternative histories
    """

    def __init__(
        self,
        max_histories: int = 16,
        delayed_delivery_seconds: float = 300.0,
        clock_skew_tolerance_seconds: float = 5.0,
        low_trust_threshold: float = 0.5,
    ):
        if max_histories < 1:
            raise ValueError("max_histories must be at least 1.")

        if delayed_delivery_seconds < 0:
            raise ValueError("Delayed delivery threshold cannot be negative.")

        if clock_skew_tolerance_seconds < 0:
            raise ValueError("Clock skew tolerance cannot be negative.")

        if not 0.0 <= low_trust_threshold <= 1.0:
            raise ValueError("Low trust threshold must be between 0 and 1.")

        self.max_histories = max_histories
        self.delayed_delivery_seconds = delayed_delivery_seconds
        self.clock_skew_tolerance_seconds = (
            clock_skew_tolerance_seconds
        )
        self.low_trust_threshold = low_trust_threshold

    @staticmethod
    def _content_key(event: Event) -> tuple:
        """
        Identifies the same delivered event.

        Arrival time is excluded because repeated deliveries may
        arrive at different times.
        """

        return (
            event.event_id,
            event.event_time.isoformat(),
            event.source,
            event.event_type,
            repr(event.value),
            event.unit,
            event.component_id,
            event.trust_score,
            event.timestamp_confidence,
            event.signature_valid,
        )

    @staticmethod
    def _conflict_key(event: Event) -> tuple:
        """
        Events with the same component, event type and occurrence
        time are checked for contradictory values.
        """

        return (
            event.component_id,
            event.event_type,
            event.event_time.isoformat(),
        )

    @staticmethod
    def _sort_key(event: Event) -> tuple:
        """
        Event time is the primary ordering basis.
        Confidence and arrival time provide deterministic tie-breaking.
        """

        return (
            event.event_time,
            -event.timestamp_confidence,
            event.arrival_time,
            event.event_id,
            event.source,
        )

    def _detect_anomalies(self, event: Event) -> list[dict]:
        anomalies = []

        delivery_delay = (
            event.arrival_time - event.event_time
        ).total_seconds()

        if delivery_delay < -self.clock_skew_tolerance_seconds:
            anomalies.append({
                "type": "event_time_after_arrival",
                "severity": "warning",
                "details": (
                    "Claimed event time is later than arrival time "
                    "beyond the configured clock-skew tolerance."
                ),
            })

        elif delivery_delay > self.delayed_delivery_seconds:
            anomalies.append({
                "type": "delayed_delivery",
                "severity": "warning",
                "delay_seconds": round(delivery_delay, 3),
            })

        if event.signature_valid is False:
            anomalies.append({
                "type": "invalid_signature",
                "severity": "high",
                "details": "The event signature is marked invalid.",
            })

        if event.trust_score < self.low_trust_threshold:
            anomalies.append({
                "type": "low_source_trust",
                "severity": "warning",
                "trust_score": event.trust_score,
            })

        if event.timestamp_confidence < 0.5:
            anomalies.append({
                "type": "low_timestamp_confidence",
                "severity": "warning",
                "timestamp_confidence": event.timestamp_confidence,
            })

        return anomalies

    def _build_histories(
        self,
        events: list[Event],
        conflict_groups: list[list[Event]],
    ) -> tuple[list[dict], bool]:

        conflicting_ids = {
           id(event)
           for group in conflict_groups
           for event in group
      }

        fixed_events = [
            event for event in events
            if id(event) in conflicting_ids
        ]

        if not conflict_groups:
            combinations = [()]
            was_limited = False
        else:
            all_combinations = product(*conflict_groups)

            # Read one extra combination to detect truncation.
            sampled = list(
                islice(all_combinations, self.max_histories + 1)
            )

            was_limited = len(sampled) > self.max_histories
            combinations = sampled[:self.max_histories]

        histories = []

        for index, choices in enumerate(combinations):
            selected_events = fixed_events + list(choices)
            selected_events.sort(key=self._sort_key)

            histories.append({
                "history_id": f"H{index + 1}",
                "selected_event_ids": [
                    event.event_id for event in selected_events
                ],
                "events": [
                    event.to_record() for event in selected_events
                ],
            })

        return histories, was_limited

    def reconstruct(self, incoming_events: Iterable[Event]) -> dict:
        """
        Reconstruct an event ledger from incoming event records.

        The input is not modified. Exact repeated deliveries are
        suppressed, while conflicting records are retained.
        """

        events = []
        duplicate_records = []
        event_id_records = defaultdict(list)

        seen_content = {}

        # 1. Validate and identify exact duplicate deliveries.
        for item in incoming_events:
            event = (
                item
                if isinstance(item, Event)
                else Event.model_validate(item)
            )

            key = self._content_key(event)

            if key in seen_content:
                duplicate_records.append({
                    "event_id": event.event_id,
                    "duplicate_of": event.event_id,
                    "arrival_time": event.arrival_time.isoformat(),
                })
                continue

            seen_content[key] = event
            events.append(event)
            event_id_records[event.event_id].append(event)

        # 2. Detect reused event IDs with different content.
        event_id_collisions = []

        for event_id, records in sorted(event_id_records.items()):
            if len(records) > 1:
                event_id_collisions.append({
                    "event_id": event_id,
                    "record_count": len(records),
                    "status": "event_id_collision",
                    "records": [
                        event.to_record() for event in records
                    ],
                })

        # 3. Group events by their conflict key.
        groups = defaultdict(list)

        for event in events:
            groups[self._conflict_key(event)].append(event)

        conflicts = []
        conflict_groups = []

        for key, group in sorted(groups.items()):
            distinct_values = {
                repr(event.value) for event in group
            }

            if len(distinct_values) <= 1:
                continue

            ordered = sorted(
                group,
                key=lambda event: (
                    -event.evidence_score,
                    event.event_id,
                    event.source,
                ),
            )

            conflict_groups.append(ordered)

            conflicts.append({
                "component_id": key[0],
                "event_type": key[1],
                "event_time": key[2],
                "candidate_values": [
                    {
                        "event_id": event.event_id,
                        "value": event.value,
                        "source": event.source,
                        "trust_score": event.trust_score,
                        "timestamp_confidence": (
                            event.timestamp_confidence
                        ),
                        "signature_valid": event.signature_valid,
                        "evidence_score": event.evidence_score,
                    }
                    for event in ordered
                ],
                "status": "unresolved_conflict",
            })

        # 4. Generate bounded alternative histories.
        alternatives, histories_limited = self._build_histories(
            events,
            conflict_groups,
        )

        # 5. Build an event ledger with provenance and anomalies.
        conflict_event_ids = {
            event.event_id
            for group in conflict_groups
            for event in group
        }

        ledger = []

        for event in sorted(events, key=self._sort_key):
            anomalies = self._detect_anomalies(event)

            if event.event_id in conflict_event_ids:
                status = "conflicting"
            elif event.signature_valid is False:
                status = "unverified_signature"
            elif anomalies:
                status = "requires_review"
            else:
                status = "recorded"

            ledger.append({
                "event": event.to_record(),
                "source": event.source,
                "component_id": event.component_id,
                "event_time": event.event_time.isoformat(),
                "arrival_time": event.arrival_time.isoformat(),
                "trust_score": event.trust_score,
                "timestamp_confidence": event.timestamp_confidence,
                "evidence_score": event.evidence_score,
                "reconciliation_status": status,
                "anomalies": anomalies,
            })

        # 6. Produce a deterministic report.
        return {
            "total_received": len(events) + len(duplicate_records),
            "unique_events": len(events),
            "duplicate_count": len(duplicate_records),
            "duplicate_records": duplicate_records,
            "event_id_collisions": event_id_collisions,
            "event_ledger": ledger,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "alternative_histories": alternatives,
            "history_count": len(alternatives),
            "history_generation_limited": histories_limited,
            "ordering_basis": (
                "event_time_then_timestamp_confidence_"
                "then_arrival_time"
            ),
            "reconstruction_status": (
                "requires_review"
                if conflicts or event_id_collisions
                else "reconstructed"
            ),
        }