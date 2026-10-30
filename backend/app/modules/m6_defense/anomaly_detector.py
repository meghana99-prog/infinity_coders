from typing import Any


class AnomalyDetector:
    """
    Detects suspicious industrial sensor readings using
    configurable range and rate-of-change rules.
    """

    def __init__(
        self,
        limits: dict[str, tuple[float, float]] | None = None,
        max_change: dict[str, float] | None = None,
    ):
        self.limits = limits or {
            "temperature": (0.0, 120.0),
            "pressure": (0.0, 200.0),
            "cooling_capacity": (0.0, 100.0),
        }

        self.max_change = max_change or {
            "temperature": 20.0,
            "pressure": 30.0,
            "cooling_capacity": 25.0,
        }

        self.previous_values: dict[tuple[str, str], float] = {}

    def inspect(self, event: dict[str, Any]) -> dict:
        if not isinstance(event, dict):
            raise TypeError("Event must be a dictionary.")

        event_id = event.get("event_id")
        sensor_id = event.get("source")
        metric = event.get("metric")
        value = event.get("value")

        if not event_id or not sensor_id or not metric:
            return {
                "event_id": event_id,
                "status": "UNKNOWN",
                "anomalies": ["Missing event or sensor metadata."],
            }

        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
        ):
            return {
                "event_id": event_id,
                "status": "UNKNOWN",
                "anomalies": ["Sensor value is missing or non-numeric."],
            }

        anomalies = []
        sensor_key = (sensor_id, metric)

        # Check configured operating limits.
        if metric in self.limits:
            lower, upper = self.limits[metric]

            if not lower <= value <= upper:
                anomalies.append("OPERATING_LIMIT_EXCEEDED")

        # Check sudden changes from the previous sensor reading.
        if sensor_key in self.previous_values:
            previous = self.previous_values[sensor_key]
            change = abs(value - previous)

            threshold = self.max_change.get(metric)

            if threshold is not None and change > threshold:
                anomalies.append("SUDDEN_VALUE_CHANGE")

        # Update sensor history after inspection.
        self.previous_values[sensor_key] = float(value)

        return {
            "event_id": event_id,
            "sensor_id": sensor_id,
            "metric": metric,
            "value": value,
            "status": "SUSPICIOUS" if anomalies else "NORMAL",
            "anomalies": anomalies,
        }

    def reset(self):
        """Clear previous sensor readings."""
        self.previous_values.clear()