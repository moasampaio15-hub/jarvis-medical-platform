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
    database_path = tmp_path / "jarvis_prescriptions_test.db"
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
    email = email or f"{role_code}-prescriptions@example.com"
    registration = register_user(client, email)
    grant_role_to_email(email, role_code)
    token = registration["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def headers_without_permission(email: str = "sem-permissao-prescriptions@example.com") -> dict[str, str]:
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
        "nome_completo": f"Paciente Prescrição {index:02d}",
        "data_nascimento": "1990-01-15",
        "sexo": "feminino",
        "cpf": f"{index:011d}",
        "cns": f"{index:015d}",
        "email": f"paciente.prescricao{index:02d}@example.com",
        "telefone": "11999990000",
    }
    payload.update(overrides)
    return payload


def professional_payload(index: int = 1, **overrides) -> dict:
    payload = {
        "nome_completo": f"Profissional Prescrição {index:02d}",
        "cpf": f"{index:011d}",
        "data_nascimento": "1985-06-20",
        "email": f"profissional.prescricao{index:02d}@example.com",
        "telefone": "11988887777",
        "conselho_tipo": "CRM",
        "conselho_numero": f"{500000 + index}",
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
        "start_at": f"2026-11-{day:02d}T{start_hour:02d}:00:00",
        "end_at": f"2026-11-{day:02d}T{start_hour:02d}:30:00",
        "motivo": "Consulta para prescrição",
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
        "queixa_principal": "Dor lombar há 3 dias",
        "historia_clinica": "Paciente fictício relata sintomas leves.",
        "exame_fisico": "Bom estado geral, sem sinais de alarme.",
        "conduta": "Orientações gerais e prescrição medicamentosa.",
        "observacoes": "Registro clínico fictício para testes.",
    }
    payload.update(overrides)
    return payload


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


def medication_item(index: int = 1, **overrides) -> dict:
    payload = {
        "medicamento": f"Medicamento Teste {index}",
        "apresentacao": "Comprimido 500 mg",
        "dose": "1 comprimido",
        "via": "oral",
        "frequencia": "a cada 8 horas",
        "duracao": "5 dias",
        "orientacoes": "Tomar após alimentação.",
    }
    payload.update(overrides)
    return payload


def prescription_payload(patient_id: int, professional_id: int, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "professional_id": professional_id,
        "observacoes": "Prescrição fictícia para testes.",
        "items": [medication_item(1)],
    }
    payload.update(overrides)
    return payload


def create_prescription(
    client: TestClient,
    headers: dict[str, str],
    patient_id: int,
    professional_id: int,
    **overrides,
) -> dict:
    response = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(patient_id, professional_id, **overrides),
    )
    assert response.status_code == 201
    return response.json()


def seed_clinical_context(
    client: TestClient,
    headers: dict[str, str],
    index: int = 1,
    *,
    with_appointment: bool = True,
    with_medical_record: bool = True,
) -> tuple[dict, dict, dict | None, dict | None]:
    patient = create_patient(client, headers, index)
    professional = create_professional(client, headers, index)
    appointment = None
    if with_appointment:
        appointment = create_appointment(client, headers, patient["id"], professional["id"], index)
    medical_record = None
    if with_medical_record:
        medical_record = create_medical_record(
            client,
            headers,
            patient["id"],
            professional["id"],
            appointment_id=appointment["id"] if appointment else None,
        )
    return patient, professional, appointment, medical_record


def test_create_valid_prescription_with_appointment_and_medical_record(client):
    headers = headers_for_role(client, "admin", "admin-prescription-create@example.com")
    patient, professional, appointment, medical_record = seed_clinical_context(client, headers, 1)

    prescription = create_prescription(
        client,
        headers,
        patient["id"],
        professional["id"],
        appointment_id=appointment["id"],
        medical_record_id=medical_record["id"],
        items=[medication_item(1), medication_item(2, medicamento="Ibuprofeno")],
    )

    assert prescription["patient_id"] == patient["id"]
    assert prescription["professional_id"] == professional["id"]
    assert prescription["appointment_id"] == appointment["id"]
    assert prescription["medical_record_id"] == medical_record["id"]
    assert prescription["status"] == "draft"
    assert len(prescription["items"]) == 2
    assert prescription["items"][0]["medicamento"] == "Medicamento Teste 1"
    assert prescription["items"][0]["created_at"]
    assert prescription["created_at"]
    assert prescription["updated_at"]


def test_create_without_appointment_or_medical_record_is_allowed(client):
    headers = headers_for_role(client, "admin", "admin-prescription-minimal@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        headers,
        2,
        with_appointment=False,
        with_medical_record=False,
    )

    prescription = create_prescription(client, headers, patient["id"], professional["id"])

    assert prescription["appointment_id"] is None
    assert prescription["medical_record_id"] is None
    assert prescription["status"] == "draft"


def test_create_rejects_empty_items_and_blank_medication_fields(client):
    headers = headers_for_role(client, "admin", "admin-prescription-validation@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        headers,
        3,
        with_appointment=False,
        with_medical_record=False,
    )

    empty_items_response = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(patient["id"], professional["id"], items=[]),
    )
    blank_medication_response = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(patient["id"], professional["id"], items=[medication_item(medicamento="  ")]),
    )

    assert empty_items_response.status_code == 422
    assert blank_medication_response.status_code == 422


def test_create_rejects_invalid_patient_professional_appointment_and_medical_record(client):
    headers = headers_for_role(client, "admin", "admin-prescription-invalid-links@example.com")
    patient, professional, appointment, medical_record = seed_clinical_context(client, headers, 4)

    invalid_patient = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(9999, professional["id"]),
    )
    invalid_professional = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(patient["id"], 9999),
    )
    invalid_appointment = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(patient["id"], professional["id"], appointment_id=9999),
    )
    invalid_medical_record = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(
            patient["id"],
            professional["id"],
            appointment_id=appointment["id"],
            medical_record_id=9999,
        ),
    )
    cancel_response = client.post(
        f"/api/v1/appointments/{appointment['id']}/cancel",
        headers=headers,
        json={"cancel_reason": "Teste de cancelamento"},
    )
    canceled_appointment = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(patient["id"], professional["id"], appointment_id=appointment["id"]),
    )

    assert medical_record["id"]
    assert invalid_patient.status_code == 400
    assert invalid_patient.json()["detail"] == "Paciente não encontrado ou inativo."
    assert invalid_professional.status_code == 400
    assert invalid_professional.json()["detail"] == "Profissional de saúde não encontrado ou inativo."
    assert invalid_appointment.status_code == 400
    assert invalid_appointment.json()["detail"] == "Consulta não encontrada ou cancelada."
    assert invalid_medical_record.status_code == 400
    assert invalid_medical_record.json()["detail"] == "Prontuário médico não encontrado."
    assert cancel_response.status_code == 200
    assert canceled_appointment.status_code == 400
    assert canceled_appointment.json()["detail"] == "Consulta não encontrada ou cancelada."


def test_create_rejects_mismatched_appointment_medical_record_and_cross_links(client):
    headers = headers_for_role(client, "admin", "admin-prescription-mismatch@example.com")
    patient_a, professional_a, appointment_a, medical_record_a = seed_clinical_context(client, headers, 5)
    patient_b, _, _, _ = seed_clinical_context(
        client,
        headers,
        6,
        with_appointment=False,
        with_medical_record=False,
    )
    appointment_b = create_appointment(client, headers, patient_a["id"], professional_a["id"], 16)

    appointment_mismatch = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(patient_b["id"], professional_a["id"], appointment_id=appointment_a["id"]),
    )
    medical_record_mismatch = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(patient_b["id"], professional_a["id"], medical_record_id=medical_record_a["id"]),
    )
    cross_link_mismatch = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(
            patient_a["id"],
            professional_a["id"],
            appointment_id=appointment_b["id"],
            medical_record_id=medical_record_a["id"],
        ),
    )

    assert appointment_mismatch.status_code == 400
    assert appointment_mismatch.json()["detail"] == "Consulta não pertence ao paciente e profissional informados."
    assert medical_record_mismatch.status_code == 400
    assert medical_record_mismatch.json()["detail"] == "Prontuário não pertence ao paciente e profissional informados."
    assert cross_link_mismatch.status_code == 400
    assert cross_link_mismatch.json()["detail"] == "Consulta informada não corresponde ao prontuário vinculado."


def test_list_prescriptions_by_patient_professional_record_status_and_pagination(client):
    headers = headers_for_role(client, "admin", "admin-prescription-list@example.com")
    patient_a, professional_a, appointment_a, medical_record_a = seed_clinical_context(client, headers, 7)
    patient_b, professional_b, appointment_b, medical_record_b = seed_clinical_context(client, headers, 8)
    first = create_prescription(
        client,
        headers,
        patient_a["id"],
        professional_a["id"],
        appointment_id=appointment_a["id"],
        medical_record_id=medical_record_a["id"],
    )
    second = create_prescription(
        client,
        headers,
        patient_b["id"],
        professional_b["id"],
        appointment_id=appointment_b["id"],
        medical_record_id=medical_record_b["id"],
        items=[medication_item(2, medicamento="Paracetamol")],
    )
    update_response = client.patch(
        f"/api/v1/prescriptions/{second['id']}",
        headers=headers,
        json={"status": "active"},
    )
    assert update_response.status_code == 200

    patient_response = client.get(
        "/api/v1/prescriptions",
        headers=headers,
        params={"patient_id": patient_a["id"]},
    )
    professional_response = client.get(
        "/api/v1/prescriptions",
        headers=headers,
        params={"professional_id": professional_b["id"], "status": "active"},
    )
    medical_record_response = client.get(
        "/api/v1/prescriptions",
        headers=headers,
        params={"medical_record_id": medical_record_a["id"]},
    )
    appointment_response = client.get(
        "/api/v1/prescriptions",
        headers=headers,
        params={"appointment_id": appointment_b["id"]},
    )
    paginated_response = client.get(
        "/api/v1/prescriptions",
        headers=headers,
        params={"page": 1, "page_size": 1},
    )

    assert patient_response.status_code == 200
    assert patient_response.json()["total"] == 1
    assert patient_response.json()["items"][0]["id"] == first["id"]
    assert professional_response.status_code == 200
    assert professional_response.json()["total"] == 1
    assert professional_response.json()["items"][0]["id"] == second["id"]
    assert medical_record_response.status_code == 200
    assert medical_record_response.json()["items"][0]["medical_record_id"] == medical_record_a["id"]
    assert appointment_response.status_code == 200
    assert appointment_response.json()["items"][0]["appointment_id"] == appointment_b["id"]
    assert paginated_response.status_code == 200
    assert paginated_response.json()["total"] == 2
    assert len(paginated_response.json()["items"]) == 1


def test_read_prescription_by_id(client):
    headers = headers_for_role(client, "admin", "admin-prescription-read@example.com")
    patient, professional, appointment, medical_record = seed_clinical_context(client, headers, 9)
    prescription = create_prescription(
        client,
        headers,
        patient["id"],
        professional["id"],
        appointment_id=appointment["id"],
        medical_record_id=medical_record["id"],
    )

    response = client.get(f"/api/v1/prescriptions/{prescription['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == prescription["id"]
    assert response.json()["items"][0]["medicamento"] == "Medicamento Teste 1"


def test_update_prescription_status_links_and_items(client):
    headers = headers_for_role(client, "admin", "admin-prescription-update@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        headers,
        10,
        with_appointment=False,
        with_medical_record=False,
    )
    appointment = create_appointment(client, headers, patient["id"], professional["id"], 10)
    medical_record = create_medical_record(
        client,
        headers,
        patient["id"],
        professional["id"],
        appointment_id=appointment["id"],
    )
    prescription = create_prescription(client, headers, patient["id"], professional["id"])

    response = client.patch(
        f"/api/v1/prescriptions/{prescription['id']}",
        headers=headers,
        json={
            "appointment_id": appointment["id"],
            "medical_record_id": medical_record["id"],
            "status": "active",
            "observacoes": "Prescrição revisada.",
            "items": [
                medication_item(
                    3,
                    medicamento="Amoxicilina",
                    apresentacao="Cápsula 500 mg",
                    dose="1 cápsula",
                    frequencia="a cada 8 horas",
                    duracao="7 dias",
                )
            ],
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["appointment_id"] == appointment["id"]
    assert updated["medical_record_id"] == medical_record["id"]
    assert updated["status"] == "active"
    assert updated["observacoes"] == "Prescrição revisada."
    assert len(updated["items"]) == 1
    assert updated["items"][0]["medicamento"] == "Amoxicilina"
    assert updated["items"][0]["duracao"] == "7 dias"


@pytest.mark.parametrize("role_code", ["medico", "enfermeiro"])
def test_clinical_roles_can_create_read_and_update_prescriptions(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-setup-{role_code}-prescricao@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-prescricao@example.com")
    patient, professional, appointment, medical_record = seed_clinical_context(
        client,
        admin_headers,
        20 if role_code == "medico" else 21,
    )

    create_response = client.post(
        "/api/v1/prescriptions",
        headers=role_headers,
        json=prescription_payload(
            patient["id"],
            professional["id"],
            appointment_id=appointment["id"],
            medical_record_id=medical_record["id"],
        ),
    )
    assert create_response.status_code == 201
    prescription_id = create_response.json()["id"]

    read_response = client.get(f"/api/v1/prescriptions/{prescription_id}", headers=role_headers)
    update_response = client.patch(
        f"/api/v1/prescriptions/{prescription_id}",
        headers=role_headers,
        json={"status": "completed", "observacoes": "Tratamento concluído."},
    )

    assert read_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "completed"


def test_farmacia_can_read_but_cannot_write_prescriptions(client):
    admin_headers = headers_for_role(client, "admin", "admin-setup-farmacia-prescricao@example.com")
    farmacia_headers = headers_for_role(client, "farmacia", "farmacia-prescricao@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        admin_headers,
        30,
        with_appointment=False,
        with_medical_record=False,
    )
    prescription = create_prescription(client, admin_headers, patient["id"], professional["id"])

    list_response = client.get("/api/v1/prescriptions", headers=farmacia_headers)
    read_response = client.get(f"/api/v1/prescriptions/{prescription['id']}", headers=farmacia_headers)
    create_response = client.post(
        "/api/v1/prescriptions",
        headers=farmacia_headers,
        json=prescription_payload(patient["id"], professional["id"]),
    )
    update_response = client.patch(
        f"/api/v1/prescriptions/{prescription['id']}",
        headers=farmacia_headers,
        json={"status": "active"},
    )

    assert list_response.status_code == 200
    assert read_response.status_code == 200
    assert create_response.status_code == 403
    assert create_response.json()["detail"]["required_permissions"] == ["medicamentos:escrever"]
    assert update_response.status_code == 403


@pytest.mark.parametrize("role_code", ["recepcionista", "laboratorio", "paciente"])
def test_roles_without_medicamentos_read_are_forbidden(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-setup-read-forbidden-{role_code}@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-sem-medicamentos-read@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        admin_headers,
        40 + len(role_code),
        with_appointment=False,
        with_medical_record=False,
    )
    prescription = create_prescription(client, admin_headers, patient["id"], professional["id"])

    list_response = client.get("/api/v1/prescriptions", headers=role_headers)
    read_response = client.get(f"/api/v1/prescriptions/{prescription['id']}", headers=role_headers)

    assert list_response.status_code == 403
    assert list_response.json()["detail"]["required_permissions"] == ["medicamentos:ler"]
    assert read_response.status_code == 403
    assert read_response.json()["detail"]["required_permissions"] == ["medicamentos:ler"]


@pytest.mark.parametrize("role_code", ["recepcionista", "laboratorio", "paciente"])
def test_roles_without_medicamentos_write_are_forbidden(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-setup-write-forbidden-{role_code}@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-sem-medicamentos-write@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        admin_headers,
        60 + len(role_code),
        with_appointment=False,
        with_medical_record=False,
    )
    prescription = create_prescription(client, admin_headers, patient["id"], professional["id"])

    create_response = client.post(
        "/api/v1/prescriptions",
        headers=role_headers,
        json=prescription_payload(patient["id"], professional["id"]),
    )
    update_response = client.patch(
        f"/api/v1/prescriptions/{prescription['id']}",
        headers=role_headers,
        json={"status": "active"},
    )

    assert create_response.status_code == 403
    assert create_response.json()["detail"]["required_permissions"] == ["medicamentos:escrever"]
    assert update_response.status_code == 403
    assert update_response.json()["detail"]["required_permissions"] == ["medicamentos:escrever"]


def test_user_without_permission_is_forbidden(client):
    admin_headers = headers_for_role(client, "admin", "admin-prescription-no-permission-setup@example.com")
    headers = headers_without_permission()
    patient, professional, _, _ = seed_clinical_context(
        client,
        admin_headers,
        80,
        with_appointment=False,
        with_medical_record=False,
    )
    prescription = create_prescription(client, admin_headers, patient["id"], professional["id"])

    create_response = client.post(
        "/api/v1/prescriptions",
        headers=headers,
        json=prescription_payload(patient["id"], professional["id"]),
    )
    read_response = client.get(f"/api/v1/prescriptions/{prescription['id']}", headers=headers)

    assert create_response.status_code == 403
    assert create_response.json()["detail"]["required_permissions"] == ["medicamentos:escrever"]
    assert read_response.status_code == 403
    assert read_response.json()["detail"]["required_permissions"] == ["medicamentos:ler"]


def test_missing_prescription_returns_404(client):
    headers = headers_for_role(client, "admin", "admin-prescription-missing@example.com")

    get_response = client.get("/api/v1/prescriptions/9999", headers=headers)
    patch_response = client.patch(
        "/api/v1/prescriptions/9999",
        headers=headers,
        json={"status": "active"},
    )

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Prescrição não encontrada."
    assert patch_response.status_code == 404
    assert patch_response.json()["detail"] == "Prescrição não encontrada."
