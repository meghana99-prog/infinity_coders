from dataclasses import dataclass, asdict


@dataclass
class IndustrialState:
    """
    Represents the current state of a synthetic industrial facility.

    All values belong to the virtual simulation environment.
    """

    simulation_time_minutes: float = 0.0

    reactor_temperature_c: float = 85.0
    cooling_capacity_pct: float = 100.0
    energy_remaining_pct: float = 100.0

    backup_cooling_active: bool = False
    network_isolated: bool = False
    reactor_shutdown: bool = False

    coolant_remaining_pct: float = 100.0

    catastrophe_threshold_c: float = 120.0

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        if self.simulation_time_minutes < 0:
            raise ValueError("Simulation time cannot be negative.")

        if self.reactor_temperature_c < -273.15:
            raise ValueError("Invalid reactor temperature.")

        bounded_values = {
            "cooling_capacity_pct": self.cooling_capacity_pct,
            "energy_remaining_pct": self.energy_remaining_pct,
            "coolant_remaining_pct": self.coolant_remaining_pct,
        }

        for name, value in bounded_values.items():
            if not 0.0 <= value <= 100.0:
                raise ValueError(
                    f"{name} must be between 0 and 100."
                )

        if self.catastrophe_threshold_c <= -273.15:
            raise ValueError("Invalid catastrophe threshold.")

        if self.reactor_shutdown and self.backup_cooling_active:
            # These states are not inherently incompatible.
            # Backup cooling may operate during shutdown.
            pass

    def to_dict(self) -> dict:
        return asdict(self)

    def copy(self):
        return IndustrialState(**self.to_dict())