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
    database_path = tmp_path / "jarvis_exam_results_test.db"
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
    email = email or f"{role_code}-exam-results@example.com"
    registration = register_user(client, email)
    grant_role_to_email(email, role_code)
    token = registration["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def headers_without_permission(email: str = "sem-permissao-exam-results@example.com") -> dict[str, str]:
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
        "nome_completo": f"Paciente Resultado {index:02d}",
        "data_nascimento": "1990-01-15",
        "sexo": "feminino",
        "cpf": f"{index:011d}",
        "cns": f"{index:015d}",
        "email": f"paciente.resultado{index:02d}@example.com",
        "telefone": "11999990000",
    }
    payload.update(overrides)
    return payload


def professional_payload(index: int = 1, **overrides) -> dict:
    payload = {
        "nome_completo": f"Profissional Resultado {index:02d}",
        "cpf": f"{index:011d}",
        "data_nascimento": "1985-06-20",
        "email": f"profissional.resultado{index:02d}@example.com",
        "telefone": "11988887777",
        "conselho_tipo": "CRM",
        "conselho_numero": f"{700000 + index}",
        "conselho_uf": "SP",
        "especialidade_principal": "Patologia clínica",
    }
    payload.update(overrides)
    return payload


def create_patient(client: TestClient, headers: dict[str, str], index: int = 1) -> dict:
    response = client.post("/api/v1/patients", headers=headers, json=patient_payload(index))
    assert response.status_code == 201
    return response.json()


def create_professional(client: TestClient, headers: dict[str, str], index: int = 1) -> dict:
    response = client.post("/api/v1/health-professionals", headers=headers, json=professional_payload(index))
    assert response.status_code == 201
    return response.json()


def exam_item(index: int = 1, **overrides) -> dict:
    payload = {
        "nome_exame": f"Exame Resultado {index}",
        "codigo": f"RES{index:03d}",
        "material": "Sangue total",
        "orientacoes": "Jejum conforme orientação clínica.",
    }
    payload.update(overrides)
    return payload


def create_exam_order(
    client: TestClient,
    headers: dict[str, str],
    patient_id: int,
    professional_id: int,
    index: int = 1,
) -> dict:
    response = client.post(
        "/api/v1/exam-orders",
        headers=headers,
        json={
            "patient_id": patient_id,
            "professional_id": professional_id,
            "prioridade": "rotina",
            "justificativa": "Investigação clínica fictícia.",
            "items": [exam_item(index)],
        },
    )
    assert response.status_code == 201
    return response.json()


def seed_exam_context(client: TestClient, headers: dict[str, str], index: int = 1) -> tuple[dict, dict, dict]:
    patient = create_patient(client, headers, index)
    professional = create_professional(client, headers, index)
    exam_order = create_exam_order(client, headers, patient["id"], professional["id"], index)
    return patient, professional, exam_order


def result_item(order_item: dict, **overrides) -> dict:
    payload = {
        "exam_order_item_id": order_item["id"],
        "resultado": "Hemoglobina 13,8 g/dL",
        "unidade": "g/dL",
        "valor_referencia": "12,0 a 16,0 g/dL",
        "interpretacao": "Resultado dentro da faixa de referência.",
    }
    payload.update(overrides)
    return payload


def result_payload(exam_order: dict, professional_id: int, **overrides) -> dict:
    payload = {
        "exam_order_id": exam_order["id"],
        "professional_id": professional_id,
        "coletado_em": "2026-08-14T10:00:00",
        "laudo": "Laudo laboratorial fictício para testes.",
        "observacoes": "Resultado validado pela equipe técnica.",
        "items": [result_item(exam_order["items"][0])],
    }
    payload.update(overrides)
    return payload


def create_exam_result(
    client: TestClient,
    headers: dict[str, str],
    exam_order: dict,
    professional_id: int,
    **overrides,
) -> dict:
    response = client.post(
        "/api/v1/exam-results",
        headers=headers,
        json=result_payload(exam_order, professional_id, **overrides),
    )
    assert response.status_code == 201
    return response.json()


def test_create_exam_result_copies_order_patient_and_items(client):
    admin_headers = headers_for_role(client, "admin", "admin-exam-result-create@example.com")
    lab_headers = headers_for_role(client, "laboratorio", "lab-exam-result-create@example.com")
    patient, professional, exam_order = seed_exam_context(client, admin_headers, 1)

    exam_result = create_exam_result(client, lab_headers, exam_order, professional["id"])

    assert exam_result["exam_order_id"] == exam_order["id"]
    assert exam_result["patient_id"] == patient["id"]
    assert exam_result["professional_id"] == professional["id"]
    assert exam_result["status"] == "draft"
    assert exam_result["items"][0]["exam_order_item_id"] == exam_order["items"][0]["id"]
    assert exam_result["items"][0]["nome_exame"] == exam_order["items"][0]["nome_exame"]
    assert exam_result["items"][0]["codigo"] == exam_order["items"][0]["codigo"]
    assert exam_result["created_at"]
    assert exam_result["updated_at"]


def test_list_get_and_update_exam_result(client):
    headers = headers_for_role(client, "admin", "admin-exam-result-list-update@example.com")
    patient, professional, exam_order = seed_exam_context(client, headers, 2)
    exam_result = create_exam_result(client, headers, exam_order, professional["id"])

    detail_response = client.get(f"/api/v1/exam-results/{exam_result['id']}", headers=headers)
    list_response = client.get(
        "/api/v1/exam-results",
        headers=headers,
        params={"patient_id": patient["id"], "status": "draft"},
    )
    update_response = client.patch(
        f"/api/v1/exam-results/{exam_result['id']}",
        headers=headers,
        json={
            "status": "final",
            "liberado_em": "2026-08-14T15:00:00",
            "laudo": "Laudo final liberado.",
            "items": [result_item(exam_order["items"][0], resultado="Hemoglobina 14,1 g/dL")],
        },
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == exam_result["id"]
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "final"
    assert updated["liberado_em"]
    assert updated["items"][0]["resultado"] == "Hemoglobina 14,1 g/dL"


def test_create_rejects_duplicate_exam_order_and_item_from_another_order(client):
    headers = headers_for_role(client, "admin", "admin-exam-result-invalid@example.com")
    _, professional, first_order = seed_exam_context(client, headers, 3)
    _, _, second_order = seed_exam_context(client, headers, 4)
    create_exam_result(client, headers, first_order, professional["id"])

    duplicate_response = client.post(
        "/api/v1/exam-results",
        headers=headers,
        json=result_payload(first_order, professional["id"]),
    )
    mismatch_response = client.post(
        "/api/v1/exam-results",
        headers=headers,
        json=result_payload(
            second_order,
            professional["id"],
            items=[result_item(first_order["items"][0])],
        ),
    )

    assert duplicate_response.status_code == 409
    assert mismatch_response.status_code == 400


def test_create_validates_required_items_and_result_text(client):
    headers = headers_for_role(client, "admin", "admin-exam-result-validation@example.com")
    _, professional, exam_order = seed_exam_context(client, headers, 5)

    empty_items_response = client.post(
        "/api/v1/exam-results",
        headers=headers,
        json=result_payload(exam_order, professional["id"], items=[]),
    )
    blank_result_response = client.post(
        "/api/v1/exam-results",
        headers=headers,
        json=result_payload(
            exam_order,
            professional["id"],
            items=[result_item(exam_order["items"][0], resultado="  ")],
        ),
    )

    assert empty_items_response.status_code == 422
    assert blank_result_response.status_code == 422


def test_exam_result_endpoints_require_exam_permissions(client):
    admin_headers = headers_for_role(client, "admin", "admin-exam-result-rbac@example.com")
    unauthorized_headers = headers_without_permission()
    _, professional, exam_order = seed_exam_context(client, admin_headers, 6)
    exam_result = create_exam_result(client, admin_headers, exam_order, professional["id"])

    create_response = client.post(
        "/api/v1/exam-results",
        headers=unauthorized_headers,
        json=result_payload(exam_order, professional["id"]),
    )
    list_response = client.get("/api/v1/exam-results", headers=unauthorized_headers)
    detail_response = client.get(f"/api/v1/exam-results/{exam_result['id']}", headers=unauthorized_headers)
    update_response = client.patch(
        f"/api/v1/exam-results/{exam_result['id']}",
        headers=unauthorized_headers,
        json={"status": "final"},
    )

    assert create_response.status_code == 403
    assert list_response.status_code == 403
    assert detail_response.status_code == 403
    assert update_response.status_code == 403
