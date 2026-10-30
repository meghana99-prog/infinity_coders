import pytest

from backend.app.modules.m3_simulation.report import ReportGenerator


@pytest.fixture
def sample_experiment():
    return {
        "module": "M3_Monte_Carlo",
        "rollout_count_per_intervention": 100,
        "intervention_count": 2,
        "total_simulations": 200,
        "seed": 42,
        "duration_minutes": 30,
        "step_minutes": 1,
        "sensor_reliability": 0.9,
        "common_scenarios_used": True,
        "results": {
            "no_action": [{"rollout_id": i} for i in range(100)],
            "backup_cooling": [{"rollout_id": i} for i in range(100)],
        },
    }


@pytest.fixture
def sample_analysis():
    return {
        "module": "M3_Risk_Analysis",
        "comparison_basis": "Common scenarios across interventions",
        "results": {
            "no_action": {
                "rollout_count": 100,
                "catastrophe_count": 30,
                "catastrophe_probability": 0.30,
                "confidence_interval": [0.22, 0.40],
                "confidence_level": 0.95,
                "mean_loss": 500.0,
                "cvar": 900.0,
                "cvar_alpha": 0.95,
                "minimum_loss": 10.0,
                "maximum_loss": 1200.0,
                "limitations": ["Synthetic baseline data."],
            },
            "backup_cooling": {
                "rollout_count": 100,
                "catastrophe_count": 10,
                "catastrophe_probability": 0.10,
                "confidence_interval": [0.05, 0.18],
                "confidence_level": 0.95,
                "mean_loss": 200.0,
                "cvar": 500.0,
                "cvar_alpha": 0.95,
                "minimum_loss": 5.0,
                "maximum_loss": 800.0,
                "limitations": [],
            },
        },
    }


def test_report_generator_creates_report(
    sample_experiment,
    sample_analysis,
):
    generator = ReportGenerator()

    report = generator.generate_report(
        sample_experiment,
        sample_analysis,
    )

    assert report["module"] == "M3_Report_Generator"
    assert report["report_status"] == "COMPLETED"


def test_report_contains_all_interventions(
    sample_experiment,
    sample_analysis,
):
    report = ReportGenerator().generate_report(
        sample_experiment,
        sample_analysis,
    )

    ids = {
        item["intervention_id"]
        for item in report["intervention_comparison"]
    }

    assert ids == {"no_action", "backup_cooling"}


def test_report_ranks_best_candidate(
    sample_experiment,
    sample_analysis,
):
    report = ReportGenerator().generate_report(
        sample_experiment,
        sample_analysis,
    )

    assert (
        report["recommended_candidate"]["intervention_id"]
        == "backup_cooling"
    )


def test_report_compares_with_baseline(
    sample_experiment,
    sample_analysis,
):
    report = ReportGenerator().generate_report(
        sample_experiment,
        sample_analysis,
    )

    comparison = report["baseline_comparison"]

    assert comparison["baseline_available"] is True
    assert comparison["catastrophe_probability_difference"] == pytest.approx(
        0.20
    )
    assert comparison["mean_loss_difference"] == pytest.approx(300.0)


def test_report_preserves_assumptions_and_limitations(
    sample_experiment,
    sample_analysis,
):
    report = ReportGenerator().generate_report(
        sample_experiment,
        sample_analysis,
    )

    assert len(report["assumptions"]) >= 4
    assert any(
        "Synthetic baseline data." in item
        for item in report["limitations"]
    )


def test_report_never_authorizes_execution(
    sample_experiment,
    sample_analysis,
):
    report = ReportGenerator().generate_report(
        sample_experiment,
        sample_analysis,
    )

    assert report["execution_authorized"] is False
    assert (
        report["recommended_candidate"]["status"]
        == "SIMULATION_BASED_CANDIDATE_REQUIRES_HUMAN_REVIEW"
    )


def test_report_rejects_missing_results(sample_analysis):
    generator = ReportGenerator()

    with pytest.raises(ValueError):
        generator.generate_report(
            {},
            sample_analysis,
        )


def test_report_rejects_empty_analysis(sample_experiment):
    generator = ReportGenerator()

    with pytest.raises(ValueError):
        generator.generate_report(
            sample_experiment,
            {"results": {}},
        )


def test_report_rejects_unknown_intervention(
    sample_experiment,
    sample_analysis,
):
    sample_analysis["results"]["unknown_action"] = {
        "catastrophe_probability": 0.1,
        "mean_loss": 100,
        "cvar": 200,
    }

    with pytest.raises(ValueError):
        ReportGenerator().generate_report(
            sample_experiment,
            sample_analysis,
        )