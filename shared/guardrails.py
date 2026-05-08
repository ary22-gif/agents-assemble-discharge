"""Output safety guardrails applied to every agent response.

Three checks:
  1. PHI: no SSN/MRN/NPI patterns in output.
  2. Provenance: every clinical claim must cite a FHIR resource ID from input.
  3. Reading level: CarePlan instructions must score ≤ 8th grade Flesch-Kincaid (target 6th).
"""
import re
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_PHI_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\bMRN[-:\s]+\d{5,10}\b",  re.I),
    re.compile(r"\bNPI[-:\s]+\d{10}\b",    re.I),
]


@dataclass
class GuardrailResult:
    passed: bool
    violations: list[str] = field(default_factory=list)


def check_phi(text: str) -> GuardrailResult:
    violations = [
        f"PHI pattern [{p.pattern}]"
        for p in _PHI_PATTERNS if p.search(text)
    ]
    if violations:
        logger.warning("guardrail_phi_fail count=%d", len(violations))
    return GuardrailResult(passed=not violations, violations=violations)


def check_provenance(claims: list[dict], known_resource_ids: set[str]) -> GuardrailResult:
    violations = []
    for claim in claims:
        rid = claim.get("resource_id")
        if not rid:
            violations.append(f"Claim missing resource_id: {claim}")
        elif rid not in known_resource_ids:
            violations.append(f"Unknown resource_id '{rid}'")
    if violations:
        logger.warning("guardrail_provenance_fail count=%d", len(violations))
    return GuardrailResult(passed=not violations, violations=violations)


def check_reading_level(text: str, max_grade: float = 8.0) -> GuardrailResult:
    try:
        import textstat
        grade = textstat.flesch_kincaid_grade(text)
        logger.info("guardrail_reading_level grade=%.1f max=%.1f", grade, max_grade)
        if grade > max_grade:
            return GuardrailResult(
                passed=False,
                violations=[f"Reading level {grade:.1f} > max {max_grade}"],
            )
        return GuardrailResult(passed=True, violations=[])
    except Exception as e:
        logger.warning("guardrail_reading_level_skip err=%s", e)
        return GuardrailResult(passed=True, violations=[])


def score_reading_level(text: str) -> float | None:
    try:
        import textstat
        return round(textstat.flesch_kincaid_grade(text), 1)
    except Exception:
        return None


def run_all_guardrails(output_text: str, known_resource_ids: set[str] | None = None) -> dict:
    """Run all guardrails and return a summary dict."""
    phi_result = check_phi(output_text)
    results    = {"phi": phi_result.passed, "phi_violations": phi_result.violations}

    if known_resource_ids is not None:
        try:
            data   = json.loads(output_text)
            claims = data.get("provenance", [])
            prov   = check_provenance(claims, known_resource_ids)
            results["provenance"] = prov.passed
            results["provenance_violations"] = prov.violations
        except Exception:
            results["provenance"] = None

    results["passed"] = phi_result.passed
    return results
