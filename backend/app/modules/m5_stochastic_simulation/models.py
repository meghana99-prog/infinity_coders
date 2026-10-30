
"""Structured data models for CHRONOS-X M5 optimization."""

from dataclasses import asdict, dataclass, field
from typing import Any
import math


@dataclass
class ActionModel:
    """Structured representation of one available action."""

    name: str
    execution_duration_minutes: int
    action_cost: float
    resource_requirements: dict[str, Any]
    dependencies: tuple[str, ...]
    failure_probability: float
    effect_delay_min: int
    effect_delay_max: int
    can_run_parallel: bool

    latest_safe_start_minute: int | None = None

    data_origin: str = "UNKNOWN"
    validation_status: str = "UNKNOWN"
    modelling_assumptions: tuple[str, ...] = ()

    @classmethod
    def from_dataset(
        cls,
        name: str,
        model: dict[str, Any],
    ) -> "ActionModel":
        """Build an action model from the V4 action definition."""

        if not isinstance(model, dict):
            raise ValueError("Action model must be a dictionary.")

        duration = model.get("execution_duration_minutes", 0)
        cost = model.get("action_cost", 0)
        failure_probability = model.get("failure_probability", 0)

        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ValueError("Execution duration must be numeric.")

        if not math.isfinite(duration) or duration < 0 or not float(duration).is_integer():
            raise ValueError("Execution duration must be a finite non-negative integer.")

        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            raise ValueError("Action cost must be numeric.")

        if not math.isfinite(cost) or cost < 0:
            raise ValueError("Action cost must be finite and non-negative.")

        if isinstance(failure_probability, bool) or not isinstance(
            failure_probability, (int, float)
        ):
            raise ValueError("Failure probability must be numeric.")

        if not math.isfinite(failure_probability) or not 0 <= failure_probability <= 1:
            raise ValueError("Failure probability must be between 0 and 1.")

        # Extract effect delay. V4 currently supplies effect_timing.
        timing = model.get("effect_timing") or {}
        effect_model = model.get("effect_model") or {}

        delay = {}

        if isinstance(timing, dict):
            delay = timing.get("delay_minutes") or {}

        # Fallback for older V3-shaped action definitions.
        if not delay and isinstance(effect_model, dict):
            delay = effect_model.get("effect_delay_minutes") or {}

        if not isinstance(delay, dict):
            raise ValueError("Effect delay must be a dictionary.")

        delay_min = delay.get("min", 0)
        delay_max = delay.get("max", 0)

        for value in (delay_min, delay_max):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Effect delays must be numeric.")
            if not math.isfinite(value) or value < 0 or not float(value).is_integer():
                raise ValueError("Effect delays must be finite non-negative integers.")

        if delay_max < delay_min:
            raise ValueError("Maximum effect delay cannot be less than minimum delay.")

        dependencies = model.get("dependencies", [])

        if not isinstance(dependencies, (list, tuple)):
            raise ValueError("Dependencies must be a list or tuple.")

        latest_start = model.get("latest_safe_start_minute")

        if latest_start is not None:
            if isinstance(latest_start, bool) or not isinstance(latest_start, (int, float)):
                raise ValueError("Latest safe start must be numeric.")
            if not math.isfinite(latest_start) or latest_start < 0 or not float(latest_start).is_integer():
                raise ValueError("Latest safe start must be a finite non-negative integer.")
            latest_start = int(latest_start)

        resource_requirements = model.get("resource_requirements", {}) or {}

        if not isinstance(resource_requirements, dict):
            raise ValueError("Resource requirements must be a dictionary.")

        return cls(
            name=name,
            execution_duration_minutes=int(duration),
            action_cost=float(cost),
            resource_requirements=dict(resource_requirements),
            dependencies=tuple(dependencies),
            failure_probability=float(failure_probability),
            effect_delay_min=int(delay_min),
            effect_delay_max=int(delay_max),
            can_run_parallel=bool(model.get("can_run_parallel", False)),
            latest_safe_start_minute=latest_start,
            data_origin=model.get("data_origin", "UNKNOWN"),
            validation_status=model.get("validation_status", "UNKNOWN"),
            modelling_assumptions=tuple(
                model.get("modelling_assumptions", [])
            ),
        )


@dataclass
class ScheduledAction:
    """One action with its planned execution timeline."""

    action: str
    start_minute: int
    completion_minute: int
    effect_delay_min: int = 0
    effect_delay_max: int = 0

    def __post_init__(self):
        if self.start_minute < 0:
            raise ValueError("Action start time cannot be negative.")

        if self.completion_minute < self.start_minute:
            raise ValueError("Completion cannot precede action start.")

        if self.effect_delay_min < 0:
            raise ValueError("Effect delay cannot be negative.")

        if self.effect_delay_max < self.effect_delay_min:
            raise ValueError("Invalid effect delay range.")

    @property
    def effect_start_minute(self) -> int:
        return self.completion_minute + self.effect_delay_min

    @property
    def effect_end_minute(self) -> int:
        return self.completion_minute + self.effect_delay_max


@dataclass
class ActionPlan:
    """An ordered candidate action plan."""

    plan_id: str
    actions: list[ScheduledAction] = field(default_factory=list)

    feasible: bool = False
    violations: list[str] = field(default_factory=list)

    expected_loss: float | None = None
    cvar_loss: float | None = None
    objective_score: float | None = None

    execution_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert the plan into a serializable dictionary."""
        return asdict(self)


@dataclass
class ObjectiveWeights:
    """Configurable weights for the M5 optimization objective."""

    catastrophe_probability: float
    cvar: float
    action_cost: float
    resource_cost: float
    delay_cost: float

    def validate(self) -> None:
        """Validate objective weights."""

        values = [
            self.catastrophe_probability,
            self.cvar,
            self.action_cost,
            self.resource_cost,
            self.delay_cost,
        ]

        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in values
        ):
            raise ValueError(
                "Objective weights must be finite and non-negative."
            )

        if not any(value > 0 for value in values):
            raise ValueError(
                "At least one objective weight must be positive."
            )
