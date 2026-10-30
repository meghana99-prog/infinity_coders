import hashlib
import json
from typing import Any


class ReplayDetector:
    """
    Detects repeated event IDs and event-ID payload collisions.

    This is an in-memory prototype. Production deployment requires
    persistent, shared replay state across service restarts.
    """

    def __init__(self):
        self._seen_events: dict[str, str] = {}

    @staticmethod
    def _fingerprint(event: dict[str, Any]) -> str:
        payload = json.dumps(
            event,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def inspect(self, event: dict[str, Any]) -> dict:
        if not isinstance(event, dict):
            raise TypeError("Event must be a dictionary.")

        event_id = event.get("event_id")

        if not isinstance(event_id, str) or not event_id.strip():
            return {
                "event_id": None,
                "status": "UNKNOWN",
                "reason": "Missing or invalid event ID.",
                "accept": False,
            }

        fingerprint = self._fingerprint(event)

        if event_id not in self._seen_events:
            self._seen_events[event_id] = fingerprint

            return {
                "event_id": event_id,
                "status": "NEW",
                "reason": "First occurrence of this event ID.",
                "accept": True,
            }

        if self._seen_events[event_id] == fingerprint:
            return {
                "event_id": event_id,
                "status": "REPLAY",
                "reason": "Previously received event was repeated.",
                "accept": False,
            }

        return {
            "event_id": event_id,
            "status": "ID_COLLISION",
            "reason": (
                "Previously used event ID has a different payload."
            ),
            "accept": False,
        }

    def reset(self) -> None:
        """Clear replay history. Intended for tests or controlled resets."""
        self._seen_events.clear()