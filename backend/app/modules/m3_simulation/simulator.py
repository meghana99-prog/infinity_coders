from dataclasses import dataclass

from backend.app.modules.m3_simulation.state import IndustrialState
from backend.app.modules.m3_simulation.interventions import Intervention


@dataclass
class SimulationRun:
    state: IndustrialState
    intervention: Intervention
    elapsed_minutes: float = 0.0
    intervention_activated: bool = False
    catastrophe_occurred: bool = False


class IndustrialSimulator:
    """
    Deterministic synthetic industrial simulator.

    This is a research prototype, not a model of real industrial
    equipment or a source of operational safety instructions.
    """

    def create_run(
        self,
        initial_state: IndustrialState,
        intervention: Intervention,
    ) -> SimulationRun:

        if not isinstance(initial_state, IndustrialState):
            raise TypeError("initial_state must be IndustrialState.")

        if not isinstance(intervention, Intervention):
            raise TypeError("intervention must be Intervention.")

        return SimulationRun(
            state=initial_state.copy(),
            intervention=intervention,
        )

    def _activate_intervention(self, run: SimulationRun) -> None:
        state = run.state
        action = run.intervention

        if state.energy_remaining_pct < action.energy_cost_pct:
            return

        if state.coolant_remaining_pct < action.coolant_cost_pct:
            return

        state.energy_remaining_pct -= action.energy_cost_pct
        state.coolant_remaining_pct -= action.coolant_cost_pct

        if action.activates_backup_cooling:
            state.backup_cooling_active = True

        if action.isolates_network:
            state.network_isolated = True

        if action.shuts_down_reactor:
            state.reactor_shutdown = True

        run.intervention_activated = True

    def step(
        self,
        run: SimulationRun,
        duration_minutes: float = 1.0,
    ) -> SimulationRun:

        if not isinstance(run, SimulationRun):
            raise TypeError("run must be a SimulationRun.")

        if duration_minutes <= 0:
            raise ValueError("Duration must be positive.")

        if run.catastrophe_occurred:
            return run

        state = run.state
        action = run.intervention

        next_elapsed = run.elapsed_minutes + duration_minutes

        # Activate intervention after its configured delay.
        if (
            not run.intervention_activated
            and next_elapsed >= action.activation_delay_minutes
        ):
            self._activate_intervention(run)

        # Synthetic thermal model.
        if state.reactor_shutdown:
            heat_gain = 0.0
        else:
            heat_gain = 1.5

        cooling_effect = (
            state.cooling_capacity_pct / 100.0
        ) * 1.0

        if state.backup_cooling_active:
            cooling_effect += 2.5

        # Synthetic resource consumption.
        energy_consumption = 0.15 * duration_minutes
        coolant_consumption = 0.20 * duration_minutes

        if state.network_isolated:
            energy_consumption *= 0.8

        state.energy_remaining_pct = max(
            0.0,
            state.energy_remaining_pct - energy_consumption,
        )

        state.coolant_remaining_pct = max(
            0.0,
            state.coolant_remaining_pct - coolant_consumption,
        )

        # Synthetic cascading failure conditions.
        if (
            state.energy_remaining_pct <= 0.0
            or state.coolant_remaining_pct <= 0.0
        ):
            state.cooling_capacity_pct = 0.0

        state.reactor_temperature_c += (
            heat_gain - cooling_effect
        ) * duration_minutes

        state.simulation_time_minutes += duration_minutes
        run.elapsed_minutes = next_elapsed

        if (
            state.reactor_temperature_c
            >= state.catastrophe_threshold_c
        ):
            run.catastrophe_occurred = True

        state.validate()

        return run

    def run(
        self,
        initial_state: IndustrialState,
        intervention: Intervention,
        duration_minutes: float = 30.0,
        step_minutes: float = 1.0,
    ) -> SimulationRun:

        if duration_minutes <= 0:
            raise ValueError("Simulation duration must be positive.")

        if step_minutes <= 0:
            raise ValueError("Step duration must be positive.")

        simulation = self.create_run(
            initial_state,
            intervention,
        )

        remaining = duration_minutes

        while remaining > 0 and not simulation.catastrophe_occurred:
            current_step = min(step_minutes, remaining)

            self.step(simulation, current_step)
            remaining -= current_step

        return simulation