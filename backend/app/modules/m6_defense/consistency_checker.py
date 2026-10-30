from collections import defaultdict
from typing import Any


class ConsistencyChecker:
    """
    Compares observations from independent sources
    for the same industrial component and metric.
    """

    def __init__(self, tolerance: float = 5.0, min_sources: int = 2):
        if tolerance < 0:
            raise ValueError("Tolerance cannot be negative.")

        if min_sources < 2:
            raise ValueError("At least two sources are required.")

        self.tolerance = tolerance
        self.min_sources = min_sources

    def inspect(self, observations: list[dict[str, Any]]) -> dict:
        if not isinstance(observations, list):
            raise TypeError("Observations must be a list.")

        groups = defaultdict(list)
        excluded = []

        for item in observations:
            if not isinstance(item, dict):
                excluded.append("Invalid observation record.")
                continue

            source = item.get("source")
            component = item.get("component_id")
            metric = item.get("metric")
            value = item.get("value")

            if not source or not component or not metric:
                excluded.append("Missing observation metadata.")
                continue

            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
            ):
                excluded.append("Non-numeric observation.")
                continue

            groups[(component, metric)].append({
                "source": source,
                "value": float(value),
            })

        results = []

        for (component, metric), records in sorted(groups.items()):
            # Avoid counting repeated records from one source
            by_source = {}

            for record in records:
                by_source.setdefault(record["source"], []).append(
                    record["value"]
                )

            source_values = {
                source: sum(values) / len(values)
                for source, values in by_source.items()
            }

            if len(source_values) < self.min_sources:
                status = "UNKNOWN"
                spread = None
            else:
                values = list(source_values.values())
                spread = max(values) - min(values)

                status = (
                    "CONSISTENT"
                    if spread <= self.tolerance
                    else "CONFLICT"
                )

            results.append({
                "component_id": component,
                "metric": metric,
                "source_count": len(source_values),
                "source_values": source_values,
                "spread": spread,
                "status": status,
            })

        return {
            "status": (
                "CONFLICT"
                if any(item["status"] == "CONFLICT" for item in results)
                else "UNKNOWN"
                if any(item["status"] == "UNKNOWN" for item in results)
                else "CONSISTENT"
            ),
            "groups_checked": len(results),
            "results": results,
            "excluded_records": excluded,
        }