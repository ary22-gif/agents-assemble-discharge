"""Unit tests for CarePlan guardrails."""
import pytest
from shared.guardrails import check_phi, check_reading_level, score_reading_level, check_provenance


def test_phi_clean():
    r = check_phi("Take your medicine every day. Call your doctor if you feel worse.")
    assert r.passed


def test_phi_ssn_blocked():
    r = check_phi("Patient SSN: 123-45-6789")
    assert not r.passed
    assert len(r.violations) == 1


def test_phi_mrn_blocked():
    r = check_phi("MRN: 1234567")
    assert not r.passed


def test_reading_level_simple():
    text = "Take your pills every day. Call the doctor if you feel sick. Go to the ER if you cannot breathe."
    grade = score_reading_level(text)
    assert grade is not None
    assert grade < 8.0


def test_reading_level_complex():
    text = "Congestive cardiac decompensation necessitates vigilant adherence to pharmacological regimens, including diuretic administration and angiotensin-converting enzyme inhibitor therapy."
    grade = score_reading_level(text)
    assert grade is not None
    assert grade > 8.0


def test_provenance_valid():
    claims = [
        {"resource_type": "Condition", "resource_id": "Condition/cond-001-chf", "agent": "careplan"}
    ]
    known = {"Condition/cond-001-chf", "CarePlan/cp-001-chf"}
    r = check_provenance(claims, known)
    assert r.passed


def test_provenance_missing_id():
    claims = [{"resource_type": "Condition", "agent": "careplan"}]  # no resource_id
    r = check_provenance(claims, {"Condition/cond-001-chf"})
    assert not r.passed


def test_provenance_unknown_id():
    claims = [{"resource_type": "Condition", "resource_id": "Condition/invented-id", "agent": "careplan"}]
    r = check_provenance(claims, {"Condition/cond-001-chf"})
    assert not r.passed
