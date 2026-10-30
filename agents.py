# agents.py (Clean Version - No ==== lines)

def investigator_agent(timeline):
    print("Investigator is working...")

    causes = []
    for event in timeline:
        if event.get("event_type") == "TEMPERATURE_READING" and event.get("trust_score", 1) < 0.4:
            causes.append("sensor_corruption")
        if event.get("event_type") == "COOLING_STATUS":
            causes.append("cooling_controller_compromise")
        if event.get("event_type") == "NETWORK_ALERT":
            causes.append("cyber_intrusion")

    causes = list(set(causes))
    if not causes:
        causes = ["unknown_cause"]

    result = {
        "agent": "Investigator",
        "ranked_causes": causes,
        "confidence": 0.75,
        "message": f"Possible causes: {causes}"
    }
    print("→", result["message"])
    return result


def predictor_agent(current_state):
    print("Predictor is working...")

    base_risk = current_state.get("estimated_catastrophe_probability", 0.7)

    predictions = {
        "CONTINUE_MONITORING": {"risk": round(base_risk, 2)},
        "ACTIVATE_BACKUP_COOLING": {"risk": round(max(base_risk - 0.45, 0.10), 2)},
        "ISOLATE_NETWORK": {"risk": round(max(base_risk - 0.25, 0.20), 2)},
        "SHUTDOWN_REACTOR": {"risk": 0.05}
    }

    result = {
        "agent": "Predictor",
        "predictions": predictions,
        "confidence": 0.70,
        "message": "Risk calculated for all actions"
    }
    print("→", result["message"])
    return result


def optimizer_agent(predictions):
    print("Optimizer is working...")

    best_action = None
    best_risk = 999

    for action, data in predictions.items():
        if data["risk"] < best_risk:
            best_risk = data["risk"]
            best_action = action

    result = {
        "agent": "Optimizer",
        "recommended_action": best_action,
        "best_risk": best_risk,
        "confidence": 0.68,
        "message": f"Best action: {best_action}"
    }
    print("→", result["message"])
    return result


def safety_agent(recommended_action, current_state):
    print("Safety is checking...")

    violations = []
    status = "PASSED"

    if recommended_action == "SHUTDOWN_REACTOR" and current_state.get("shutdown_permission") is False:
        violations.append("Shutdown not allowed")
        status = "FAILED"

    if recommended_action == "ACTIVATE_BACKUP_COOLING" and current_state.get("backup_cooling_available") is False:
        violations.append("Backup cooling not available")
        status = "FAILED"

    if recommended_action == "CONTINUE_MONITORING" and current_state.get("temperature", 0) > 95:
        violations.append("Temperature too high for monitoring")
        status = "UNKNOWN"

    result = {
        "agent": "Safety",
        "status": status,
        "violations": violations,
        "confidence": 0.90,
        "message": f"Safety status: {status}"
    }
    print("→", result["message"])
    return result


def red_team_agent(timeline, safety_status):
    print("Red Team is checking...")

    warnings = []
    challenge = False

    low_trust = sum(1 for event in timeline if event.get("trust_score", 1) < 0.35)

    if low_trust >= 2:
        warnings.append(f"{low_trust} low-trust events found")
        challenge = True

    if safety_status == "FAILED":
        warnings.append("Safety already failed")
        challenge = True

    result = {
        "agent": "Red-Team",
        "warnings": warnings,
        "challenge": challenge,
        "confidence": 0.80,
        "message": "Problems found" if challenge else "No major problems"
    }
    print("→", result["message"])
    return result


def run_multi_agent_system(timeline, current_state):
    print("\nMulti-Agent System Started\n")

    inv = investigator_agent(timeline)
    pred = predictor_agent(current_state)
    opt = optimizer_agent(pred["predictions"])
    safe = safety_agent(opt["recommended_action"], current_state)
    red = red_team_agent(timeline, safe["status"])

    print("\nFinal Decision Process:")

    if safe["status"] == "FAILED":
        final_decision = "ABSTAIN"
        reason = "Blocked by Safety Agent"
    elif red["challenge"] == True:
        final_decision = "ABSTAIN"
        reason = "Blocked by Red Team"
    else:
        final_decision = opt["recommended_action"]
        reason = "All agents agreed"

    print(f"Final Decision : {final_decision}")
    print(f"Reason         : {reason}\n")

    return {
        "final_decision": final_decision,
        "reason": reason,
        "investigator": inv,
        "predictor": pred,
        "optimizer": opt,
        "safety": safe,
        "red_team": red
    }


# Test
if __name__ == "__main__":
    example_timeline = [
        {"event_id": "E1", "event_type": "TEMPERATURE_READING", "trust_score": 0.25, "source": "SENSOR_14"},
        {"event_id": "E2", "event_type": "COOLING_STATUS", "trust_score": 0.80, "source": "MAINTENANCE_AGENT"},
        {"event_id": "E3", "event_type": "NETWORK_ALERT", "trust_score": 0.30, "source": "SECURITY_SENSOR"}
    ]

    example_state = {
        "estimated_catastrophe_probability": 0.78,
        "temperature": 96.5,
        "backup_cooling_available": True,
        "shutdown_permission": False
    }

    run_multi_agent_system(example_timeline, example_state)