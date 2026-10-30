from backend.app.modules.m3_simulation.state import IndustrialState
from backend.app.modules.m3_simulation.interventions import (
    get_default_interventions,
)
from backend.app.modules.m3_simulation.monte_carlo import MonteCarloEngine
from backend.app.modules.m3_simulation.risk_analyzer import RiskAnalyzer
from backend.app.modules.m3_simulation.report import ReportGenerator


def test_complete_m3_pipeline():
    # 1. Create the initial industrial state
    base_state = IndustrialState()

    # 2. Load all available interventions
    interventions = get_default_interventions()

    # 3. Run Monte Carlo simulations
    engine = MonteCarloEngine()

    experiment = engine.run_experiment(
        base_state=base_state,
        interventions=interventions,
        rollout_count=100,
        duration_minutes=30,
        step_minutes=1,
        sensor_reliability=0.9,
        seed=42,
    )

    assert "results" in experiment
    assert len(experiment["results"]) == len(interventions)

    # Every intervention must have at least 100 rollouts
    for intervention_id, rollouts in experiment["results"].items():
        assert len(rollouts) >= 100

    # 4. Analyze simulation risks
    analyzer = RiskAnalyzer()
    risk_analysis = analyzer.analyze_experiment(experiment)
     
    print("\n========== INTERVENTION RISK COMPARISON ==========")

    for intervention_id, metrics in risk_analysis["results"].items():
        print(f"\nIntervention: {intervention_id}")
        print("Catastrophe probability:", metrics["catastrophe_probability"])
        print("Mean loss:", metrics["mean_loss"])
        print("CVaR:", metrics["cvar"])

    print("==================================================\n")
    print("\n========== INTERVENTION RISK COMPARISON ==========")

    assert "results" in risk_analysis

    for intervention_id in experiment["results"]:
        assert intervention_id in risk_analysis["results"]

    # 5. Generate the final decision report
    generator = ReportGenerator()

    report = generator.generate_report(
        experiment,
        risk_analysis,
    )

    # 6. Validate the complete report
    assert report["report_status"] == "COMPLETED"

    assert report["intervention_count"] == len(interventions)

    assert report["total_simulations"] >= (
        100 * len(interventions)
    )

    assert report["recommended_candidate"]["intervention_id"]

    assert report["execution_authorized"] is False

    assert report["baseline_comparison"]["baseline_available"] is True

    print("\n========== M3 INTEGRATION REPORT ==========")
    print("Interventions:", report["intervention_count"])
    print("Total simulations:", report["total_simulations"])
    print(
        "Recommended candidate:",
        report["recommended_candidate"]["intervention_id"],
    )
    print(
        "Recommendation status:",
        report["recommended_candidate"]["status"],
    )
    print("Execution authorized:", report["execution_authorized"])
    print("===========================================\n")