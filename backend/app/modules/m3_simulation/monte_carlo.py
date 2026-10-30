from backend.app.modules.m3_simulation.state import IndustrialState
from backend.app.modules.m3_simulation.interventions import Intervention
from backend.app.modules.m3_simulation.simulator import IndustrialSimulator
from backend.app.modules.m3_simulation.scenario_generator import ScenarioGenerator


class MonteCarloEngine:
    """
    Runs repeated synthetic industrial simulations.

    Every intervention uses the same initial scenario set
    to ensure fair counterfactual comparisons.
    """

    def __init__(self):
        self.simulator = IndustrialSimulator()

    def run_experiment(
        self,
        base_state: IndustrialState,
        interventions: list[Intervention],
        rollout_count: int = 100,
        duration_minutes: float = 30.0,
        step_minutes: float = 1.0,
        sensor_reliability: float = 0.9,
        seed: int = 42,
    ) -> dict:

        if not isinstance(base_state, IndustrialState):
            raise TypeError("base_state must be IndustrialState.")

        if not interventions:
            raise ValueError("At least one intervention is required.")

        if not all(
            isinstance(item, Intervention)
            for item in interventions
        ):
            raise TypeError("All interventions must be Intervention objects.")

        if len({
            item.intervention_id for item in interventions
        }) != len(interventions):
            raise ValueError("Intervention IDs must be unique.")

        if rollout_count < 100:
            raise ValueError(
                "At least 100 rollouts are required per intervention."
            )

        if duration_minutes <= 0 or step_minutes <= 0:
            raise ValueError("Simulation durations must be positive.")

        # Generate one shared scenario set for every intervention.
        generator = ScenarioGenerator(seed=seed)

        scenarios = generator.generate(
            base_state=base_state,
            count=rollout_count,
            sensor_reliability=sensor_reliability,
        )

        results_by_intervention = {}

        for intervention in interventions:
            rollout_results = []

            for scenario in scenarios:
                simulation = self.simulator.run(
                    initial_state=scenario.initial_state,
                    intervention=intervention,
                    duration_minutes=duration_minutes,
                    step_minutes=step_minutes,
                )

                final_state = simulation.state

                rollout_results.append({
                    "rollout_id": scenario.scenario_id,
                    "intervention_id": intervention.intervention_id,
                    "initial_state": scenario.initial_state.to_dict(),
                    "final_state": final_state.to_dict(),
                    "catastrophe_occurred": (
                        simulation.catastrophe_occurred
                    ),
                    "intervention_activated": (
                        simulation.intervention_activated
                    ),
                    "sensor_reliability": (
                        scenario.sensor_reliability
                    ),
                    "sampled_variations": (
                        scenario.sampled_variations
                    ),
                    "elapsed_minutes": simulation.elapsed_minutes,
                })

            results_by_intervention[
                intervention.intervention_id
            ] = rollout_results

        return {
            "module": "M3_Monte_Carlo_Simulation",
            "rollout_count_per_intervention": rollout_count,
            "intervention_count": len(interventions),
            "total_simulations": rollout_count * len(interventions),
            "seed": seed,
            "duration_minutes": duration_minutes,
            "step_minutes": step_minutes,
            "sensor_reliability": sensor_reliability,
            "common_scenarios_used": True,
            "results": results_by_intervention,
        }