"""MedRecon Agent tools — medication FHIR queries + drug interaction check."""
import logging
import time

import httpx
from google.adk.tools import ToolContext

from shared.fhir_client import (
    _get_fhir_context,
    fhir_get,
    http_error_result,
    connection_error_result,
    coding_display,
    extract_resource_id,
)

logger = logging.getLogger(__name__)

# ── Synthetic drug interaction table (RxNorm code pairs → interaction) ────────
# Clinically plausible interactions — for demo purposes only.
_INTERACTIONS: dict[frozenset, dict] = {
    frozenset(["1599543", "197805"]): {
        "severity": "major",
        "description": (
            "MAJOR: Apixaban + NSAIDs (ibuprofen). Concurrent use significantly "
            "increases bleeding risk. Ibuprofen must remain stopped while on apixaban."
        ),
    },
    frozenset(["1049221", "198440"]): {
        "severity": "major",
        "description": (
            "MAJOR: Oxycodone/Acetaminophen (contains 325mg APAP per tablet) "
            "combined with standalone Acetaminophen 500mg. Duplicate acetaminophen "
            "source — total daily dose may exceed 3000mg limit. Patient MUST understand "
            "not to take both simultaneously at full doses."
        ),
    },
    frozenset(["314077", "200033"]): {
        "severity": "moderate",
        "description": (
            "Lisinopril + Carvedilol: additive hypotension and bradycardia. "
            "Standard CHF combination — monitor BP and heart rate. Separate doses if tolerated."
        ),
    },
    frozenset(["313988", "861007"]): {
        "severity": "moderate",
        "description": (
            "Furosemide + Metformin: furosemide-induced volume depletion may impair "
            "renal clearance of metformin, increasing lactic acidosis risk. "
            "Monitor renal function (BMP) at follow-up."
        ),
    },
    frozenset(["313988", "314077"]): {
        "severity": "minor",
        "description": (
            "Furosemide + Lisinopril: additive hypotensive effect and risk of first-dose "
            "hypotension. Monitor electrolytes — both can affect potassium levels."
        ),
    },
    frozenset(["308460", "245314"]): {
        "severity": "moderate",
        "description": (
            "Azithromycin + Albuterol: both agents can prolong the QT interval. "
            "Risk is higher with electrolyte imbalances. Monitor for palpitations or dizziness."
        ),
    },
    frozenset(["308460", "312617"]): {
        "severity": "moderate",
        "description": (
            "Azithromycin + Prednisone: additive QT prolongation risk. "
            "Short course (5 days each) limits risk, but monitor for cardiac symptoms."
        ),
    },
    frozenset(["896232", "312617"]): {
        "severity": "minor",
        "description": (
            "Fluticasone/Salmeterol + Prednisone: concurrent systemic and inhaled "
            "corticosteroids — risk of HPA axis suppression with prolonged use. "
            "Acceptable for short prednisone burst; resume Advair as directed."
        ),
    },
}


def _check_interactions(rxnorm_codes: list[str]) -> list[dict]:
    """Check a list of RxNorm codes against the interaction table."""
    found = []
    codes = set(rxnorm_codes)
    checked = set()
    for pair, interaction in _INTERACTIONS.items():
        if pair <= codes and pair not in checked:
            checked.add(pair)
            found.append({"pair": list(pair), **interaction})
    return found


# ── FHIR tools ────────────────────────────────────────────────────────────────

def get_patient_info(tool_context: ToolContext) -> dict:
    """Fetch basic patient demographics (name, DOB, gender) from FHIR."""
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    logger.info("medrecon_tool get_patient_info patient_id=%s", patient_id)
    try:
        p = fhir_get(fhir_url, fhir_token, f"Patient/{patient_id}")
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)
    names    = p.get("name", [])
    official = next((n for n in names if n.get("use") == "official"), names[0] if names else {})
    return {
        "status": "success",
        "resource_id": extract_resource_id(p),
        "patient_id": patient_id,
        "name": f"{' '.join(official.get('given', []))} {official.get('family', '')}".strip(),
        "birth_date": p.get("birthDate"),
        "gender": p.get("gender"),
    }


def get_medication_requests(tool_context: ToolContext) -> dict:
    """
    Retrieve all active MedicationRequest resources for the patient from FHIR.

    Returns a list of medications with resource IDs (for provenance), RxNorm codes,
    dosage instructions, and prescriber. Never invents medications not in FHIR.
    """
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    logger.info("medrecon_tool get_medication_requests patient_id=%s", patient_id)
    try:
        bundle = fhir_get(fhir_url, fhir_token, "MedicationRequest",
                          params={"patient": patient_id, "_count": "100"})
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)

    meds = []
    for entry in bundle.get("entry", []):
        r       = entry.get("resource", {})
        concept = r.get("medicationCodeableConcept", {})
        codings = concept.get("coding", [])
        rxnorm  = next((c["code"] for c in codings
                        if "rxnorm" in c.get("system", "").lower()), None)
        dosage  = r.get("dosageInstruction", [{}])
        meds.append({
            "resource_id": extract_resource_id(r),
            "medication_name": concept.get("text") or coding_display(codings),
            "rxnorm_code": rxnorm,
            "status": r.get("status"),
            "dosage": dosage[0].get("text", "See label") if dosage else "See label",
            "authored_on": r.get("authoredOn"),
            "requester": (r.get("requester") or {}).get("display"),
            "notes": " | ".join(n.get("text", "") for n in r.get("note", [])),
        })
    return {"status": "success", "patient_id": patient_id,
            "count": len(meds), "medications": meds}


def get_medication_statements(tool_context: ToolContext) -> dict:
    """
    Retrieve MedicationStatement resources for the patient from FHIR.

    These are patient-reported or reconciled home medications, including
    stopped medications that may affect discharge reconciliation.
    """
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    logger.info("medrecon_tool get_medication_statements patient_id=%s", patient_id)
    try:
        bundle = fhir_get(fhir_url, fhir_token, "MedicationStatement",
                          params={"patient": patient_id, "_count": "100"})
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)

    stmts = []
    for entry in bundle.get("entry", []):
        r       = entry.get("resource", {})
        concept = r.get("medicationCodeableConcept", {})
        codings = concept.get("coding", [])
        rxnorm  = next((c["code"] for c in codings
                        if "rxnorm" in c.get("system", "").lower()), None)
        stmts.append({
            "resource_id": extract_resource_id(r),
            "medication_name": concept.get("text") or coding_display(codings),
            "rxnorm_code": rxnorm,
            "status": r.get("status"),
            "date_asserted": r.get("dateAsserted"),
            "notes": " | ".join(n.get("text", "") for n in r.get("note", [])),
        })
    return {"status": "success", "patient_id": patient_id,
            "count": len(stmts), "statements": stmts}


def check_drug_interactions(rxnorm_codes: list[str], tool_context: ToolContext) -> dict:
    """
    Check a list of RxNorm codes for known drug-drug interactions.

    Args:
        rxnorm_codes: List of RxNorm code strings to check pairwise.

    Returns interaction details including severity (major/moderate/minor)
    and clinical description. Only returns interactions present in the
    reference interaction table — never invents interactions.
    """
    logger.info("medrecon_tool check_drug_interactions codes=%s", rxnorm_codes)
    interactions = _check_interactions(rxnorm_codes)
    return {
        "status": "success",
        "codes_checked": rxnorm_codes,
        "interaction_count": len(interactions),
        "interactions": interactions,
        "polypharmacy_flag": len(rxnorm_codes) >= 5,
    }
