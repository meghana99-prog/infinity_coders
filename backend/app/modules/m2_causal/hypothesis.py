from datetime import datetime, timezone
import networkx as nx


class HypothesisRanker:
    """
    Ranks possible upstream causes of a target variable.

    Rankings indicate evidence support, not proof of causation.
    """

    def __init__(self, minimum_evidence_score: float = 0.0):
        if not 0.0 <= minimum_evidence_score <= 1.0:
            raise ValueError(
                "minimum_evidence_score must be between 0 and 1"
            )

        self.minimum_evidence_score = minimum_evidence_score

    @staticmethod
    def _parse_time(value):
        if not isinstance(value, str):
            return None

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
            if parsed.tzinfo is None:
                return None
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _path_details(graph, path):
        confidence = 1.0
        validated = True
        evidence_ids = []
        assumptions = []

        for source, target in zip(path, path[1:]):
            edge = graph.graph.edges[source, target]

            confidence *= float(edge.get("confidence", 0.5))
            validated = (
                validated
                and edge.get("validated_by_simulator", False)
            )

            evidence_ids.extend(edge.get("evidence_ids", []))
            assumptions.extend(edge.get("assumptions", []))

        return {
            "confidence": confidence,
            "validated": validated,
            "evidence_ids": sorted(set(evidence_ids)),
            "assumptions": sorted(set(assumptions)),
        }

    def rank_causes(
        self,
        causal_graph,
        extracted_evidence: dict,
        target_variable: str,
    ) -> dict:

        if not isinstance(extracted_evidence, dict):
            raise TypeError(
                "extracted_evidence must be a dictionary"
            )

        if not causal_graph.has_variable(target_variable):
            raise ValueError(
                f"Unknown target variable: {target_variable}"
            )

        records = extracted_evidence.get("evidence_records", [])

        if not isinstance(records, list):
            raise ValueError("evidence_records must be a list")

        valid_records = []

        for record in records:
            if not isinstance(record, dict):
                continue

            component = record.get("component_id")

            try:
                score = float(record.get("evidence_score", 0.0))
            except (TypeError, ValueError):
                continue

            if not 0.0 <= score <= 1.0:
                continue

            if score < self.minimum_evidence_score or not component:
                continue

            valid_records.append(record)

        target_records = [
            record for record in valid_records
            if record.get("component_id") == target_variable
        ]

        target_times = [
            self._parse_time(record.get("event_time"))
            for record in target_records
        ]
        target_times = [t for t in target_times if t is not None]

        earliest_target_time = (
            min(target_times) if target_times else None
        )

        hypotheses = []

        for cause in causal_graph.get_possible_causes(target_variable):
            cause_records = [
                record for record in valid_records
                if record.get("component_id") == cause
            ]

            if not cause_records:
                continue

            evidence_strength = max(
                float(record["evidence_score"])
                for record in cause_records
            )

            cause_times = [
                self._parse_time(record.get("event_time"))
                for record in cause_records
            ]
            cause_times = [t for t in cause_times if t is not None]

            if earliest_target_time and cause_times:
                precedes = any(
                    t < earliest_target_time for t in cause_times
                )
                temporal_support = 1.0 if precedes else 0.0
                temporal_status = (
                    "cause_evidence_precedes_target"
                    if precedes
                    else "cause_evidence_does_not_precede_target"
                )
            else:
                temporal_support = None
                temporal_status = "chronology_not_established"

            try:
                path = nx.shortest_path(
                    causal_graph.graph,
                    source=cause,
                    target=target_variable,
                )
            except nx.NetworkXNoPath:
                continue

            details = self._path_details(causal_graph, path)

            score = details["confidence"] * evidence_strength

            if temporal_support is not None:
                score *= temporal_support

            hypotheses.append({
                "cause": cause,
                "target": target_variable,
                "score": round(score, 4),
                "path": path,
                "path_confidence": round(
                    details["confidence"], 4
                ),
                "evidence_strength": round(
                    evidence_strength, 4
                ),
                "supporting_event_ids": sorted({
                    str(record["event_id"])
                    for record in cause_records
                    if record.get("event_id") is not None
                }),
                "temporal_support": temporal_support,
                "temporal_status": temporal_status,
                "simulator_validated": details["validated"],
                "causal_claim_status": (
                    "simulator_validated_path"
                    if details["validated"]
                    else "observational_hypothesis"
                ),
                "assumptions": details["assumptions"],
                "graph_evidence_ids": details["evidence_ids"],
            })

        hypotheses.sort(
            key=lambda item: (-item["score"], item["cause"])
        )

        for rank, hypothesis in enumerate(hypotheses, start=1):
            hypothesis["rank"] = rank

        return {
            "target_variable": target_variable,
            "hypothesis_count": len(hypotheses),
            "target_evidence_available": bool(target_records),
            "ranking_method": (
                "path confidence × evidence strength "
                "× temporal support when available"
            ),
            "hypotheses": hypotheses,
            "warning": (
                "Ranked hypotheses are not proof of causation. "
                "Intervention simulation is required to assess "
                "causal effects."
            ),
        }