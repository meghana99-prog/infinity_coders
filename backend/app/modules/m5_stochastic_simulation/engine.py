"""CHRONOS-X Responsibility 05: Stochastic Simulation & Action Planning.

Uses the shared Universal Dataset V4 as the sole source of scenario/action inputs.
This is a synthetic decision-support prototype, not an industrial controller.
Only the thermal variable is simulated because V4 supplies no pressure units,
limits, or pressure dynamics. A temperature threshold exceedance is NOT a
catastrophe probability or a validated safety conclusion.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from app.modules.m5_stochastic_simulation.resource_manager import (
    validate_resource_plan,
)

from app.shared_data.complete_test_dataset_v4 import (
    get_universal_dataset,
    get_scenario_dataset,
    get_responsibility_input,
)


class SimulationInputError(ValueError):
    pass


def _clock_minutes(value: str) -> int:
    try:
        t = datetime.strptime(value, "%H:%M:%S")
        return t.hour * 60 + t.minute + t.second / 60
    except (TypeError, ValueError) as exc:
        raise SimulationInputError(f"Invalid HH:MM:SS time: {value!r}") from exc


def _resolve_field(state: dict, field: str) -> Any:
    if field in state:
        return state[field]
    raise SimulationInputError(f"Safety/precondition field not present in state: {field}")


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    ops = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
    }
    if operator not in ops:
        raise SimulationInputError(f"Unsupported operator: {operator}")
    return bool(ops[operator](actual, expected))


def _condition_failures(conditions: list[dict], state: dict) -> list[str]:
    failures = []
    for item in conditions or []:
        field = item["field"]
        actual = _resolve_field(state, field)
        if not _compare(actual, item["operator"], item["expected_value"]):
            failures.append(
                f"{field}={actual!r} does not satisfy "
                f"{item['operator']} {item['expected_value']!r}"
            )
    return failures


def validate_action(action_name: str, dataset: dict, state: dict) -> dict:
    """Independent pre-execution policy check. A simulation score cannot override it."""
    model = dataset["action_models"].get(action_name)
    if model is None:
        return {"approved": False, "violations": ["UNKNOWN_ACTION"]}
    violations = _condition_failures(model.get("preconditions", []), state)
    for rule in dataset["safety_constraints"]["rules"]:
        if rule.get("action") != action_name or rule.get("effect") != "REJECT":
            continue
        field = rule["field"]
        actual = _resolve_field(state, field)
        if _compare(actual, rule["operator"], rule["expected_value"]):
            violations.append(f"{rule['rule_id']}: {rule['description']}")
    # V4 action requirements are qualitative. Explicit synthetic token mapping
    # below is documented and kept separate from the source dataset.
    resource_needs = _resource_needs(action_name, model)
    available = dataset["resource_inventory"]["current_availability"]
    for resource, amount in resource_needs.items():
        if available.get(resource, 0) < amount:
            violations.append(
                f"INSUFFICIENT_RESOURCE:{resource}:need={amount}:available={available.get(resource, 0)}"
            )
    return {"approved": not violations, "violations": violations,
            "resource_needs": resource_needs, "authority": "SIMULATION_ONLY"}


def _resource_needs(action_name: str, model: dict) -> dict[str, int]:
    """Translate V4's qualitative resource labels into labelled synthetic tokens.

    V4 defines capacities in synthetic tokens but some actions only say 'medium'
    or 'required'. This mapping is a modelling assumption, not source fact.
    """
    req = model.get("resource_requirements", {}) or {}
    needs: dict[str, int] = {}
    if req.get("power") in {"low", "medium", "high"}:
        needs["power"] = 1  # one synthetic token for any non-zero power class
    if req.get("authorization") == "required":
        needs["authorization"] = 1
    if action_name == "ISOLATE_NETWORK":
        needs["network_control_channel"] = 1
    if action_name in {"ACTIVATE_BACKUP_COOLING", "ISOLATE_NETWORK"}:
        needs["operators"] = 1
    if action_name == "SHUTDOWN_REACTOR":
        needs["operators"] = 2
    return needs
def validate_plan_resources(plan: tuple[str, ...], dataset: dict) -> dict:
    """Validate cumulative synthetic resource consumption for an ordered plan."""

    action_requirements = []

    for action_name in plan:
        model = dataset["action_models"].get(action_name)

        if model is None:
            return {
                "status": "UNKNOWN",
                "feasible": False,
                "violations": [],
                "unknowns": [f"Unknown action: {action_name}"],
                "execution_authorized": False,
            }

        # Uses the existing documented synthetic-token mapping.
        resources = _resource_needs(action_name, model)

        action_requirements.append({
            "action": action_name,
            "resources": resources,
        })

    return validate_resource_plan(
        dataset.get("resource_inventory", {}),
        action_requirements,
    )

def _effect_parameters(model: dict) -> tuple[float, float, int, int]:
    effect = model.get("effects", {}).get("temperature_change", {})
    if not effect:
        # Backward-compatible extraction from V3-shaped action data.
        effect = model.get("effect_model", {}).get("temperature_change", {})
    if effect.get("distribution") != "NORMAL":
        raise SimulationInputError("Only NORMAL temperature effect distributions are supported")
    mean = float(effect["mean"])
    std = float(effect["std_dev"])
    timing = model.get("effect_timing", {})
    if timing == "IMMEDIATE_PER_SIMULATION_STEP":
        lo = hi = 0
    else:
        delay = timing.get("delay_minutes", {})
        lo, hi = int(delay.get("min", 0)), int(delay.get("max", 0))
    if std < 0 or lo < 0 or hi < lo:
        raise SimulationInputError("Invalid effect distribution or delay range")
    return mean, std, lo, hi


def generate_candidate_plans(dataset: dict, max_actions: int = 2) -> list[tuple[str, ...]]:
    """Create a small, explainable plan set; monitoring is the baseline-only plan."""
    actions = list(dataset["action_models"].keys())
    plans: list[tuple[str, ...]] = [("CONTINUE_MONITORING",)]
    intervention_actions = [a for a in actions if a != "CONTINUE_MONITORING"]
    for length in range(1, min(max_actions, len(intervention_actions)) + 1):
        plans.extend(itertools.permutations(intervention_actions, length))
    # Stable de-duplication/order.
    return list(dict.fromkeys(plans))


def _schedule_plan(plan: tuple[str, ...], dataset: dict) -> list[dict]:
    clock = 0
    scheduled = []
    for name in plan:
        model = dataset["action_models"][name]
        duration = int(model.get("execution_duration_minutes", 0))
        start = clock
        finish = start + duration
        _, _, delay_min, delay_max = _effect_parameters(model)
        scheduled.append({"action": name, "start_minute": start,
                          "finish_minute": finish,
                          "delay_min": delay_min, "delay_max": delay_max})
        # Sequential plan execution is conservative: no overlap is assumed,
        # even when an action declares that it could run in parallel.
        clock = finish
    return scheduled


def _simulate_one(dataset: dict, plan: tuple[str, ...], rng: random.Random,
                  horizon: int, step: int) -> dict:
    state = deepcopy(dataset["current_state"])
    temp = float(state["temperature"])
    threshold = dataset["state_history"]["state_variables"][0].get("threshold")
    if threshold is None:
        raise SimulationInputError("Temperature restriction threshold is missing")
    schedule = _schedule_plan(plan, dataset)
    action_results = []
    events: list[tuple[int, float, str]] = []
    cost = 0.0
    resource_usage: dict[str, int] = {}
    failed = False
    remaining_resources = deepcopy(dataset["resource_inventory"]["current_availability"])

    # Validate each action against the state known at its scheduled start and
    # the resources remaining after earlier actions in this plan.
    for item in schedule:
        name = item["action"]
        if item["start_minute"] > horizon:
            action_results.append({"action": name, "status": "NOT_REACHED_DEADLINE"})
            continue
        validation_dataset = deepcopy(dataset)
        validation_dataset["resource_inventory"]["current_availability"] = remaining_resources
        validation = validate_action(name, validation_dataset, state)
        if not validation["approved"]:
            action_results.append({"action": name, "status": "REJECTED_BY_SAFETY_OR_RESOURCES",
                                   "violations": validation["violations"]})
            failed = True
            break
        model = dataset["action_models"][name]
        cost += float(model.get("action_cost", 0))
        for resource, amount in validation["resource_needs"].items():
            resource_usage[resource] = resource_usage.get(resource, 0) + amount
            remaining_resources[resource] = remaining_resources.get(resource, 0) - amount
        failure_probability = float(model.get("failure_probability", 0))
        did_fail = rng.random() < failure_probability
        if did_fail:
            action_results.append({"action": name, "status": "FAILED_NO_BENEFIT",
                                   "failure_probability": failure_probability})
            continue
        mean, std, _, _ = _effect_parameters(model)
        sampled_effect = rng.gauss(mean, std)
        delay = rng.randint(item["delay_min"], item["delay_max"])
        effect_minute = item["finish_minute"] + delay
        if effect_minute <= horizon:
            events.append((effect_minute, sampled_effect, name))
        action_results.append({"action": name, "status": "SCHEDULED",
                               "effect_minute": effect_minute,
                               "sampled_temperature_change": round(sampled_effect, 4)})

    # CONTINUE_MONITORING is represented by the V4 per-step drift. This drift
    # applies while the system evolves in every plan; an intervention effect is
    # an additional delayed change. This follows the model's stated step semantics.
    trajectory = []
    events_by_minute: dict[int, list[tuple[float, str]]] = {}
    for minute, delta, name in events:
        events_by_minute.setdefault(minute, []).append((delta, name))
    for minute in range(0, horizon + 1, step):
        if minute > 0:
            drift_model = dataset["action_models"]["CONTINUE_MONITORING"]
            drift_mean, drift_std, _, _ = _effect_parameters(drift_model)
            # Its mean/std are explicitly per configured simulation step.
            temp += rng.gauss(drift_mean, drift_std)
        for delta, _name in events_by_minute.get(minute, []):
            temp += delta
        trajectory.append({"minute": minute, "temperature": round(temp, 4)})
    exceed_minutes = sum(1 for p in trajectory if p["temperature"] > threshold)
    first_exceed = next((p["minute"] for p in trajectory if p["temperature"] > threshold), None)
    return {
        "trajectory": trajectory,
        "final_temperature": temp,
        "max_temperature": max(p["temperature"] for p in trajectory),
        "threshold_exceeded": first_exceed is not None,
        "first_threshold_exceedance_minute": first_exceed,
        "threshold_exceedance_minutes": exceed_minutes,
        "action_cost": cost,
        "resource_usage": resource_usage,
        "action_results": action_results,
        "plan_blocked": failed,
    }


def _aggregate(dataset: dict, plan: tuple[str, ...], runs: list[dict]) -> dict:
    n = len(runs)
    costs = sorted(x["action_cost"] for x in runs)
    finals = sorted(x["final_temperature"] for x in runs)
    maxes = sorted(x["max_temperature"] for x in runs)
    exceed = sum(x["threshold_exceeded"] for x in runs) / n
    failed = sum(any(a["status"] == "FAILED_NO_BENEFIT" for a in x["action_results"])
                 for x in runs) / n
    blocked = sum(x["plan_blocked"] for x in runs) / n
    avg_trajectory = []
    points = len(runs[0]["trajectory"])
    for i in range(points):
        vals = [x["trajectory"][i]["temperature"] for x in runs]
        avg_trajectory.append({"minute": runs[0]["trajectory"][i]["minute"],
                               "mean_temperature": round(sum(vals) / n, 4),
                               "p05": round(_quantile(vals, .05), 4),
                               "p95": round(_quantile(vals, .95), 4)})
    resources: dict[str, float] = {}
    for x in runs:
        for key, val in x["resource_usage"].items():
            resources[key] = resources.get(key, 0) + val / n
    return {
        "plan": list(plan), "iterations": n,
        "mean_action_cost": round(sum(costs) / n, 4),
        "p95_action_cost": round(_quantile(costs, .95), 4),
        "mean_final_temperature": round(sum(finals) / n, 4),
        "p95_max_temperature": round(_quantile(maxes, .95), 4),
        "temperature_threshold_exceedance_rate": round(exceed, 6),
        "action_failure_rate": round(failed, 6),
        "safety_or_resource_block_rate": round(blocked, 6),
        "mean_resource_usage_tokens": {k: round(v, 4) for k, v in resources.items()},
        "mean_temperature_trajectory": avg_trajectory,
    }


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    pos = (len(ordered) - 1) * q
    low, high = int(pos), min(int(pos) + 1, len(ordered) - 1)
    frac = pos - low
    return ordered[low] * (1 - frac) + ordered[high] * frac


def run_stage5(dataset: dict | None = None, scenario: str = "BASELINE_THERMAL_EVENT",
               iterations: int | None = None, seed: int | None = None,
               max_actions: int = 2) -> dict:
    """Run reproducible Monte Carlo comparisons for Responsibility 05."""
    if dataset is None:
        dataset = get_scenario_dataset(scenario)
    else:
        dataset = deepcopy(dataset)
    contract_input = get_responsibility_input(dataset, "05_STOCHASTIC_SIMULATION")
    required = {"state_history", "action_models", "resource_inventory", "simulation_config"}
    if not required.issubset(contract_input):
        raise SimulationInputError(f"Missing Responsibility 05 inputs: {required - set(contract_input)}")
    cfg = dataset["simulation_config"]
    n = int(iterations or cfg["iterations"])
    random_seed = int(cfg["random_seed"] if seed is None else seed)
    horizon = int(cfg["evaluation_horizon_minutes"])
    step = int(cfg["time_step_minutes"])
    if n < 1 or horizon < 1 or step < 1 or max_actions < 1:
        raise SimulationInputError("iterations, horizon, step and max_actions must be positive")
    if horizon % step:
        raise SimulationInputError("Horizon must be divisible by time_step_minutes")

    # Build plans and pre-screen against safety/resource rules using snapshot state.
    plans = generate_candidate_plans(dataset, max_actions=max_actions)
    plan_reports = []
    root_rng = random.Random(random_seed)
    for plan in plans:
        plan_rng = random.Random(root_rng.randrange(0, 2**32))
        runs = [_simulate_one(dataset, plan, plan_rng, horizon, step) for _ in range(n)]
        report = _aggregate(dataset, plan, runs)
        report["initial_safety_checks"] = [
            {"action": action, **validate_action(action, dataset, deepcopy(dataset["current_state"]))}
            for action in plan
        ]
                # Validate cumulative synthetic resource consumption across the plan.
        resource_report = validate_plan_resources(plan, dataset)
        report["resource_validation"] = resource_report
        report["resource_feasible"] = resource_report["feasible"]

        report["feasible_in_all_runs"] = (
            report["safety_or_resource_block_rate"] == 0
            and report["resource_feasible"]
        )

        plan_reports.append(report)
    # Incident relevance is a separate gate from technical feasibility.
    # V4 scenario descriptions are explicit: some incidents require investigation
    # or mitigation capabilities that are NOT present in the Stage 5 action set.
    # In those cases, abstain rather than repurpose an unrelated action.
    active_name = dataset.get("active_scenario", {}).get("name", scenario)
    relevance_policy = {
        "BASELINE_THERMAL_EVENT": {
            "relevant_actions": {"ACTIVATE_BACKUP_COOLING", "SHUTDOWN_REACTOR"},
            "reason": "Thermal mitigation actions are represented in the action model.",
        },
        "COOLING_FAILURE": {
            "relevant_actions": {"ACTIVATE_BACKUP_COOLING", "SHUTDOWN_REACTOR"},
            "reason": "No feasible action directly mitigates the cooling failure: backup cooling is unavailable and shutdown lacks permission.",
        },
        "POWER_FAILURE": {
            "relevant_actions": set(),
            "reason": "No power-restoration action exists in the V4 action model; network isolation is not a power-failure mitigation.",
        },
        "CYBER_INTRUSION": {
            "relevant_actions": set(),
            "reason": "The scenario is a suspected intrusion requiring investigation; V4 has no investigation/containment workflow, and suspicion alone does not justify network isolation.",
        },
        "CASCADING_FAILURE": {
            "relevant_actions": {"ACTIVATE_BACKUP_COOLING", "SHUTDOWN_REACTOR"},
            "reason": "No feasible thermal mitigation remains: backup cooling is unavailable, power is unavailable, and shutdown permission is absent.",
        },
        "SENSOR_MANIPULATION": {
            "relevant_actions": set(),
            "reason": "Sensor manipulation requires trust validation or sensor-recovery actions; V4 provides no such Stage 5 action, so a thermal intervention cannot resolve the evidence-integrity issue.",
        },
    }
    policy = relevance_policy.get(active_name)
    for item in plan_reports:
        plan_actions = set(item["plan"])
        relevant_actions = policy["relevant_actions"] if policy else set()
        relevant = bool(plan_actions) and plan_actions.issubset(relevant_actions) and bool(plan_actions.intersection(relevant_actions))
        # Monitoring alone is not a mitigation. For scenarios with no
        # implemented relevant action, all plans remain simulation-only.
        item["incident_relevant"] = relevant
        item["incident_relevance_reason"] = (
            "Contains an action mapped to the active incident's mitigation scope."
            if relevant else
            (policy["reason"] if policy else "No scenario-specific relevance policy exists; incident relevance is unverified.")
        )

    # Ranking is deliberately transparent and not a safety certification:
    # first minimize thermal threshold exceedance, then p95 max temperature,
    # then expected action cost. Threshold 95 is the V3 monitoring restriction,
    # not a validated catastrophe boundary.
    ranked = sorted(plan_reports, key=lambda x: (
        x["safety_or_resource_block_rate"] > 0,
        x["temperature_threshold_exceedance_rate"],
        x["p95_max_temperature"], x["mean_action_cost"], tuple(x["plan"])))
    for rank, item in enumerate(ranked, 1):
        item["simulation_rank"] = rank
    technically_feasible = [x for x in ranked if x["feasible_in_all_runs"]]
    feasible = [x for x in technically_feasible if x["incident_relevant"]]
    thermal_only_candidate = technically_feasible[0] if technically_feasible else None
    candidate = feasible[0] if feasible else None

    pressure_unknown = any(
        v.get("field") == "pressure" and v.get("threshold") is None
        for v in dataset["state_history"].get("state_variables", [])
    )
    flags = dataset.get("scenario_flags", {})
    limitations = [
        "Synthetic action distributions and resource-token mappings are not industrially validated.",
        "Temperature unit is unspecified; threshold 95 is only the V3 monitoring-action restriction.",
        "Pressure is not simulated because V4 supplies no pressure unit, threshold, or dynamics.",
        "This engine ranks simulation candidates only; Responsibility 06 must independently verify safety.",
        "No plan is authorized for real equipment control.",
    ]
    if pressure_unknown:
        limitations.append("Pressure state is present but cannot be assessed by this thermal-only model.")
    if flags.get("pressure_instability"):
        limitations.append("Pressure-instability scenario requires abstention from any whole-system recommendation.")

    # The engine returns a candidate for human review, never an executable command.
    whole_system_abstain = bool(flags.get("pressure_instability")) or candidate is None
    abstention_reason = None
    if flags.get("pressure_instability"):
        abstention_reason = "Pressure instability cannot be evaluated because pressure units, limits and dynamics are missing; thermal-only results are not whole-system recommendations."
    elif candidate is None and policy:
        abstention_reason = policy["reason"]
    elif candidate is None:
        abstention_reason = "No candidate plan passed all technical feasibility and incident-relevance gates."
    return {
        "responsibility": "05_STOCHASTIC_SIMULATION",
        "scenario_id": dataset["incident"]["scenario_id"],
        "scenario_name": scenario,
        "simulation_metadata": {"iterations": n, "random_seed": random_seed,
            "horizon_minutes": horizon, "time_step_minutes": step,
            "confidence_level": cfg["confidence_level"], "engine": "stdlib Monte Carlo"},
        "model_scope": {"simulated_variable": "temperature only",
            "threshold_value": dataset["state_history"]["state_variables"][0]["threshold"],
            "threshold_semantics": "V3 monitoring-action restriction only; not catastrophe threshold",
            "pressure_model_available": False},
        "candidate_plans": ranked,
        "best_candidate_for_human_review": candidate["plan"] if candidate else None,
        "best_candidate_metrics": candidate,
        "thermal_only_candidate_for_analysis": (
            {"plan": thermal_only_candidate["plan"],
             "metrics": thermal_only_candidate,
             "warning": "Thermal-only analysis; not a whole-system recommendation."}
            if flags.get("pressure_instability") and thermal_only_candidate else None
        ),
        "recommended_plan": None,
        "abstain": whole_system_abstain,
        "abstention_reason": abstention_reason,
        "decision_status": "ABSTAINED_NO_RELEVANT_FEASIBLE_PLAN" if whole_system_abstain else "SIMULATION_ONLY_REQUIRES_INDEPENDENT_SAFETY_VERIFICATION",
        "execution_authorized": False,
        "limitations": limitations,
        "data_origin": "V4_SHARED_DATASET_WITH_LABELLED_SYNTHETIC_ASSUMPTIONS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CHRONOS-X Stage 5 stochastic simulator")
    parser.add_argument("--scenario", default="BASELINE_THERMAL_EVENT",
        choices=list(get_universal_dataset()["scenario_variants"].keys()))
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max-actions", type=int, default=2)
    parser.add_argument("--output", default="stage5_output.json")
    args = parser.parse_args()
    result = run_stage5(scenario=args.scenario, iterations=args.iterations,
                        seed=args.seed, max_actions=args.max_actions)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("CHRONOS-X RESPONSIBILITY 05 COMPLETE")
    print("Scenario:", args.scenario)
    print("Iterations:", result["simulation_metadata"]["iterations"])
    print("Candidate plans:", len(result["candidate_plans"]))
    print("Best candidate for human review:", result["best_candidate_for_human_review"])
    print("Abstain:", result["abstain"])
    print("Output:", args.output)
    print("Execution authorized:", result["execution_authorized"])


if __name__ == "__main__":
    main()
