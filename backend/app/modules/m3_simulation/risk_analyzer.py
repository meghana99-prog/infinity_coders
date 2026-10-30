import math


class RiskAnalyzer:
    """
    Analyzes Monte Carlo simulation outcomes.

    Calculates catastrophe probability, mean loss, CVaR,
    and Wilson confidence intervals.

    Loss values are illustrative synthetic scoring values,
    not real industrial risk measurements.
    """

    def __init__(
        self,
        catastrophe_penalty: float = 1000.0,
        temperature_penalty: float = 10.0,
        resource_penalty: float = 0.1,
        confidence_level: float = 0.95,
        cvar_alpha: float = 0.95,
    ):
        if catastrophe_penalty < 0:
            raise ValueError("Catastrophe penalty cannot be negative.")

        if temperature_penalty < 0 or resource_penalty < 0:
            raise ValueError("Loss penalties cannot be negative.")

        if not 0.0 < confidence_level < 1.0:
            raise ValueError("Confidence level must be between 0 and 1.")

        if not 0.0 < cvar_alpha < 1.0:
            raise ValueError("CVaR alpha must be between 0 and 1.")

        self.catastrophe_penalty = catastrophe_penalty
        self.temperature_penalty = temperature_penalty
        self.resource_penalty = resource_penalty
        self.confidence_level = confidence_level
        self.cvar_alpha = cvar_alpha

    def _calculate_loss(self, rollout: dict) -> float:
        final_state = rollout.get("final_state")

        if not isinstance(final_state, dict):
            raise ValueError("Rollout must contain final_state.")

        required = [
            "reactor_temperature_c",
            "catastrophe_threshold_c",
            "energy_remaining_pct",
            "coolant_remaining_pct",
        ]

        if any(key not in final_state for key in required):
            raise ValueError("Final state is missing required fields.")

        temperature = float(final_state["reactor_temperature_c"])
        threshold = float(final_state["catastrophe_threshold_c"])
        energy = float(final_state["energy_remaining_pct"])
        coolant = float(final_state["coolant_remaining_pct"])

        if not all(
            math.isfinite(value)
            for value in (temperature, threshold, energy, coolant)
        ):
            raise ValueError("Final state contains non-finite values.")

        if not 0.0 <= energy <= 100.0:
            raise ValueError("Energy must be between 0 and 100.")

        if not 0.0 <= coolant <= 100.0:
            raise ValueError("Coolant must be between 0 and 100.")

        catastrophe = rollout.get("catastrophe_occurred")

        if not isinstance(catastrophe, bool):
            raise ValueError("catastrophe_occurred must be boolean.")

        temperature_excess = max(0.0, temperature - threshold)

        resource_depletion = (
            (100.0 - energy) + (100.0 - coolant)
        )

        loss = (
            self.catastrophe_penalty * int(catastrophe)
            + temperature_excess * self.temperature_penalty
            + resource_depletion * self.resource_penalty
        )

        return round(loss, 6)

    @staticmethod
    def _wilson_interval(
        successes: int,
        trials: int,
        confidence_level: float,
    ) -> tuple[float, float]:
        """
        Wilson score interval for a binomial probability.
        """

        if trials <= 0:
            raise ValueError("Trials must be positive.")

        # Critical values for common confidence levels.
        critical_values = {
            0.90: 1.644854,
            0.95: 1.959964,
            0.99: 2.575829,
        }

        z = critical_values.get(confidence_level)

        if z is None:
            raise ValueError(
                "Supported confidence levels: 0.90, 0.95, 0.99."
            )

        p = successes / trials
        z2 = z * z

        denominator = 1.0 + z2 / trials

        center = (
            p + z2 / (2.0 * trials)
        ) / denominator

        margin = (
            z
            * math.sqrt(
                p * (1.0 - p) / trials
                + z2 / (4.0 * trials * trials)
            )
            / denominator
        )

        return (
            max(0.0, center - margin),
            min(1.0, center + margin),
        )

    def analyze_rollouts(self, rollouts: list[dict]) -> dict:
        if not isinstance(rollouts, list) or not rollouts:
            raise ValueError("At least one rollout is required.")

        losses = [
            self._calculate_loss(rollout)
            for rollout in rollouts
        ]

        catastrophe_count = sum(
            rollout["catastrophe_occurred"]
            for rollout in rollouts
        )

        count = len(rollouts)

        catastrophe_probability = catastrophe_count / count

        lower, upper = self._wilson_interval(
            catastrophe_count,
            count,
            self.confidence_level,
        )

        mean_loss = sum(losses) / count

        # Average the worst (1 - alpha) fraction of losses.
        sorted_losses = sorted(losses, reverse=True)

        tail_count = max(
            1,
            math.ceil((1.0 - self.cvar_alpha) * count),
        )

        cvar = sum(sorted_losses[:tail_count]) / tail_count

        return {
            "rollout_count": count,
            "catastrophe_count": catastrophe_count,
            "catastrophe_probability": round(
                catastrophe_probability, 6
            ),
            "catastrophe_probability_confidence_interval": [
                round(lower, 6),
                round(upper, 6),
            ],
            "confidence_level": self.confidence_level,
            "mean_loss": round(mean_loss, 6),
            "cvar": round(cvar, 6),
            "cvar_alpha": self.cvar_alpha,
            "minimum_loss": round(min(losses), 6),
            "maximum_loss": round(max(losses), 6),
            "losses": losses,
            "limitations": [
                "Risk estimates depend on the synthetic simulator.",
                "Confidence intervals describe sampling uncertainty, not model validity.",
                "CVaR is calculated from the worst sampled rollout losses.",
            ],
        }

    def analyze_experiment(self, experiment: dict) -> dict:
        if not isinstance(experiment, dict):
            raise TypeError("Experiment must be a dictionary.")

        results = experiment.get("results")

        if not isinstance(results, dict) or not results:
            raise ValueError("Experiment contains no intervention results.")

        analysis = {}

        for intervention_id, rollouts in results.items():
            analysis[intervention_id] = self.analyze_rollouts(
                rollouts
            )

        return {
            "module": "M3_Risk_Analysis",
            "intervention_count": len(analysis),
            "results": analysis,
            "comparison_basis": (
                "Shared initial scenarios from Monte Carlo experiment."
            ),
        }