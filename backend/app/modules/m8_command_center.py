"""
M8 - Interactive Time-Travel Command Center for CHRONOS-X.

API-ready backend service for exploring the reconstructed event history,
replaying the synthetic facility state at a selected event-time, comparing
historical states, and preparing a dashboard payload for a frontend.

This module is READ-ONLY. It never sends commands to industrial equipment,
never invents simulation results, and labels unknown state as unknown.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable


# Event types that can safely be projected into a display-state snapshot.
# Unknown event types remain visible in the timeline but do not mutate state.
STATE_FIELD_MAP = {
    "TEMPERATURE_READING": "reactor_temperature_c",
    "COOLING_CAPACITY": "cooling_capacity_pct",
    "ENERGY_LEVEL": "energy_remaining_pct",
    "COOLANT_LEVEL": "coolant_remaining_pct",
    "BACKUP_COOLING_STATUS": "backup_cooling_active",
    "NETWORK_ISOLATION_STATUS": "network_isolated",
    "REACTOR_STATUS": "reactor_shutdown",
}

NUMERIC_RANGES = {
    "reactor_temperature_c": (-273.15, None),
    "cooling_capacity_pct": (0.0, 100.0),
    "energy_remaining_pct": (0.0, 100.0),
    "coolant_remaining_pct": (0.0, 100.0),
}


class CommandCenterError(ValueError):
    """Raised when a command-center request is invalid."""


def _parse_time(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CommandCenterError(
                f"{field_name} must be an ISO-8601 timestamp."
            ) from exc
    else:
        raise CommandCenterError(f"{field_name} must be a timestamp.")

    if result.tzinfo is None or result.utcoffset() is None:
        raise CommandCenterError(f"{field_name} must include a timezone.")
    return result


def _json_time(value: Any) -> str | None:
    if value is None:
        return None
    return _parse_time(value, "timestamp").isoformat()


def _event_record(event: Any) -> dict[str, Any]:
    if hasattr(event, "to_record"):
        record = event.to_record()
    elif hasattr(event, "model_dump"):
        record = event.model_dump(mode="json")
    elif isinstance(event, dict):
        record = deepcopy(event)
    else:
        raise CommandCenterError("Each event must be a dictionary or Event model.")

    required = ("event_id", "event_time", "arrival_time", "event_type")
    missing = [key for key in required if record.get(key) is None]
    if missing:
        raise CommandCenterError(
            "Event is missing required field(s): " + ", ".join(missing)
        )

    record["event_time"] = _json_time(record["event_time"])
    record["arrival_time"] = _json_time(record["arrival_time"])
    record["event_type"] = str(record["event_type"]).upper()
    record["event_id"] = str(record["event_id"])
    return record


def _event_value(event: dict[str, Any]) -> Any:
    value = event.get("value")
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _validate_state_value(field: str, value: Any) -> tuple[bool, Any, str | None]:
    if field in NUMERIC_RANGES:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False, None, "Expected a numeric sensor value."
        low, high = NUMERIC_RANGES[field]
        if value < low or (high is not None and value > high):
            return False, None, "Sensor value is outside the accepted display range."
        return True, float(value), None

    if field in {"backup_cooling_active", "network_isolated", "reactor_shutdown"}:
        if isinstance(value, bool):
            return True, value, None
        if isinstance(value, str) and value.strip().lower() in {
            "true", "false", "active", "inactive", "on", "off", "isolated", "connected", "shutdown", "running"
        }:
            normalized = value.strip().lower()
            return True, normalized in {"true", "active", "on", "isolated", "shutdown"}, None
        return False, None, "Expected a boolean-like status value."

    return False, None, "Unsupported state field."


class ChronosCommandCenter:
    """Read-only query and replay service for M8.

    Parameters are plain event records or the project's Event model objects.
    State replay uses event_time (not arrival_time), while both timestamps are
    retained in every timeline item so delayed delivery remains inspectable.
    """

    def __init__(self, events: Iterable[Any] | None = None):
        self._events: list[dict[str, Any]] = []
        self._event_ids: set[str] = set()
        if events is not None:
            self.load_events(events)

    def load_events(self, events: Iterable[Any]) -> dict[str, Any]:
        """Load/reload event records; duplicate event IDs are retained as conflicts."""
        records = [_event_record(event) for event in events]
        self._events = records
        self._event_ids = {item["event_id"] for item in records}
        return {
            "loaded_count": len(records),
            "unique_event_id_count": len(self._event_ids),
            "duplicate_event_ids": self._duplicate_ids(records),
        }

    @staticmethod
    def _duplicate_ids(events: list[dict[str, Any]]) -> list[str]:
        seen, duplicates = set(), set()
        for event in events:
            event_id = event["event_id"]
            if event_id in seen:
                duplicates.add(event_id)
            seen.add(event_id)
        return sorted(duplicates)

    def timeline(
        self,
        start: str | datetime | None = None,
        end: str | datetime | None = None,
        event_type: str | None = None,
        component_id: str | None = None,
        min_trust: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return a filterable, event-time ordered timeline with provenance."""
        start_dt = _parse_time(start, "start") if start is not None else None
        end_dt = _parse_time(end, "end") if end is not None else None
        if start_dt and end_dt and start_dt > end_dt:
            raise CommandCenterError("start must be earlier than or equal to end.")
        if min_trust is not None and not 0 <= min_trust <= 1:
            raise CommandCenterError("min_trust must be between 0 and 1.")
        if limit is not None and limit < 1:
            raise CommandCenterError("limit must be at least 1.")

        selected = []
        for event in self._events:
            event_time = _parse_time(event["event_time"], "event_time")
            if start_dt and event_time < start_dt:
                continue
            if end_dt and event_time > end_dt:
                continue
            if event_type and event["event_type"] != event_type.upper():
                continue
            if component_id and event.get("component_id") != component_id:
                continue
            trust = event.get("trust_score")
            if min_trust is not None and (
                not isinstance(trust, (int, float)) or trust < min_trust
            ):
                continue
            selected.append(deepcopy(event))

        selected.sort(key=lambda item: (
            _parse_time(item["event_time"], "event_time"),
            -float(item.get("timestamp_confidence", 1.0) or 0.0),
            _parse_time(item["arrival_time"], "arrival_time"),
            item["event_id"],
        ))
        total = len(selected)
        if limit is not None:
            selected = selected[:limit]

        return {
            "items": selected,
            "total_matching": total,
            "returned": len(selected),
            "filters": {
                "start": start_dt.isoformat() if start_dt else None,
                "end": end_dt.isoformat() if end_dt else None,
                "event_type": event_type.upper() if event_type else None,
                "component_id": component_id,
                "min_trust": min_trust,
                "limit": limit,
            },
        }

    def replay(self, as_of: str | datetime) -> dict[str, Any]:
        """Reconstruct the latest known display-state at a selected event-time."""
        target = _parse_time(as_of, "as_of")
        eligible = [
            event for event in self._events
            if _parse_time(event["event_time"], "event_time") <= target
        ]
        eligible.sort(key=lambda item: (
            _parse_time(item["event_time"], "event_time"),
            -float(item.get("timestamp_confidence", 1.0) or 0.0),
            _parse_time(item["arrival_time"], "arrival_time"),
            item["event_id"],
        ))

        state: dict[str, Any] = {}
        provenance: dict[str, dict[str, Any]] = {}
        ignored: list[dict[str, str]] = []
        for event in eligible:
            field = STATE_FIELD_MAP.get(event["event_type"])
            if field is None:
                continue
            valid, value, reason = _validate_state_value(field, _event_value(event))
            if not valid:
                ignored.append({"event_id": event["event_id"], "reason": reason or "Invalid value"})
                continue
            state[field] = value
            provenance[field] = {
                "event_id": event["event_id"],
                "event_time": event["event_time"],
                "arrival_time": event["arrival_time"],
                "source": event.get("source"),
                "component_id": event.get("component_id"),
                "trust_score": event.get("trust_score"),
                "timestamp_confidence": event.get("timestamp_confidence"),
                "signature_valid": event.get("signature_valid"),
            }

        delayed = [
            event["event_id"] for event in eligible
            if _parse_time(event["arrival_time"], "arrival_time") > target
        ]
        return {
            "as_of": target.isoformat(),
            "state": state,
            "known_fields": sorted(state),
            "unknown_fields": sorted(set(STATE_FIELD_MAP.values()) - set(state)),
            "provenance": provenance,
            "events_considered": len(eligible),
            "delayed_events_not_yet_arrived": delayed,
            "invalid_state_events_ignored": ignored,
            "replay_basis": "event_time",
            "read_only": True,
            "notice": (
                "This is a synthetic display-state replay from supplied events; "
                "missing fields remain unknown and no physical equipment is controlled."
            ),
        }

    def compare(self, first_time: str | datetime, second_time: str | datetime) -> dict[str, Any]:
        """Compare two historical replay points field by field."""
        first = self.replay(first_time)
        second = self.replay(second_time)
        keys = sorted(set(first["state"]) | set(second["state"]))
        changes = []
        for key in keys:
            before = first["state"].get(key)
            after = second["state"].get(key)
            if before != after:
                changes.append({"field": key, "before": before, "after": after})
        return {
            "first_as_of": first["as_of"],
            "second_as_of": second["as_of"],
            "changes": changes,
            "unchanged_fields": [key for key in keys if first["state"].get(key) == second["state"].get(key)],
            "first_unknown_fields": first["unknown_fields"],
            "second_unknown_fields": second["unknown_fields"],
        }

    def dashboard(
        self,
        as_of: str | datetime | None = None,
        simulation_report: dict[str, Any] | None = None,
        agent_result: dict[str, Any] | None = None,
        defense_result: dict[str, Any] | None = None,
        safety_certificate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a frontend-ready dashboard payload from supplied module outputs."""
        if as_of is None:
            if not self._events:
                raise CommandCenterError("Cannot infer as_of because no events are loaded.")
            as_of = max(
                self._events,
                key=lambda e: _parse_time(e["event_time"], "event_time"),
            )["event_time"]
        snapshot = self.replay(as_of)
        timeline = self.timeline(end=as_of)
        records = timeline["items"]
        anomaly_types = {
            "invalid_signature", "low_source_trust", "low_timestamp_confidence",
            "delayed_delivery", "event_time_after_arrival",
        }
        anomalies = []
        for event in records:
            event_anomalies = []
            if event.get("signature_valid") is False:
                event_anomalies.append("invalid_signature")
            if isinstance(event.get("trust_score"), (int, float)) and event["trust_score"] < 0.5:
                event_anomalies.append("low_source_trust")
            if isinstance(event.get("timestamp_confidence"), (int, float)) and event["timestamp_confidence"] < 0.5:
                event_anomalies.append("low_timestamp_confidence")
            delay = (
                _parse_time(event["arrival_time"], "arrival_time")
                - _parse_time(event["event_time"], "event_time")
            ).total_seconds()
            if delay > 300:
                event_anomalies.append("delayed_delivery")
            elif delay < -5:
                event_anomalies.append("event_time_after_arrival")
            if event_anomalies:
                anomalies.append({"event_id": event["event_id"], "types": event_anomalies})

        module_panels = {
            "m3_simulation": deepcopy(simulation_report),
            "m4_agent_decision": deepcopy(agent_result),
            "m6_defense": deepcopy(defense_result),
            "m7_safety_certificate": deepcopy(safety_certificate),
        }
        return {
            "module": "M8_INTERACTIVE_TIME_TRAVEL_COMMAND_CENTER",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "selected_time": snapshot["as_of"],
            "kpis": {
                "events_in_view": len(records),
                "unique_event_ids": len({e["event_id"] for e in records}),
                "components_observed": len({e.get("component_id") for e in records if e.get("component_id")}),
                "anomalous_events": len(anomalies),
                "known_state_fields": len(snapshot["known_fields"]),
                "unknown_state_fields": len(snapshot["unknown_fields"]),
            },
            "timeline": records,
            "snapshot": snapshot,
            "anomalies": anomalies,
            "module_panels": module_panels,
            "controls": {
                "time_travel_enabled": True,
                "timeline_filtering_enabled": True,
                "historical_comparison_enabled": True,
                "simulation_overlay_available": simulation_report is not None,
                "agent_overlay_available": agent_result is not None,
                "defense_overlay_available": defense_result is not None,
                "safety_certificate_available": safety_certificate is not None,
                "industrial_execution_enabled": False,
            },
            "safety_notice": (
                "Synthetic decision-support view only. A dashboard status, "
                "simulation estimate, or agent recommendation is not proof of safety. "
                "No command is sent to industrial equipment."
            ),
        }

    def event_detail(self, event_id: str) -> dict[str, Any]:
        """Return every delivery with this ID so duplicate/conflicting records remain visible."""
        matches = [deepcopy(e) for e in self._events if e["event_id"] == str(event_id)]
        if not matches:
            raise CommandCenterError(f"Unknown event_id: {event_id}")
        matches.sort(key=lambda e: (e["event_time"], e["arrival_time"]))
        return {
            "event_id": str(event_id),
            "delivery_count": len(matches),
            "duplicate_delivery": len(matches) > 1,
            "records": matches,
        }


def build_command_center(
    events: Iterable[Any],
    as_of: str | datetime | None = None,
    **module_outputs: Any,
) -> dict[str, Any]:
    """Convenience function for API routes and demos."""
    return ChronosCommandCenter(events).dashboard(as_of=as_of, **module_outputs)
