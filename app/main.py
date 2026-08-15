from fastapi import FastAPI, HTTPException, status

from app.api.appointments import router as appointments_router
from app.api.auth import router as auth_router
from app.api.clinical_diagnoses import router as clinical_diagnoses_router
from app.api.exam_orders import router as exam_orders_router
from app.api.exam_results import router as exam_results_router
from app.api.health_professionals import router as health_professionals_router
from app.api.medical_records import router as medical_records_router
from app.api.patients import router as patients_router
from app.api.patient_allergies import router as patient_allergies_router
from app.api.prescriptions import router as prescriptions_router
from app.api.rbac import router as rbac_router
from app.api.vital_signs import router as vital_signs_router
from app.database.connection import check_database_connection

app = FastAPI(
    title="JARVIS Medical Platform",
    description="API modular da JARVIS Medical Platform com autenticação JWT e autorização RBAC.",
    version="0.1.0",
)
app.include_router(auth_router)
app.include_router(rbac_router)
app.include_router(patients_router)
app.include_router(health_professionals_router)
app.include_router(appointments_router)
app.include_router(medical_records_router)
app.include_router(prescriptions_router)
app.include_router(exam_orders_router)
app.include_router(exam_results_router)
app.include_router(patient_allergies_router)
app.include_router(vital_signs_router)
app.include_router(clinical_diagnoses_router)


@app.get("/saúde/db", tags=["Saúde"])
def database_health_check() -> dict[str, str]:
    if not check_database_connection():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    return {"status": "ok", "database": "connected"}
