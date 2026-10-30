# data/complete_test_dataset.py
# FINAL Improved Baseline Dataset for CHRONOS-X
# Incident: CHRONOS-2035-001

def get_complete_dataset():
    dataset = {

        # ====================================================
        # INCIDENT METADATA
        # ====================================================
        "incident": {
            "scenario_id": "CHRONOS-2035-001",
            "name": "Thermal Event Warning - 08:00",
            "current_time": "08:00:00",
            "simulation_snapshot_time": "08:02:18",
            "catastrophe_deadline_minutes": 90,
            "status": "ACTIVE"
        },

        # ====================================================
        # 1. TEMPORAL EVENTS
        # ====================================================
        "temporal_events": [
            {
                "event_id": "EVT-001",
                "event_time": "07:52:10",
                "arrival_time": "08:01:05",
                "source": "REACTOR_SENSOR_14",
                "event_type": "TEMPERATURE_READING",
                "value": 91.8,
                "trust_score": 0.28,
                "signature_valid": False,
                "component_id": "COOLING_LOOP_02"
            },
            {
                "event_id": "EVT-002",
                "event_time": "07:55:30",
                "arrival_time": "07:55:35",
                "source": "MAINTENANCE_AGENT",
                "event_type": "COOLING_STATUS",
                "value": "OPERATIONAL",
                "trust_score": 0.87,
                "signature_valid": True,
                "component_id": "COOLING_LOOP_02"
            },
            {
                "event_id": "EVT-001",  # Duplicate
                "event_time": "07:52:10",
                "arrival_time": "08:02:18",
                "source": "REACTOR_SENSOR_14",
                "event_type": "TEMPERATURE_READING",
                "value": 91.8,
                "trust_score": 0.28,
                "signature_valid": False,
                "component_id": "COOLING_LOOP_02"
            },
            {
                "event_id": "EVT-003",
                "event_time": "07:48:00",
                "arrival_time": "08:00:40",
                "source": "SECURITY_SENSOR",
                "event_type": "NETWORK_ALERT",
                "value": "SUSPICIOUS_TRAFFIC",
                "trust_score": 0.33,
                "signature_valid": False,
                "component_id": "NETWORK_01"
            },
            {
                "event_id": "EVT-004",
                "event_time": "07:58:20",
                "arrival_time": "07:58:22",
                "source": "PRESSURE_SENSOR_07",
                "event_type": "PRESSURE_READING",
                "value": 4.7,  # No unit / no threshold defined
                "trust_score": 0.91,
                "signature_valid": True,
                "component_id": "COOLING_LOOP_02"
            },
            {
                "event_id": "EVT-005",
                "event_time": "07:59:45",
                "arrival_time": "08:00:05",
                "source": "REACTOR_SENSOR_14",
                "event_type": "TEMPERATURE_READING",
                "value": 94.1,
                "trust_score": 0.31,
                "signature_valid": False,
                "component_id": "COOLING_LOOP_02"
            }
        ],

        # ====================================================
        # 6. MANIPULATED EVENTS
        # ====================================================
        "manipulated_events": [
            {
                "event_id": "FAKE-001",
                "event_time": "07:59:10",
                "arrival_time": "08:00:12",
                "source": "MAINTENANCE_AGENT",
                "event_type": "COOLING_STATUS",
                "value": "ALL_SYSTEMS_NORMAL",
                "trust_score": 0.12,
                "signature_valid": False,
                "is_manipulated": True
            },
            {
                "event_id": "FAKE-002",
                "event_time": "07:56:45",
                "arrival_time": "08:01:50",
                "source": "UNKNOWN_SENSOR",
                "event_type": "TEMPERATURE_READING",
                "value": 71.5,
                "trust_score": 0.09,
                "signature_valid": False,
                "is_manipulated": True
            }
        ],

        # ====================================================
        # EVENT STATISTICS
        # ====================================================
        "event_statistics": {
            "total_received_records": 8,
            "unique_event_ids": 7,
            "duplicate_records": 1,
            "low_trust_received_records": 6,
            "low_trust_unique_events": 5,
            "manipulated_records": 2
        },

        # ====================================================
        # 2. CAUSAL HYPOTHESES
        # ====================================================
        "causal_hypotheses": {
            "cooling_controller_compromise": {
                "related_event_types": ["TEMPERATURE_READING", "COOLING_STATUS"],
                "supporting_evidence": ["EVT-001", "EVT-002", "EVT-005"],
                "confidence": 0.71,
                "confidence_type": "SYNTHETIC_TEST_VALUE",
                "method": "MANUALLY_ASSIGNED_FOR_TESTING"
            },
            "sensor_corruption": {
                "related_event_types": ["TEMPERATURE_READING"],
                "supporting_evidence": ["EVT-001", "EVT-005"],
                "confidence": 0.58,
                "confidence_type": "SYNTHETIC_TEST_VALUE",
                "method": "MANUALLY_ASSIGNED_FOR_TESTING"
            },
            "cyber_intrusion": {
                "related_event_types": ["NETWORK_ALERT"],
                "supporting_evidence": ["EVT-003"],
                "confidence": 0.49,
                "confidence_type": "SYNTHETIC_TEST_VALUE",
                "method": "MANUALLY_ASSIGNED_FOR_TESTING"
            },
            "previous_recovery_side_effect": {
                "related_event_types": ["COOLING_STATUS", "PRESSURE_READING"],
                "supporting_evidence": ["EVT-002", "EVT-004"],
                "confidence": 0.36,
                "confidence_type": "SYNTHETIC_TEST_VALUE",
                "method": "MANUALLY_ASSIGNED_FOR_TESTING"
            }
        },

        # ====================================================
        # CURRENT STATE + TEMPERATURE PROVENANCE
        # ====================================================
        "current_state": {
            "scenario_id": "CHRONOS-2035-001",
            "current_time": "08:00:00",
            "simulation_snapshot_time": "08:02:18",
            "catastrophe_deadline_minutes": 90,
            "estimated_catastrophe_probability": 0.76,
            "probability_note": "SYNTHETIC INITIAL ESTIMATE – not a validated probability",
            "temperature": 94.3,
            "temperature_metadata": {
                "value": 94.3,
                "source": "STATE_ESTIMATOR",
                "timestamp": "08:02:18",
                "data_type": "ESTIMATED",
                "confidence": 0.85,
                "confidence_type": "SYNTHETIC_TEST_VALUE",
                "note": "Synthetic estimated value for testing (not a direct sensor reading)"
            },
            "pressure": 4.7,  # No unit / no threshold defined
            "backup_cooling_available": True,
            "shutdown_permission": False,
            "critical_comms_required": False
        },

        # ====================================================
        # AVAILABLE ACTIONS (with structured preconditions + effect models)
        # ====================================================
        "available_actions": {
            "CONTINUE_MONITORING": {
                "preconditions": [],
                "execution_duration_minutes": 0,
                "resource_requirements": {},
                "can_run_parallel": True,
                "effect_model": {
                    "temperature_change": {
                        "distribution": "NORMAL",
                        "mean": 0.4,
                        "std_dev": 0.25,
                        "unit": "degrees",
                        "note": "SYNTHETIC – temperature continues to rise slowly"
                    },
                    "effect_delay_minutes": {"min": 0, "max": 0}
                },
                "failure_probability": 0.0,
                "action_cost": 0,
                "note": "SYNTHETIC PARAMETERS FOR TESTING ONLY"
            },
            "ACTIVATE_BACKUP_COOLING": {
                "preconditions": [
                    {
                        "field": "backup_cooling_available",
                        "operator": "==",
                        "expected_value": True
                    }
                ],
                "execution_duration_minutes": 8,
                "resource_requirements": {"power": "medium"},
                "can_run_parallel": False,
                "effect_model": {
                    "temperature_change": {
                        "distribution": "NORMAL",
                        "mean": -3.2,
                        "std_dev": 0.9,
                        "unit": "degrees",
                        "note": "SYNTHETIC – illustrative cooling effect"
                    },
                    "effect_delay_minutes": {"min": 12, "max": 18}
                },
                "failure_probability": 0.12,
                "action_cost": 35,
                "note": "SYNTHETIC PARAMETERS FOR TESTING ONLY"
            },
            "ISOLATE_NETWORK": {
                "preconditions": [
                    {
                        "field": "critical_comms_required",
                        "operator": "==",
                        "expected_value": False
                    }
                ],
                "execution_duration_minutes": 3,
                "resource_requirements": {},
                "can_run_parallel": True,
                "effect_model": {
                    "temperature_change": {
                        "distribution": "NORMAL",
                        "mean": 0.1,
                        "std_dev": 0.3,
                        "unit": "degrees",
                        "note": "SYNTHETIC – almost no direct thermal effect"
                    },
                    "effect_delay_minutes": {"min": 1, "max": 3}
                },
                "failure_probability": 0.05,
                "action_cost": 10,
                "note": "SYNTHETIC PARAMETERS FOR TESTING ONLY"
            },
            "SHUTDOWN_REACTOR": {
                "preconditions": [
                    {
                        "field": "shutdown_permission",
                        "operator": "==",
                        "expected_value": True
                    }
                ],
                "execution_duration_minutes": 25,
                "resource_requirements": {"authorization": "required"},
                "can_run_parallel": False,
                "effect_model": {
                    "temperature_change": {
                        "distribution": "NORMAL",
                        "mean": -8.5,
                        "std_dev": 1.5,
                        "unit": "degrees",
                        "note": "SYNTHETIC – strong cooling after full shutdown"
                    },
                    "effect_delay_minutes": {"min": 20, "max": 30}
                },
                "failure_probability": 0.08,
                "action_cost": 100,
                "note": "SYNTHETIC PARAMETERS FOR TESTING ONLY"
            }
        },

        # ====================================================
        # 7. SAFETY RULES (Structured)
        # ====================================================
        "safety_rules": [
            {
                "rule_id": "R1",
                "description": "Cannot shutdown without permission",
                "action": "SHUTDOWN_REACTOR",
                "field": "shutdown_permission",
                "operator": "==",
                "expected_value": False,
                "effect": "REJECT"
            },
            {
                "rule_id": "R2",
                "description": "Backup cooling must be available",
                "action": "ACTIVATE_BACKUP_COOLING",
                "field": "backup_cooling_available",
                "operator": "==",
                "expected_value": False,
                "effect": "REJECT"
            },
            {
                "rule_id": "R3",
                "description": "Cannot only monitor if temperature is critical",
                "action": "CONTINUE_MONITORING",
                "field": "temperature",
                "operator": ">",
                "expected_value": 95,
                "effect": "REJECT"
            },
            {
                "rule_id": "R4",
                "description": "Network isolation blocked if critical communications needed",
                "action": "ISOLATE_NETWORK",
                "field": "critical_comms_required",
                "operator": "==",
                "expected_value": True,
                "effect": "REJECT"
            }
        ],

        # ====================================================
        # 8. COMMAND CENTER
        # ====================================================
        "command_center": {
            "scenario_id": "CHRONOS-2035-001",
            "scenario_name": "Thermal Event Warning - 08:00",
            "deadline_minutes": 90,
            "status": "ACTIVE",
            "summary": {
                "total_received_records": 8,
                "unique_event_ids": 7,
                "duplicate_records": 1,
                "low_trust_received_records": 6,
                "low_trust_unique_events": 5,
                "manipulated_records": 2,
                "current_temperature": 94.3,
                "current_pressure": 4.7
            }
        }
    }

    return dataset


if __name__ == "__main__":
    data = get_complete_dataset()
    print("FINAL Improved Dataset Loaded")
    print("Scenario ID               :", data["incident"]["scenario_id"])
    print("Simulation Snapshot Time  :", data["incident"]["simulation_snapshot_time"])
    print("Temperature (estimated)   :", data["current_state"]["temperature"])
    print("Temperature Source        :", data["current_state"]["temperature_metadata"]["source"])
    print("Low-trust received records:", data["event_statistics"]["low_trust_received_records"])