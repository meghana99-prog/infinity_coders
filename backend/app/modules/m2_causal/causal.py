from typing import Any

from backend.app.modules.m2_causal.graph import CausalGraph
from backend.app.modules.m2_causal.evidence import EvidenceExtractor
from backend.app.modules.m2_causal.hypothesis import HypothesisRanker


class CausalInvestigator:
    """
    Coordinates M2 causal investigation.

    Connects:
    - CausalGraph
    - EvidenceExtractor
    - HypothesisRanker
    """

    def __init__(
        self,
        graph: CausalGraph | None = None,
        minimum_evidence_score: float = 0.0,
    ):
        self.graph = graph or CausalGraph()
        self.evidence_extractor = EvidenceExtractor()
        self.hypothesis_ranker = HypothesisRanker(
            minimum_evidence_score=minimum_evidence_score
        )

    def add_variable(
        self,
        variable_id: str,
        description: str = "",
        category: str = "system",
    ) -> None:
        self.graph.add_variable(
            variable_id=variable_id,
            description=description,
            category=category,
        )

    def add_causal_link(
        self,
        cause: str,
        effect: str,
        confidence: float = 0.5,
        evidence_ids: list[str] | None = None,
        assumptions: list[str] | None = None,
        validated_by_simulator: bool = False,
    ) -> None:
        self.graph.add_causal_link(
            cause=cause,
            effect=effect,
            confidence=confidence,
            evidence_ids=evidence_ids,
            assumptions=assumptions,
            validated_by_simulator=validated_by_simulator,
        )

    def investigate(
        self,
        reconstruction: dict[str, Any],
        target_variable: str,
    ) -> dict:
        """
        Extracts M1 evidence and ranks possible causes
        of the requested target variable.
        """

        if not isinstance(reconstruction, dict):
            raise TypeError("reconstruction must be a dictionary")

        graph_validation = self.graph.validate()

        if not graph_validation["valid"]:
            raise ValueError("Causal graph is invalid")

        extracted_evidence = self.evidence_extractor.extract(
            reconstruction
        )

        ranking = self.hypothesis_ranker.rank_causes(
            causal_graph=self.graph,
            extracted_evidence=extracted_evidence,
            target_variable=target_variable,
        )

        return {
            "module": "M2_Causal_Discovery",
            "target_variable": target_variable,
            "graph_validation": graph_validation,
            "evidence_summary": {
                "ledger_records": extracted_evidence[
                    "total_ledger_records"
                ],
                "extracted_observations": extracted_evidence[
                    "extracted_observations"
                ],
                "excluded_observations": extracted_evidence[
                    "excluded_observations"
                ],
            },
            "evidence": extracted_evidence,
            "investigation": ranking,
            "limitations": [
                "A ranked hypothesis is not proof of causation.",
                "Observational evidence does not establish an intervention effect.",
                "Simulator validation must be supported by actual simulator evidence.",
                "Missing or unreliable timestamps can prevent temporal ordering.",
            ],
        }

    def export_graph(self) -> dict:
        return self.graph.to_dict()