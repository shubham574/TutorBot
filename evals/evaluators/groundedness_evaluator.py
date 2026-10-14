"""GroundednessEvaluator: Verifies RAG answer modes, citation fidelity, and transparency disclaimers."""
from typing import Dict, Any, List, Tuple
from app.rag.tutor import GENERAL_KNOWLEDGE_DISCLAIMER


class GroundednessEvaluator:
    """Audits RAG responses for groundedness, exact citations, and mode compliance."""

    def evaluate(
        self,
        test_case: Dict[str, Any],
        actual_mode: str,
        actual_answer: str,
    ) -> Tuple[bool, List[str]]:
        """
        Validates answer mode, citation presence, and required factual elements.
        """
        reasons = []
        expected_mode = test_case.get("expected_mode")

        # 1. Mode Matching Check
        if actual_mode != expected_mode:
            reasons.append(f"Answer mode mismatch: expected {expected_mode}, got {actual_mode}")

        answer_lower = actual_answer.lower()

        # 2. Citation Check for GROUNDED mode
        if expected_mode == "GROUNDED":
            req_citation = test_case.get("required_citation")
            if req_citation and req_citation.lower() not in answer_lower:
                reasons.append(f"Missing mandatory citation '{req_citation}' in grounded response")

        # 3. Disclaimer Check for GENERAL_KNOWLEDGE mode
        if expected_mode == "GENERAL_KNOWLEDGE":
            if (
                "general knowledge" not in answer_lower
                or "not your uploaded study material" not in answer_lower
            ):
                reasons.append("Missing mandatory transparency disclaimer for general knowledge mode")

        # 4. Required Content Check
        for req in test_case.get("required_in_answer", []):
            if req.lower() not in answer_lower:
                reasons.append(f"Expected concept '{req}' was missing from the response")

        passed = len(reasons) == 0
        return passed, reasons
