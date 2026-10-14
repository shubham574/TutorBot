"""QuestionAuditEvaluator: Audits MCQ questions against verifier agreement and WhatsApp UI limits."""
from typing import Dict, Any, List, Tuple


class QuestionAuditEvaluator:
    """Verifies MCQ question quality, dual-pass agreement, and WhatsApp reply button constraints."""

    def audit_question(self, question_item: Dict[str, Any]) -> Tuple[str, List[str]]:
        """
        Runs quality audits on a question item and returns (status, issues).
        Possible statuses: PASS, FAIL_VERIFIER_MISMATCH, FAIL_BUTTON_LENGTH, FAIL_EXPLANATION.
        """
        issues = []
        options = question_item.get("options", {})
        correct_option = question_item.get("correct_option")
        solver_choice = question_item.get("solver_choice")
        explanation = question_item.get("explanation") or ""

        # 1. Verifier agreement check
        if solver_choice != correct_option:
            issues.append(
                f"Dual-pass verifier mismatch: key={correct_option}, solver={solver_choice}"
            )
            return "FAIL_VERIFIER_MISMATCH", issues

        # 2. WhatsApp Reply Button constraints
        if len(options) > 3:
            issues.append(f"Too many options for WhatsApp reply buttons: {len(options)} (max 3)")
            return "FAIL_BUTTON_COUNT", issues

        for key, text in options.items():
            button_label = f"{key}. {text}"
            # WhatsApp Cloud API interactive button title limit is 20 chars
            if len(button_label) > 20 and len(text) > 17:
                issues.append(
                    f"Option '{button_label}' exceeds WhatsApp 20-character button limit ({len(button_label)} chars)"
                )
                return "FAIL_BUTTON_LENGTH", issues

        # 3. Explanation check
        if len(explanation.strip()) < 10:
            issues.append("Explanation missing or too brief (<10 chars)")
            return "FAIL_EXPLANATION", issues

        return "PASS", []

    def evaluate_item(self, question_item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates that the audit outcome matches the expected status.
        """
        expected_status = question_item.get("expected_status", "PASS")
        actual_status, issues = self.audit_question(question_item)

        passed = actual_status == expected_status
        reasons = []
        if not passed:
            reasons.append(f"Expected status {expected_status}, but audit returned {actual_status}: {issues}")

        return passed, reasons
