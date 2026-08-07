import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.auth.authorization import assign_role_to_user, ensure_default_rbac
from app.auth.password import hash_password
from app.database.base import Base
from app.database.connection import get_engine, get_session_factory
from app.main import app
from app.models.patient import Patient
from app.models.user import User

STRONG_PASSWORD = "SenhaForte#123"


@pytest.fixture()
def client(monkeypatch, tmp_path):
    database_path = tmp_path / "jarvis_patients_test.db"
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


def headers_without_permission(email: str = "sem-permissao@example.com") -> dict[str, str]:
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
        "nome_completo": f"Paciente Fictício {index:02d}",
        "nome_social": f"Social {index:02d}",
        "data_nascimento": "1990-01-15",
        "sexo": "feminino",
        "cpf": f"{index:011d}",
        "rg": f"RG{index:06d}",
        "cns": f"{index:015d}",
        "email": f"paciente{index:02d}@example.com",
        "telefone": "11999990000",
        "telefone_secundario": "11888880000",
        "nome_mae": f"Mãe Fictícia {index:02d}",
        "nome_pai": f"Pai Fictício {index:02d}",
        "estado_civil": "solteiro",
        "profissao": "Profissão Fictícia",
        "cep": "01001000",
        "logradouro": "Rua Fictícia",
        "numero": str(index),
        "complemento": "Apto Teste",
        "bairro": "Bairro Fictício",
        "cidade": "Cidade Teste",
        "estado": "sp",
    }
    payload.update(overrides)
    return payload


def create_patient(client: TestClient, headers: dict[str, str], index: int = 1, **overrides) -> dict:
    response = client.post("/api/v1/patients", headers=headers, json=patient_payload(index, **overrides))
    assert response.status_code == 201
    return response.json()


def test_create_valid_patient(client):
    headers = headers_for_role(client, "admin", "admin-create@example.com")

    response = client.post("/api/v1/patients", headers=headers, json=patient_payload(1))

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["nome_completo"] == "Paciente Fictício 01"
    assert body["cpf"] == "00000000001"
    assert body["cns"] == "000000000000001"
    assert body["estado"] == "SP"
    assert body["ativo"] is True


def test_create_rejects_duplicate_cpf(client):
    headers = headers_for_role(client, "admin", "admin-cpf@example.com")
    create_patient(client, headers, 1)

    response = client.post(
        "/api/v1/patients",
        headers=headers,
        json=patient_payload(2, cpf="000.000.000-01"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Paciente com CPF já cadastrado."


def test_create_rejects_duplicate_cns(client):
    headers = headers_for_role(client, "admin", "admin-cns@example.com")
    create_patient(client, headers, 1)

    response = client.post(
        "/api/v1/patients",
        headers=headers,
        json=patient_payload(2, cns="000000000000001"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Paciente com CNS já cadastrado."


def test_read_patient_by_id(client):
    headers = headers_for_role(client, "admin", "admin-read@example.com")
    patient = create_patient(client, headers, 1)

    response = client.get(f"/api/v1/patients/{patient['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == patient["id"]
    assert response.json()["nome_completo"] == "Paciente Fictício 01"


def test_update_patient(client):
    headers = headers_for_role(client, "admin", "admin-update@example.com")
    patient = create_patient(client, headers, 1)

    response = client.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=headers,
        json={"nome_social": "Nome Atualizado", "email": "atualizado@example.com", "estado": "rj"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["nome_social"] == "Nome Atualizado"
    assert body["email"] == "atualizado@example.com"
    assert body["estado"] == "RJ"


def test_deactivate_patient_is_logical(client):
    headers = headers_for_role(client, "admin", "admin-deactivate@example.com")
    patient = create_patient(client, headers, 1)

    response = client.delete(f"/api/v1/patients/{patient['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["ativo"] is False

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        persisted = session.get(Patient, patient["id"])
        assert persisted is not None
        assert persisted.ativo is False


def test_list_patients_uses_pagination(client):
    headers = headers_for_role(client, "admin", "admin-pagination@example.com")
    create_patient(client, headers, 1, nome_completo="Paciente Fictício Alfa")
    create_patient(client, headers, 2, nome_completo="Paciente Fictício Beta")
    create_patient(client, headers, 3, nome_completo="Paciente Fictício Gama")

    response = client.get("/api/v1/patients?page=2&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["nome_completo"] == "Paciente Fictício Gama"


def test_search_patients_by_name_cpf_and_cns(client):
    headers = headers_for_role(client, "admin", "admin-search@example.com")
    first = create_patient(client, headers, 1, nome_completo="Paciente Busca Alfa")
    create_patient(client, headers, 2, nome_completo="Paciente Outro Beta")

    by_name = client.get("/api/v1/patients?nome=busca", headers=headers)
    assert by_name.status_code == 200
    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["id"] == first["id"]

    by_cpf = client.get("/api/v1/patients?cpf=000.000.000-01", headers=headers)
    assert by_cpf.status_code == 200
    assert by_cpf.json()["total"] == 1
    assert by_cpf.json()["items"][0]["id"] == first["id"]

    by_cns = client.get("/api/v1/patients?cns=000000000000001", headers=headers)
    assert by_cns.status_code == 200
    assert by_cns.json()["total"] == 1
    assert by_cns.json()["items"][0]["id"] == first["id"]


@pytest.mark.parametrize("role_code", ["medico", "enfermeiro", "recepcionista"])
def test_allowed_roles_can_create_read_and_update(client, role_code):
    headers = headers_for_role(client, role_code, f"{role_code}-patients@example.com")

    patient = create_patient(client, headers, 1)
    read_response = client.get(f"/api/v1/patients/{patient['id']}", headers=headers)
    update_response = client.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=headers,
        json={"telefone": "11777770000"},
    )

    assert read_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["telefone"] == "11777770000"


def test_laboratorio_can_read_but_cannot_create_or_update(client):
    admin_headers = headers_for_role(client, "admin", "admin-lab-seed@example.com")
    patient = create_patient(client, admin_headers, 1)
    laboratorio_headers = headers_for_role(client, "laboratorio", "lab@example.com")

    read_response = client.get(f"/api/v1/patients/{patient['id']}", headers=laboratorio_headers)
    create_response = client.post("/api/v1/patients", headers=laboratorio_headers, json=patient_payload(2))
    update_response = client.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=laboratorio_headers,
        json={"telefone": "11666660000"},
    )

    assert read_response.status_code == 200
    assert create_response.status_code == 403
    assert create_response.json()["detail"]["required_permissions"] == ["patients:create"]
    assert update_response.status_code == 403
    assert update_response.json()["detail"]["required_permissions"] == ["patients:update"]


@pytest.mark.parametrize("role_code", ["farmacia", "paciente"])
def test_roles_without_patient_management_access_are_forbidden(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-{role_code}-seed@example.com")
    patient = create_patient(client, admin_headers, 1)
    headers = headers_for_role(client, role_code, f"{role_code}-blocked@example.com")

    response = client.get(f"/api/v1/patients/{patient['id']}", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"]["required_permissions"] == ["patients:read"]


def test_user_without_permission_is_forbidden(client):
    headers = headers_without_permission()

    response = client.get("/api/v1/patients", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"]["required_permissions"] == ["patients:read"]


def test_missing_patient_returns_404(client):
    headers = headers_for_role(client, "admin", "admin-not-found@example.com")

    response = client.get("/api/v1/patients/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Paciente não encontrado."
