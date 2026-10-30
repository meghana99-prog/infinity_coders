from dataclasses import dataclass


@dataclass(frozen=True)
class Intervention:
    """
    Declarative intervention for synthetic industrial simulation.

    This class describes an action. The simulator will execute
    its effects in a later development stage.
    """

    intervention_id: str
    name: str

    activates_backup_cooling: bool = False
    isolates_network: bool = False
    shuts_down_reactor: bool = False

    activation_delay_minutes: float = 0.0

    energy_cost_pct: float = 0.0
    coolant_cost_pct: float = 0.0

    def __post_init__(self):
        if not self.intervention_id.strip():
            raise ValueError("Intervention ID cannot be empty.")

        if not self.name.strip():
            raise ValueError("Intervention name cannot be empty.")

        if self.activation_delay_minutes < 0:
            raise ValueError("Activation delay cannot be negative.")

        for field_name in (
            "energy_cost_pct",
            "coolant_cost_pct",
        ):
            value = getattr(self, field_name)

            if not 0.0 <= value <= 100.0:
                raise ValueError(
                    f"{field_name} must be between 0 and 100."
                )


def get_default_interventions() -> list[Intervention]:
    """
    Returns synthetic intervention scenarios.
    """

    return [
        Intervention(
            intervention_id="no_action",
            name="No Action Baseline",
        ),

        Intervention(
            intervention_id="backup_cooling",
            name="Activate Backup Cooling",
            activates_backup_cooling=True,
            activation_delay_minutes=2.0,
            energy_cost_pct=5.0,
            coolant_cost_pct=10.0,
        ),

        Intervention(
            intervention_id="network_isolation",
            name="Network Isolation",
            isolates_network=True,
            activation_delay_minutes=1.0,
            energy_cost_pct=2.0,
        ),

        Intervention(
            intervention_id="reactor_shutdown",
            name="Reactor Shutdown",
            shuts_down_reactor=True,
            activation_delay_minutes=3.0,
            energy_cost_pct=8.0,
        ),
    ]


def get_intervention(intervention_id: str) -> Intervention:
    """
    Retrieve an intervention using its ID.
    """

    for intervention in get_default_interventions():
        if intervention.intervention_id == intervention_id:
            return intervention

    raise ValueError(
        f"Unknown intervention: {intervention_id}"
    )