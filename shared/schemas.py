"""Pydantic output schemas shared across all agents."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ProvenanceItem(BaseModel):
    resource_type: str
    resource_id: str
    agent: str


# ── MedRecon ──────────────────────────────────────────────────────────────────

class ReconciledMedication(BaseModel):
    resource_id: str
    medication_name: str
    rxnorm_code: Optional[str] = None
    dosage: str
    status: str
    action: str  # continue | stop | modify | new
    notes: Optional[str] = None


class DrugInteraction(BaseModel):
    medications: list[str]
    rxnorm_codes: list[str]
    severity: str  # major | moderate | minor
    description: str
    resource_ids: list[str]


class MedReconOutput(BaseModel):
    status: str
    patient_id: str
    reconciled_medications: list[ReconciledMedication]
    stopped_medications: list[ReconciledMedication] = Field(default_factory=list)
    drug_interactions: list[DrugInteraction] = Field(default_factory=list)
    polypharmacy_flag: bool = False  # True if >= 5 active meds
    total_active_medications: int = 0
    provenance: list[ProvenanceItem] = Field(default_factory=list)
    error: Optional[str] = None


# ── CarePlan ──────────────────────────────────────────────────────────────────

class CarePlanOutput(BaseModel):
    status: str
    patient_id: str
    primary_diagnosis: str
    secondary_diagnoses: list[str] = Field(default_factory=list)
    discharge_instructions: str  # patient-readable markdown
    red_flag_symptoms: list[str] = Field(default_factory=list)
    diet_activity_restrictions: list[str] = Field(default_factory=list)
    procedures_performed: list[str] = Field(default_factory=list)
    reading_level_grade: Optional[float] = None
    provenance: list[ProvenanceItem] = Field(default_factory=list)
    error: Optional[str] = None


# ── FollowUp ──────────────────────────────────────────────────────────────────

class PendingReferral(BaseModel):
    resource_id: str
    referral_type: str
    priority: str
    suggested_window: str
    status: str  # NOT SCHEDULED | scheduled | completed
    action_required: bool
    notes: Optional[str] = None


class ScheduledAppointment(BaseModel):
    resource_id: str
    appointment_type: str
    scheduled_date: Optional[str] = None
    status: str


class FollowUpOutput(BaseModel):
    status: str
    patient_id: str
    scheduled_appointments: list[ScheduledAppointment] = Field(default_factory=list)
    pending_referrals: list[PendingReferral] = Field(default_factory=list)
    follow_up_gap_count: int = 0
    provenance: list[ProvenanceItem] = Field(default_factory=list)
    error: Optional[str] = None


# ── Discharge Packet (Orchestrator output) ────────────────────────────────────

class AgentTiming(BaseModel):
    agent: str
    duration_ms: float
    status: str


class DischargePacket(BaseModel):
    status: str
    patient_id: str
    patient_name: str
    generated_at: str
    total_duration_ms: float
    medications: Optional[MedReconOutput] = None
    care_instructions: Optional[CarePlanOutput] = None
    follow_up: Optional[FollowUpOutput] = None
    agent_timings: list[AgentTiming] = Field(default_factory=list)
    provenance: list[ProvenanceItem] = Field(default_factory=list)
    disclaimer: str = "DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE."
    error: Optional[str] = None
