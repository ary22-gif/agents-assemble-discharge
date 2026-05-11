"""
Integration tests — FHIR tool correctness with a live in-process FHIR server.

LLM-dependent tests would require GEMINI_API_KEY + running agents; those
are in scripts/test_e2e.py instead.  Everything here is deterministic and
runs without network access.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from fhir_server.routes import load_bundles

SYNTHETIC_DIR = Path(__file__).parent.parent / "synthetic_data"


@pytest.fixture(autouse=True)
def load_test_bundles():
    load_bundles(SYNTHETIC_DIR)


# ── Agent app imports ─────────────────────────────────────────────────────────


def test_all_apps_import():
    """All four agent app modules must import without errors."""
    import importlib

    for module in [
        "agents.medrecon.app",
        "agents.careplan.app",
        "agents.followup.app",
        "agents.orchestrator.app",
    ]:
        m = importlib.import_module(module)
        assert hasattr(m, "a2a_app"), f"{module} missing a2a_app"


# ── FHIR tool tests — patch fhir_get at tool-module level ────────────────────


def _make_fhir_mock(patient_id: str):
    """Return a fhir_get replacement that answers from the live FHIR TestClient."""
    from fhir_server.main import app

    def _mock_fhir_get(
        fhir_url: str, token: str, path: str, params: dict | None = None
    ):
        with TestClient(app) as c:
            headers = {"Authorization": f"Bearer {token}"}
            r = c.get(f"/fhir/{path}", headers=headers, params=params or {})
            return r.json()

    return _mock_fhir_get


def _make_ctx(patient_id: str) -> MagicMock:
    ctx = MagicMock()
    ctx.state = {
        "fhir_url": "http://mock-fhir/fhir",
        "fhir_token": "test-token",
        "patient_id": patient_id,
    }
    return ctx


# MedRecon tools


def test_medrecon_medication_requests_patient001():
    from agents.medrecon import tools as t

    ctx = _make_ctx("patient-001")
    with patch.object(t, "fhir_get", _make_fhir_mock("patient-001")):
        result = t.get_medication_requests(ctx)
    assert result["status"] == "success"
    assert result["count"] == 5
    rxnorms = [m["rxnorm_code"] for m in result["medications"]]
    assert "313988" in rxnorms  # furosemide
    assert "314077" in rxnorms  # lisinopril
    assert "200033" in rxnorms  # carvedilol


def test_medrecon_medication_statements_patient001():
    from agents.medrecon import tools as t

    ctx = _make_ctx("patient-001")
    with patch.object(t, "fhir_get", _make_fhir_mock("patient-001")):
        result = t.get_medication_statements(ctx)
    assert result["status"] == "success"
    assert result["count"] == 1  # spironolactone stopped
    assert result["statements"][0]["status"] == "stopped"


def test_medrecon_drug_interactions_patient001():
    """CHF patient should have ≥2 interactions and polypharmacy flag."""
    from agents.medrecon import tools as t

    ctx = _make_ctx("patient-001")
    # furosemide + lisinopril + carvedilol + metformin + aspirin
    codes = ["313988", "314077", "200033", "861007", "243670"]
    result = t.check_drug_interactions(codes, ctx)
    assert result["status"] == "success"
    assert result["polypharmacy_flag"] is True
    assert result["interaction_count"] >= 2


def test_medrecon_drug_interactions_patient002_major():
    """TKR patient: apixaban + ibuprofen (stopped) = MAJOR interaction."""
    from agents.medrecon import tools as t

    ctx = _make_ctx("patient-002")
    codes = ["1599543", "197805", "1049221", "198440", "312086"]
    result = t.check_drug_interactions(codes, ctx)
    assert result["status"] == "success"
    majors = [i for i in result["interactions"] if i["severity"] == "major"]
    assert len(majors) >= 2  # apixaban+ibuprofen AND duplicate APAP


# CarePlan tools


def test_careplan_conditions_patient001():
    from agents.careplan import tools as t

    ctx = _make_ctx("patient-001")
    with patch.object(t, "fhir_get", _make_fhir_mock("patient-001")):
        result = t.get_conditions(ctx)
    assert result["status"] == "success"
    assert result["count"] == 4
    codes = [c["icd10_code"] for c in result["conditions"]]
    assert "I50.32" in codes
    assert "E11.9" in codes


def test_careplan_procedures_patient003():
    from agents.careplan import tools as t

    ctx = _make_ctx("patient-003")
    with patch.object(t, "fhir_get", _make_fhir_mock("patient-003")):
        result = t.get_procedures(ctx)
    assert result["status"] == "success"
    assert result["count"] == 3
    names = [p["procedure_name"] for p in result["procedures"]]
    assert any("X-ray" in n or "chest" in n.lower() for n in names)


def test_careplan_careplans_patient002():
    from agents.careplan import tools as t

    ctx = _make_ctx("patient-002")
    with patch.object(t, "fhir_get", _make_fhir_mock("patient-002")):
        result = t.get_care_plans(ctx)
    assert result["status"] == "success"
    assert result["count"] == 1
    assert (
        "TKR" in result["care_plans"][0]["title"]
        or "knee" in result["care_plans"][0]["title"].lower()
    )


# FollowUp tools — critical: patient-001 has ZERO appointments (care gap)


def test_followup_no_appointments_patient001():
    from agents.followup import tools as t

    ctx = _make_ctx("patient-001")
    with patch.object(t, "fhir_get", _make_fhir_mock("patient-001")):
        result = t.get_appointments(ctx)
    assert result["status"] == "success"
    assert result["count"] == 0  # THE care gap — no follow-up scheduled!


def test_followup_service_requests_patient001():
    from agents.followup import tools as t

    ctx = _make_ctx("patient-001")
    with patch.object(t, "fhir_get", _make_fhir_mock("patient-001")):
        result = t.get_service_requests(ctx)
    assert result["status"] == "success"
    assert result["count"] == 2  # cardiology + dietitian


def test_followup_conditions_include_windows_patient001():
    from agents.followup import tools as t

    ctx = _make_ctx("patient-001")
    with patch.object(t, "fhir_get", _make_fhir_mock("patient-001")):
        result = t.get_conditions(ctx)
    assert result["status"] == "success"
    chf = next((c for c in result["conditions"] if c["icd10_code"] == "I50.32"), None)
    assert chf is not None
    assert chf["recommended_followup_window"] == "within 7 days"
    assert chf["recommended_followup_priority"] == "urgent"


def test_followup_service_requests_patient002_pt():
    from agents.followup import tools as t

    ctx = _make_ctx("patient-002")
    with patch.object(t, "fhir_get", _make_fhir_mock("patient-002")):
        result = t.get_service_requests(ctx)
    assert result["status"] == "success"
    assert result["count"] == 2
    types = [sr["service_type"] for sr in result["service_requests"]]
    assert any("physical therapy" in s.lower() for s in types)


# A2A format


def test_a2a_request_has_fhir_metadata():
    from shared.a2a_helpers import build_a2a_request

    payload = build_a2a_request(
        "discharge patient-001", "http://fhir", "tok", "patient-001"
    )
    assert payload["jsonrpc"] == "2.0"
    assert payload["method"] == "message/send"
    meta = payload["params"]["message"]["metadata"]
    key = next((k for k in meta if "fhir-context" in k), None)
    assert key is not None
    assert meta[key]["patientId"] == "patient-001"
    assert meta[key]["fhirToken"] == "tok"
