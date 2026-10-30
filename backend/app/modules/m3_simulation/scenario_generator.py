import random
from dataclasses import dataclass

from backend.app.modules.m3_simulation.state import IndustrialState


@dataclass
class Scenario:
    """One plausible synthetic industrial starting scenario."""

    scenario_id: str
    initial_state: IndustrialState
    sensor_reliability: float
    sampled_variations: dict


class ScenarioGenerator:
    """
    Generates reproducible uncertain industrial scenarios.

    Sensor reliability controls how much measurement uncertainty
    is applied to the initial state.

    This is a synthetic uncertainty model, not a calibrated
    industrial sensor model.
    """

    def __init__(self, seed: int | None = None):
        self.random = random.Random(seed)

    def generate(
        self,
        base_state: IndustrialState,
        count: int = 100,
        sensor_reliability: float = 0.9,
        temperature_std_c: float = 3.0,
        resource_std_pct: float = 5.0,
    ) -> list[Scenario]:

        if not isinstance(base_state, IndustrialState):
            raise TypeError("base_state must be IndustrialState.")

        if count <= 0:
            raise ValueError("Scenario count must be positive.")

        if not 0.0 <= sensor_reliability <= 1.0:
            raise ValueError(
                "Sensor reliability must be between 0 and 1."
            )

        if temperature_std_c < 0 or resource_std_pct < 0:
            raise ValueError("Standard deviations cannot be negative.")

        uncertainty_factor = 1.0 - sensor_reliability

        scenarios = []

        for index in range(count):
            state = base_state.copy()

            temperature_delta = self.random.gauss(
                0.0,
                temperature_std_c * uncertainty_factor,
            )

            cooling_delta = self.random.gauss(
                0.0,
                resource_std_pct * uncertainty_factor,
            )

            energy_delta = self.random.gauss(
                0.0,
                resource_std_pct * uncertainty_factor,
            )

            coolant_delta = self.random.gauss(
                0.0,
                resource_std_pct * uncertainty_factor,
            )

            state.reactor_temperature_c = max(
                -273.15,
                state.reactor_temperature_c + temperature_delta,
            )

            state.cooling_capacity_pct = min(
                100.0,
                max(0.0, state.cooling_capacity_pct + cooling_delta),
            )

            state.energy_remaining_pct = min(
                100.0,
                max(0.0, state.energy_remaining_pct + energy_delta),
            )

            state.coolant_remaining_pct = min(
                100.0,
                max(0.0, state.coolant_remaining_pct + coolant_delta),
            )

            state.validate()

            scenarios.append(
                Scenario(
                    scenario_id=f"scenario_{index + 1:03d}",
                    initial_state=state,
                    sensor_reliability=sensor_reliability,
                    sampled_variations={
                        "temperature_delta_c": round(
                            temperature_delta, 4
                        ),
                        "cooling_delta_pct": round(
                            cooling_delta, 4
                        ),
                        "energy_delta_pct": round(
                            energy_delta, 4
                        ),
                        "coolant_delta_pct": round(
                            coolant_delta, 4
                        ),
                    },
                )
            )

        return scenarios