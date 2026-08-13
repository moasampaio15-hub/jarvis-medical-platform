import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.auth.authorization import assign_role_to_user, ensure_default_rbac
from app.auth.password import hash_password
from app.database.base import Base
from app.database.connection import get_engine, get_session_factory
from app.main import app
from app.models.appointment import Appointment
from app.models.user import User

STRONG_PASSWORD = "SenhaForte#123"


@pytest.fixture()
def client(monkeypatch, tmp_path):
    database_path = tmp_path / "jarvis_appointments_test.db"
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
    email = email or f"{role_code}@example.com"
    registration = register_user(client, email)
    grant_role_to_email(email, role_code)
    token = registration["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def headers_without_permission(email: str = "sem-permissao-consultas@example.com") -> dict[str, str]:
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


def patient_payload(index: int = 1, **overrides) -> dict:
    payload = {
        "nome_completo": f"Paciente Agenda {index:02d}",
        "data_nascimento": "1990-01-15",
        "sexo": "feminino",
        "cpf": f"{index:011d}",
        "cns": f"{index:015d}",
        "email": f"paciente.agenda{index:02d}@example.com",
        "telefone": "11999990000",
    }
    payload.update(overrides)
    return payload


def professional_payload(index: int = 1, **overrides) -> dict:
    payload = {
        "nome_completo": f"Profissional Agenda {index:02d}",
        "cpf": f"{index:011d}",
        "data_nascimento": "1985-06-20",
        "email": f"profissional.agenda{index:02d}@example.com",
        "telefone": "11988887777",
        "conselho_tipo": "CRM",
        "conselho_numero": f"{200000 + index}",
        "conselho_uf": "SP",
        "especialidade_principal": "Clínica médica",
    }
    payload.update(overrides)
    return payload


def create_patient(client: TestClient, headers: dict[str, str], index: int = 1, **overrides) -> dict:
    response = client.post("/api/v1/patients", headers=headers, json=patient_payload(index, **overrides))
    assert response.status_code == 201
    return response.json()


def create_professional(client: TestClient, headers: dict[str, str], index: int = 1, **overrides) -> dict:
    response = client.post(
        "/api/v1/health-professionals",
        headers=headers,
        json=professional_payload(index, **overrides),
    )
    assert response.status_code == 201
    return response.json()


def appointment_payload(patient_id: int, professional_id: int, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "professional_id": professional_id,
        "start_at": "2026-09-01T09:00:00",
        "end_at": "2026-09-01T09:30:00",
        "motivo": "Consulta de rotina",
        "observacoes": "Observação administrativa fictícia.",
    }
    payload.update(overrides)
    return payload


def seed_patient_and_professional(client: TestClient, headers: dict[str, str], index: int = 1) -> tuple[dict, dict]:
    patient = create_patient(client, headers, index)
    professional = create_professional(client, headers, index)
    return patient, professional


def create_appointment(
    client: TestClient,
    headers: dict[str, str],
    patient_id: int,
    professional_id: int,
    **overrides,
) -> dict:
    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(patient_id, professional_id, **overrides),
    )
    assert response.status_code == 201
    return response.json()


def test_create_valid_appointment(client):
    headers = headers_for_role(client, "admin", "admin-appointment-create@example.com")
    patient, professional = seed_patient_and_professional(client, headers, 1)

    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(patient["id"], professional["id"]),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["patient_id"] == patient["id"]
    assert body["professional_id"] == professional["id"]
    assert body["status"] == "scheduled"
    assert body["start_at"].startswith("2026-09-01T09:00:00")
    assert body["end_at"].startswith("2026-09-01T09:30:00")


def test_create_rejects_invalid_patient_and_professional(client):
    headers = headers_for_role(client, "admin", "admin-appointment-invalid@example.com")
    patient, professional = seed_patient_and_professional(client, headers, 1)

    invalid_patient = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(9999, professional["id"]),
    )
    invalid_professional = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(patient["id"], 9999),
    )

    assert invalid_patient.status_code == 400
    assert invalid_patient.json()["detail"] == "Paciente não encontrado ou inativo."
    assert invalid_professional.status_code == 400
    assert invalid_professional.json()["detail"] == "Profissional de saúde não encontrado ou inativo."


def test_create_rejects_professional_time_conflict(client):
    headers = headers_for_role(client, "admin", "admin-appointment-prof-conflict@example.com")
    first_patient, professional = seed_patient_and_professional(client, headers, 1)
    second_patient = create_patient(client, headers, 2)
    create_appointment(client, headers, first_patient["id"], professional["id"])

    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(
            second_patient["id"],
            professional["id"],
            start_at="2026-09-01T09:15:00",
            end_at="2026-09-01T09:45:00",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Conflito de horário para o profissional de saúde."


def test_create_rejects_patient_time_conflict(client):
    headers = headers_for_role(client, "admin", "admin-appointment-patient-conflict@example.com")
    patient, first_professional = seed_patient_and_professional(client, headers, 1)
    second_professional = create_professional(client, headers, 2)
    create_appointment(client, headers, patient["id"], first_professional["id"])

    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(
            patient["id"],
            second_professional["id"],
            start_at="2026-09-01T09:15:00",
            end_at="2026-09-01T09:45:00",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Conflito de horário para o paciente."


def test_adjacent_appointments_are_allowed(client):
    headers = headers_for_role(client, "admin", "admin-appointment-adjacent@example.com")
    first_patient, professional = seed_patient_and_professional(client, headers, 1)
    second_patient = create_patient(client, headers, 2)
    create_appointment(client, headers, first_patient["id"], professional["id"])

    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(
            second_patient["id"],
            professional["id"],
            start_at="2026-09-01T09:30:00",
            end_at="2026-09-01T10:00:00",
        ),
    )

    assert response.status_code == 201
    assert response.json()["start_at"].startswith("2026-09-01T09:30:00")


def test_list_appointments_by_period_and_pagination(client):
    headers = headers_for_role(client, "admin", "admin-appointment-period@example.com")
    first_patient, professional = seed_patient_and_professional(client, headers, 1)
    second_patient = create_patient(client, headers, 2)
    third_patient = create_patient(client, headers, 3)
    create_appointment(client, headers, first_patient["id"], professional["id"], start_at="2026-09-01T09:00:00", end_at="2026-09-01T09:30:00")
    create_appointment(client, headers, second_patient["id"], professional["id"], start_at="2026-09-01T10:00:00", end_at="2026-09-01T10:30:00")
    create_appointment(client, headers, third_patient["id"], professional["id"], start_at="2026-10-01T09:00:00", end_at="2026-10-01T09:30:00")

    response = client.get(
        "/api/v1/appointments?start_at=2026-09-01T00:00:00&end_at=2026-09-30T23:59:59&page=2&page_size=1",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 2
    assert body["page_size"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["patient_id"] == second_patient["id"]


def test_search_appointments_by_patient_professional_and_status(client):
    headers = headers_for_role(client, "admin", "admin-appointment-search@example.com")
    first_patient, first_professional = seed_patient_and_professional(client, headers, 1)
    second_patient = create_patient(client, headers, 2)
    second_professional = create_professional(client, headers, 2)
    first = create_appointment(client, headers, first_patient["id"], first_professional["id"])
    second = create_appointment(
        client,
        headers,
        second_patient["id"],
        second_professional["id"],
        start_at="2026-09-01T10:00:00",
        end_at="2026-09-01T10:30:00",
    )
    client.patch(f"/api/v1/appointments/{second['id']}/status", headers=headers, json={"status": "confirmed"})

    by_patient = client.get(f"/api/v1/appointments?patient_id={first_patient['id']}", headers=headers)
    by_professional = client.get(
        f"/api/v1/appointments?professional_id={second_professional['id']}", headers=headers
    )
    by_status = client.get("/api/v1/appointments?status=confirmed", headers=headers)

    assert by_patient.status_code == 200
    assert by_patient.json()["total"] == 1
    assert by_patient.json()["items"][0]["id"] == first["id"]
    assert by_professional.status_code == 200
    assert by_professional.json()["total"] == 1
    assert by_professional.json()["items"][0]["id"] == second["id"]
    assert by_status.status_code == 200
    assert by_status.json()["total"] == 1
    assert by_status.json()["items"][0]["id"] == second["id"]


def test_read_appointment_by_id(client):
    headers = headers_for_role(client, "admin", "admin-appointment-read@example.com")
    patient, professional = seed_patient_and_professional(client, headers, 1)
    appointment = create_appointment(client, headers, patient["id"], professional["id"])

    response = client.get(f"/api/v1/appointments/{appointment['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == appointment["id"]
    assert response.json()["patient_id"] == patient["id"]


def test_update_appointment_status(client):
    headers = headers_for_role(client, "admin", "admin-appointment-status@example.com")
    patient, professional = seed_patient_and_professional(client, headers, 1)
    appointment = create_appointment(client, headers, patient["id"], professional["id"])

    response = client.patch(
        f"/api/v1/appointments/{appointment['id']}/status",
        headers=headers,
        json={"status": "confirmed"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_cancel_appointment_is_logical_and_releases_time_slot(client):
    headers = headers_for_role(client, "admin", "admin-appointment-cancel@example.com")
    first_patient, professional = seed_patient_and_professional(client, headers, 1)
    second_patient = create_patient(client, headers, 2)
    appointment = create_appointment(client, headers, first_patient["id"], professional["id"])

    cancel_response = client.post(
        f"/api/v1/appointments/{appointment['id']}/cancel",
        headers=headers,
        json={"cancel_reason": "Solicitação do paciente"},
    )
    replacement_response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(second_patient["id"], professional["id"]),
    )

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "canceled"
    assert cancel_response.json()["cancel_reason"] == "Solicitação do paciente"
    assert cancel_response.json()["canceled_at"] is not None
    assert replacement_response.status_code == 201

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        persisted = session.get(Appointment, appointment["id"])
        assert persisted is not None
        assert persisted.status == "canceled"


@pytest.mark.parametrize("role_code", ["medico", "recepcionista"])
def test_roles_with_consultas_gerenciar_can_create_update_and_cancel(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-appointment-{role_code}-seed@example.com")
    patient, professional = seed_patient_and_professional(client, admin_headers, 1)
    headers = headers_for_role(client, role_code, f"{role_code}-appointment-manage@example.com")

    appointment = create_appointment(client, headers, patient["id"], professional["id"])
    update_response = client.patch(
        f"/api/v1/appointments/{appointment['id']}/status",
        headers=headers,
        json={"status": "confirmed"},
    )
    cancel_response = client.post(
        f"/api/v1/appointments/{appointment['id']}/cancel",
        headers=headers,
        json={"cancel_reason": "Teste RBAC"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["status"] == "confirmed"
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "canceled"


def test_enfermeiro_can_read_but_cannot_manage_appointments(client):
    admin_headers = headers_for_role(client, "admin", "admin-appointment-nurse-seed@example.com")
    patient, professional = seed_patient_and_professional(client, admin_headers, 1)
    appointment = create_appointment(client, admin_headers, patient["id"], professional["id"])
    headers = headers_for_role(client, "enfermeiro", "enfermeiro-appointment-read@example.com")

    read_response = client.get(f"/api/v1/appointments/{appointment['id']}", headers=headers)
    create_response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(patient["id"], professional["id"], start_at="2026-09-01T10:00:00", end_at="2026-09-01T10:30:00"),
    )
    update_response = client.patch(
        f"/api/v1/appointments/{appointment['id']}/status",
        headers=headers,
        json={"status": "confirmed"},
    )
    cancel_response = client.post(
        f"/api/v1/appointments/{appointment['id']}/cancel",
        headers=headers,
        json={"cancel_reason": "Teste"},
    )

    assert read_response.status_code == 200
    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert cancel_response.status_code == 403


@pytest.mark.parametrize("role_code", ["laboratorio", "farmacia", "paciente"])
def test_roles_without_consultas_permissions_are_forbidden(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-appointment-{role_code}-seed@example.com")
    patient, professional = seed_patient_and_professional(client, admin_headers, 1)
    appointment = create_appointment(client, admin_headers, patient["id"], professional["id"])
    headers = headers_for_role(client, role_code, f"{role_code}-appointment-forbidden@example.com")

    read_response = client.get(f"/api/v1/appointments/{appointment['id']}", headers=headers)
    create_response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(patient["id"], professional["id"], start_at="2026-09-01T10:00:00", end_at="2026-09-01T10:30:00"),
    )

    assert read_response.status_code == 403
    assert create_response.status_code == 403


def test_user_without_permission_is_forbidden(client):
    admin_headers = headers_for_role(client, "admin", "admin-appointment-no-permission-seed@example.com")
    patient, professional = seed_patient_and_professional(client, admin_headers, 1)
    headers = headers_without_permission()

    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(patient["id"], professional["id"]),
    )

    assert response.status_code == 403


def test_missing_appointment_returns_404(client):
    headers = headers_for_role(client, "admin", "admin-appointment-missing@example.com")

    read_response = client.get("/api/v1/appointments/9999", headers=headers)
    update_response = client.patch("/api/v1/appointments/9999/status", headers=headers, json={"status": "confirmed"})
    cancel_response = client.post("/api/v1/appointments/9999/cancel", headers=headers, json={"cancel_reason": "Teste"})

    assert read_response.status_code == 404
    assert update_response.status_code == 404
    assert cancel_response.status_code == 404
