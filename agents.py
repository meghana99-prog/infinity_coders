"""
M4 - Multi-Agent Adversarial Decision System for CHRONOS-X.

This module coordinates five bounded roles:
- Investigator: summarizes possible causes from supplied evidence.
- Predictor: reads M3 simulation results; it does not invent risk reductions.
- Optimizer: ranks feasible simulated candidates for review.
- Safety: independently checks basic hard constraints supplied in current_state.
- Red Team: challenges weak evidence, suspicious recommendations, and disagreement.

M4 produces a review recommendation only. It never executes industrial actions.
M1, M2, M3 and M6 modules are not modified by this file.
"""

from __future__ import annotations

from typing import Any


ACTION_CATALOG = {
    "CONTINUE_MONITORING",
    "ACTIVATE_BACKUP_COOLING",
    "ISOLATE_NETWORK",
    "SHUTDOWN_REACTOR",
}

# M3's Intervention IDs are lowercase; normalize them to M4 action names.
M3_ACTION_MAP = {
    "no_action": "CONTINUE_MONITORING",
    "backup_cooling": "ACTIVATE_BACKUP_COOLING",
    "network_isolation": "ISOLATE_NETWORK",
    "reactor_shutdown": "SHUTDOWN_REACTOR",
}

CAUSE_RULES = {
    "TEMPERATURE_READING": "possible_sensor_or_thermal_anomaly",
    "COOLING_STATUS": "possible_cooling_system_issue",
    "NETWORK_ALERT": "possible_cyber_or_network_incident",
    "CONTROLLER_ALERT": "possible_controller_fault",
}


def _valid_event_ids(timeline: list[dict]) -> list[str]:
    return [
        str(event["event_id"])
        for event in timeline
        if isinstance(event, dict)
        and event.get("event_id") is not None
        and str(event.get("event_id")).strip()
    ]


def _message(agent: str, recommendation: str | None,
             evidence_ids: list[str], confidence: float,
             rationale: list[str], status: str = "READY") -> dict:
    """Create a consistent, auditable agent message."""
    return {
        "agent": agent,
        "recommendation": recommendation,
        "evidence_ids": sorted(set(evidence_ids)),
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "rationale": rationale,
        "status": status,
    }


def investigator_agent(timeline: list[dict],
                       causal_result: dict | None = None) -> dict:
    """Generate cause hypotheses while preserving their evidence links."""
    if not isinstance(timeline, list):
        raise TypeError("timeline must be a list")

    causes: dict[str, list[str]] = {}
    for event in timeline:
        if not isinstance(event, dict):
            continue

        event_type = str(event.get("event_type", "")).upper()
        cause = CAUSE_RULES.get(event_type)

        if cause:
            event_id = event.get("event_id")
            causes.setdefault(cause, [])

            if event_id is not None:
                causes[cause].append(str(event_id))

    # If M2 output is supplied, retain its ranked hypotheses and evidence.
    m2_investigation = (
        causal_result.get("investigation", {})
        if isinstance(causal_result, dict) else {}
    )

    ranked = m2_investigation.get("ranked_causes", [])

    if isinstance(ranked, list):
        for item in ranked:
            if not isinstance(item, dict):
                continue

            cause = item.get("cause") or item.get("variable")

            if cause:
                causes.setdefault(str(cause), [])
                causes[str(cause)].extend(
                    str(x) for x in item.get("evidence_ids", [])
                )

    ranked_causes = [
        {"cause": cause, "evidence_ids": sorted(set(ids))}
        for cause, ids in sorted(causes.items())
    ]

    evidence_ids = [
        eid
        for item in ranked_causes
        for eid in item["evidence_ids"]
    ]

    return {
        **_message(
            "Investigator",
            "INVESTIGATE_CAUSAL_HYPOTHESES" if ranked_causes else None,
            evidence_ids,
            0.65 if ranked_causes else 0.0,
            ["Causes are hypotheses, not proven causal effects."],
            "READY" if ranked_causes else "INSUFFICIENT_EVIDENCE",
        ),
        "ranked_causes": ranked_causes,
    }


def predictor_agent(current_state: dict,
                    simulation_report: dict | None = None) -> dict:
    """
    Extract candidate risks from M3's report.

    No fixed risk reduction is fabricated. If M3 results are absent,
    the predictor explicitly reports insufficient simulation evidence.
    """
    if not isinstance(current_state, dict):
        raise TypeError("current_state must be a dictionary")

    predictions = {}

    if isinstance(simulation_report, dict):
        comparisons = simulation_report.get(
            "intervention_comparison", []
        )

        if isinstance(comparisons, list):
            for item in comparisons:
                if not isinstance(item, dict):
                    continue

                raw_action = item.get("intervention_id")
                action = M3_ACTION_MAP.get(raw_action, raw_action)

                risk = item.get("catastrophe_probability")

                if (
                    action in ACTION_CATALOG
                    and isinstance(risk, (int, float))
                    and not isinstance(risk, bool)
                    and 0 <= risk <= 1
                ):
                    predictions[action] = {
                        "risk": float(risk),
                        "mean_loss": item.get("mean_loss"),
                        "cvar": item.get("cvar"),
                        "source": "M3_SIMULATION",
                    }

    if not predictions:
        return {
            **_message(
                "Predictor",
                None,
                [],
                0.0,
                [
                    "No usable M3 intervention comparison was supplied.",
                    "A risk reduction must not be invented.",
                ],
                "INSUFFICIENT_SIMULATION_EVIDENCE",
            ),
            "predictions": {},
        }

    best = min(
        predictions,
        key=lambda action: (
            predictions[action]["risk"],
            predictions[action]["cvar"]
            if isinstance(
                predictions[action]["cvar"], (int, float)
            )
            else float("inf"),
        ),
    )

    return {
        **_message(
            "Predictor",
            best,
            [],
            0.75,
            [
                "Risk values were read from the supplied M3 simulation report."
            ],
        ),
        "predictions": predictions,
    }


def optimizer_agent(predictions: dict,
                    current_state: dict | None = None) -> dict:
    """Rank M3 candidates after applying available-resource constraints."""
    if not isinstance(predictions, dict):
        raise TypeError("predictions must be a dictionary")

    state = current_state or {}

    rejected = {}
    feasible = {}

    for action, metrics in predictions.items():

        if action not in ACTION_CATALOG or not isinstance(metrics, dict):
            rejected[str(action)] = "Unknown action or invalid metrics"
            continue

        if (
            action == "ACTIVATE_BACKUP_COOLING"
            and state.get("backup_cooling_available") is False
        ):
            rejected[action] = "Backup cooling unavailable"
            continue

        if (
            action == "SHUTDOWN_REACTOR"
            and state.get("shutdown_permission") is False
        ):
            rejected[action] = "Shutdown permission unavailable"
            continue

        if (
            action == "ISOLATE_NETWORK"
            and state.get("network_isolation_available") is False
        ):
            rejected[action] = "Network isolation unavailable"
            continue

        risk = metrics.get("risk")

        if (
            not isinstance(risk, (int, float))
            or not 0 <= risk <= 1
        ):
            rejected[action] = "Invalid or missing simulated risk"
            continue

        feasible[action] = metrics

    if not feasible:
        return {
            **_message(
                "Optimizer",
                None,
                [],
                0.0,
                ["No feasible simulated candidate remains."],
                "NO_FEASIBLE_CANDIDATE",
            ),
            "ranked_actions": [],
            "rejected_actions": rejected,
        }

    ranked = sorted(
        feasible,
        key=lambda action: (
            feasible[action]["risk"],
            feasible[action].get("cvar")
            if isinstance(
                feasible[action].get("cvar"), (int, float)
            )
            else float("inf"),
            feasible[action].get("mean_loss")
            if isinstance(
                feasible[action].get("mean_loss"), (int, float)
            )
            else float("inf"),
        ),
    )

    return {
        **_message(
            "Optimizer",
            ranked[0],
            [],
            0.75,
            [
                "Candidates ranked by catastrophe probability, "
                "then CVaR, then mean loss.",
                "This is candidate ranking, not full sequential M5 optimization.",
            ],
        ),
        "ranked_actions": ranked,
        "rejected_actions": rejected,
    }


def safety_agent(recommended_action: str | None,
                 current_state: dict) -> dict:
    """Perform independent, conservative pre-checks for the proposed action."""
    if not isinstance(current_state, dict):
        raise TypeError("current_state must be a dictionary")

    checks = []

    if recommended_action not in ACTION_CATALOG:
        checks.append({
            "constraint": "action_allowlist",
            "status": "FAIL",
        })
    else:
        checks.append({
            "constraint": "action_allowlist",
            "status": "PASS",
        })

    if recommended_action == "SHUTDOWN_REACTOR":
        value = current_state.get("shutdown_permission")

        checks.append({
            "constraint": "shutdown_permission",
            "status": (
                "PASS" if value is True
                else "FAIL" if value is False
                else "UNKNOWN"
            ),
        })

    elif recommended_action == "ACTIVATE_BACKUP_COOLING":
        value = current_state.get("backup_cooling_available")

        checks.append({
            "constraint": "backup_cooling_available",
            "status": (
                "PASS" if value is True
                else "FAIL" if value is False
                else "UNKNOWN"
            ),
        })

    elif recommended_action == "CONTINUE_MONITORING":
        temperature = current_state.get("temperature")

        if isinstance(temperature, (int, float)):
            checks.append({
                "constraint": "monitoring_temperature_limit",
                "status": "FAIL" if temperature > 95 else "PASS",
            })
        else:
            checks.append({
                "constraint": "monitoring_temperature_limit",
                "status": "UNKNOWN",
            })

    statuses = [item["status"] for item in checks]

    overall = (
        "FAILED" if "FAIL" in statuses
        else "UNKNOWN" if "UNKNOWN" in statuses
        else "PASSED"
    )

    return {
        **_message(
            "Safety",
            None,
            [],
            0.95,
            [
                "Safety checks are independent of the optimizer's confidence."
            ],
            overall,
        ),
        "status": overall,
        "checked_action": recommended_action,
        "checks": checks,
        "execution_allowed": False,
        "requires_human_approval": True,
    }


def red_team_agent(timeline: list[dict],
                   agent_messages: list[dict],
                   safety_status: str,
                   optimizer_result: dict | None = None) -> dict:
    """Challenge unsupported, conflicting, or suspicious agent claims."""
    if (
        not isinstance(timeline, list)
        or not isinstance(agent_messages, list)
    ):
        raise TypeError("timeline and agent_messages must be lists")

    warnings = []
    known_ids = set(_valid_event_ids(timeline))

    for message in agent_messages:
        if not isinstance(message, dict):
            warnings.append("Malformed agent message")
            continue

        unknown = (
            set(message.get("evidence_ids", [])) - known_ids
        )

        if unknown:
            warnings.append(
                f"{message.get('agent', 'Unknown')} referenced unknown evidence"
            )

        if (
            message.get("recommendation") is not None
            and message.get("confidence", 0) >= 0.95
            and not message.get("evidence_ids")
        ):
            warnings.append(
                f"{message.get('agent', 'Unknown')} made a high-confidence "
                "recommendation without evidence"
            )

    # Compare only roles that recommend operational candidate actions.
    recommendations = {
        item.get("recommendation")
        for item in agent_messages
        if (
            isinstance(item, dict)
            and item.get("agent") in {"Predictor", "Optimizer"}
            and item.get("recommendation")
        )
    }

    if len(recommendations) > 1:
        predictor_choice = next(
            (
                item.get("recommendation")
                for item in agent_messages
                if (
                    isinstance(item, dict)
                    and item.get("agent") == "Predictor"
                )
            ),
            None,
        )

        optimizer_rejections = (
            optimizer_result.get("rejected_actions", {})
            if isinstance(optimizer_result, dict)
            else {}
        )

        # A disagreement is resolved when the optimizer excludes the
        # predictor's preferred action for an explicit hard constraint.
        if not (predictor_choice in optimizer_rejections):
            warnings.append(
                "Unresolved agent disagreement requires adjudication"
            )

    if safety_status != "PASSED":
        warnings.append(f"Safety status is {safety_status}")

    if sum(
        1
        for event in timeline
        if (
            isinstance(event, dict)
            and isinstance(event.get("trust_score"), (int, float))
            and event.get("trust_score", 1) < 0.35
        )
    ) >= 2:
        warnings.append("Multiple low-trust events detected")

    return {
        **_message(
            "Red-Team",
            None,
            [],
            0.85,
            warnings or [
                "No configured red-team rule was triggered."
            ],
            "CHALLENGE" if warnings else "CLEAR",
        ),
        "warnings": warnings,
        "challenge": bool(warnings),
    }


def run_multi_agent_system(
    timeline: list[dict],
    current_state: dict,
    simulation_report: dict | None = None,
    causal_result: dict | None = None,
    external_recommendations: list[dict] | None = None,
) -> dict:
    """
    Run the five M4 roles and adjudicate their messages.

    Backward-compatible call:
        run_multi_agent_system(timeline, current_state)

    Recommended integrated call:
        run_multi_agent_system(
            timeline, current_state,
            simulation_report=m3_report,
            causal_result=m2_result,
        )
    """
    if not isinstance(timeline, list):
        raise TypeError("timeline must be a list")

    if not isinstance(current_state, dict):
        raise TypeError("current_state must be a dictionary")

    investigator = investigator_agent(timeline, causal_result)

    predictor = predictor_agent(
        current_state,
        simulation_report,
    )

    optimizer = optimizer_agent(
        predictor["predictions"],
        current_state,
    )

    proposed_action = optimizer["recommendation"]

    safety = safety_agent(
        proposed_action,
        current_state,
    )

    messages = [
        investigator,
        predictor,
        optimizer,
        safety,
    ]

    # External agents are untrusted. A persuasive confidence score or a
    # self-declared safety PASS is never sufficient for acceptance.
    known_ids = set(_valid_event_ids(timeline))

    rejected_external_agents = []
    accepted_external_agents = []

    for external in external_recommendations or []:
        reasons = []

        if not isinstance(external, dict):
            rejected_external_agents.append({
                "agent": "UNKNOWN",
                "status": "REJECT",
                "reasons": ["Malformed recommendation"],
            })
            continue

        action = (
            external.get("recommendation")
            or external.get("action")
        )

        evidence_ids = external.get("evidence_ids", [])

        if action not in ACTION_CATALOG:
            reasons.append(
                "Action is not in the M4 action allowlist"
            )

        if not isinstance(evidence_ids, list) or not evidence_ids:
            reasons.append("Evidence references are missing")

        elif any(eid not in known_ids for eid in evidence_ids):
            reasons.append(
                "Recommendation references unknown evidence"
            )

        if external.get("safety_status") == "PASS":
            # Safety status must come from the independent Safety role.
            reasons.append(
                "Self-declared safety PASS is not trusted"
            )

        if reasons:
            rejected_external_agents.append({
                "agent": external.get(
                    "agent", "ExternalAgent"
                ),
                "status": "OVERRULED",
                "reasons": reasons,
                "execution_allowed": False,
            })

        else:
            accepted_external_agents.append({
                "agent": external.get(
                    "agent", "ExternalAgent"
                ),
                "status": "UNVERIFIED_FOR_REVIEW",
                "action": action,
                "evidence_ids": list(evidence_ids),
                "execution_allowed": False,
            })

    red_team = red_team_agent(
        timeline,
        messages,
        safety["status"],
        optimizer_result=optimizer,
    )

    # Adjudication: a candidate is accepted for human review only when
    # simulation evidence exists, constraints pass, and red-team checks clear.
    if predictor["status"] != "READY":
        decision = "ABSTAIN"
        reason = "M3 simulation evidence is unavailable"

    elif optimizer["status"] != "READY" or proposed_action is None:
        decision = "ABSTAIN"
        reason = "No feasible candidate was identified"

    elif safety["status"] != "PASSED":
        decision = "ABSTAIN"
        reason = "Safety checks failed or remain unknown"

    elif red_team["challenge"]:
        decision = "ABSTAIN"
        reason = "Red Team challenge requires review"

    else:
        decision = proposed_action
        reason = (
            "Candidate passed M4 review; human approval is still required"
        )

    return {
        "module": "M4_Multi_Agent_Adversarial_Decision_System",
        "final_decision": decision,
        "reason": reason,
        "execution_allowed": False,
        "requires_human_approval": True,
        "agent_messages": messages + [red_team],
        "rejected_external_agents": rejected_external_agents,
        "accepted_external_agents": accepted_external_agents,
        "investigator": investigator,
        "predictor": predictor,
        "optimizer": optimizer,
        "safety": safety,
        "red_team": red_team,
        "audit": {
            "known_evidence_ids": _valid_event_ids(timeline),
            "decision_status": (
                "ABSTAIN"
                if decision == "ABSTAIN"
                else "CANDIDATE_FOR_HUMAN_REVIEW"
            ),
            "external_agents_overruled": len(
                rejected_external_agents
            ),
            "independent_roles": [
                "Investigator",
                "Predictor",
                "Optimizer",
                "Safety",
                "Red-Team",
            ],
        },
    }


if __name__ == "__main__":
    print(
        "M4 module loaded. Supply M3 simulation_report "
        "to obtain a decision."
    )