from typing import Any

from .invariant_checker import InvariantChecker
from .permission_checker import PermissionChecker
from .resource_checker import ResourceChecker
from .conflict_checker import ConflictChecker
from .counterexample_generator import CounterexampleGenerator
from .decision_certificate import DecisionCertificate


class SafetyVerificationEngine:
    """
    M7 integrated safety verification pipeline.

    Evaluates proposed interventions against configured safety
    invariants, permissions, resources, and action conflicts.

    This prototype does not execute industrial actions.
    """

    def __init__(
        self,
        invariant_checker=None,
        permission_checker=None,
        resource_checker=None,
        conflict_checker=None,
        counterexample_generator=None,
        decision_certificate=None,
    ):
        self.invariant_checker = (
            invariant_checker or InvariantChecker()
        )
        self.permission_checker = (
            permission_checker or PermissionChecker()
        )
        self.resource_checker = (
            resource_checker or ResourceChecker()
        )
        self.conflict_checker = (
            conflict_checker or ConflictChecker()
        )
        self.counterexample_generator = (
            counterexample_generator or CounterexampleGenerator()
        )
        self.decision_certificate = (
            decision_certificate or DecisionCertificate()
        )

    def verify(
        self,
        action: str,
        state: dict[str, Any],
        approvals: dict[str, Any],
        available_resources: dict[str, Any],
        proposed_actions: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Run all M7 safety checks for a proposed intervention.
        """

        if not isinstance(action, str) or not action.strip():
            action = "UNKNOWN_ACTION"

            invalid_action = True
        else:
            action = action.upper().strip()
            invalid_action = False

        if proposed_actions is None:
            proposed_actions = [action]

        if not isinstance(proposed_actions, list):
            proposed_actions = None

        # 1. Equipment invariant verification
        invariant_result = self.invariant_checker.check(state)

        # 2. Permission verification
        permission_result = self.permission_checker.check(
            action,
            approvals
        )

        # 3. Resource verification
        resource_result = self.resource_checker.check(
            action,
            available_resources
        )

        # 4. Action conflict verification
        conflict_result = self.conflict_checker.check(
            proposed_actions
        )

        if invalid_action:
            invariant_result["status"] = "UNKNOWN"
            permission_result["status"] = "UNKNOWN"
            resource_result["status"] = "UNKNOWN"
            conflict_result["status"] = "UNKNOWN"

            permission_result["unknowns"].append(
                "Cannot verify an invalid action"
            )

        # Collect all component results
        verification_results = {
            "invariants": invariant_result,
            "permissions": permission_result,
            "resources": resource_result,
            "conflicts": conflict_result,
        }

        # 5. Generate explanations and counterexamples
        counterexample_result = (
            self.counterexample_generator.generate(
                action,
                verification_results
            )
        )

        # 6. Generate final machine-readable certificate
        certificate = self.decision_certificate.generate(
            action,
            verification_results,
            counterexample_result
        )

        return {
            "module": "M7_SAFETY_VERIFICATION",
            "action": action,
            "status": certificate["status"],
            "verification_results": verification_results,
            "counterexample_result": counterexample_result,
            "decision_certificate": certificate,
            "execution_allowed": False,
            "requires_human_approval": (
                certificate["requires_human_approval"]
            ),
        }