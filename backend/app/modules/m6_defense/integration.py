from .provenance import ProvenanceValidator
from .replay_detector import ReplayDetector
from .anomaly_detector import AnomalyDetector
from .consistency_checker import ConsistencyChecker
from .agent_guard import AgentRecommendationGuard


class M6DefensePipeline:
    """
    Coordinates all five M6 defense components.

    1. Provenance validation
    2. Replay detection
    3. Anomaly detection
    4. Cross-source consistency
    5. Adversarial agent recommendation defense

    This pipeline is for defensive screening and review.
    It does not execute industrial actions.
    """

    def __init__(
        self,
        provenance_validator=None,
        replay_detector=None,
        anomaly_detector=None,
        consistency_checker=None,
        agent_guard=None,
    ):
        self.provenance = (
            provenance_validator
            if provenance_validator is not None
            else ProvenanceValidator()
        )

        self.replay = (
            replay_detector
            if replay_detector is not None
            else ReplayDetector()
        )

        self.anomaly = (
            anomaly_detector
            if anomaly_detector is not None
            else AnomalyDetector()
        )

        self.consistency = (
            consistency_checker
            if consistency_checker is not None
            else ConsistencyChecker()
        )

        self.agent_guard = (
            agent_guard
            if agent_guard is not None
            else AgentRecommendationGuard()
        )

    # -----------------------------------------------
    # 1. EVENT DEFENSE
    # -----------------------------------------------

    def inspect_event(self, event):
        if not isinstance(event, dict):
            raise TypeError("event must be a dictionary")

        # Stage 1: Provenance validation
        # IMPORTANT: ProvenanceValidator uses validate(),
        # not inspect().
        provenance_result = self.provenance.validate(event)

        if provenance_result.get("status") != "PASS":
            return {
                "status": "BLOCKED",
                "accepted": False,
                "stage": "PROVENANCE",
                "provenance": provenance_result,
                "reason": "Event failed provenance validation",
                "execution_allowed": False,
            }

        # Stage 2: Replay detection
        replay_result = self.replay.inspect(event)

        if not replay_result.get("accept", False):
            return {
                "status": "BLOCKED",
                "accepted": False,
                "stage": "REPLAY",
                "provenance": provenance_result,
                "replay": replay_result,
                "reason": "Event rejected by replay detection",
                "execution_allowed": False,
            }

        # Stage 3: Anomaly detection
        anomaly_result = self.anomaly.inspect(event)

        anomaly_status = anomaly_result.get(
            "status", "UNKNOWN"
        )

        review_required = anomaly_status != "NORMAL"

        return {
            "status": (
                "REVIEW_REQUIRED"
                if review_required
                else "ACCEPTED"
            ),
            "accepted": True,
            "stage": "COMPLETE",
            "provenance": provenance_result,
            "replay": replay_result,
            "anomaly": anomaly_result,
            "review_required": review_required,
            "execution_allowed": False,
        }

    # -----------------------------------------------
    # 2. CROSS-SOURCE CONSISTENCY
    # -----------------------------------------------

    def inspect_consistency(self, observations):
        return self.consistency.inspect(observations)

    # -----------------------------------------------
    # 3. AGENT RECOMMENDATION DEFENSE
    # -----------------------------------------------

    def inspect_recommendation(
        self,
        recommendation,
        known_evidence_ids,
    ):
        return self.agent_guard.inspect(
            recommendation,
            known_evidence_ids,
        )

    # -----------------------------------------------
    # 4. RESET
    # -----------------------------------------------

    def reset(self):
        self.replay.reset()
        self.anomaly.reset()