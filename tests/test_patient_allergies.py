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
    database_path = tmp_path / "jarvis_patient_allergies_test.db"
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
    email = email or f"{role_code}-patient-allergies@example.com"
    registration = register_user(client, email)
    grant_role_to_email(email, role_code)
    token = registration["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def headers_without_permission(email: str = "sem-permissao-patient-allergies@example.com") -> dict[str, str]:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        ensure_default_rbac(session)
        user = User(
            nome="Usuário Sem Permissão",
            email=email,
            senha_hash=hash_password(STRONG_PASSWORD),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


def patient_payload(index: int = 1) -> dict:
    return {
        "nome_completo": f"Paciente Alergia {index:02d}",
        "data_nascimento": "1990-01-15",
        "sexo": "feminino",
        "cpf": f"{index:011d}",
        "cns": f"{index:015d}",
        "email": f"paciente.alergia{index:02d}@example.com",
        "telefone": "11999990000",
    }


def professional_payload(index: int = 1) -> dict:
    return {
        "nome_completo": f"Profissional Alergia {index:02d}",
        "cpf": f"{index:011d}",
        "data_nascimento": "1985-06-20",
        "email": f"profissional.alergia{index:02d}@example.com",
        "telefone": "11988887777",
        "conselho_tipo": "CRM",
        "conselho_numero": f"{800000 + index}",
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


def create_medical_record(client: TestClient, headers: dict[str, str], patient_id: int, professional_id: int) -> dict:
    response = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json={
            "patient_id": patient_id,
            "professional_id": professional_id,
            "queixa_principal": "Avaliação de alergia",
            "historia_clinica": "Paciente relata reação prévia.",
            "conduta": "Registrar alerta de segurança.",
            "observacoes": "Registro clínico fictício para testes.",
        },
    )
    assert response.status_code == 201
    return response.json()


def seed_context(client: TestClient, headers: dict[str, str], index: int = 1, with_record: bool = True) -> tuple[dict, dict, dict | None]:
    patient = create_patient(client, headers, index)
    professional = create_professional(client, headers, index)
    medical_record = create_medical_record(client, headers, patient["id"], professional["id"]) if with_record else None
    return patient, professional, medical_record


def allergy_payload(patient_id: int, professional_id: int, medical_record_id: int | None = None, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "professional_id": professional_id,
        "medical_record_id": medical_record_id,
        "tipo": "allergy",
        "categoria": "medication",
        "substancia": " Dipirona ",
        "reacao": "Urticária",
        "gravidade": "moderate",
        "observado_em": "2026-08-14",
        "observacoes": "Alergia referida pelo paciente.",
    }
    payload.update(overrides)
    return payload


def create_allergy(client: TestClient, headers: dict[str, str], patient: dict, professional: dict, medical_record: dict | None = None, **overrides) -> dict:
    response = client.post(
        "/api/v1/patient-allergies",
        headers=headers,
        json=allergy_payload(
            patient["id"],
            professional["id"],
            medical_record["id"] if medical_record else None,
            **overrides,
        ),
    )
    assert response.status_code == 201
    return response.json()


def test_create_patient_allergy_with_medical_record(client):
    headers = headers_for_role(client, "admin", "admin-allergy-create@example.com")
    patient, professional, medical_record = seed_context(client, headers, 1)

    allergy = create_allergy(client, headers, patient, professional, medical_record)

    assert allergy["patient_id"] == patient["id"]
    assert allergy["professional_id"] == professional["id"]
    assert allergy["medical_record_id"] == medical_record["id"]
    assert allergy["status"] == "active"
    assert allergy["substancia"] == "Dipirona"
    assert allergy["categoria"] == "medication"
    assert allergy["created_at"]
    assert allergy["updated_at"]


def test_list_get_and_update_patient_allergy(client):
    headers = headers_for_role(client, "admin", "admin-allergy-list-update@example.com")
    patient, professional, medical_record = seed_context(client, headers, 2)
    allergy = create_allergy(client, headers, patient, professional, medical_record)

    detail_response = client.get(f"/api/v1/patient-allergies/{allergy['id']}", headers=headers)
    list_response = client.get(
        "/api/v1/patient-allergies",
        headers=headers,
        params={"patient_id": patient["id"], "status": "active", "substancia": "dip"},
    )
    update_response = client.patch(
        f"/api/v1/patient-allergies/{allergy['id']}",
        headers=headers,
        json={"status": "inactive", "gravidade": "severe", "reacao": "Anafilaxia"},
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == allergy["id"]
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "inactive"
    assert update_response.json()["gravidade"] == "severe"
    assert update_response.json()["reacao"] == "Anafilaxia"


def test_create_rejects_invalid_patient_and_medical_record_mismatch(client):
    headers = headers_for_role(client, "admin", "admin-allergy-invalid-links@example.com")
    patient_a, professional, medical_record = seed_context(client, headers, 3)
    patient_b = create_patient(client, headers, 4)

    invalid_patient_response = client.post(
        "/api/v1/patient-allergies",
        headers=headers,
        json=allergy_payload(9999, professional["id"]),
    )
    mismatch_response = client.post(
        "/api/v1/patient-allergies",
        headers=headers,
        json=allergy_payload(patient_b["id"], professional["id"], medical_record["id"]),
    )

    assert patient_a["id"] != patient_b["id"]
    assert invalid_patient_response.status_code == 400
    assert mismatch_response.status_code == 400


def test_patient_allergy_endpoints_require_allergy_permissions(client):
    admin_headers = headers_for_role(client, "admin", "admin-allergy-rbac@example.com")
    unauthorized_headers = headers_without_permission()
    patient, professional, medical_record = seed_context(client, admin_headers, 5)
    allergy = create_allergy(client, admin_headers, patient, professional, medical_record)

    create_response = client.post(
        "/api/v1/patient-allergies",
        headers=unauthorized_headers,
        json=allergy_payload(patient["id"], professional["id"]),
    )
    list_response = client.get("/api/v1/patient-allergies", headers=unauthorized_headers)
    detail_response = client.get(f"/api/v1/patient-allergies/{allergy['id']}", headers=unauthorized_headers)
    update_response = client.patch(
        f"/api/v1/patient-allergies/{allergy['id']}",
        headers=unauthorized_headers,
        json={"status": "inactive"},
    )

    assert create_response.status_code == 403
    assert list_response.status_code == 403
    assert detail_response.status_code == 403
    assert update_response.status_code == 403


@pytest.mark.parametrize("role_code", ["medico", "enfermeiro"])
def test_clinical_roles_can_manage_patient_allergies(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-allergy-{role_code}@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-allergy-manage@example.com")
    patient, professional, medical_record = seed_context(client, admin_headers, 6 if role_code == "medico" else 7)

    allergy = create_allergy(client, role_headers, patient, professional, medical_record)
    update_response = client.patch(
        f"/api/v1/patient-allergies/{allergy['id']}",
        headers=role_headers,
        json={"observacoes": "Atualizado pelo perfil clínico."},
    )

    assert update_response.status_code == 200
    assert update_response.json()["observacoes"] == "Atualizado pelo perfil clínico."


def test_pharmacy_can_read_but_not_manage_patient_allergies(client):
    admin_headers = headers_for_role(client, "admin", "admin-allergy-pharmacy@example.com")
    pharmacy_headers = headers_for_role(client, "farmacia", "farmacia-allergy-read@example.com")
    patient, professional, medical_record = seed_context(client, admin_headers, 8)
    allergy = create_allergy(client, admin_headers, patient, professional, medical_record)

    detail_response = client.get(f"/api/v1/patient-allergies/{allergy['id']}", headers=pharmacy_headers)
    create_response = client.post(
        "/api/v1/patient-allergies",
        headers=pharmacy_headers,
        json=allergy_payload(patient["id"], professional["id"]),
    )

    assert detail_response.status_code == 200
    assert create_response.status_code == 403
