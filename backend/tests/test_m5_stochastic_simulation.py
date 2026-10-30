import unittest
from app.shared_data.complete_test_dataset_v4 import get_scenario_dataset
from app.modules.m5_stochastic_simulation.engine import run_stage5, validate_action

class Stage5Tests(unittest.TestCase):
    def test_shutdown_rejected_without_permission(self):
        d = get_scenario_dataset("BASELINE_THERMAL_EVENT")
        result = validate_action("SHUTDOWN_REACTOR", d, d["current_state"])
        self.assertFalse(result["approved"])

    def test_cooling_rejected_when_unavailable(self):
        d = get_scenario_dataset("COOLING_FAILURE")
        result = validate_action("ACTIVATE_BACKUP_COOLING", d, d["current_state"])
        self.assertFalse(result["approved"])

    def test_network_isolation_rejected_if_comms_required(self):
        d = get_scenario_dataset("BASELINE_THERMAL_EVENT")
        d["current_state"]["critical_comms_required"] = True
        result = validate_action("ISOLATE_NETWORK", d, d["current_state"])
        self.assertFalse(result["approved"])

    def test_pressure_instability_abstains(self):
        result = run_stage5(scenario="PRESSURE_INSTABILITY", iterations=20)
        self.assertTrue(result["abstain"])
        self.assertFalse(result["execution_authorized"])

    def test_cooling_failure_abstains_when_no_relevant_mitigation_is_feasible(self):
        result = run_stage5(scenario="COOLING_FAILURE", iterations=30)
        self.assertTrue(result["abstain"])
        self.assertIsNone(result["best_candidate_for_human_review"])
        self.assertIsNone(result["best_candidate_metrics"])
        self.assertIn("cooling failure", result["abstention_reason"].lower())
        # Network isolation can remain technically feasible, but must not be
        # treated as a direct cooling-failure mitigation.
        network_only = next(
            p for p in result["candidate_plans"] if p["plan"] == ["ISOLATE_NETWORK"]
        )
        self.assertFalse(network_only["incident_relevant"])

    def test_reproducible(self):
        a = run_stage5(scenario="BASELINE_THERMAL_EVENT", iterations=30, seed=7)
        b = run_stage5(scenario="BASELINE_THERMAL_EVENT", iterations=30, seed=7)
        self.assertEqual(a["candidate_plans"], b["candidate_plans"])

    def test_responsibility_contract_outputs(self):
        result = run_stage5(iterations=20)
        self.assertIn("candidate_plans", result)
        self.assertIn("temperature_threshold_exceedance_rate", result["candidate_plans"][0])
        self.assertIn("mean_resource_usage_tokens", result["candidate_plans"][0])
        self.assertIsNone(result["recommended_plan"])

    def test_power_failure_abstains_without_power_restoration_action(self):
        result = run_stage5(scenario="POWER_FAILURE", iterations=30)
        self.assertTrue(result["abstain"])
        self.assertIsNone(result["best_candidate_for_human_review"])
        self.assertIsNone(result["best_candidate_metrics"])
        self.assertIn("power-restoration", result["abstention_reason"].lower())

    def test_pressure_instability_has_no_whole_system_candidate(self):
        result = run_stage5(scenario="PRESSURE_INSTABILITY", iterations=30)
        self.assertTrue(result["abstain"])
        self.assertIsNone(result["best_candidate_for_human_review"])
        self.assertIsNone(result["best_candidate_metrics"])
        self.assertIsNotNone(result["thermal_only_candidate_for_analysis"])

    def test_cyber_intrusion_does_not_isolate_on_suspicion_alone(self):
        result = run_stage5(scenario="CYBER_INTRUSION", iterations=30)
        self.assertTrue(result["abstain"])
        self.assertIsNone(result["best_candidate_for_human_review"])
        self.assertIn("suspected intrusion", result["abstention_reason"].lower())

    def test_cascading_failure_abstains_when_mitigations_unavailable(self):
        result = run_stage5(scenario="CASCADING_FAILURE", iterations=30)
        self.assertTrue(result["abstain"])
        self.assertIsNone(result["best_candidate_for_human_review"])
        self.assertIn("no feasible thermal mitigation", result["abstention_reason"].lower())

    def test_sensor_manipulation_abstains_without_trust_recovery_action(self):
        result = run_stage5(scenario="SENSOR_MANIPULATION", iterations=30)
        self.assertTrue(result["abstain"])
        self.assertIsNone(result["best_candidate_for_human_review"])
        self.assertIn("sensor-recovery", result["abstention_reason"].lower())

    def test_baseline_keeps_thermal_mitigation_candidate(self):
        result = run_stage5(scenario="BASELINE_THERMAL_EVENT", iterations=30)
        self.assertFalse(result["abstain"])
        self.assertIsNotNone(result["best_candidate_for_human_review"])
        self.assertIn("ACTIVATE_BACKUP_COOLING", result["best_candidate_for_human_review"])

    def test_plan_cannot_consume_more_than_available_shared_resources(self):
        d = get_scenario_dataset("BASELINE_THERMAL_EVENT")
        d["resource_inventory"]["current_availability"]["operators"] = 1
        result = run_stage5(dataset=d, iterations=20, max_actions=2)
        two_action_plan = next(
            p for p in result["candidate_plans"]
            if p["plan"] == ["ACTIVATE_BACKUP_COOLING", "SHUTDOWN_REACTOR"]
        )
        self.assertGreater(two_action_plan["safety_or_resource_block_rate"], 0)

if __name__ == "__main__":
    unittest.main()
