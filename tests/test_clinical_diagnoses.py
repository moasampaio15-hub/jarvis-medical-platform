import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.auth.authorization import assign_role_to_user, ensure_default_rbac
from app.auth.password import hash_password
from app.database.base import Base
from app.database.connection import get_engine, get_session_factory
from app.main import app
from app.models.user import User

STRONG_PASSWORD = "SenhaForte#123"


@pytest.fixture()
def client(monkeypatch, tmp_path):
    database_path = tmp_path / "jarvis_clinical_diagnoses_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    engine = get_engine()
    Base.metadata.create_all(engine)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def register_user(client: TestClient, email: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"nome": "Usuário Fictício", "email": email, "senha": STRONG_PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


def grant_role_to_email(email: str, role_code: str) -> None:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        ensure_default_rbac(session)
        user = session.query(User).filter_by(email=email).one()
        assign_role_to_user(session, user, role_code)
        session.commit()


def headers_for_role(client: TestClient, role_code: str, email: str | None = None) -> dict[str, str]:
    email = email or f"{role_code}-clinical-diagnoses@example.com"
    registration = register_user(client, email)
    grant_role_to_email(email, role_code)
    token = registration["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def headers_without_permission(email: str = "sem-permissao-clinical-diagnoses@example.com") -> dict[str, str]:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        ensure_default_rbac(session)
        user = User(nome="Usuário Sem Permissão", email=email, senha_hash=hash_password(STRONG_PASSWORD))
        session.add(user)
        session.commit()
        session.refresh(user)
        token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


def patient_payload(index: int = 1) -> dict:
    return {
        "nome_completo": f"Paciente Diagnóstico {index:02d}",
        "data_nascimento": "1990-01-15",
        "sexo": "feminino",
        "cpf": f"{index:011d}",
        "cns": f"{index:015d}",
        "email": f"paciente.diagnostico{index:02d}@example.com",
        "telefone": "11999990000",
    }


def professional_payload(index: int = 1) -> dict:
    return {
        "nome_completo": f"Profissional Diagnóstico {index:02d}",
        "cpf": f"{index:011d}",
        "data_nascimento": "1985-06-20",
        "email": f"profissional.diagnostico{index:02d}@example.com",
        "telefone": "11988887777",
        "conselho_tipo": "CRM",
        "conselho_numero": f"{950000 + index}",
        "conselho_uf": "SP",
        "especialidade_principal": "Clínica médica",
    }


def create_patient(client: TestClient, headers: dict[str, str], index: int = 1) -> dict:
    response = client.post("/api/v1/patients", headers=headers, json=patient_payload(index))
    assert response.status_code == 201
    return response.json()


def create_professional(client: TestClient, headers: dict[str, str], index: int = 1) -> dict:
    response = client.post("/api/v1/health-professionals", headers=headers, json=professional_payload(index))
    assert response.status_code == 201
    return response.json()


def create_appointment(client: TestClient, headers: dict[str, str], patient_id: int, professional_id: int, index: int = 1) -> dict:
    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "patient_id": patient_id,
            "professional_id": professional_id,
            "start_at": f"2026-10-{index:02d}T09:00:00",
            "end_at": f"2026-10-{index:02d}T09:30:00",
            "motivo": "Consulta diagnóstica",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_medical_record(client: TestClient, headers: dict[str, str], patient_id: int, professional_id: int, appointment_id: int | None = None) -> dict:
    response = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json={
            "patient_id": patient_id,
            "professional_id": professional_id,
            "appointment_id": appointment_id,
            "queixa_principal": "Avaliação diagnóstica",
            "historia_clinica": "Paciente em acompanhamento.",
            "conduta": "Registrar problema clínico.",
        },
    )
    assert response.status_code == 201
    return response.json()


def seed_context(client: TestClient, headers: dict[str, str], index: int = 1) -> tuple[dict, dict, dict, dict]:
    patient = create_patient(client, headers, index)
    professional = create_professional(client, headers, index)
    appointment = create_appointment(client, headers, patient["id"], professional["id"], index)
    medical_record = create_medical_record(client, headers, patient["id"], professional["id"], appointment["id"])
    return patient, professional, appointment, medical_record


def diagnosis_payload(patient_id: int, professional_id: int, appointment_id: int | None = None, medical_record_id: int | None = None, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "professional_id": professional_id,
        "appointment_id": appointment_id,
        "medical_record_id": medical_record_id,
        "cid10_codigo": " i10 ",
        "descricao": " Hipertensão arterial sistêmica ",
        "tipo": "hipotese",
        "status": "ativo",
        "data_inicio": "2026-10-01",
        "observacoes": "Problema registrado durante consulta.",
    }
    payload.update(overrides)
    return payload


def create_diagnosis(client: TestClient, headers: dict[str, str], patient: dict, professional: dict, appointment: dict | None = None, medical_record: dict | None = None, **overrides) -> dict:
    response = client.post(
        "/api/v1/clinical-diagnoses",
        headers=headers,
        json=diagnosis_payload(
            patient["id"],
            professional["id"],
            appointment["id"] if appointment else None,
            medical_record["id"] if medical_record else None,
            **overrides,
        ),
    )
    assert response.status_code == 201
    return response.json()


def test_create_clinical_diagnosis_with_links(client):
    headers = headers_for_role(client, "admin", "admin-diagnosis-create@example.com")
    patient, professional, appointment, medical_record = seed_context(client, headers, 1)

    diagnosis = create_diagnosis(client, headers, patient, professional, appointment, medical_record)

    assert diagnosis["patient_id"] == patient["id"]
    assert diagnosis["professional_id"] == professional["id"]
    assert diagnosis["appointment_id"] == appointment["id"]
    assert diagnosis["medical_record_id"] == medical_record["id"]
    assert diagnosis["cid10_codigo"] == "I10"
    assert diagnosis["descricao"] == "Hipertensão arterial sistêmica"
    assert diagnosis["tipo"] == "hipotese"
    assert diagnosis["status"] == "ativo"
    assert diagnosis["created_at"]


def test_list_get_and_update_clinical_diagnosis(client):
    headers = headers_for_role(client, "admin", "admin-diagnosis-list-update@example.com")
    patient, professional, appointment, medical_record = seed_context(client, headers, 2)
    diagnosis = create_diagnosis(client, headers, patient, professional, appointment, medical_record)

    detail_response = client.get(f"/api/v1/clinical-diagnoses/{diagnosis['id']}", headers=headers)
    list_response = client.get(
        "/api/v1/clinical-diagnoses",
        headers=headers,
        params={"patient_id": patient["id"], "status": "ativo", "cid10_codigo": "i10"},
    )
    update_response = client.patch(
        f"/api/v1/clinical-diagnoses/{diagnosis['id']}",
        headers=headers,
        json={"tipo": "confirmado", "status": "resolvido", "data_resolucao": "2026-10-10"},
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == diagnosis["id"]
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert update_response.status_code == 200
    assert update_response.json()["tipo"] == "confirmado"
    assert update_response.json()["status"] == "resolvido"


def test_create_rejects_invalid_links_and_date_range(client):
    headers = headers_for_role(client, "admin", "admin-diagnosis-invalid@example.com")
    patient_a, professional, _, medical_record = seed_context(client, headers, 3)
    patient_b = create_patient(client, headers, 4)

    invalid_patient_response = client.post(
        "/api/v1/clinical-diagnoses",
        headers=headers,
        json=diagnosis_payload(9999, professional["id"]),
    )
    mismatch_response = client.post(
        "/api/v1/clinical-diagnoses",
        headers=headers,
        json=diagnosis_payload(patient_b["id"], professional["id"], None, medical_record["id"]),
    )
    invalid_date_response = client.post(
        "/api/v1/clinical-diagnoses",
        headers=headers,
        json=diagnosis_payload(patient_a["id"], professional["id"], data_resolucao="2026-09-01"),
    )

    assert invalid_patient_response.status_code == 400
    assert mismatch_response.status_code == 400
    assert invalid_date_response.status_code == 422


def test_clinical_diagnosis_endpoints_require_permissions(client):
    admin_headers = headers_for_role(client, "admin", "admin-diagnosis-rbac@example.com")
    unauthorized_headers = headers_without_permission()
    patient, professional, appointment, medical_record = seed_context(client, admin_headers, 5)
    diagnosis = create_diagnosis(client, admin_headers, patient, professional, appointment, medical_record)

    create_response = client.post(
        "/api/v1/clinical-diagnoses",
        headers=unauthorized_headers,
        json=diagnosis_payload(patient["id"], professional["id"]),
    )
    list_response = client.get("/api/v1/clinical-diagnoses", headers=unauthorized_headers)
    detail_response = client.get(f"/api/v1/clinical-diagnoses/{diagnosis['id']}", headers=unauthorized_headers)
    update_response = client.patch(
        f"/api/v1/clinical-diagnoses/{diagnosis['id']}",
        headers=unauthorized_headers,
        json={"status": "resolvido"},
    )

    assert create_response.status_code == 403
    assert list_response.status_code == 403
    assert detail_response.status_code == 403
    assert update_response.status_code == 403


def test_medico_can_manage_clinical_diagnoses(client):
    admin_headers = headers_for_role(client, "admin", "admin-diagnosis-medico@example.com")
    medico_headers = headers_for_role(client, "medico", "medico-diagnosis-manage@example.com")
    patient, professional, appointment, medical_record = seed_context(client, admin_headers, 6)

    diagnosis = create_diagnosis(client, medico_headers, patient, professional, appointment, medical_record)
    update_response = client.patch(
        f"/api/v1/clinical-diagnoses/{diagnosis['id']}",
        headers=medico_headers,
        json={"observacoes": "Atualizado pelo médico."},
    )

    assert update_response.status_code == 200
    assert update_response.json()["observacoes"] == "Atualizado pelo médico."


def test_enfermeiro_can_read_but_not_manage_clinical_diagnoses(client):
    admin_headers = headers_for_role(client, "admin", "admin-diagnosis-enfermeiro@example.com")
    nurse_headers = headers_for_role(client, "enfermeiro", "enfermeiro-diagnosis-read@example.com")
    patient, professional, appointment, medical_record = seed_context(client, admin_headers, 7)
    diagnosis = create_diagnosis(client, admin_headers, patient, professional, appointment, medical_record)

    detail_response = client.get(f"/api/v1/clinical-diagnoses/{diagnosis['id']}", headers=nurse_headers)
    create_response = client.post(
        "/api/v1/clinical-diagnoses",
        headers=nurse_headers,
        json=diagnosis_payload(patient["id"], professional["id"]),
    )

    assert detail_response.status_code == 200
    assert create_response.status_code == 403
