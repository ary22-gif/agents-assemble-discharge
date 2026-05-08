"""
FHIR R4 route handlers.

Implements:
  GET /fhir/Patient/{id}
  GET /fhir/{resource_type}?patient={id}

All responses are proper FHIR R4 JSON. Auth: any non-empty Bearer token accepted.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store: {patient_id: {resource_type: [resource, ...]}}
_store: dict[str, dict[str, list[dict]]] = {}
# Flat patient resource store: {patient_id: Patient resource}
_patients: dict[str, dict] = {}

SEARCHABLE_TYPES = {
    "Condition", "MedicationRequest", "MedicationStatement",
    "CarePlan", "Procedure", "Appointment", "ServiceRequest",
}


def load_bundles(data_dir: Path) -> None:
    """Load all patient JSON bundles from data_dir into memory."""
    _store.clear()
    _patients.clear()
    for bundle_file in sorted(data_dir.glob("patient-*.json")):
        try:
            bundle = json.loads(bundle_file.read_text())
            _ingest_bundle(bundle)
            logger.info("FHIR loaded bundle %s", bundle_file.name)
        except Exception as e:
            logger.error("FHIR failed to load %s: %s", bundle_file.name, e)


def _ingest_bundle(bundle: dict) -> None:
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype    = resource.get("resourceType", "")
        rid      = resource.get("id", "")
        if not rtype or not rid:
            continue

        if rtype == "Patient":
            _patients[rid] = resource
            _store.setdefault(rid, {})
        else:
            # Find patient reference
            patient_ref = _patient_ref_from(resource)
            if patient_ref:
                patient_id = patient_ref.split("/")[-1]
                _store.setdefault(patient_id, {})
                _store[patient_id].setdefault(rtype, [])
                _store[patient_id][rtype].append(resource)


def _patient_ref_from(resource: dict) -> Optional[str]:
    """Extract patient reference string from a resource."""
    subject = resource.get("subject") or resource.get("patient")
    if isinstance(subject, dict):
        return subject.get("reference", "")
    return None


def _require_auth(authorization: Optional[str]) -> None:
    """Require a non-empty Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token must not be empty")


def _fhir_bundle(resource_type: str, resources: list[dict]) -> dict:
    """Wrap resources in a FHIR R4 searchset Bundle."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(resources),
        "entry": [
            {
                "fullUrl": f"{resource_type}/{r.get('id', '')}",
                "resource": r,
                "search": {"mode": "match"},
            }
            for r in resources
        ],
    }


def _fhir_json(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(content=data, status_code=status,
                        media_type="application/fhir+json")


# ── Patient read ───────────────────────────────────────────────────────────────

@router.get("/Patient/{patient_id}")
def read_patient(patient_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    patient = _patients.get(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient/{patient_id} not found")
    logger.info("FHIR GET Patient/%s", patient_id)
    return _fhir_json(patient)


# ── Generic resource search by patient ────────────────────────────────────────

def _search_handler(resource_type: str, patient_id: str, authorization: Optional[str]) -> JSONResponse:
    _require_auth(authorization)
    if patient_id not in _store and patient_id not in _patients:
        raise HTTPException(status_code=404, detail=f"Patient/{patient_id} not found")
    resources = _store.get(patient_id, {}).get(resource_type, [])
    logger.info("FHIR GET %s?patient=%s → %d results", resource_type, patient_id, len(resources))
    return _fhir_json(_fhir_bundle(resource_type, resources))


@router.get("/Condition")
def search_conditions(patient: str = Query(...), authorization: Optional[str] = Header(None)):
    return _search_handler("Condition", patient, authorization)


@router.get("/MedicationRequest")
def search_medication_requests(patient: str = Query(...), authorization: Optional[str] = Header(None)):
    return _search_handler("MedicationRequest", patient, authorization)


@router.get("/MedicationStatement")
def search_medication_statements(patient: str = Query(...), authorization: Optional[str] = Header(None)):
    return _search_handler("MedicationStatement", patient, authorization)


@router.get("/CarePlan")
def search_care_plans(patient: str = Query(...), authorization: Optional[str] = Header(None)):
    return _search_handler("CarePlan", patient, authorization)


@router.get("/Procedure")
def search_procedures(patient: str = Query(...), authorization: Optional[str] = Header(None)):
    return _search_handler("Procedure", patient, authorization)


@router.get("/Appointment")
def search_appointments(patient: str = Query(...), authorization: Optional[str] = Header(None)):
    return _search_handler("Appointment", patient, authorization)


@router.get("/ServiceRequest")
def search_service_requests(patient: str = Query(...), authorization: Optional[str] = Header(None)):
    return _search_handler("ServiceRequest", patient, authorization)


# ── Metadata (capability statement stub) ──────────────────────────────────────

@router.get("/metadata")
def capability_statement():
    return _fhir_json({
        "resourceType": "CapabilityStatement",
        "status": "active",
        "kind": "instance",
        "fhirVersion": "4.0.1",
        "format": ["application/fhir+json"],
        "rest": [{"mode": "server", "resource": [
            {"type": t, "interaction": [{"code": "search-type"}]}
            for t in ["Patient"] + list(SEARCHABLE_TYPES)
        ]}],
    })
