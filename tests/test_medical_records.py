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
    database_path = tmp_path / "jarvis_medical_records_test.db"
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
    email = email or f"{role_code}-medical-records@example.com"
    registration = register_user(client, email)
    grant_role_to_email(email, role_code)
    token = registration["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def headers_without_permission(email: str = "sem-permissao-prontuarios@example.com") -> dict[str, str]:
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
        "nome_completo": f"Paciente Prontuário {index:02d}",
        "data_nascimento": "1990-01-15",
        "sexo": "feminino",
        "cpf": f"{index:011d}",
        "cns": f"{index:015d}",
        "email": f"paciente.prontuario{index:02d}@example.com",
        "telefone": "11999990000",
    }
    payload.update(overrides)
    return payload


def professional_payload(index: int = 1, **overrides) -> dict:
    payload = {
        "nome_completo": f"Profissional Prontuário {index:02d}",
        "cpf": f"{index:011d}",
        "data_nascimento": "1985-06-20",
        "email": f"profissional.prontuario{index:02d}@example.com",
        "telefone": "11988887777",
        "conselho_tipo": "CRM",
        "conselho_numero": f"{300000 + index}",
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


def appointment_payload(patient_id: int, professional_id: int, index: int = 1, **overrides) -> dict:
    start_hour = 8 + (index % 10)
    day = 1 + (index // 10)
    payload = {
        "patient_id": patient_id,
        "professional_id": professional_id,
        "start_at": f"2026-10-{day:02d}T{start_hour:02d}:00:00",
        "end_at": f"2026-10-{day:02d}T{start_hour:02d}:30:00",
        "motivo": "Consulta para registro clínico",
        "observacoes": "Observação administrativa fictícia.",
    }
    payload.update(overrides)
    return payload


def create_appointment(
    client: TestClient,
    headers: dict[str, str],
    patient_id: int,
    professional_id: int,
    index: int = 1,
    **overrides,
) -> dict:
    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=appointment_payload(patient_id, professional_id, index, **overrides),
    )
    assert response.status_code == 201
    return response.json()


def medical_record_payload(patient_id: int, professional_id: int, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "professional_id": professional_id,
        "queixa_principal": "Dor abdominal há 2 dias",
        "historia_clinica": "Paciente fictício relata sintomas leves.",
        "exame_fisico": "Bom estado geral, sem sinais de alarme.",
        "conduta": "Orientações gerais e retorno se piora.",
        "observacoes": "Registro clínico fictício para testes.",
    }
    payload.update(overrides)
    return payload


def seed_clinical_context(
    client: TestClient,
    headers: dict[str, str],
    index: int = 1,
    *,
    with_appointment: bool = True,
) -> tuple[dict, dict, dict | None]:
    patient = create_patient(client, headers, index)
    professional = create_professional(client, headers, index)
    appointment = None
    if with_appointment:
        appointment = create_appointment(client, headers, patient["id"], professional["id"], index)
    return patient, professional, appointment


def create_medical_record(
    client: TestClient,
    headers: dict[str, str],
    patient_id: int,
    professional_id: int,
    **overrides,
) -> dict:
    response = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json=medical_record_payload(patient_id, professional_id, **overrides),
    )
    assert response.status_code == 201
    return response.json()


def test_create_valid_medical_record_with_appointment(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-create@example.com")
    patient, professional, appointment = seed_clinical_context(client, headers, 1)

    record = create_medical_record(
        client,
        headers,
        patient["id"],
        professional["id"],
        appointment_id=appointment["id"],
    )

    assert record["patient_id"] == patient["id"]
    assert record["professional_id"] == professional["id"]
    assert record["appointment_id"] == appointment["id"]
    assert record["status"] == "draft"
    assert record["queixa_principal"] == "Dor abdominal há 2 dias"
    assert record["created_at"]
    assert record["updated_at"]


def test_create_without_appointment_is_allowed(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-no-appointment@example.com")
    patient, professional, _ = seed_clinical_context(client, headers, 2, with_appointment=False)

    record = create_medical_record(client, headers, patient["id"], professional["id"])

    assert record["appointment_id"] is None
    assert record["status"] == "draft"


def test_create_rejects_invalid_patient_and_professional(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-invalid-links@example.com")
    patient, professional, _ = seed_clinical_context(client, headers, 3, with_appointment=False)

    invalid_patient = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json=medical_record_payload(9999, professional["id"]),
    )
    invalid_professional = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json=medical_record_payload(patient["id"], 9999),
    )

    assert invalid_patient.status_code == 400
    assert invalid_patient.json()["detail"] == "Paciente não encontrado ou inativo."
    assert invalid_professional.status_code == 400
    assert invalid_professional.json()["detail"] == "Profissional de saúde não encontrado ou inativo."


def test_create_rejects_invalid_or_canceled_appointment(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-invalid-appointment@example.com")
    patient, professional, appointment = seed_clinical_context(client, headers, 4)

    missing_response = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json=medical_record_payload(patient["id"], professional["id"], appointment_id=9999),
    )
    cancel_response = client.post(
        f"/api/v1/appointments/{appointment['id']}/cancel",
        headers=headers,
        json={"cancel_reason": "Teste de cancelamento"},
    )
    canceled_response = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json=medical_record_payload(patient["id"], professional["id"], appointment_id=appointment["id"]),
    )

    assert missing_response.status_code == 400
    assert missing_response.json()["detail"] == "Consulta não encontrada ou cancelada."
    assert cancel_response.status_code == 200
    assert canceled_response.status_code == 400
    assert canceled_response.json()["detail"] == "Consulta não encontrada ou cancelada."


def test_create_rejects_mismatched_appointment(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-mismatch@example.com")
    patient_a, professional_a, appointment_a = seed_clinical_context(client, headers, 5)
    patient_b, _, _ = seed_clinical_context(client, headers, 6, with_appointment=False)

    response = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json=medical_record_payload(patient_b["id"], professional_a["id"], appointment_id=appointment_a["id"]),
    )

    assert patient_a["id"] != patient_b["id"]
    assert response.status_code == 400
    assert response.json()["detail"] == "Consulta não pertence ao paciente e profissional informados."


def test_create_rejects_duplicate_appointment_record(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-duplicate-appointment@example.com")
    patient, professional, appointment = seed_clinical_context(client, headers, 7)
    create_medical_record(client, headers, patient["id"], professional["id"], appointment_id=appointment["id"])

    response = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json=medical_record_payload(
            patient["id"],
            professional["id"],
            appointment_id=appointment["id"],
            queixa_principal="Outra queixa",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Consulta já vinculada a outro prontuário."


def test_list_medical_records_by_patient_professional_status_and_pagination(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-list@example.com")
    patient_a, professional_a, appointment_a = seed_clinical_context(client, headers, 8)
    patient_b, professional_b, appointment_b = seed_clinical_context(client, headers, 9)
    first = create_medical_record(
        client,
        headers,
        patient_a["id"],
        professional_a["id"],
        appointment_id=appointment_a["id"],
    )
    second = create_medical_record(
        client,
        headers,
        patient_b["id"],
        professional_b["id"],
        appointment_id=appointment_b["id"],
        queixa_principal="Cefaleia leve",
    )
    update_response = client.patch(
        f"/api/v1/medical-records/{second['id']}",
        headers=headers,
        json={"status": "finalized"},
    )
    assert update_response.status_code == 200

    patient_response = client.get(
        "/api/v1/medical-records",
        headers=headers,
        params={"patient_id": patient_a["id"]},
    )
    professional_response = client.get(
        "/api/v1/medical-records",
        headers=headers,
        params={"professional_id": professional_b["id"], "status": "finalized"},
    )
    appointment_response = client.get(
        "/api/v1/medical-records",
        headers=headers,
        params={"appointment_id": appointment_a["id"]},
    )
    paginated_response = client.get(
        "/api/v1/medical-records",
        headers=headers,
        params={"page": 1, "page_size": 1},
    )

    assert patient_response.status_code == 200
    assert patient_response.json()["total"] == 1
    assert patient_response.json()["items"][0]["id"] == first["id"]
    assert professional_response.status_code == 200
    assert professional_response.json()["total"] == 1
    assert professional_response.json()["items"][0]["id"] == second["id"]
    assert appointment_response.status_code == 200
    assert appointment_response.json()["items"][0]["appointment_id"] == appointment_a["id"]
    assert paginated_response.status_code == 200
    assert paginated_response.json()["total"] == 2
    assert len(paginated_response.json()["items"]) == 1


def test_read_medical_record_by_id(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-read@example.com")
    patient, professional, appointment = seed_clinical_context(client, headers, 10)
    record = create_medical_record(
        client,
        headers,
        patient["id"],
        professional["id"],
        appointment_id=appointment["id"],
    )

    response = client.get(f"/api/v1/medical-records/{record['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == record["id"]
    assert response.json()["appointment_id"] == appointment["id"]


def test_update_medical_record_fields_status_and_appointment(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-update@example.com")
    patient, professional, _ = seed_clinical_context(client, headers, 11, with_appointment=False)
    appointment = create_appointment(client, headers, patient["id"], professional["id"], 11)
    record = create_medical_record(client, headers, patient["id"], professional["id"])

    response = client.patch(
        f"/api/v1/medical-records/{record['id']}",
        headers=headers,
        json={
            "appointment_id": appointment["id"],
            "status": "finalized",
            "queixa_principal": "Dor lombar crônica",
            "historia_clinica": "Evolução clínica atualizada.",
            "exame_fisico": "Exame físico sem alterações relevantes.",
            "conduta": "Solicitado acompanhamento ambulatorial.",
            "observacoes": "Atualizado em teste.",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["appointment_id"] == appointment["id"]
    assert updated["status"] == "finalized"
    assert updated["queixa_principal"] == "Dor lombar crônica"
    assert updated["conduta"] == "Solicitado acompanhamento ambulatorial."


def test_update_rejects_duplicate_appointment(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-update-duplicate@example.com")
    patient_a, professional_a, appointment_a = seed_clinical_context(client, headers, 12)
    patient_b, professional_b, _ = seed_clinical_context(client, headers, 13, with_appointment=False)
    first = create_medical_record(
        client,
        headers,
        patient_a["id"],
        professional_a["id"],
        appointment_id=appointment_a["id"],
    )
    second = create_medical_record(client, headers, patient_b["id"], professional_b["id"])

    response = client.patch(
        f"/api/v1/medical-records/{second['id']}",
        headers=headers,
        json={
            "patient_id": patient_a["id"],
            "professional_id": professional_a["id"],
            "appointment_id": appointment_a["id"],
        },
    )

    assert first["appointment_id"] == appointment_a["id"]
    assert response.status_code == 409
    assert response.json()["detail"] == "Consulta já vinculada a outro prontuário."


@pytest.mark.parametrize("role_code", ["medico", "enfermeiro"])
def test_clinical_roles_can_create_read_and_update_medical_records(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-setup-{role_code}-prontuario@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-prontuario@example.com")
    patient, professional, appointment = seed_clinical_context(client, admin_headers, 20 if role_code == "medico" else 21)

    create_response = client.post(
        "/api/v1/medical-records",
        headers=role_headers,
        json=medical_record_payload(patient["id"], professional["id"], appointment_id=appointment["id"]),
    )
    assert create_response.status_code == 201
    record_id = create_response.json()["id"]

    read_response = client.get(f"/api/v1/medical-records/{record_id}", headers=role_headers)
    update_response = client.patch(
        f"/api/v1/medical-records/{record_id}",
        headers=role_headers,
        json={"status": "amended", "observacoes": "Revisado pelo perfil clínico."},
    )

    assert read_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "amended"


@pytest.mark.parametrize("role_code", ["recepcionista", "laboratorio", "farmacia", "paciente"])
def test_roles_without_prontuarios_permissions_are_forbidden(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-setup-forbidden-{role_code}@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-sem-prontuario@example.com")
    patient, professional, appointment = seed_clinical_context(client, admin_headers, 30 + len(role_code))
    record = create_medical_record(
        client,
        admin_headers,
        patient["id"],
        professional["id"],
        appointment_id=appointment["id"],
    )

    create_response = client.post(
        "/api/v1/medical-records",
        headers=role_headers,
        json=medical_record_payload(patient["id"], professional["id"]),
    )
    list_response = client.get("/api/v1/medical-records", headers=role_headers)
    read_response = client.get(f"/api/v1/medical-records/{record['id']}", headers=role_headers)
    update_response = client.patch(
        f"/api/v1/medical-records/{record['id']}",
        headers=role_headers,
        json={"status": "finalized"},
    )

    assert create_response.status_code == 403
    assert list_response.status_code == 403
    assert read_response.status_code == 403
    assert update_response.status_code == 403


def test_user_without_permission_is_forbidden(client):
    admin_headers = headers_for_role(client, "admin", "admin-prontuario-no-permission-setup@example.com")
    headers = headers_without_permission()
    patient, professional, appointment = seed_clinical_context(client, admin_headers, 40)
    record = create_medical_record(
        client,
        admin_headers,
        patient["id"],
        professional["id"],
        appointment_id=appointment["id"],
    )

    create_response = client.post(
        "/api/v1/medical-records",
        headers=headers,
        json=medical_record_payload(patient["id"], professional["id"]),
    )
    read_response = client.get(f"/api/v1/medical-records/{record['id']}", headers=headers)

    assert create_response.status_code == 403
    assert create_response.json()["detail"]["required_permissions"] == ["prontuarios:escrever"]
    assert read_response.status_code == 403
    assert read_response.json()["detail"]["required_permissions"] == ["prontuarios:ler"]


def test_missing_medical_record_returns_404(client):
    headers = headers_for_role(client, "admin", "admin-prontuario-missing@example.com")

    get_response = client.get("/api/v1/medical-records/9999", headers=headers)
    patch_response = client.patch(
        "/api/v1/medical-records/9999",
        headers=headers,
        json={"status": "finalized"},
    )

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Prontuário médico não encontrado."
    assert patch_response.status_code == 404
    assert patch_response.json()["detail"] == "Prontuário médico não encontrado."
