"""Tests for the mock FHIR server — no LLM calls, pure HTTP."""
import json
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from fhir_server.main import app
from fhir_server.routes import load_bundles

SYNTHETIC_DIR = Path(__file__).parent.parent / "synthetic_data"
TOKEN = "Bearer test-token"

@pytest.fixture(autouse=True)
def load_test_data():
    load_bundles(SYNTHETIC_DIR)

@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "SYNTHETIC" in r.json()["disclaimer"]


def test_patient_001(client):
    r = client.get("/fhir/Patient/patient-001", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    data = r.json()
    assert data["resourceType"] == "Patient"
    assert "Strider" in data["name"][0]["family"]


def test_patient_002(client):
    r = client.get("/fhir/Patient/patient-002", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    assert "Amidala" in r.json()["name"][0]["family"]


def test_patient_003(client):
    r = client.get("/fhir/Patient/patient-003", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    assert "Baggins" in r.json()["name"][0]["family"]


def test_patient_not_found(client):
    r = client.get("/fhir/Patient/patient-999", headers={"Authorization": TOKEN})
    assert r.status_code == 404


def test_no_auth_rejected(client):
    r = client.get("/fhir/Patient/patient-001")
    assert r.status_code == 401


def test_conditions_patient_001(client):
    r = client.get("/fhir/Condition?patient=patient-001", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    data = r.json()
    assert data["resourceType"] == "Bundle"
    assert data["total"] == 4
    codes = [e["resource"]["code"]["coding"][0]["code"] for e in data["entry"]]
    assert "I50.32" in codes
    assert "E11.9" in codes


def test_medication_requests_patient_001(client):
    r = client.get("/fhir/MedicationRequest?patient=patient-001", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    rxnorms = [
        e["resource"]["medicationCodeableConcept"]["coding"][0]["code"]
        for e in data["entry"]
    ]
    assert "313988" in rxnorms  # furosemide
    assert "314077" in rxnorms  # lisinopril
    assert "200033" in rxnorms  # carvedilol


def test_medication_statements_patient_001(client):
    r = client.get("/fhir/MedicationStatement?patient=patient-001", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_service_requests_patient_002(client):
    r = client.get("/fhir/ServiceRequest?patient=patient-002", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    types = [e["resource"]["code"]["text"] for e in data["entry"]]
    assert any("physical therapy" in t.lower() for t in types)


def test_appointments_patient_001_empty(client):
    """Patient-001 has no Appointments scheduled — this is the care gap."""
    r = client.get("/fhir/Appointment?patient=patient-001", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_procedures_patient_003(client):
    r = client.get("/fhir/Procedure?patient=patient-003", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    names = [e["resource"]["code"]["text"] for e in data["entry"]]
    assert any("X-ray" in n or "chest" in n.lower() for n in names)


def test_careplan_patient_002(client):
    r = client.get("/fhir/CarePlan?patient=patient-002", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_metadata(client):
    r = client.get("/fhir/metadata")
    assert r.status_code == 200
    assert r.json()["resourceType"] == "CapabilityStatement"
