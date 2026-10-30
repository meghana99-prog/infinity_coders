import pytest

from backend.app.modules.m2_causal.graph import CausalGraph
from backend.app.modules.m2_causal.evidence import EvidenceExtractor
from backend.app.modules.m2_causal.causal import CausalInvestigator


def sample_reconstruction():
    return {
        "event_ledger": [
            {
                "event_id": "EV-001",
                "event_time": "2026-10-30T08:00:00+00:00",
                "arrival_time": "2026-10-30T08:00:05+00:00",
                "source": "temperature_sensor",
                "event_type": "temperature_reading",
                "component_id": "cooling_pump",
                "value": 95.0,
                "unit": "C",
                "evidence_score": 0.9,
                "reconciliation_status": "recorded",
                "anomalies": [],
            },
            {
                "event_id": "EV-002",
                "event_time": "2026-10-30T08:05:00+00:00",
                "arrival_time": "2026-10-30T08:05:03+00:00",
                "source": "reactor_sensor",
                "event_type": "temperature_reading",
                "component_id": "reactor",
                "value": 110.0,
                "unit": "C",
                "evidence_score": 0.95,
                "reconciliation_status": "recorded",
                "anomalies": [],
            },
        ]
    }


def build_investigator(validated=False):
    investigator = CausalInvestigator()

    investigator.add_variable(
        "cooling_pump",
        "Cooling pump condition",
        "equipment",
    )
    investigator.add_variable(
        "reactor",
        "Reactor temperature",
        "equipment",
    )

    investigator.add_causal_link(
        cause="cooling_pump",
        effect="reactor",
        confidence=0.8,
        evidence_ids=["EV-001"],
        assumptions=["Cooling failure can increase reactor temperature"],
        validated_by_simulator=validated,
    )

    return investigator


def test_graph_adds_variables_and_causal_link():
    graph = CausalGraph()

    graph.add_variable("pump")
    graph.add_variable("reactor")
    graph.add_causal_link("pump", "reactor", confidence=0.8)

    result = graph.validate()

    assert result["valid"] is True
    assert result["variable_count"] == 2
    assert result["causal_link_count"] == 1
    assert result["is_acyclic"] is True


def test_graph_rejects_causal_cycle():
    graph = CausalGraph()

    graph.add_variable("pump")
    graph.add_variable("reactor")

    graph.add_causal_link("pump", "reactor")

    with pytest.raises(ValueError):
        graph.add_causal_link("reactor", "pump")

    assert graph.validate()["is_acyclic"] is True


def test_graph_rejects_unknown_variable_in_link():
    graph = CausalGraph()
    graph.add_variable("pump")

    with pytest.raises(ValueError):
        graph.add_causal_link("pump", "reactor")


def test_evidence_extractor_extracts_numeric_observations():
    extractor = EvidenceExtractor()

    result = extractor.extract(sample_reconstruction())

    assert result["total_ledger_records"] == 2
    assert result["extracted_observations"] == 2
    assert len(result["evidence_records"]) == 2
    assert "cooling_pump" in result["observations_by_component"]


def test_evidence_extractor_excludes_non_numeric_observations():
    extractor = EvidenceExtractor()

    reconstruction = {
        "event_ledger": [
            {
                "event_id": "EV-003",
                "event_time": "2026-10-30T08:00:00+00:00",
                "source": "maintenance_agent",
                "event_type": "maintenance_report",
                "component_id": "cooling_pump",
                "value": "pump looks normal",
                "evidence_score": 0.8,
            }
        ]
    }

    result = extractor.extract(reconstruction)

    assert result["extracted_observations"] == 0
    assert result["excluded_observations"] == 1


def test_investigator_ranks_a_possible_cause():
    investigator = build_investigator()

    result = investigator.investigate(
        sample_reconstruction(),
        "reactor",
    )

    hypotheses = result["investigation"]["hypotheses"]

    assert len(hypotheses) == 1
    assert hypotheses[0]["cause"] == "cooling_pump"
    assert hypotheses[0]["rank"] == 1
    assert hypotheses[0]["score"] > 0


def test_observational_path_is_not_claimed_as_proven():
    investigator = build_investigator(validated=False)

    result = investigator.investigate(
        sample_reconstruction(),
        "reactor",
    )

    hypotheses = result["investigation"]["hypotheses"]

    assert len(hypotheses) > 0, (
       f"No observational hypotheses generated. "
       f"Investigation result: {result['investigation']}"
   )

    hypothesis = hypotheses[0]
    assert hypothesis["simulator_validated"] is False
    assert hypothesis["causal_claim_status"] == "observational_hypothesis"


    hypotheses = result["investigation"]["hypotheses"]

    assert len(hypotheses) > 0, (
       f"No simulator-validated hypotheses generated. "
       f"Investigation result: {result['investigation']}"
    )

    hypothesis = hypotheses[0]
    investigator = build_investigator(validated=True)

    result = investigator.investigate(
        sample_reconstruction(),
        "reactor",
    )

    hypothesis = result["investigation"]["hypotheses"][0]

    assert hypothesis["simulator_validated"] is True
    assert hypothesis["causal_claim_status"] == "simulator_validated_path"


def test_investigator_rejects_unknown_target():
    investigator = build_investigator()

    with pytest.raises(ValueError):
        investigator.investigate(
            sample_reconstruction(),
            "unknown_component",
        )


def test_investigator_reports_no_cause_without_supporting_evidence():
    investigator = build_investigator()

    reconstruction = {"event_ledger": []}

    result = investigator.investigate(
        reconstruction,
        "reactor",
    )

    assert result["investigation"]["hypothesis_count"] == 0
    assert result["investigation"]["hypotheses"] == []