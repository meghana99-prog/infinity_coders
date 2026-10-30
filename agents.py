"""
M4 - Multi-Agent Adversarial Decision System
CHRONOS-X / Industrial Crisis Decision Support

Drop-in replacement for the existing root-level agents.py.

Safety boundary:
- M4 produces recommendations for human review only.
- It never controls equipment or executes interventions.
- Missing/unknown safety constraints cause ABSTAIN.
- M7 verification is an optional injected callable. Do not claim M7
  integration until the real M7 public API is connected and tested.
- M5 resource data is accepted through a normalized resource_status
  contract. Do not claim native M5 integration until its real API is mapped.

Existing public function names are retained:
  investigator_agent(...)
  predictor_agent(...)
  optimizer_agent(...)
  safety_agent(...)
  red_team_agent(...)
  run_multi_agent_system(...)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Optional
import math
import uuid


ACTION_CATALOG = {
    "CONTINUE_MONITORING",
    "ACTIVATE_BACKUP_COOLING",
    "ISOLATE_NETWORK",
    "SHUTDOWN_REACTOR",
}

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

# These are required only for actions that need the corresponding resource.
ACTION_RESOURCE_REQUIREMENTS = {
    "ACTIVATE_BACKUP_COOLING": ("backup_cooling_available",),
    "ISOLATE_NETWORK": ("network_isolation_available",),
    "SHUTDOWN_REACTOR": ("shutdown_permission",),
    "CONTINUE_MONITORING": (),
}


def _is_number(value: Any) -> bool:
    """True only for finite int/float values; bool is deliberately rejected."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _safe_string(value: Any, max_length: int = 200) -> Optional[str]:
    if not isinstance(value, (str, int, float)):
        return None
    result = str(value).strip()
    if not result or len(result) > max_length:
        return None
    return result


def normalize_timeline(timeline: list[dict]) -> list[dict]:
    """
    Convert M1 nested or legacy flat event records into a stable M4 shape.

    M1 nested example:
      {"event": {"event_id": "E1", "event_type": "TEMP"},
       "event_time": "...", "trust_score": 0.8}

    Metadata from the outer record is retained. Nested event fields take
    precedence for event identity/type; outer trust/time metadata is kept.
    Invalid records are skipped rather than fabricated.
    """
    if not isinstance(timeline, list):
        raise TypeError("timeline must be a list")

    normalized = []
    seen = set()

    for record in timeline:
        if not isinstance(record, dict):
            continue

        nested = record.get("event")
        if isinstance(nested, dict):
            event = dict(record)
            event.update(nested)
        else:
            event = dict(record)

        event_id = _safe_string(event.get("event_id"))
        event_type = _safe_string(event.get("event_type"))

        if event_id is None or event_type is None:
            continue

        if event_id in seen:
            # Duplicate IDs are ambiguous evidence; keep the first occurrence.
            continue
        seen.add(event_id)

        event["event_id"] = event_id
        event["event_type"] = event_type.upper()

        trust = event.get("trust_score")
        if trust is not None:
            event["trust_score"] = (
                float(trust) if _is_number(trust) and 0 <= trust <= 1 else None
            )

        normalized.append(event)

    return normalized


def _valid_event_ids(timeline: list[dict]) -> list[str]:
    return [
        event["event_id"]
        for event in normalize_timeline(timeline)
    ]


def _message(
    agent: str,
    recommendation: Optional[str],
    evidence_ids: list[str],
    confidence: float,
    rationale: list[str],
    status: str = "READY",
) -> dict:
    confidence_value = (
        float(confidence) if _is_number(confidence) else 0.0
    )
    return {
        "agent": agent,
        "recommendation": recommendation,
        "evidence_ids": sorted(set(str(x) for x in evidence_ids)),
        # This is an agent confidence score, NOT a safety probability.
        "confidence": round(max(0.0, min(1.0, confidence_value)), 3),
        "rationale": list(rationale),
        "status": status,
    }


def _extract_m2_hypotheses(causal_result: Any) -> list[dict]:
    """Read common M2 hypothesis containers without assuming one schema."""
    if not isinstance(causal_result, dict):
        return []

    candidates = []
    for key in ("ranked_causes", "causal_hypotheses", "hypotheses", "causes"):
        value = causal_result.get(key)
        if isinstance(value, list):
            candidates.extend(value)

    investigation = causal_result.get("investigation")
    if isinstance(investigation, dict):
        value = investigation.get("ranked_causes")
        if isinstance(value, list):
            candidates.extend(value)

    output = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        label = (
            item.get("cause")
            or item.get("variable")
            or item.get("hypothesis")
            or item.get("name")
        )
        if not isinstance(label, str) or not label.strip():
            continue
        refs = item.get("evidence_ids", item.get("event_ids", []))
        if not isinstance(refs, list):
            refs = []
        output.append({
            "cause": label.strip(),
            "evidence_ids": [
                str(x) for x in refs if isinstance(x, (str, int))
            ],
            "source": "M2",
        })
    return output


def investigator_agent(
    timeline: list[dict],
    causal_result: Optional[dict] = None,
) -> dict:
    """Build evidence-linked hypotheses; never present correlation as proof."""
    events = normalize_timeline(timeline)
    causes: dict[str, set[str]] = {}

    for event in events:
        cause = CAUSE_RULES.get(event["event_type"])
        if cause:
            causes.setdefault(cause, set()).add(event["event_id"])

    hypotheses = [
        {
            "cause": cause,
            "evidence_ids": sorted(refs),
            "source": "M4_EVENT_RULE",
            "interpretation": "hypothesis_not_proven_causation",
        }
        for cause, refs in sorted(causes.items())
    ]

    hypotheses.extend(_extract_m2_hypotheses(causal_result))

    known = set(_valid_event_ids(events))
    for hypothesis in hypotheses:
        hypothesis["evidence_ids"] = sorted({
            ref for ref in hypothesis["evidence_ids"] if ref in known
        })

    all_refs = sorted({
        ref for item in hypotheses for ref in item["evidence_ids"]
    })

    return {
        **_message(
            "Investigator",
            "INVESTIGATE_CAUSAL_HYPOTHESES" if hypotheses else None,
            all_refs,
            0.65 if hypotheses else 0.0,
            [
                "Outputs are hypotheses, not proven causal effects.",
                "Every retained evidence reference must exist in the normalized M1 timeline.",
            ],
            "READY" if hypotheses else "INSUFFICIENT_EVIDENCE",
        ),
        "ranked_causes": hypotheses,
    }


def _extract_m3_comparisons(simulation_report: Any) -> list[dict]:
    if not isinstance(simulation_report, dict):
        return []
    comparisons = simulation_report.get("intervention_comparison")
    if not isinstance(comparisons, list):
        return []
    return [x for x in comparisons if isinstance(x, dict)]


def predictor_agent(
    current_state: dict,
    simulation_report: Optional[dict] = None,
) -> dict:
    """
    Read candidate metrics from M3 only. No synthetic risk estimates,
    no assumed intervention benefit, and no fallback prediction.
    """
    if not isinstance(current_state, dict):
        raise TypeError("current_state must be a dictionary")

    predictions = {}
    invalid_rows = []

    for index, item in enumerate(_extract_m3_comparisons(simulation_report)):
        raw_action = item.get("intervention_id", item.get("action"))
        action = M3_ACTION_MAP.get(raw_action, raw_action)

        risk = item.get("catastrophe_probability")
        if risk is None:
            risk = item.get("catastrophe_risk")

        if action not in ACTION_CATALOG:
            invalid_rows.append({"row": index, "reason": "unknown_action"})
            continue
        if not _is_number(risk) or not 0 <= float(risk) <= 1:
            invalid_rows.append({"row": index, "reason": "invalid_risk"})
            continue

        mean_loss = item.get("mean_loss")
        cvar = item.get("cvar", item.get("cvar_loss"))

        predictions[action] = {
            "risk": float(risk),
            "mean_loss": float(mean_loss) if _is_number(mean_loss) else None,
            "cvar": float(cvar) if _is_number(cvar) else None,
            "source": "M3_SIMULATION",
            "scenario_count": item.get("scenario_count"),
            "scenario_set_id": item.get("scenario_set_id"),
        }

    if not predictions:
        return {
            **_message(
                "Predictor",
                None,
                [],
                0.0,
                [
                    "No valid M3 intervention comparison was supplied.",
                    "M4 will not invent risk values or risk reductions.",
                ],
                "INSUFFICIENT_SIMULATION_EVIDENCE",
            ),
            "predictions": {},
            "invalid_rows": invalid_rows,
        }

    ranked = sorted(
        predictions,
        key=lambda action: (
            predictions[action]["risk"],
            predictions[action]["cvar"]
            if predictions[action]["cvar"] is not None else math.inf,
            predictions[action]["mean_loss"]
            if predictions[action]["mean_loss"] is not None else math.inf,
        ),
    )

    return {
        **_message(
            "Predictor",
            ranked[0],
            [],
            0.70,
            ["All risk metrics were read from the supplied M3 report."],
        ),
        "predictions": predictions,
        "ranked_by_simulated_risk": ranked,
        "invalid_rows": invalid_rows,
    }


def _resource_value(resource_status: Any, key: str) -> Optional[bool]:
    """
    Normalized M5 adapter contract:
      {"backup_cooling_available": True/False, ...}
    Missing or malformed values return None (unknown).
    """
    if not isinstance(resource_status, dict):
        return None
    value = resource_status.get(key)
    return value if isinstance(value, bool) else None


def optimizer_agent(
    predictions: dict,
    current_state: Optional[dict] = None,
    resource_status: Optional[dict] = None,
) -> dict:
    """
    Rank simulated candidates. Resource-dependent candidates are rejected
    unless the required resource/permission is explicitly True.
    """
    if not isinstance(predictions, dict):
        raise TypeError("predictions must be a dictionary")

    state = current_state if isinstance(current_state, dict) else {}
    resources = resource_status if isinstance(resource_status, dict) else {}
    rejected = {}
    feasible = {}

    for action, metrics in predictions.items():
        if action not in ACTION_CATALOG or not isinstance(metrics, dict):
            rejected[str(action)] = "Unknown action or malformed metrics"
            continue

        risk = metrics.get("risk")
        if not _is_number(risk) or not 0 <= float(risk) <= 1:
            rejected[action] = "Missing or invalid simulated risk"
            continue

        missing = []
        unavailable = []
        for key in ACTION_RESOURCE_REQUIREMENTS[action]:
            # Prefer explicit M5 resource snapshot, then current_state.
            value = _resource_value(resources, key)
            if value is None:
                value = _resource_value(state, key)
            if value is None:
                missing.append(key)
            elif value is False:
                unavailable.append(key)

        if unavailable:
            rejected[action] = "Required resource unavailable: " + ", ".join(unavailable)
            continue
        if missing:
            rejected[action] = "Required resource status unknown: " + ", ".join(missing)
            continue

        feasible[action] = metrics

    if not feasible:
        return {
            **_message(
                "Optimizer",
                None,
                [],
                0.0,
                ["No candidate passed the simulation and resource checks."],
                "NO_FEASIBLE_CANDIDATE",
            ),
            "ranked_actions": [],
            "rejected_actions": rejected,
        }

    ranked = sorted(
        feasible,
        key=lambda action: (
            float(feasible[action]["risk"]),
            feasible[action].get("cvar")
            if _is_number(feasible[action].get("cvar")) else math.inf,
            feasible[action].get("mean_loss")
            if _is_number(feasible[action].get("mean_loss")) else math.inf,
        ),
    )

    return {
        **_message(
            "Optimizer",
            ranked[0],
            [],
            0.70,
            [
                "Ranked by catastrophe probability, then CVaR, then mean loss.",
                "This is a bounded candidate ranking, not a replacement for M5 optimization.",
            ],
        ),
        "ranked_actions": ranked,
        "rejected_actions": rejected,
    }


def safety_agent(
    recommended_action: Optional[str],
    current_state: dict,
    safety_constraints: Optional[dict] = None,
) -> dict:
    """
    Deterministic M4 pre-check only.

    safety_constraints must contain explicitly configured, approved rules.
    Example:
      {
        "approved": True,
        "limits": {"max_temperature": 88.0},
        "required_flags": {"backup_cooling_available": True}
      }

    Do not copy illustrative dataset values into this configuration.
    A real limit must come from an authorized, validated source.
    """
    if not isinstance(current_state, dict):
        raise TypeError("current_state must be a dictionary")

    constraints = safety_constraints
    if constraints is None:
        constraints = current_state.get("safety_constraints")

    checks = []

    checks.append({
        "constraint": "action_allowlist",
        "status": "PASS" if recommended_action in ACTION_CATALOG else "FAIL",
    })

    if not isinstance(constraints, dict) or constraints.get("approved") is not True:
        checks.append({
            "constraint": "approved_safety_configuration",
            "status": "UNKNOWN",
            "detail": "No explicitly approved safety configuration supplied",
        })
    else:
        limits = constraints.get("limits", {})
        required_flags = constraints.get("required_flags", {})

        if not isinstance(limits, dict) or not isinstance(required_flags, dict):
            checks.append({
                "constraint": "safety_configuration_schema",
                "status": "FAIL",
            })
        else:
            for field, maximum in limits.items():
                observed = current_state.get(field)
                if not _is_number(maximum) or not _is_number(observed):
                    status = "UNKNOWN"
                else:
                    status = "FAIL" if float(observed) > float(maximum) else "PASS"
                checks.append({
                    "constraint": f"{field}_maximum",
                    "status": status,
                    "observed": observed if _is_number(observed) else None,
                    "configured_limit": maximum if _is_number(maximum) else None,
                })

            for field, required_value in required_flags.items():
                observed = current_state.get(field)
                status = (
                    "PASS" if observed is required_value
                    else "FAIL" if isinstance(observed, bool)
                    else "UNKNOWN"
                )
                checks.append({
                    "constraint": field,
                    "status": status,
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
            0.0,
            [
                "This is an M4 pre-check, not independent certification.",
                "M7 must independently verify the candidate before it can be considered for human review.",
            ],
            overall,
        ),
        "status": overall,
        "checked_action": recommended_action,
        "checks": checks,
        "execution_allowed": False,
        "requires_human_approval": True,
    }


def red_team_agent(
    timeline: list[dict],
    agent_messages: list[dict],
    safety_status: str,
    optimizer_result: Optional[dict] = None,
) -> dict:
    """Challenge invalid evidence references, malformed messages and conflicts."""
    events = normalize_timeline(timeline)
    known_ids = {event["event_id"] for event in events}
    warnings = []

    recommendations = {}
    for message in agent_messages:
        if not isinstance(message, dict):
            warnings.append("Malformed agent message")
            continue

        refs = message.get("evidence_ids", [])
        if not isinstance(refs, list):
            warnings.append(f"{message.get('agent', 'Unknown')}: malformed evidence list")
            refs = []

        unknown = [
            str(ref) for ref in refs
            if str(ref) not in known_ids
        ]
        if unknown:
            warnings.append(
                f"{message.get('agent', 'Unknown')}: unknown evidence references"
            )

        confidence = message.get("confidence", 0)
        if not _is_number(confidence) or not 0 <= float(confidence) <= 1:
            warnings.append(f"{message.get('agent', 'Unknown')}: invalid confidence value")

        if message.get("agent") in {"Predictor", "Optimizer"}:
            action = message.get("recommendation")
            if action:
                recommendations[message["agent"]] = action

    if len(set(recommendations.values())) > 1:
        warnings.append("Predictor and Optimizer disagree; adjudication required")

    if safety_status != "PASSED":
        warnings.append(f"M4 safety pre-check is {safety_status}")

    low_trust = [
        event["event_id"]
        for event in events
        if _is_number(event.get("trust_score"))
        and float(event["trust_score"]) < 0.35
    ]
    if len(low_trust) >= 2:
        warnings.append("Multiple low-trust events detected")

    return {
        **_message(
            "Red-Team",
            None,
            low_trust,
            0.0,
            warnings or ["No configured red-team challenge was triggered."],
            "CHALLENGE" if warnings else "CLEAR",
        ),
        "warnings": warnings,
        "challenge": bool(warnings),
        "low_trust_event_ids": low_trust,
    }


def _run_m7_verifier(
    verifier: Optional[Callable],
    action: Optional[str],
    context: dict,
) -> dict:
    """
    Adapter contract for the real M7 verifier.

    Inject a callable accepting (action, context) and returning a dict:
      {"status": "PASSED" | "FAILED" | "UNKNOWN",
       "checks": [...], "evidence_ids": [...]}

    This wrapper intentionally does not guess/import an unknown M7 API.
    """
    if verifier is None:
        return {
            "status": "UNKNOWN",
            "checks": [],
            "evidence_ids": [],
            "reason": "M7 verifier callable was not connected",
        }

    try:
        result = verifier(action, context)
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "checks": [],
            "evidence_ids": [],
            "reason": f"M7 verifier raised {type(exc).__name__}",
        }

    if not isinstance(result, dict):
        return {
            "status": "UNKNOWN",
            "checks": [],
            "evidence_ids": [],
            "reason": "M7 returned a malformed result",
        }

    status = result.get("status")
    if status not in {"PASSED", "FAILED", "UNKNOWN"}:
        status = "UNKNOWN"

    refs = result.get("evidence_ids", [])
    if not isinstance(refs, list):
        refs = []

    return {
        "status": status,
        "checks": result.get("checks", []) if isinstance(result.get("checks", []), list) else [],
        "evidence_ids": [str(x) for x in refs if isinstance(x, (str, int))],
        "reason": result.get("reason"),
    }


def run_multi_agent_system(
    timeline: list[dict],
    current_state: dict,
    simulation_report: Optional[dict] = None,
    causal_result: Optional[dict] = None,
    external_recommendations: Optional[list[dict]] = None,
    *,
    resource_status: Optional[dict] = None,
    safety_constraints: Optional[dict] = None,
    m7_verifier: Optional[Callable] = None,
) -> dict:
    """
    Run M4.

    Backward-compatible positional arguments are retained.
    New integrations are keyword-only:
      resource_status: normalized M5 resource snapshot
      safety_constraints: approved, validated safety limits/flags
      m7_verifier: callable adapter for the actual M7 public API

    Output is always advisory; execution_allowed is always False.
    """
    if not isinstance(current_state, dict):
        raise TypeError("current_state must be a dictionary")

    normalized_timeline = normalize_timeline(timeline)
    run_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    investigator = investigator_agent(normalized_timeline, causal_result)
    predictor = predictor_agent(current_state, simulation_report)
    optimizer = optimizer_agent(
        predictor["predictions"],
        current_state,
        resource_status=resource_status,
    )

    candidate = optimizer.get("recommendation")
    m4_safety = safety_agent(
        candidate,
        current_state,
        safety_constraints=safety_constraints,
    )

    # M7 is a mandatory independent gate for a non-empty candidate.
    m7_result = _run_m7_verifier(
        m7_verifier,
        candidate,
        {
            "run_id": run_id,
            "timeline": normalized_timeline,
            "current_state": current_state,
            "simulation_report": simulation_report,
            "resource_status": resource_status,
            "safety_constraints": safety_constraints,
        },
    )

    messages = [investigator, predictor, optimizer, m4_safety]

    known_ids = {event["event_id"] for event in normalized_timeline}
    rejected_external = []
    accepted_external = []

    for item in _as_list(external_recommendations):
        if not isinstance(item, dict):
            rejected_external.append({
                "status": "REJECTED",
                "reasons": ["Malformed external recommendation"],
            })
            continue

        action = item.get("recommendation", item.get("action"))
        refs = item.get("evidence_ids")
        reasons = []

        if action not in ACTION_CATALOG:
            reasons.append("Unknown or disallowed action")
        if not isinstance(refs, list) or not refs:
            reasons.append("Evidence references missing")
        elif any(str(ref) not in known_ids for ref in refs):
            reasons.append("Unknown evidence reference")
        if item.get("safety_status") in {"PASS", "PASSED"}:
            reasons.append("External self-declared safety PASS is not trusted")

        if reasons:
            rejected_external.append({
                "agent": _safe_string(item.get("agent")) or "ExternalAgent",
                "status": "REJECTED",
                "reasons": reasons,
            })
        else:
            accepted_external.append({
                "agent": _safe_string(item.get("agent")) or "ExternalAgent",
                "status": "UNVERIFIED_FOR_REVIEW",
                "action": action,
                "evidence_ids": [str(x) for x in refs],
            })

    red_team = red_team_agent(
        normalized_timeline,
        messages,
        m4_safety["status"],
        optimizer_result=optimizer,
    )

    # Fail-closed adjudication.
    if predictor["status"] != "READY":
        decision, reason = "ABSTAIN", "Valid M3 simulation evidence is missing"
    elif optimizer["status"] != "READY" or candidate is None:
        decision, reason = "ABSTAIN", "No feasible candidate is available"
    elif m4_safety["status"] != "PASSED":
        decision, reason = "ABSTAIN", "M4 safety pre-check failed or is unknown"
    elif m7_result["status"] != "PASSED":
        decision, reason = "ABSTAIN", "Independent M7 verification did not pass"
    elif red_team["challenge"]:
        decision, reason = "ABSTAIN", "Red-Team challenge requires adjudication"
    else:
        decision = candidate
        reason = "Candidate passed configured gates; human approval is still required"

    return {
        "module": "M4_Multi_Agent_Adversarial_Decision_System",
        "run_id": run_id,
        "created_at": created_at,
        "final_decision": decision,
        "reason": reason,
        "decision_status": (
            "ABSTAIN" if decision == "ABSTAIN"
            else "CANDIDATE_FOR_HUMAN_REVIEW"
        ),
        "execution_allowed": False,
        "requires_human_approval": True,
        "agent_messages": messages + [red_team],
        "investigator": investigator,
        "predictor": predictor,
        "optimizer": optimizer,
        "safety": m4_safety,
        "m7_verification": m7_result,
        "red_team": red_team,
        "accepted_external_agents": accepted_external,
        "rejected_external_agents": rejected_external,
        "audit": {
            "run_id": run_id,
            "created_at": created_at,
            "known_evidence_ids": sorted(known_ids),
            "m3_evidence_available": predictor["status"] == "READY",
            "m5_resource_snapshot_supplied": isinstance(resource_status, dict),
            "m7_verifier_connected": m7_verifier is not None,
            "m7_status": m7_result["status"],
            "human_approval_required": True,
            "physical_execution_permitted": False,
            "agent_roles": [
                "Investigator", "Predictor", "Optimizer", "Safety", "Red-Team"
            ],
        },
    }


if __name__ == "__main__":
    print("M4 loaded. Use run_multi_agent_system(...) with M3 evidence.")
