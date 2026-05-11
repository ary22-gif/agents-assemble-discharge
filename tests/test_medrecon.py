"""Unit tests for MedRecon tools — no LLM, tests FHIR retrieval + interaction check."""

from unittest.mock import MagicMock

from agents.medrecon.tools import check_drug_interactions, _check_interactions


def test_no_interactions():
    result = _check_interactions(["999999", "888888"])
    assert result == []


def test_apixaban_ibuprofen_major():
    result = _check_interactions(["1599543", "197805"])
    assert len(result) == 1
    assert result[0]["severity"] == "major"
    assert "bleeding" in result[0]["description"].lower()


def test_acetaminophen_duplicate_major():
    result = _check_interactions(["1049221", "198440"])
    assert len(result) == 1
    assert result[0]["severity"] == "major"
    assert "acetaminophen" in result[0]["description"].lower()


def test_chf_polypharmacy():
    # Patient-001: furosemide + lisinopril + carvedilol + metformin + aspirin
    codes = ["313988", "314077", "200033", "861007", "243670"]
    result = _check_interactions(codes)
    assert len(result) >= 2
    severities = {r["severity"] for r in result}
    assert "moderate" in severities or "minor" in severities


def test_azithromycin_albuterol_qt():
    result = _check_interactions(["308460", "245314"])
    assert len(result) == 1
    assert result[0]["severity"] == "moderate"
    assert "QT" in result[0]["description"]


def test_check_drug_interactions_tool():
    mock_ctx = MagicMock()
    mock_ctx.state = {
        "fhir_url": "http://localhost:8000/fhir",
        "fhir_token": "demo-token",
        "patient_id": "patient-001",
    }
    result = check_drug_interactions(["1599543", "197805"], mock_ctx)
    assert result["status"] == "success"
    assert result["interaction_count"] == 1
    assert result["interactions"][0]["severity"] == "major"


def test_polypharmacy_flag():
    mock_ctx = MagicMock()
    mock_ctx.state = {
        "fhir_url": "http://localhost:8000/fhir",
        "fhir_token": "demo-token",
        "patient_id": "patient-001",
    }
    result = check_drug_interactions(["a", "b", "c", "d", "e"], mock_ctx)
    assert result["polypharmacy_flag"] is True


def test_no_polypharmacy():
    mock_ctx = MagicMock()
    mock_ctx.state = {
        "fhir_url": "http://localhost:8000/fhir",
        "fhir_token": "demo-token",
        "patient_id": "patient-001",
    }
    result = check_drug_interactions(["a", "b", "c"], mock_ctx)
    assert result["polypharmacy_flag"] is False
