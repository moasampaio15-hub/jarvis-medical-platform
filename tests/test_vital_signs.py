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
    database_path = tmp_path / "jarvis_vital_signs_test.db"
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
    email = email or f"{role_code}-vital-signs@example.com"
    registration = register_user(client, email)
    grant_role_to_email(email, role_code)
    token = registration["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def headers_without_permission(email: str = "sem-permissao-vital-signs@example.com") -> dict[str, str]:
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
        "nome_completo": f"Paciente Triagem {index:02d}",
        "data_nascimento": "1990-01-15",
        "sexo": "feminino",
        "cpf": f"{index:011d}",
        "cns": f"{index:015d}",
        "email": f"paciente.triagem{index:02d}@example.com",
        "telefone": "11999990000",
    }


def professional_payload(index: int = 1) -> dict:
    return {
        "nome_completo": f"Profissional Triagem {index:02d}",
        "cpf": f"{index:011d}",
        "data_nascimento": "1985-06-20",
        "email": f"profissional.triagem{index:02d}@example.com",
        "telefone": "11988887777",
        "conselho_tipo": "COREN",
        "conselho_numero": f"{900000 + index}",
        "conselho_uf": "SP",
        "especialidade_principal": "Enfermagem",
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
            "start_at": f"2026-09-{index:02d}T09:00:00",
            "end_at": f"2026-09-{index:02d}T09:30:00",
            "motivo": "Triagem clínica",
            "observacoes": "Consulta fictícia para testes.",
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
            "queixa_principal": "Triagem inicial",
            "historia_clinica": "Paciente encaminhado para avaliação.",
            "conduta": "Registrar sinais vitais.",
            "observacoes": "Registro clínico fictício para testes.",
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


def vital_sign_payload(patient_id: int, professional_id: int, appointment_id: int | None = None, medical_record_id: int | None = None, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "professional_id": professional_id,
        "appointment_id": appointment_id,
        "medical_record_id": medical_record_id,
        "recorded_at": "2026-09-01T09:05:00",
        "pressao_sistolica": 120,
        "pressao_diastolica": 80,
        "frequencia_cardiaca": 76,
        "frequencia_respiratoria": 18,
        "temperatura_c": 36.7,
        "spo2": 98,
        "peso_kg": 72.5,
        "altura_cm": 175,
        "glicemia_capilar": 95,
        "dor_escala": 3,
        "observacoes": " Triagem inicial sem queixas adicionais. ",
    }
    payload.update(overrides)
    return payload


def create_vital_sign(client: TestClient, headers: dict[str, str], patient: dict, professional: dict, appointment: dict | None = None, medical_record: dict | None = None, **overrides) -> dict:
    response = client.post(
        "/api/v1/vital-signs",
        headers=headers,
        json=vital_sign_payload(
            patient["id"],
            professional["id"],
            appointment["id"] if appointment else None,
            medical_record["id"] if medical_record else None,
            **overrides,
        ),
    )
    assert response.status_code == 201
    return response.json()


def test_create_vital_sign_with_links_and_calculated_imc(client):
    headers = headers_for_role(client, "admin", "admin-vital-create@example.com")
    patient, professional, appointment, medical_record = seed_context(client, headers, 1)

    vital_sign = create_vital_sign(client, headers, patient, professional, appointment, medical_record)

    assert vital_sign["patient_id"] == patient["id"]
    assert vital_sign["professional_id"] == professional["id"]
    assert vital_sign["appointment_id"] == appointment["id"]
    assert vital_sign["medical_record_id"] == medical_record["id"]
    assert vital_sign["imc"] == 23.67
    assert vital_sign["observacoes"] == "Triagem inicial sem queixas adicionais."
    assert vital_sign["created_at"]
    assert vital_sign["updated_at"]


def test_list_get_and_update_vital_sign(client):
    headers = headers_for_role(client, "admin", "admin-vital-list-update@example.com")
    patient, professional, appointment, medical_record = seed_context(client, headers, 2)
    vital_sign = create_vital_sign(client, headers, patient, professional, appointment, medical_record)

    detail_response = client.get(f"/api/v1/vital-signs/{vital_sign['id']}", headers=headers)
    list_response = client.get(
        "/api/v1/vital-signs",
        headers=headers,
        params={"patient_id": patient["id"], "appointment_id": appointment["id"]},
    )
    update_response = client.patch(
        f"/api/v1/vital-signs/{vital_sign['id']}",
        headers=headers,
        json={"peso_kg": 80, "altura_cm": 180, "dor_escala": 0, "observacoes": "Sem dor."},
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == vital_sign["id"]
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert update_response.status_code == 200
    assert update_response.json()["imc"] == 24.69
    assert update_response.json()["dor_escala"] == 0


def test_create_rejects_invalid_appointment_and_medical_record_mismatch(client):
    headers = headers_for_role(client, "admin", "admin-vital-invalid-links@example.com")
    patient_a, professional, appointment, medical_record = seed_context(client, headers, 3)
    patient_b = create_patient(client, headers, 4)

    invalid_appointment_response = client.post(
        "/api/v1/vital-signs",
        headers=headers,
        json=vital_sign_payload(patient_a["id"], professional["id"], 9999),
    )
    mismatch_response = client.post(
        "/api/v1/vital-signs",
        headers=headers,
        json=vital_sign_payload(patient_b["id"], professional["id"], None, medical_record["id"]),
    )

    assert appointment["id"]
    assert invalid_appointment_response.status_code == 400
    assert mismatch_response.status_code == 400


def test_create_validates_measurement_ranges(client):
    headers = headers_for_role(client, "admin", "admin-vital-validation@example.com")
    patient, professional, appointment, medical_record = seed_context(client, headers, 5)

    response = client.post(
        "/api/v1/vital-signs",
        headers=headers,
        json=vital_sign_payload(patient["id"], professional["id"], appointment["id"], medical_record["id"], dor_escala=11),
    )

    assert response.status_code == 422


def test_vital_sign_endpoints_require_permissions(client):
    admin_headers = headers_for_role(client, "admin", "admin-vital-rbac@example.com")
    unauthorized_headers = headers_without_permission()
    patient, professional, appointment, medical_record = seed_context(client, admin_headers, 6)
    vital_sign = create_vital_sign(client, admin_headers, patient, professional, appointment, medical_record)

    create_response = client.post(
        "/api/v1/vital-signs",
        headers=unauthorized_headers,
        json=vital_sign_payload(patient["id"], professional["id"]),
    )
    list_response = client.get("/api/v1/vital-signs", headers=unauthorized_headers)
    detail_response = client.get(f"/api/v1/vital-signs/{vital_sign['id']}", headers=unauthorized_headers)
    update_response = client.patch(
        f"/api/v1/vital-signs/{vital_sign['id']}",
        headers=unauthorized_headers,
        json={"dor_escala": 1},
    )

    assert create_response.status_code == 403
    assert list_response.status_code == 403
    assert detail_response.status_code == 403
    assert update_response.status_code == 403


@pytest.mark.parametrize("role_code", ["medico", "enfermeiro"])
def test_clinical_roles_can_manage_vital_signs(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-vital-{role_code}@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-vital-manage@example.com")
    patient, professional, appointment, medical_record = seed_context(client, admin_headers, 7 if role_code == "medico" else 8)

    vital_sign = create_vital_sign(client, role_headers, patient, professional, appointment, medical_record)
    update_response = client.patch(
        f"/api/v1/vital-signs/{vital_sign['id']}",
        headers=role_headers,
        json={"observacoes": "Atualizado pelo perfil clínico."},
    )

    assert update_response.status_code == 200
    assert update_response.json()["observacoes"] == "Atualizado pelo perfil clínico."
