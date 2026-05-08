"""Output safety guardrails — run on every agent response before it leaves the system.

Three checks:
  1. Provenance: every clinical claim must cite a FHIR resource ID from the input bundle.
  2. PHI: no SSN/MRN/NPI patterns in output (defense-in-depth).
  3. Reading level: CarePlan output must score ≤ 8th grade Flesch-Kincaid (target 6th).
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── PHI patterns (same as phi_guard.py pre-commit hook) ──────────────────────
_PHI_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),           # SSN
    re.compile(r"\bMRN[-:\s]?\d{5,10}\b", re.I),    # MRN
    re.compile(r"\bNPI[-:\s]?\d{10}\b",   re.I),    # NPI
]


@dataclass
class GuardrailResult:
    passed: bool
    violations: list[str]


def check_phi(text: str) -> GuardrailResult:
    """Block any PHI pattern in the output string."""
    violations = []
    for pat in _PHI_PATTERNS:
        if pat.search(text):
            violations.append(f"PHI pattern detected: {pat.pattern}")
    passed = len(violations) == 0
    if not passed:
        logger.warning("guardrail_phi_fail violations=%s", violations)
    return GuardrailResult(passed=passed, violations=violations)


def check_provenance(claims: list[dict], known_resource_ids: set[str]) -> GuardrailResult:
    """Every claim dict must have a 'resource_id' key present in known_resource_ids."""
    violations = []
    for claim in claims:
        rid = claim.get("resource_id")
        if not rid:
            violations.append(f"Claim missing resource_id: {claim}")
        elif rid not in known_resource_ids:
            violations.append(f"resource_id '{rid}' not in FHIR input: {claim}")
    passed = len(violations) == 0
    if not passed:
        logger.warning("guardrail_provenance_fail count=%d", len(violations))
    return GuardrailResult(passed=passed, violations=violations)


def check_reading_level(text: str, max_grade: float = 8.0) -> GuardrailResult:
    """Score Flesch-Kincaid grade level. Warn (don't block) if above max_grade."""
    try:
        import textstat
        grade = textstat.flesch_kincaid_grade(text)
        logger.info("guardrail_reading_level grade=%.1f max=%.1f", grade, max_grade)
        if grade > max_grade:
            return GuardrailResult(
                passed=False,
                violations=[f"Reading level {grade:.1f} exceeds max {max_grade} (target 6th grade)"],
            )
        return GuardrailResult(passed=True, violations=[])
    except Exception as e:
        logger.warning("guardrail_reading_level_error err=%s", e)
        return GuardrailResult(passed=True, violations=[])  # don't block on scorer failure
