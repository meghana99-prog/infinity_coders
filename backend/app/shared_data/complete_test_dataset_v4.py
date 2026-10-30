
"""CHRONOS-X Universal Dataset V4.

V3 is preserved verbatim in data/v3_baseline.py. V4 deep-copies that baseline
and adds shared, linked structures for all eight responsibilities.

All additions not explicitly present in V3 are labelled synthetic test data.
This is a hackathon dataset, not validated industrial data. Never use eval().
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any
from .data.v3_baseline import get_complete_dataset as get_v3_baseline

SYNTHETIC = "SYNTHETIC_TEST_DATA"

def meta(note: str) -> dict:
    return {"data_origin": SYNTHETIC, "validation_status": "NOT_INDUSTRIALLY_VALIDATED", "note": note}

def cond(field: str, operator: str, value: Any) -> dict:
    return {"field": field, "operator": operator, "expected_value": value}

def _variants():
    return {
        "BASELINE_THERMAL_EVENT": {"overrides": {}, "goal": "Evaluate the unchanged V3 thermal incident."},
        "COOLING_FAILURE": {"overrides": {"current_state.backup_cooling_available": False}, "goal": "Test backup cooling unavailable."},
        "POWER_FAILURE": {"overrides": {"resource_inventory.current_availability.power": 0}, "goal": "Test resource unavailability."},
        "PRESSURE_INSTABILITY": {"overrides": {}, "flags": {"pressure_instability": True, "pressure_model_available": False}, "goal": "Test safe handling of unknown pressure dynamics."},
        "CYBER_INTRUSION": {"overrides": {}, "flags": {"network_intrusion_suspected": True}, "goal": "Test network alert investigation; suspicion is not confirmation."},
        "CASCADING_FAILURE": {"overrides": {"current_state.backup_cooling_available": False, "resource_inventory.current_availability.power": 0}, "goal": "Test simultaneous constraints and abstention."},
        "SENSOR_MANIPULATION": {"overrides": {}, "flags": {"sensor_manipulation": True}, "goal": "Test event trust and adversarial detection."},
    }

def validate_dataset(d: dict) -> dict:
    errors, warnings = [], []
    required = [
        "incident", "event_ledger", "temporal_model", "sensor_registry",
        "system_topology", "state_history", "causal_relationships",
        "action_models", "resource_inventory", "safety_constraints",
        "counterfactual_scenarios", "simulation_config", "attack_scenarios",
        "agent_registry", "decision_history", "ground_truth",
        "scenario_variants", "responsibility_contracts", "shared_data_index"
    ]
    for key in required:
        if key not in d: errors.append(f"Missing section: {key}")
    if len(d.get("event_ledger", {}).get("records", [])) != 8:
        errors.append("Expected 8 received records from preserved V3 baseline.")
    ids = [r.get("record_id") for r in d.get("event_ledger", {}).get("records", [])]
    if len(ids) != len(set(ids)): errors.append("Ledger record_id values are not unique.")
    if len(d.get("agent_registry", [])) != 8: errors.append("Expected eight agent contracts.")
    shutdown = d.get("action_models", {}).get("SHUTDOWN_REACTOR", {})
    if not any(x.get("field") == "shutdown_permission" and x.get("expected_value") is True
               for x in shutdown.get("preconditions", [])):
        errors.append("Shutdown must require explicit permission.")
    for action, model in d.get("action_models", {}).items():
        for p in model.get("preconditions", []):
            if p.get("operator") not in {"==", "!=", ">", ">=", "<", "<="}:
                errors.append(f"Unsupported operator in {action}.")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors,
            "warnings": warnings, "checks": ["required sections", "record count",
            "unique record IDs", "eight agents", "shutdown permission", "safe operators"]}

def get_universal_dataset() -> dict:
    d = deepcopy(get_v3_baseline())  # V3 source is not mutated.
    d["dataset_metadata"] = {
        "dataset_name": "CHRONOS-X Universal Dataset", "version": "4.0.0",
        "baseline_version": "V3", "status": "SYNTHETIC_HACKATHON_BASELINE",
        "preservation": "All original V3 sections and values are retained.",
        "snapshot_rule": "A record is visible only when arrival_time <= simulation_snapshot_time; then order by event_time.",
        **meta("Common source of truth for all eight responsibilities.")
    }

    records = []
    for i, e in enumerate(d["temporal_events"], 1):
        r = deepcopy(e); r.update(record_id=f"REC-TEMP-{i:03}", record_class="TEMPORAL_EVENT",
            deduplication_key=f'{e["source"]}|{e["event_id"]}|{e["event_time"]}|{e["event_type"]}')
        records.append(r)
    for i, e in enumerate(d["manipulated_events"], 1):
        r = deepcopy(e); r.update(record_id=f"REC-MANIP-{i:03}", record_class="MANIPULATED_EVENT_CANDIDATE",
            deduplication_key=f'{e["source"]}|{e["event_id"]}|{e["event_time"]}|{e["event_type"]}')
        records.append(r)
    d["event_ledger"] = {"records": records, "ordering": ["event_time", "arrival_time", "record_id"],
        "duplicate_policy": "Retain duplicate arrivals for audit; mark duplicate groups.",
        "snapshot_policy": "Filter on arrival_time before reconstructing event-time order.",
        **meta("Derived without deleting or rewriting V3 event records.")}

    d["temporal_model"] = {
        "event_time": "Claimed occurrence time", "arrival_time": "Platform receipt time",
        "snapshot_time": "Latest data visible to a run", "timezone": None, "date": None,
        "clock_offset_ms": None, "late_event_policy": "Append and replay affected event-time window.",
        "clock_policy": "Unknown clock offsets must not be inferred.",
        **meta("V3 does not supply timezone, calendar date or clock-offset measurements.")}

    d["sensor_registry"] = {
        "REACTOR_SENSOR_14": {"registered": True, "component_id": "COOLING_LOOP_02",
            "authentication_status": "FAILED", "calibration_status": "UNKNOWN",
            "expected_event_types": ["TEMPERATURE_READING"], **meta("Synthetic registry metadata; V3 invalid signatures preserved.")},
        "PRESSURE_SENSOR_07": {"registered": True, "component_id": "COOLING_LOOP_02",
            "authentication_status": "PASSED", "calibration_status": "UNKNOWN",
            "expected_event_types": ["PRESSURE_READING"], **meta("Pressure unit and calibration remain unknown.")},
        "SECURITY_SENSOR": {"registered": True, "component_id": "NETWORK_01",
            "authentication_status": "FAILED", "calibration_status": "NOT_APPLICABLE",
            "expected_event_types": ["NETWORK_ALERT"], **meta("Synthetic registry entry.")},
        "UNKNOWN_SENSOR": {"registered": False, "component_id": None,
            "authentication_status": "FAILED", "calibration_status": "UNKNOWN",
            "expected_event_types": [], **meta("Retained as unknown-source test case.")}}

    d["system_topology"] = {
        "components": [
            {"component_id": "REACTOR_01", "type": "PROCESS_UNIT"},
            {"component_id": "COOLING_LOOP_02", "type": "COOLING_SYSTEM"},
            {"component_id": "COOLING_CONTROLLER", "type": "CONTROLLER"},
            {"component_id": "BACKUP_COOLING_01", "type": "BACKUP_SYSTEM"},
            {"component_id": "NETWORK_01", "type": "NETWORK_SEGMENT"},
            {"component_id": "PRESSURE_SENSOR_07", "type": "SENSOR"}],
        "relationships": [
            {"source": "COOLING_CONTROLLER", "target": "COOLING_LOOP_02", "relationship": "CONTROLS"},
            {"source": "COOLING_LOOP_02", "target": "REACTOR_01", "relationship": "INFLUENCES_THERMAL_STATE"},
            {"source": "BACKUP_COOLING_01", "target": "COOLING_LOOP_02", "relationship": "CAN_SUPPORT"},
            {"source": "NETWORK_01", "target": "COOLING_CONTROLLER", "relationship": "COMMUNICATES_WITH"},
            {"source": "PRESSURE_SENSOR_07", "target": "COOLING_LOOP_02", "relationship": "OBSERVES"}],
        **meta("Illustrative topology only; not a verified engineering diagram.")}

    d["state_history"] = {
        "observations": [
            {"state_id": "STATE-OBS-001", "timestamp": "07:59:45", "field": "temperature",
             "value": 94.1, "unit": None, "source_event": "EVT-005", "state_type": "OBSERVED_EVENT_VALUE"},
            {"state_id": "STATE-EST-001", "timestamp": "08:02:18", "field": "temperature",
             "value": 94.3, "unit": None, "source": "STATE_ESTIMATOR", "state_type": "ESTIMATED",
             "confidence": 0.85, "confidence_type": "SYNTHETIC_TEST_VALUE"},
            {"state_id": "STATE-OBS-002", "timestamp": "07:58:20", "field": "pressure",
             "value": 4.7, "unit": None, "source_event": "EVT-004", "state_type": "OBSERVED_EVENT_VALUE"}],
        "state_variables": [
            {"field": "temperature", "unit": None, "threshold": 95,
             "threshold_meaning": "V3 monitoring-action restriction only"},
            {"field": "pressure", "unit": None, "threshold": None},
            {"field": "backup_cooling_available"},
            {"field": "shutdown_permission"}, {"field": "critical_comms_required"}],
        **meta("Sparse history; no missing pressure units, limits or dynamics invented.")}

    d["causal_relationships"] = [
        {"id": "CAUSE-001", "cause": "COOLING_CONTROLLER_COMPROMISE",
         "effect": "COOLING_LOOP_02_THERMAL_RESPONSE", "status": "UNVERIFIED_HYPOTHESIS",
         "evidence": ["EVT-001", "EVT-002", "EVT-005"], "confidence": .71,
         "confidence_type": "SYNTHETIC_TEST_VALUE"},
        {"id": "CAUSE-002", "cause": "SENSOR_CORRUPTION",
         "effect": "TEMPERATURE_READING_RELIABILITY", "status": "UNVERIFIED_HYPOTHESIS",
         "evidence": ["EVT-001", "EVT-005"], "confidence": .58,
         "confidence_type": "SYNTHETIC_TEST_VALUE"},
        {"id": "CAUSE-003", "cause": "CYBER_INTRUSION", "effect": "NETWORK_01_TRAFFIC",
         "status": "UNVERIFIED_HYPOTHESIS", "evidence": ["EVT-003"], "confidence": .49,
         "confidence_type": "SYNTHETIC_TEST_VALUE"}]
    for x in d["causal_relationships"]:
        x.update(meta("Mapped from V3 hypotheses; not validated causal effects."))

    # V3's quantitative action effects are preserved and normalized into action_models.
    # The distributions are illustrative synthetic parameters, not equipment specifications.
    d["action_models"] = deepcopy(d["available_actions"])
    d["action_models"]["CONTINUE_MONITORING"].update({
        "preconditions": [], "can_run_parallel": True, "action_cost": 0,
        "effect_timing": "IMMEDIATE_PER_SIMULATION_STEP",
        "effects": {"temperature_change": {"distribution": "NORMAL", "mean": .4, "std_dev": .25,
            **meta("Illustrative drift per simulation step; step length must be configured.")}}})
    d["action_models"]["ACTIVATE_BACKUP_COOLING"].update({
        "preconditions": [cond("backup_cooling_available", "==", True)],
        "can_run_parallel": False, "action_cost": 35,
        "effect_timing": {"mode": "DELAYED", "delay_minutes": {"min": 12, "max": 18},
            "application": "Apply sampled effect after delay; no ramp curve supplied."},
        "effects": {"temperature_change": {"distribution": "NORMAL", "mean": -3.2, "std_dev": .9,
            **meta("Illustrative cooling effect from V3.")}}})
    d["action_models"]["ISOLATE_NETWORK"].update({
        "preconditions": [cond("critical_comms_required", "==", False)],
        "can_run_parallel": True, "action_cost": 10,
        "effect_timing": {"mode": "DELAYED", "delay_minutes": {"min": 1, "max": 3}},
        "effects": {"temperature_change": {"distribution": "NORMAL", "mean": .1, "std_dev": .3,
            **meta("Illustrative negligible direct thermal effect.")},
            "network_external_command_access": {"effect": "REDUCED"}}})
    d["action_models"]["SHUTDOWN_REACTOR"].update({
        "preconditions": [cond("shutdown_permission", "==", True)],
        "can_run_parallel": False, "action_cost": 100,
        "effect_timing": {"mode": "DELAYED", "delay_minutes": {"min": 20, "max": 30}},
        "effects": {"temperature_change": {"distribution": "NORMAL", "mean": -8.5, "std_dev": 1.5,
            **meta("Illustrative shutdown effect from V3.")}}})
    for a in d["action_models"].values():
        a["failure_effect"] = "NO_BENEFIT_ON_FAILURE"
        a.update(meta("Synthetic action model; not validated equipment performance."))
    d["available_actions"] = deepcopy(d["action_models"])

    d["resource_inventory"] = {
        "capacities": {"power": {"capacity": 1, "unit": "synthetic token"},
                       "operators": {"capacity": 2, "unit": "synthetic slots"},
                       "authorization": {"capacity": 0, "unit": "permission tokens"},
                       "network_control_channel": {"capacity": 1, "unit": "synthetic channel"}},
        "current_availability": {"power": 1, "operators": 2,
                                 "authorization": 0, "network_control_channel": 1},
        "policy": "Do not exceed capacity; recheck before each action.",
        **meta("All resource capacities are synthetic tokens, not real quantities.")}

    d["safety_constraints"] = {
        "rules": deepcopy(d["safety_rules"]),
        "sequence_constraints": [{"constraint_id": "SEQ-001",
            "action": "SHUTDOWN_REACTOR",
            "condition": cond("shutdown_permission", "==", True), "effect": "REJECT"}],
        "validation_policy": ["Check structured preconditions.",
            "Independently apply safety rules before execution.",
            "Revalidate when state changes.", "Reject unknown operators; never eval strings.",
            "Simulation benefit cannot override safety rejection."],
        **meta("Prototype policy representation, not an operational safety case.")}

    d["counterfactual_scenarios"] = [
        {"id": "CF-001", "question": "What if backup cooling were activated at snapshot time?",
         "intervention": {"action": "ACTIVATE_BACKUP_COOLING"},
         "metrics": ["temperature", "action_cost", "threshold_exceedance"], "horizon_minutes": 30},
        {"id": "CF-002", "question": "What if network isolation were performed?",
         "intervention": {"action": "ISOLATE_NETWORK"},
         "metrics": ["network_external_command_access", "action_cost"], "horizon_minutes": 30},
        {"id": "CF-003", "question": "What if monitoring continued?",
         "intervention": {"action": "CONTINUE_MONITORING"},
         "metrics": ["temperature", "threshold_exceedance", "action_cost"], "horizon_minutes": 30}]
    for x in d["counterfactual_scenarios"]:
        x.update(meta("Modelled alternative, not an observed outcome."))

    d["simulation_config"] = {
        "iterations": 10000, "random_seed": 42, "confidence_level": .95,
        "evaluation_horizon_minutes": 90, "time_step_minutes": 1,
        "metrics": ["temperature_trajectory", "temperature_threshold_exceedance",
                    "action_cost", "resource_usage", "action_failure", "deadline_completion"],
        "warning": "Threshold exceedance is not validated catastrophe probability.",
        **meta("Reproducibility defaults for prototype simulation.")}

    d["attack_scenarios"] = [
        {"attack_id": "ATK-001", "type": "SENSOR_SPOOFING", "target": "REACTOR_SENSOR_14",
         "event_ids": ["EVT-001", "EVT-005"], "indicators": ["INVALID_SIGNATURE", "LOW_TRUST"],
         "label": "SUSPICIOUS_SYNTHETIC_CASE", "severity": "HIGH"},
        {"attack_id": "ATK-002", "type": "FALSE_MAINTENANCE_REPORT", "target": "COOLING_LOOP_02",
         "event_ids": ["FAKE-001"], "indicators": ["INVALID_SIGNATURE", "LOW_TRUST", "CONFLICTING_STATUS"],
         "label": "MALICIOUS_SYNTHETIC_CASE", "severity": "HIGH"},
        {"attack_id": "ATK-003", "type": "UNKNOWN_SENSOR_INJECTION", "target": "UNKNOWN_SENSOR",
         "event_ids": ["FAKE-002"], "indicators": ["UNREGISTERED_SOURCE", "INVALID_SIGNATURE"],
         "label": "MALICIOUS_SYNTHETIC_CASE", "severity": "HIGH"},
        {"attack_id": "ATK-004", "type": "DUPLICATE_OR_REPLAY", "target": "EVT-001",
         "event_ids": ["EVT-001"], "indicators": ["REPEATED_EVENT_ID", "MATCHING_PAYLOAD"],
         "label": "DUPLICATE_RECORD", "severity": "MEDIUM"}]
    for x in d["attack_scenarios"]:
        x.update(meta("Synthetic test case; low trust alone does not prove malicious intent."))

    d["agent_registry"] = [
        ("AGENT-01", "Temporal Agent", "TEMPORAL_RECONSTRUCTION", ["event_ledger", "temporal_model"], [], "RECONSTRUCTED_TIMELINE", "ANALYSIS_ONLY"),
        ("AGENT-02", "Trust Agent", "TRUST_VALIDATION", ["event_ledger", "sensor_registry"], ["AGENT-01"], "VALIDATED_EVENT_ASSESSMENT", "ANALYSIS_ONLY"),
        ("AGENT-03", "Causal Agent", "CAUSAL_INVESTIGATION", ["event_ledger", "state_history", "causal_relationships", "system_topology"], ["AGENT-01", "AGENT-02"], "CAUSAL_HYPOTHESES", "ANALYSIS_ONLY"),
        ("AGENT-04", "Counterfactual Agent", "COUNTERFACTUAL_ANALYSIS", ["causal_relationships", "counterfactual_scenarios", "action_models"], ["AGENT-03"], "COUNTERFACTUAL_COMPARISON", "ANALYSIS_ONLY"),
        ("AGENT-05", "Simulation Agent", "STOCHASTIC_SIMULATION", ["state_history", "action_models", "resource_inventory", "simulation_config"], ["AGENT-01", "AGENT-03"], "SIMULATION_RESULTS", "ANALYSIS_ONLY"),
        ("AGENT-06", "Safety Agent", "SAFETY_VERIFICATION", ["safety_constraints", "action_models", "resource_inventory"], [], "SAFETY_DECISION", "INDEPENDENT_VETO"),
        ("AGENT-07", "Adversarial Agent", "ADVERSARIAL_DETECTION", ["event_ledger", "sensor_registry", "attack_scenarios"], ["AGENT-01", "AGENT-02"], "THREAT_ASSESSMENT", "ANALYSIS_ONLY"),
        ("AGENT-08", "Coordination Agent", "MULTI_AGENT_COORDINATION", ["agent_registry", "decision_history"], ["AGENT-03", "AGENT-04", "AGENT-05", "AGENT-06", "AGENT-07"], "COORDINATED_DECISION_RECORD", "COORDINATION_ONLY")]
    d["agent_registry"] = [{"agent_id": a, "name": n, "responsibility": r,
        "input_refs": ins, "depends_on": deps, "output_type": out, "authority": auth,
        **meta("Software coordination contract; no autonomous equipment authority.")}
        for a, n, r, ins, deps, out, auth in d["agent_registry"]]

    d["decision_history"] = {"records": [],
        "record_schema": ["decision_id", "snapshot_time", "input_refs", "hypotheses_considered",
            "candidate_actions", "safety_result_refs", "simulation_result_ref",
            "selected_plan", "abstain", "reason", "created_by"],
        "audit_policy": "Append-only; never overwrite prior decisions.",
        **meta("Runtime log starts empty; no fabricated decisions.")}

    d["ground_truth"] = {
        "event_labels": [
            {"event_id": "FAKE-001", "label": "MANIPULATED", "basis": "V3 is_manipulated=True"},
            {"event_id": "FAKE-002", "label": "MANIPULATED", "basis": "V3 is_manipulated=True"},
            {"event_id": "EVT-001", "label": "DUPLICATE_GROUP", "basis": "Repeated event ID and matching payload"}],
        "hypothesis_labels": [{"hypothesis": h, "label": "UNVERIFIED"}
            for h in d["causal_hypotheses"]],
        "warning": "Causal hypotheses are not ground truth; labels only use explicit V3 annotations.",
        **meta("Limited to explicit synthetic annotations and duplicate structure.")}

    d["scenario_variants"] = _variants()
    d["responsibility_contracts"] = {
        "01_TEMPORAL_RECONSTRUCTION": {"inputs": ["event_ledger", "temporal_model"], "outputs": ["ordered_events", "duplicate_groups", "late_events", "snapshot_state"]},
        "02_TRUST_VALIDATION": {"inputs": ["event_ledger", "sensor_registry"], "outputs": ["trust_assessments", "signature_checks", "source_anomalies"]},
        "03_CAUSAL_INVESTIGATION": {"inputs": ["event_ledger", "state_history", "causal_relationships", "system_topology"], "outputs": ["ranked_hypotheses", "supporting_evidence", "contradictory_evidence", "unknowns"]},
        "04_COUNTERFACTUAL_ANALYSIS": {"inputs": ["causal_relationships", "counterfactual_scenarios", "action_models"], "outputs": ["alternative_outcomes", "assumptions", "uncertainty_ranges"]},
        "05_STOCHASTIC_SIMULATION": {"inputs": ["state_history", "action_models", "resource_inventory", "simulation_config"], "outputs": ["trajectories", "costs", "resource_usage", "threshold_exceedance", "failure_rates"]},
        "06_SAFETY_VERIFICATION": {"inputs": ["safety_constraints", "action_models", "resource_inventory"], "outputs": ["approved_actions", "rejected_actions", "rule_violations"]},
        "07_ADVERSARIAL_DETECTION": {"inputs": ["event_ledger", "sensor_registry", "attack_scenarios"], "outputs": ["anomaly_flags", "attack_indicators", "evidence_refs"]},
        "08_MULTI_AGENT_COORDINATION": {"inputs": ["agent_registry", "decision_history", "all_agent_outputs"], "outputs": ["dependency_status", "conflict_report", "coordinated_decision"]}}
    d["shared_data_index"] = {
        "incident": "incident", "events": "event_ledger.records", "sensors": "sensor_registry",
        "topology": "system_topology", "state": "current_state", "state_history": "state_history",
        "causes": "causal_hypotheses", "causal_graph": "causal_relationships",
        "actions": "action_models", "resources": "resource_inventory", "safety": "safety_constraints",
        "counterfactuals": "counterfactual_scenarios", "simulation": "simulation_config",
        "attacks": "attack_scenarios", "agents": "agent_registry", "audit": "decision_history",
        "evaluation": "ground_truth", "variants": "scenario_variants"}
    d["dataset_validation"] = validate_dataset(d)
    return d

def get_scenario_dataset(name: str) -> dict:
    d = get_universal_dataset()
    if name not in d["scenario_variants"]:
        raise KeyError(f"Unknown scenario {name}; choose {list(d['scenario_variants'])}")
    variant = d["scenario_variants"][name]
    for path, value in variant["overrides"].items():
        parts, target = path.split("."), d
        for p in parts[:-1]: target = target[p]
        target[parts[-1]] = deepcopy(value)
    if "flags" in variant: d["scenario_flags"] = deepcopy(variant["flags"])
    d["active_scenario"] = {"name": name, "goal": variant["goal"], **meta("Synthetic overlay on V3 baseline.")}
    d["dataset_validation"] = validate_dataset(d)
    return d

def get_responsibility_input(dataset: dict, responsibility_id: str) -> dict:
    key = responsibility_id.upper()
    if key not in dataset["responsibility_contracts"]:
        raise KeyError(f"Unknown responsibility: {responsibility_id}")
    return {section: deepcopy(dataset[section])
            for section in dataset["responsibility_contracts"][key]["inputs"]
            if section != "all_agent_outputs"}

def main():
    d = get_universal_dataset()
    print("CHRONOS-X Universal Dataset V4")
    print("Scenario:", d["incident"]["scenario_id"])
    print("Ledger records:", len(d["event_ledger"]["records"]))
    print("Agents:", len(d["agent_registry"]))
    print("Scenario variants:", len(d["scenario_variants"]))
    print("Validation:", d["dataset_validation"]["status"])
    for name in d["scenario_variants"]: print(" -", name)

if __name__ == "__main__":
    main()
