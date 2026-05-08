"""Mock FHIR R4 server — fully implemented in Phase 2."""
from fastapi import FastAPI
from fhir_server.routes import router

app = FastAPI(
    title="Discharge Coordinator — Mock FHIR Server",
    description="Synthetic FHIR R4 data. DEMO ONLY — NOT FOR CLINICAL USE.",
    version="1.0.0",
)

app.include_router(router, prefix="/fhir")


@app.get("/health")
def health():
    return {"status": "ok", "disclaimer": "DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE."}
