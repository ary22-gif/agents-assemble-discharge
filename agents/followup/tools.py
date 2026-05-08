"""FollowUp Agent tools — appointments, service requests, conditions from FHIR."""
import logging
import httpx
from google.adk.tools import ToolContext
from shared.fhir_client import (
    _get_fhir_context, fhir_get, http_error_result,
    connection_error_result, coding_display, extract_resource_id,
)

logger = logging.getLogger(__name__)

# Condition-to-follow-up window mapping (ICD-10 prefix → suggested window).
# Used to flag clinically inappropriate gaps even when no ServiceRequest exists.
_CONDITION_WINDOWS = {
    "I50": ("Cardiology", "within 7 days", "urgent"),
    "I48": ("Cardiology", "within 7 days", "urgent"),
    "I25": ("Cardiology", "within 2 weeks", "routine"),
    "E11": ("Endocrinology/PCP", "within 2 weeks", "routine"),
    "M17": ("Orthopedic Surgery", "within 2 weeks", "routine"),
    "Z96": ("Orthopedic Surgery", "within 2 weeks", "routine"),
    "J18": ("PCP", "within 14 days", "routine"),
    "J45": ("PCP/Pulmonology", "within 14 days", "routine"),
    "J44": ("Pulmonology", "within 2 weeks", "urgent"),
}


def get_patient_info(tool_context: ToolContext) -> dict:
    """Fetch patient demographics from FHIR."""
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
    names    = p.get("name", [])
    official = next((n for n in names if n.get("use") == "official"), names[0] if names else {})
    return {
        "status": "success",
        "resource_id": extract_resource_id(p),
        "patient_id": patient_id,
        "name": f"{' '.join(official.get('given', []))} {official.get('family', '')}".strip(),
        "birth_date": p.get("birthDate"),
    }


def get_appointments(tool_context: ToolContext) -> dict:
    """
    Retrieve Appointment resources for this patient from FHIR.

    Returns any scheduled follow-up appointments with dates and status.
    An empty result means no follow-up appointments are scheduled — this is
    a care gap that MUST be flagged. Do not infer that appointments exist
    if this tool returns zero results.
    """
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    logger.info("followup_tool get_appointments patient_id=%s", patient_id)
    try:
        bundle = fhir_get(fhir_url, fhir_token, "Appointment",
                          params={"patient": patient_id, "_count": "50"})
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)

    appts = []
    for entry in bundle.get("entry", []):
        r = entry.get("resource", {})
        service_type = r.get("serviceType", [{}])
        appt_type    = (service_type[0].get("coding", [{}])[0].get("display")
                        if service_type else r.get("appointmentType", {}).get("text", "Unknown"))
        appts.append({
            "resource_id": extract_resource_id(r),
            "appointment_type": appt_type or "Unspecified",
            "scheduled_date": r.get("start"),
            "status": r.get("status"),
            "description": r.get("description"),
        })
    return {"status": "success", "patient_id": patient_id,
            "count": len(appts), "appointments": appts}


def get_service_requests(tool_context: ToolContext) -> dict:
    """
    Retrieve ServiceRequest resources for this patient from FHIR.

    Returns referral orders and service requests placed by the hospitalist.
    A ServiceRequest with no corresponding Appointment is an UNSCHEDULED referral —
    a critical care gap. Report all active ServiceRequests as pending unless
    a matching Appointment explicitly fulfills them.
    """
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    logger.info("followup_tool get_service_requests patient_id=%s", patient_id)
    try:
        bundle = fhir_get(fhir_url, fhir_token, "ServiceRequest",
                          params={"patient": patient_id, "_count": "50"})
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)

    requests = []
    for entry in bundle.get("entry", []):
        r       = entry.get("resource", {})
        code    = r.get("code", {})
        codings = code.get("coding", [])
        requests.append({
            "resource_id": extract_resource_id(r),
            "service_type": code.get("text") or coding_display(codings),
            "status": r.get("status"),
            "priority": r.get("priority", "routine"),
            "authored_on": r.get("authoredOn"),
            "requester": (r.get("requester") or {}).get("display"),
            "notes": " | ".join(n.get("text", "") for n in r.get("note", [])),
        })
    return {"status": "success", "patient_id": patient_id,
            "count": len(requests), "service_requests": requests}


def get_conditions(tool_context: ToolContext) -> dict:
    """
    Retrieve active Condition resources for this patient from FHIR.

    Used to cross-reference conditions against recommended follow-up windows.
    For example, post-CHF admission (I50.x) requires cardiology within 7 days.
    """
    ctx = _get_fhir_context(tool_context)
    if isinstance(ctx, dict):
        return ctx
    fhir_url, fhir_token, patient_id = ctx
    logger.info("followup_tool get_conditions patient_id=%s", patient_id)
    try:
        bundle = fhir_get(fhir_url, fhir_token, "Condition",
                          params={"patient": patient_id, "_count": "100"})
    except httpx.HTTPStatusError as e:
        return http_error_result(e)
    except Exception as e:
        return connection_error_result(e)

    conditions = []
    for entry in bundle.get("entry", []):
        r       = entry.get("resource", {})
        code    = r.get("code", {})
        codings = code.get("coding", [])
        icd10   = next((c["code"] for c in codings
                        if "icd-10" in c.get("system", "").lower()), "")
        prefix  = icd10[:3] if icd10 else ""
        window  = _CONDITION_WINDOWS.get(prefix)
        conditions.append({
            "resource_id": extract_resource_id(r),
            "condition_name": code.get("text") or coding_display(codings),
            "icd10_code": icd10,
            "recommended_followup_specialty": window[0] if window else None,
            "recommended_followup_window": window[1] if window else None,
            "recommended_followup_priority": window[2] if window else None,
        })
    return {"status": "success", "patient_id": patient_id,
            "count": len(conditions), "conditions": conditions}
