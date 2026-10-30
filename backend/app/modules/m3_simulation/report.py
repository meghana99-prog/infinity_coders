from __future__ import annotations

from typing import Any


class ReportGenerator:
    """
    Builds a structured, simulation-based decision report.

    This report is for analysis and human review only.
    It does not authorize real-world industrial actions.
    """

    REQUIRED_EXPERIMENT_FIELDS = ("results",)
    REQUIRED_ANALYSIS_FIELDS = ("results",)

    def generate_report(
        self,
        experiment: dict[str, Any],
        risk_analysis: dict[str, Any],
    ) -> dict[str, Any]:

        self._validate_inputs(experiment, risk_analysis)

        experiment_results = experiment["results"]
        analysis_results = risk_analysis["results"]

        intervention_summaries = []

        for intervention_id, metrics in analysis_results.items():
            if intervention_id not in experiment_results:
                raise ValueError(
                    f"Risk analysis references unknown intervention: "
                    f"{intervention_id}"
                )

            rollouts = experiment_results[intervention_id]

            if not isinstance(rollouts, list) or not rollouts:
                raise ValueError(
                    f"No valid rollouts found for intervention: "
                    f"{intervention_id}"
                )

            summary = self._build_intervention_summary(
                intervention_id,
                metrics,
                rollouts,
            )

            intervention_summaries.append(summary)

        if not intervention_summaries:
            raise ValueError("No intervention results available.")

        # Prefer lower catastrophe probability, then lower CVaR,
        # then lower mean loss.
        ranked = sorted(
            intervention_summaries,
            key=lambda item: (
                item["catastrophe_probability"],
                item["cvar"],
                item["mean_loss"],
            ),
        )

        recommended = ranked[0]

        baseline = next(
            (
                item
                for item in intervention_summaries
                if item["intervention_id"] == "no_action"
            ),
            None,
        )

        return {
            "module": "M3_Report_Generator",
            "report_status": "COMPLETED",
            "simulation_metadata": self._extract_metadata(experiment),
            "intervention_count": len(intervention_summaries),
            "total_simulations": sum(
                item["rollout_count"]
                for item in intervention_summaries
            ),
            "intervention_comparison": intervention_summaries,
            "ranked_interventions": [
                item["intervention_id"] for item in ranked
            ],
            "recommended_candidate": {
                "intervention_id": recommended["intervention_id"],
                "reason": (
                    "This intervention has the lowest catastrophe "
                    "probability, followed by CVaR and mean loss "
                    "as tie-breakers in the evaluated simulations."
                ),
                "catastrophe_probability": (
                    recommended["catastrophe_probability"]
                ),
                "cvar": recommended["cvar"],
                "mean_loss": recommended["mean_loss"],
                "status": (
                    "SIMULATION_BASED_CANDIDATE_REQUIRES_HUMAN_REVIEW"
                ),
            },
            "baseline_comparison": self._compare_with_baseline(
                recommended,
                baseline,
            ),
            "comparison_basis": risk_analysis.get(
                "comparison_basis",
                "Common scenarios across interventions",
            ),
            "assumptions": self._build_assumptions(experiment),
            "limitations": self._collect_limitations(
                risk_analysis,
                intervention_summaries,
            ),
            "execution_authorized": False,
            "safety_notice": (
                "This report contains synthetic simulation results. "
                "It does not establish real-world safety or authorize "
                "industrial control actions. Independent verification "
                "and qualified human approval are required."
            ),
        }

    def _validate_inputs(
        self,
        experiment: dict[str, Any],
        risk_analysis: dict[str, Any],
    ) -> None:

        if not isinstance(experiment, dict):
            raise ValueError("Experiment must be a dictionary.")

        if not isinstance(risk_analysis, dict):
            raise ValueError("Risk analysis must be a dictionary.")

        for field in self.REQUIRED_EXPERIMENT_FIELDS:
            if field not in experiment:
                raise ValueError(
                    f"Experiment is missing required field: {field}"
                )

        for field in self.REQUIRED_ANALYSIS_FIELDS:
            if field not in risk_analysis:
                raise ValueError(
                    f"Risk analysis is missing required field: {field}"
                )

        if not isinstance(experiment["results"], dict):
            raise ValueError("Experiment results must be a dictionary.")

        if not isinstance(risk_analysis["results"], dict):
            raise ValueError("Risk analysis results must be a dictionary.")

        if not risk_analysis["results"]:
            raise ValueError("Risk analysis contains no intervention results.")

    def _build_intervention_summary(
        self,
        intervention_id: str,
        metrics: dict[str, Any],
        rollouts: list[dict[str, Any]],
    ) -> dict[str, Any]:

        if not isinstance(metrics, dict):
            raise ValueError(
                f"Invalid risk metrics for intervention: {intervention_id}"
            )

        required_metrics = (
            "catastrophe_probability",
            "mean_loss",
            "cvar",
        )

        for field in required_metrics:
            if field not in metrics:
                raise ValueError(
                    f"Missing metric '{field}' for {intervention_id}"
                )

        probability = float(metrics["catastrophe_probability"])
        mean_loss = float(metrics["mean_loss"])
        cvar = float(metrics["cvar"])

        if not 0 <= probability <= 1:
            raise ValueError("Catastrophe probability must be between 0 and 1.")

        if mean_loss < 0 or cvar < 0:
            raise ValueError("Loss metrics cannot be negative.")

        return {
            "intervention_id": intervention_id,
            "rollout_count": metrics.get(
                "rollout_count",
                len(rollouts),
            ),
            "catastrophe_count": metrics.get("catastrophe_count"),
            "catastrophe_probability": probability,
            "confidence_interval": metrics.get(
                "confidence_interval"
            ),
            "confidence_level": metrics.get("confidence_level"),
            "mean_loss": mean_loss,
            "cvar": cvar,
            "cvar_alpha": metrics.get("cvar_alpha"),
            "minimum_loss": metrics.get("minimum_loss"),
            "maximum_loss": metrics.get("maximum_loss"),
            "rollouts_evaluated": len(rollouts),
        }

    def _extract_metadata(
        self,
        experiment: dict[str, Any],
    ) -> dict[str, Any]:

        fields = (
            "rollout_count_per_intervention",
            "intervention_count",
            "total_simulations",
            "seed",
            "duration_minutes",
            "step_minutes",
            "sensor_reliability",
            "common_scenarios_used",
        )

        return {
            field: experiment[field]
            for field in fields
            if field in experiment
        }

    def _build_assumptions(
        self,
        experiment: dict[str, Any],
    ) -> list[str]:

        assumptions = [
            "All industrial scenarios and observations are synthetic.",
            "Interventions are evaluated using the same generated scenarios.",
            "Risk estimates depend on the simulator's assumptions and parameters.",
            "Simulation outcomes do not guarantee real-world safety.",
        ]

        if experiment.get("common_scenarios_used"):
            assumptions.append(
                "Common scenarios were used to compare interventions."
            )

        if "sensor_reliability" in experiment:
            assumptions.append(
                "Sensor reliability was modeled using the configured "
                "simulation parameter."
            )

        return assumptions

    def _collect_limitations(
        self,
        risk_analysis: dict[str, Any],
        summaries: list[dict[str, Any]],
    ) -> list[str]:

        limitations = [
            "Results are conditional on the synthetic simulator model.",
            "Confidence intervals quantify statistical uncertainty, "
            "not all forms of model uncertainty.",
            "A low estimated catastrophe probability does not prove safety.",
            "The recommended candidate requires independent human review.",
        ]

        for summary in summaries:
            metrics = risk_analysis["results"].get(
                summary["intervention_id"],
                {},
            )

            for limitation in metrics.get("limitations", []):
                if limitation not in limitations:
                    limitations.append(limitation)

        return limitations

    def _compare_with_baseline(
        self,
        recommended: dict[str, Any],
        baseline: dict[str, Any] | None,
    ) -> dict[str, Any]:

        if baseline is None:
            return {
                "baseline_available": False,
                "message": (
                    "No no_action baseline was provided for comparison."
                ),
            }

        return {
            "baseline_available": True,
            "baseline_intervention": "no_action",
            "recommended_intervention": recommended["intervention_id"],
            "catastrophe_probability_difference": (
                baseline["catastrophe_probability"]
                - recommended["catastrophe_probability"]
            ),
            "mean_loss_difference": (
                baseline["mean_loss"] - recommended["mean_loss"]
            ),
            "cvar_difference": (
                baseline["cvar"] - recommended["cvar"]
            ),
            "message": (
                "Positive differences indicate lower estimated risk "
                "or loss for the recommended candidate compared "
                "with the no-action baseline."
            ),
        }