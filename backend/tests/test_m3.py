import pytest

from backend.app.modules.m3_simulation.state import IndustrialState
from backend.app.modules.m3_simulation.interventions import (
    get_intervention,
)


def test_default_industrial_state():
    state = IndustrialState()

    assert state.reactor_temperature_c == 85.0
    assert state.cooling_capacity_pct == 100.0
    assert state.energy_remaining_pct == 100.0


def test_state_to_dict():
    state = IndustrialState()

    result = state.to_dict()

    assert isinstance(result, dict)
    assert result["reactor_temperature_c"] == 85.0


def test_state_copy():
    state = IndustrialState()
    copied = state.copy()

    assert copied == state
    assert copied is not state


def test_invalid_energy_level():
    with pytest.raises(ValueError):
        IndustrialState(energy_remaining_pct=120.0)


def test_invalid_cooling_capacity():
    with pytest.raises(ValueError):
        IndustrialState(cooling_capacity_pct=-10.0)


def test_negative_simulation_time():
    with pytest.raises(ValueError):
        IndustrialState(simulation_time_minutes=-1)

from backend.app.modules.m3_simulation.interventions import (
    Intervention,
    get_default_interventions,
    get_intervention,
)


def test_default_interventions_count():
    interventions = get_default_interventions()

    assert len(interventions) == 4


def test_no_action_baseline():
    intervention = get_intervention("no_action")

    assert intervention.activates_backup_cooling is False
    assert intervention.isolates_network is False
    assert intervention.shuts_down_reactor is False


def test_backup_cooling_intervention():
    intervention = get_intervention("backup_cooling")

    assert intervention.activates_backup_cooling is True
    assert intervention.activation_delay_minutes == 2.0


def test_network_isolation_intervention():
    intervention = get_intervention("network_isolation")

    assert intervention.isolates_network is True


def test_reactor_shutdown_intervention():
    intervention = get_intervention("reactor_shutdown")

    assert intervention.shuts_down_reactor is True


def test_invalid_intervention_cost():
    with pytest.raises(ValueError):
        Intervention(
            intervention_id="invalid",
            name="Invalid Intervention",
            energy_cost_pct=150.0,
        )


def test_unknown_intervention():
    with pytest.raises(ValueError):
        get_intervention("unknown_action")
        
from backend.app.modules.m3_simulation.simulator import (
    IndustrialSimulator,
)


def test_simulator_creates_independent_state():
    simulator = IndustrialSimulator()
    initial = IndustrialState()

    run = simulator.create_run(
        initial,
        get_intervention("no_action"),
    )

    assert run.state is not initial
    assert run.state == initial


def test_simulator_advances_time():
    simulator = IndustrialSimulator()

    run = simulator.run(
        IndustrialState(),
        get_intervention("no_action"),
        duration_minutes=5,
    )

    assert run.state.simulation_time_minutes == 5


def test_backup_cooling_activates_after_delay():
    simulator = IndustrialSimulator()

    run = simulator.run(
        IndustrialState(),
        get_intervention("backup_cooling"),
        duration_minutes=3,
    )

    assert run.intervention_activated is True
    assert run.state.backup_cooling_active is True


def test_reactor_shutdown_activates():
    simulator = IndustrialSimulator()

    run = simulator.run(
        IndustrialState(),
        get_intervention("reactor_shutdown"),
        duration_minutes=4,
    )

    assert run.state.reactor_shutdown is True


def test_simulator_rejects_invalid_duration():
    simulator = IndustrialSimulator()

    with pytest.raises(ValueError):
        simulator.run(
            IndustrialState(),
            get_intervention("no_action"),
            duration_minutes=-1,
        )


def test_simulator_does_not_modify_initial_state():
    simulator = IndustrialSimulator()
    initial = IndustrialState()

    simulator.run(
        initial,
        get_intervention("backup_cooling"),
        duration_minutes=5,
    )

    assert initial.simulation_time_minutes == 0
    assert initial.reactor_temperature_c == 85.0
    
from backend.app.modules.m3_simulation.scenario_generator import (
    ScenarioGenerator,
)


def test_scenario_generator_creates_requested_count():
    generator = ScenarioGenerator(seed=42)

    scenarios = generator.generate(
        IndustrialState(),
        count=100,
    )

    assert len(scenarios) == 100


def test_scenario_ids_are_unique():
    generator = ScenarioGenerator(seed=42)

    scenarios = generator.generate(
        IndustrialState(),
        count=100,
    )

    ids = [scenario.scenario_id for scenario in scenarios]

    assert len(ids) == len(set(ids))


def test_scenarios_are_reproducible_with_same_seed():
    first = ScenarioGenerator(seed=123).generate(
        IndustrialState(),
        count=5,
    )

    second = ScenarioGenerator(seed=123).generate(
        IndustrialState(),
        count=5,
    )

    for a, b in zip(first, second):
        assert a.initial_state == b.initial_state
        assert a.sampled_variations == b.sampled_variations


def test_perfect_sensor_reliability_has_no_variation():
    generator = ScenarioGenerator(seed=42)

    scenarios = generator.generate(
        IndustrialState(),
        count=5,
        sensor_reliability=1.0,
    )

    for scenario in scenarios:
        assert scenario.initial_state.reactor_temperature_c == 85.0
        assert scenario.initial_state.cooling_capacity_pct == 100.0
        assert scenario.sampled_variations[
            "temperature_delta_c"
        ] == 0.0


def test_generated_resource_values_stay_in_bounds():
    generator = ScenarioGenerator(seed=42)

    scenarios = generator.generate(
        IndustrialState(),
        count=100,
        sensor_reliability=0.1,
    )

    for scenario in scenarios:
        state = scenario.initial_state

        assert 0 <= state.cooling_capacity_pct <= 100
        assert 0 <= state.energy_remaining_pct <= 100
        assert 0 <= state.coolant_remaining_pct <= 100


def test_scenario_generation_does_not_modify_base_state():
    base = IndustrialState()

    ScenarioGenerator(seed=42).generate(
        base,
        count=10,
        sensor_reliability=0.5,
    )

    assert base.reactor_temperature_c == 85.0
    assert base.cooling_capacity_pct == 100.0
    assert base.energy_remaining_pct == 100.0


def test_scenario_generator_rejects_invalid_count():
    generator = ScenarioGenerator(seed=42)

    with pytest.raises(ValueError):
        generator.generate(
            IndustrialState(),
            count=0,
        )
        
from backend.app.modules.m3_simulation.monte_carlo import (
    MonteCarloEngine,
)


def test_monte_carlo_runs_100_rollouts():
    engine = MonteCarloEngine()

    result = engine.run_experiment(
        base_state=IndustrialState(),
        interventions=[get_intervention("no_action")],
        rollout_count=100,
        seed=42,
    )

    assert result["rollout_count_per_intervention"] == 100
    assert result["total_simulations"] == 100


def test_monte_carlo_runs_all_interventions():
    engine = MonteCarloEngine()

    interventions = get_default_interventions()

    result = engine.run_experiment(
        IndustrialState(),
        interventions,
        rollout_count=100,
        seed=42,
    )

    assert result["intervention_count"] == 4
    assert result["total_simulations"] == 400


def test_every_intervention_uses_same_scenarios():
    engine = MonteCarloEngine()

    result = engine.run_experiment(
        IndustrialState(),
        get_default_interventions(),
        rollout_count=100,
        seed=42,
    )

    no_action = result["results"]["no_action"]
    backup = result["results"]["backup_cooling"]

    no_action_ids = [
        item["rollout_id"] for item in no_action
    ]

    backup_ids = [
        item["rollout_id"] for item in backup
    ]

    assert no_action_ids == backup_ids


def test_monte_carlo_results_are_reproducible():
    engine = MonteCarloEngine()

    first = engine.run_experiment(
        IndustrialState(),
        [get_intervention("no_action")],
        rollout_count=100,
        seed=123,
    )

    second = engine.run_experiment(
        IndustrialState(),
        [get_intervention("no_action")],
        rollout_count=100,
        seed=123,
    )

    assert first["results"] == second["results"]


def test_monte_carlo_rejects_less_than_100_rollouts():
    engine = MonteCarloEngine()

    with pytest.raises(ValueError):
        engine.run_experiment(
            IndustrialState(),
            [get_intervention("no_action")],
            rollout_count=50,
        )


def test_monte_carlo_rejects_duplicate_interventions():
    engine = MonteCarloEngine()
    intervention = get_intervention("no_action")

    with pytest.raises(ValueError):
        engine.run_experiment(
            IndustrialState(),
            [intervention, intervention],
            rollout_count=100,
        )


def test_monte_carlo_preserves_base_state():
    engine = MonteCarloEngine()
    initial = IndustrialState()

    engine.run_experiment(
        initial,
        [get_intervention("backup_cooling")],
        rollout_count=100,
        seed=42,
    )

    assert initial.simulation_time_minutes == 0.0
    assert initial.reactor_temperature_c == 85.0
    
from backend.app.modules.m3_simulation.risk_analyzer import (
    RiskAnalyzer,
)


def make_rollout(catastrophe=False, temperature=100.0):
    return {
        "catastrophe_occurred": catastrophe,
        "final_state": {
            "reactor_temperature_c": temperature,
            "catastrophe_threshold_c": 120.0,
            "energy_remaining_pct": 80.0,
            "coolant_remaining_pct": 80.0,
        },
    }


def test_risk_analyzer_calculates_catastrophe_probability():
    analyzer = RiskAnalyzer()

    rollouts = [
        make_rollout(True),
        make_rollout(False),
        make_rollout(True),
        make_rollout(False),
    ]

    result = analyzer.analyze_rollouts(rollouts)

    assert result["catastrophe_count"] == 2
    assert result["catastrophe_probability"] == 0.5


def test_risk_analyzer_calculates_mean_loss():
    analyzer = RiskAnalyzer()

    rollouts = [
        make_rollout(False),
        make_rollout(True),
    ]

    result = analyzer.analyze_rollouts(rollouts)

    assert result["mean_loss"] == 504.0


def test_risk_analyzer_calculates_cvar():
    analyzer = RiskAnalyzer(cvar_alpha=0.5)

    rollouts = [
        make_rollout(False, 100.0),
        make_rollout(False, 110.0),
        make_rollout(True, 130.0),
        make_rollout(True, 140.0),
    ]

    result = analyzer.analyze_rollouts(rollouts)

    assert result["cvar"] == 1154.0


def test_risk_analyzer_returns_confidence_interval():
    analyzer = RiskAnalyzer()

    result = analyzer.analyze_rollouts([
        make_rollout(True),
        make_rollout(False),
    ])

    lower, upper = (
        result["catastrophe_probability_confidence_interval"]
    )

    assert 0.0 <= lower <= 0.5
    assert 0.5 <= upper <= 1.0


def test_risk_analyzer_rejects_empty_rollouts():
    analyzer = RiskAnalyzer()

    with pytest.raises(ValueError):
        analyzer.analyze_rollouts([])


def test_risk_analyzer_analyzes_monte_carlo_experiment():
    engine = MonteCarloEngine()

    experiment = engine.run_experiment(
        IndustrialState(),
        [
            get_intervention("no_action"),
            get_intervention("backup_cooling"),
        ],
        rollout_count=100,
        seed=42,
    )

    analyzer = RiskAnalyzer()
    result = analyzer.analyze_experiment(experiment)

    assert result["intervention_count"] == 2
    assert "no_action" in result["results"]
    assert "backup_cooling" in result["results"]

    for intervention_result in result["results"].values():
        assert intervention_result["rollout_count"] == 100
        assert "mean_loss" in intervention_result
        assert "cvar" in intervention_result