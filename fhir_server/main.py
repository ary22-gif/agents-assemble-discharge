"""
Mock FHIR R4 server — synthetic data only.

DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.

Loads patient bundles from ../synthetic_data/ at startup.
Accepts any non-empty Bearer token (mock auth).
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fhir_server.routes import router, load_bundles

logger = logging.getLogger(__name__)

SYNTHETIC_DATA_DIR = Path(__file__).parent.parent / "synthetic_data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_bundles(SYNTHETIC_DATA_DIR)
    logger.info("FHIR mock server loaded bundles from %s", SYNTHETIC_DATA_DIR)
    yield


app = FastAPI(
    title="Discharge Coordinator — Mock FHIR R4 Server",
    description="DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/fhir")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "disclaimer": "DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.",
    }


@app.get("/")
def root():
    return {
        "service": "Mock FHIR R4 Server",
        "disclaimer": "DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.",
        "endpoints": [
            "/fhir/Patient/{id}",
            "/fhir/Condition",
            "/fhir/MedicationRequest",
            "/fhir/MedicationStatement",
            "/fhir/CarePlan",
            "/fhir/Procedure",
            "/fhir/Appointment",
            "/fhir/ServiceRequest",
            "/health",
        ],
    }
