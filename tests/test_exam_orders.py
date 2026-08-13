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
    database_path = tmp_path / "jarvis_exam_orders_test.db"
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
    email = email or f"{role_code}-exam-orders@example.com"
    registration = register_user(client, email)
    grant_role_to_email(email, role_code)
    token = registration["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def headers_without_permission(email: str = "sem-permissao-exam-orders@example.com") -> dict[str, str]:
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
        "nome_completo": f"Paciente Exames {index:02d}",
        "data_nascimento": "1990-01-15",
        "sexo": "feminino",
        "cpf": f"{index:011d}",
        "cns": f"{index:015d}",
        "email": f"paciente.exames{index:02d}@example.com",
        "telefone": "11999990000",
    }
    payload.update(overrides)
    return payload


def professional_payload(index: int = 1, **overrides) -> dict:
    payload = {
        "nome_completo": f"Profissional Exames {index:02d}",
        "cpf": f"{index:011d}",
        "data_nascimento": "1985-06-20",
        "email": f"profissional.exames{index:02d}@example.com",
        "telefone": "11988887777",
        "conselho_tipo": "CRM",
        "conselho_numero": f"{600000 + index}",
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
        "start_at": f"2026-12-{day:02d}T{start_hour:02d}:00:00",
        "end_at": f"2026-12-{day:02d}T{start_hour:02d}:30:00",
        "motivo": "Consulta para solicitação de exames",
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
        "queixa_principal": "Fadiga há 2 semanas",
        "historia_clinica": "Paciente fictício relata sintomas inespecíficos.",
        "exame_fisico": "Bom estado geral, sem sinais de alarme.",
        "conduta": "Solicitar exames laboratoriais para investigação.",
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


def exam_item(index: int = 1, **overrides) -> dict:
    payload = {
        "nome_exame": f"Exame Teste {index}",
        "codigo": f"EX{index:03d}",
        "material": "Sangue total",
        "orientacoes": "Jejum conforme orientação clínica.",
    }
    payload.update(overrides)
    return payload


def exam_order_payload(patient_id: int, professional_id: int, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "professional_id": professional_id,
        "prioridade": "rotina",
        "justificativa": "Investigação clínica fictícia.",
        "observacoes": "Solicitação de exame fictícia para testes.",
        "items": [exam_item(1)],
    }
    payload.update(overrides)
    return payload


def create_exam_order(
    client: TestClient,
    headers: dict[str, str],
    patient_id: int,
    professional_id: int,
    **overrides,
) -> dict:
    response = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(patient_id, professional_id, **overrides),
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


def test_create_valid_exam_order_with_appointment_and_medical_record(client):
    headers = headers_for_role(client, "admin", "admin-exam-order-create@example.com")
    patient, professional, appointment, medical_record = seed_clinical_context(client, headers, 1)

    exam_order = create_exam_order(
        client,
        headers,
        patient["id"],
        professional["id"],
        appointment_id=appointment["id"],
        medical_record_id=medical_record["id"],
        prioridade="urgente",
        items=[exam_item(1), exam_item(2, nome_exame="Glicemia de jejum")],
    )

    assert exam_order["patient_id"] == patient["id"]
    assert exam_order["professional_id"] == professional["id"]
    assert exam_order["appointment_id"] == appointment["id"]
    assert exam_order["medical_record_id"] == medical_record["id"]
    assert exam_order["status"] == "draft"
    assert exam_order["prioridade"] == "urgente"
    assert len(exam_order["items"]) == 2
    assert exam_order["items"][0]["nome_exame"] == "Exame Teste 1"
    assert exam_order["items"][0]["created_at"]
    assert exam_order["created_at"]
    assert exam_order["updated_at"]


def test_create_without_appointment_or_medical_record_is_allowed(client):
    headers = headers_for_role(client, "admin", "admin-exam-order-minimal@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        headers,
        2,
        with_appointment=False,
        with_medical_record=False,
    )

    exam_order = create_exam_order(client, headers, patient["id"], professional["id"])

    assert exam_order["appointment_id"] is None
    assert exam_order["medical_record_id"] is None
    assert exam_order["status"] == "draft"
    assert exam_order["prioridade"] == "rotina"


def test_create_rejects_empty_items_and_blank_exam_name(client):
    headers = headers_for_role(client, "admin", "admin-exam-order-validation@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        headers,
        3,
        with_appointment=False,
        with_medical_record=False,
    )

    empty_items_response = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(patient["id"], professional["id"], items=[]),
    )
    blank_exam_response = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(patient["id"], professional["id"], items=[exam_item(nome_exame="  ")]),
    )

    assert empty_items_response.status_code == 422
    assert blank_exam_response.status_code == 422


def test_create_rejects_invalid_patient_professional_appointment_and_medical_record(client):
    headers = headers_for_role(client, "admin", "admin-exam-order-invalid-links@example.com")
    patient, professional, appointment, medical_record = seed_clinical_context(client, headers, 4)

    invalid_patient = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(9999, professional["id"]),
    )
    invalid_professional = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(patient["id"], 9999),
    )
    invalid_appointment = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(patient["id"], professional["id"], appointment_id=9999),
    )
    invalid_medical_record = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(
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
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(patient["id"], professional["id"], appointment_id=appointment["id"]),
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
    headers = headers_for_role(client, "admin", "admin-exam-order-mismatch@example.com")
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
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(patient_b["id"], professional_a["id"], appointment_id=appointment_a["id"]),
    )
    medical_record_mismatch = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(patient_b["id"], professional_a["id"], medical_record_id=medical_record_a["id"]),
    )
    cross_link_mismatch = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(
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


def test_list_exam_orders_by_patient_professional_record_status_priority_and_pagination(client):
    headers = headers_for_role(client, "admin", "admin-exam-order-list@example.com")
    patient_a, professional_a, appointment_a, medical_record_a = seed_clinical_context(client, headers, 7)
    patient_b, professional_b, appointment_b, medical_record_b = seed_clinical_context(client, headers, 8)
    first = create_exam_order(
        client,
        headers,
        patient_a["id"],
        professional_a["id"],
        appointment_id=appointment_a["id"],
        medical_record_id=medical_record_a["id"],
    )
    second = create_exam_order(
        client,
        headers,
        patient_b["id"],
        professional_b["id"],
        appointment_id=appointment_b["id"],
        medical_record_id=medical_record_b["id"],
        prioridade="urgente",
        items=[exam_item(2, nome_exame="TSH")],
    )
    update_response = client.patch(
        f"/api/v1/exam-orders/{second['id']}",
        headers=headers,
        json={"status": "requested"},
    )
    assert update_response.status_code == 200

    patient_response = client.get(
        "/api/v1/exam-orders",
        headers=headers,
        params={"patient_id": patient_a["id"]},
    )
    professional_response = client.get(
        "/api/v1/exam-orders",
        headers=headers,
        params={"professional_id": professional_b["id"], "status": "requested"},
    )
    medical_record_response = client.get(
        "/api/v1/exam-orders",
        headers=headers,
        params={"medical_record_id": medical_record_a["id"]},
    )
    appointment_response = client.get(
        "/api/v1/exam-orders",
        headers=headers,
        params={"appointment_id": appointment_b["id"]},
    )
    priority_response = client.get(
        "/api/v1/exam-orders",
        headers=headers,
        params={"prioridade": "urgente"},
    )
    paginated_response = client.get(
        "/api/v1/exam-orders",
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
    assert priority_response.status_code == 200
    assert priority_response.json()["items"][0]["prioridade"] == "urgente"
    assert paginated_response.status_code == 200
    assert paginated_response.json()["total"] == 2
    assert len(paginated_response.json()["items"]) == 1


def test_read_exam_order_by_id(client):
    headers = headers_for_role(client, "admin", "admin-exam-order-read@example.com")
    patient, professional, appointment, medical_record = seed_clinical_context(client, headers, 9)
    exam_order = create_exam_order(
        client,
        headers,
        patient["id"],
        professional["id"],
        appointment_id=appointment["id"],
        medical_record_id=medical_record["id"],
    )

    response = client.get(f"/api/v1/exam-orders/{exam_order['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == exam_order["id"]
    assert response.json()["items"][0]["nome_exame"] == "Exame Teste 1"


def test_update_exam_order_status_links_priority_and_items(client):
    headers = headers_for_role(client, "admin", "admin-exam-order-update@example.com")
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
    exam_order = create_exam_order(client, headers, patient["id"], professional["id"])

    response = client.patch(
        f"/api/v1/exam-orders/{exam_order['id']}",
        headers=headers,
        json={
            "appointment_id": appointment["id"],
            "medical_record_id": medical_record["id"],
            "status": "requested",
            "prioridade": "urgente",
            "justificativa": "Investigação revisada.",
            "observacoes": "Solicitação revisada.",
            "items": [
                exam_item(
                    3,
                    nome_exame="Ferritina",
                    codigo="FER001",
                    material="Soro",
                    orientacoes="Sem preparo obrigatório.",
                )
            ],
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["appointment_id"] == appointment["id"]
    assert updated["medical_record_id"] == medical_record["id"]
    assert updated["status"] == "requested"
    assert updated["prioridade"] == "urgente"
    assert updated["justificativa"] == "Investigação revisada."
    assert len(updated["items"]) == 1
    assert updated["items"][0]["nome_exame"] == "Ferritina"
    assert updated["items"][0]["material"] == "Soro"


@pytest.mark.parametrize("role_code", ["medico", "enfermeiro", "laboratorio"])
def test_allowed_roles_can_create_read_and_update_exam_orders(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-setup-{role_code}-exames@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-exames@example.com")
    patient, professional, appointment, medical_record = seed_clinical_context(
        client,
        admin_headers,
        20 if role_code == "medico" else 21 if role_code == "enfermeiro" else 22,
    )

    create_response = client.post(
        "/api/v1/exam-orders",
        headers=role_headers,
        json=exam_order_payload(
            patient["id"],
            professional["id"],
            appointment_id=appointment["id"],
            medical_record_id=medical_record["id"],
        ),
    )
    assert create_response.status_code == 201
    exam_order_id = create_response.json()["id"]

    read_response = client.get(f"/api/v1/exam-orders/{exam_order_id}", headers=role_headers)
    update_response = client.patch(
        f"/api/v1/exam-orders/{exam_order_id}",
        headers=role_headers,
        json={"status": "completed", "observacoes": "Fluxo concluído."},
    )

    assert read_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "completed"


@pytest.mark.parametrize("role_code", ["recepcionista", "farmacia", "paciente"])
def test_roles_without_exames_read_are_forbidden(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-setup-read-forbidden-{role_code}@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-sem-exames-read@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        admin_headers,
        40 + len(role_code),
        with_appointment=False,
        with_medical_record=False,
    )
    exam_order = create_exam_order(client, admin_headers, patient["id"], professional["id"])

    list_response = client.get("/api/v1/exam-orders", headers=role_headers)
    read_response = client.get(f"/api/v1/exam-orders/{exam_order['id']}", headers=role_headers)

    assert list_response.status_code == 403
    assert list_response.json()["detail"]["required_permissions"] == ["exames:ler"]
    assert read_response.status_code == 403
    assert read_response.json()["detail"]["required_permissions"] == ["exames:ler"]


@pytest.mark.parametrize("role_code", ["recepcionista", "farmacia", "paciente"])
def test_roles_without_exames_manage_are_forbidden(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-setup-write-forbidden-{role_code}@example.com")
    role_headers = headers_for_role(client, role_code, f"{role_code}-sem-exames-write@example.com")
    patient, professional, _, _ = seed_clinical_context(
        client,
        admin_headers,
        60 + len(role_code),
        with_appointment=False,
        with_medical_record=False,
    )
    exam_order = create_exam_order(client, admin_headers, patient["id"], professional["id"])

    create_response = client.post(
        "/api/v1/exam-orders",
        headers=role_headers,
        json=exam_order_payload(patient["id"], professional["id"]),
    )
    update_response = client.patch(
        f"/api/v1/exam-orders/{exam_order['id']}",
        headers=role_headers,
        json={"status": "requested"},
    )

    assert create_response.status_code == 403
    assert create_response.json()["detail"]["required_permissions"] == ["exames:gerenciar"]
    assert update_response.status_code == 403
    assert update_response.json()["detail"]["required_permissions"] == ["exames:gerenciar"]


def test_user_without_permission_is_forbidden(client):
    admin_headers = headers_for_role(client, "admin", "admin-exam-order-no-permission-setup@example.com")
    headers = headers_without_permission()
    patient, professional, _, _ = seed_clinical_context(
        client,
        admin_headers,
        80,
        with_appointment=False,
        with_medical_record=False,
    )
    exam_order = create_exam_order(client, admin_headers, patient["id"], professional["id"])

    create_response = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json=exam_order_payload(patient["id"], professional["id"]),
    )
    read_response = client.get(f"/api/v1/exam-orders/{exam_order['id']}", headers=headers)

    assert create_response.status_code == 403
    assert create_response.json()["detail"]["required_permissions"] == ["exames:gerenciar"]
    assert read_response.status_code == 403
    assert read_response.json()["detail"]["required_permissions"] == ["exames:ler"]


def test_missing_exam_order_returns_404(client):
    headers = headers_for_role(client, "admin", "admin-exam-order-missing@example.com")

    get_response = client.get("/api/v1/exam-orders/9999", headers=headers)
    patch_response = client.patch(
        "/api/v1/exam-orders/9999",
        headers=headers,
        json={"status": "requested"},
    )

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Solicitação de exame não encontrada."
    assert patch_response.status_code == 404
    assert patch_response.json()["detail"] == "Solicitação de exame não encontrada."
