"""CarePlan Agent tools — conditions, care plans, procedures from FHIR."""

import logging
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


def get_patient_info(tool_context: ToolContext) -> dict:
    """Fetch patient name, DOB, and gender from FHIR."""
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    try:
        p = fhir_get(fhir_url, fhir_token, f"Patient/{patient_id}")
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)
    names = p.get("name", [])
    official = next(
        (n for n in names if n.get("use") == "official"), names[0] if names else {}
    )
    return {
        "status": "success",
        "resource_id": extract_resource_id(p),
        "patient_id": patient_id,
        "name": f"{' '.join(official.get('given', []))} {official.get('family', '')}".strip(),
        "birth_date": p.get("birthDate"),
        "gender": p.get("gender"),
    }


def get_conditions(tool_context: ToolContext) -> dict:
    """
    Retrieve all Condition resources for this patient from FHIR.

    Returns conditions with ICD-10 codes, clinical status, and onset dates.
    Used to identify the primary admission diagnosis and active comorbidities.
    """
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    logger.info("careplan_tool get_conditions patient_id=%s", patient_id)
    try:
        bundle = fhir_get(
            fhir_url,
            fhir_token,
            "Condition",
            params={"patient": patient_id, "_count": "100"},
        )
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)

    conditions = []
    for entry in bundle.get("entry", []):
        r = entry.get("resource", {})
        code = r.get("code", {})
        codings = code.get("coding", [])
        icd10 = next(
            (c["code"] for c in codings if "icd-10" in c.get("system", "").lower()),
            None,
        )
        clin_status = ((r.get("clinicalStatus") or {}).get("coding") or [{}])[0].get(
            "code"
        )
        conditions.append(
            {
                "resource_id": extract_resource_id(r),
                "condition_name": code.get("text") or coding_display(codings),
                "icd10_code": icd10,
                "clinical_status": clin_status,
                "onset": r.get("onsetDateTime"),
                "recorded_date": r.get("recordedDate"),
                "notes": " | ".join(n.get("text", "") for n in r.get("note", [])),
            }
        )
    return {
        "status": "success",
        "patient_id": patient_id,
        "count": len(conditions),
        "conditions": conditions,
    }


def get_care_plans(tool_context: ToolContext) -> dict:
    """
    Retrieve CarePlan resources for this patient from FHIR.

    Returns care plan title, description, and activity details.
    The care plan contains the hospitalist's discharge planning notes
    and identifies unscheduled follow-up activities.
    """
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    logger.info("careplan_tool get_care_plans patient_id=%s", patient_id)
    try:
        bundle = fhir_get(
            fhir_url,
            fhir_token,
            "CarePlan",
            params={"patient": patient_id, "_count": "50"},
        )
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)

    plans = []
    for entry in bundle.get("entry", []):
        r = entry.get("resource", {})
        activities = []
        for act in r.get("activity", []):
            detail = act.get("detail", {})
            activities.append(
                {
                    "kind": detail.get("kind"),
                    "status": detail.get("status"),
                    "description": detail.get("description"),
                }
            )
        plans.append(
            {
                "resource_id": extract_resource_id(r),
                "title": r.get("title"),
                "description": r.get("description"),
                "status": r.get("status"),
                "period_start": (r.get("period") or {}).get("start"),
                "activities": activities,
            }
        )
    return {
        "status": "success",
        "patient_id": patient_id,
        "count": len(plans),
        "care_plans": plans,
    }


def get_procedures(tool_context: ToolContext) -> dict:
    """
    Retrieve Procedure resources for this patient from FHIR.

    Returns procedures performed during the admission with CPT/LOINC codes,
    dates, and relevant notes. Used to contextualize discharge instructions.
    """
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    logger.info("careplan_tool get_procedures patient_id=%s", patient_id)
    try:
        bundle = fhir_get(
            fhir_url,
            fhir_token,
            "Procedure",
            params={"patient": patient_id, "_count": "50"},
        )
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)

    procs = []
    for entry in bundle.get("entry", []):
        r = entry.get("resource", {})
        code = r.get("code", {})
        codings = code.get("coding", [])
        procs.append(
            {
                "resource_id": extract_resource_id(r),
                "procedure_name": code.get("text") or coding_display(codings),
                "status": r.get("status"),
                "performed_date": r.get("performedDateTime"),
                "performer": ((r.get("performer") or [{}])[0].get("actor") or {}).get(
                    "display"
                ),
                "notes": " | ".join(n.get("text", "") for n in r.get("note", [])),
            }
        )
    return {
        "status": "success",
        "patient_id": patient_id,
        "count": len(procs),
        "procedures": procs,
    }
