import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.auth.authorization import assign_role_to_user, ensure_default_rbac
from app.auth.password import hash_password
from app.database.base import Base
from app.database.connection import get_engine, get_session_factory
from app.main import app
from app.models.health_professional import HealthProfessional
from app.models.user import User

STRONG_PASSWORD = "SenhaForte#123"


@pytest.fixture()
def client(monkeypatch, tmp_path):
    database_path = tmp_path / "jarvis_health_professionals_test.db"
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


def headers_without_permission(email: str = "sem-permissao-profissionais@example.com") -> dict[str, str]:
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


def create_user_for_link(email: str = "profissional-vinculo@example.com") -> int:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        user = User(
            nome="Conta Vinculável Fictícia",
            email=email,
            senha_hash=hash_password(STRONG_PASSWORD),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def professional_payload(index: int = 1, **overrides) -> dict:
    payload = {
        "nome_completo": f"Profissional Fictício {index:02d}",
        "nome_social": f"Social Profissional {index:02d}",
        "cpf": f"{index:011d}",
        "data_nascimento": "1985-06-20",
        "email": f"profissional{index:02d}@example.com",
        "telefone": "11988887777",
        "conselho_tipo": "CRM",
        "conselho_numero": f"{100000 + index}",
        "conselho_uf": "sp",
        "especialidade_principal": "Cardiologia",
        "outras_especialidades": ["Clínica médica", "Medicina fictícia"],
        "rqe": f"RQE{index:05d}",
    }
    payload.update(overrides)
    return payload


def create_professional(client: TestClient, headers: dict[str, str], index: int = 1, **overrides) -> dict:
    response = client.post(
        "/api/v1/health-professionals",
        headers=headers,
        json=professional_payload(index, **overrides),
    )
    assert response.status_code == 201
    return response.json()


def test_create_valid_health_professional(client):
    headers = headers_for_role(client, "admin", "admin-prof-create@example.com")

    response = client.post("/api/v1/health-professionals", headers=headers, json=professional_payload(1))

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["nome_completo"] == "Profissional Fictício 01"
    assert body["cpf"] == "00000000001"
    assert body["conselho_tipo"] == "CRM"
    assert body["conselho_uf"] == "SP"
    assert body["ativo"] is True
    assert "senha" not in body
    assert "senha_hash" not in body


def test_create_rejects_duplicate_cpf(client):
    headers = headers_for_role(client, "admin", "admin-prof-cpf@example.com")
    create_professional(client, headers, 1)

    response = client.post(
        "/api/v1/health-professionals",
        headers=headers,
        json=professional_payload(2, cpf="000.000.000-01"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Profissional de saúde com CPF já cadastrado."


def test_create_rejects_duplicate_conselho(client):
    headers = headers_for_role(client, "admin", "admin-prof-conselho@example.com")
    create_professional(client, headers, 1)

    response = client.post(
        "/api/v1/health-professionals",
        headers=headers,
        json=professional_payload(2, conselho_tipo="crm", conselho_numero="100001", conselho_uf="SP"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Profissional de saúde com conselho já cadastrado."


def test_read_health_professional_by_id(client):
    headers = headers_for_role(client, "admin", "admin-prof-read@example.com")
    professional = create_professional(client, headers, 1)

    response = client.get(f"/api/v1/health-professionals/{professional['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == professional["id"]
    assert response.json()["nome_completo"] == "Profissional Fictício 01"


def test_update_health_professional(client):
    headers = headers_for_role(client, "admin", "admin-prof-update@example.com")
    professional = create_professional(client, headers, 1)

    response = client.patch(
        f"/api/v1/health-professionals/{professional['id']}",
        headers=headers,
        json={
            "nome_social": "Nome Profissional Atualizado",
            "email": "profissional.atualizado@example.com",
            "conselho_uf": "rj",
            "especialidade_principal": "Neurologia",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["nome_social"] == "Nome Profissional Atualizado"
    assert body["email"] == "profissional.atualizado@example.com"
    assert body["conselho_uf"] == "RJ"
    assert body["especialidade_principal"] == "Neurologia"


def test_deactivate_health_professional_is_logical(client):
    headers = headers_for_role(client, "admin", "admin-prof-deactivate@example.com")
    professional = create_professional(client, headers, 1)

    response = client.delete(f"/api/v1/health-professionals/{professional['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["ativo"] is False

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        persisted = session.get(HealthProfessional, professional["id"])
        assert persisted is not None
        assert persisted.ativo is False


def test_list_health_professionals_uses_pagination(client):
    headers = headers_for_role(client, "admin", "admin-prof-pagination@example.com")
    create_professional(client, headers, 1, nome_completo="Profissional Fictício Alfa")
    create_professional(client, headers, 2, nome_completo="Profissional Fictício Beta")
    create_professional(client, headers, 3, nome_completo="Profissional Fictício Gama")

    response = client.get("/api/v1/health-professionals?page=2&page_size=2", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["nome_completo"] == "Profissional Fictício Gama"


def test_search_health_professionals_by_name_cpf_conselho_and_specialty(client):
    headers = headers_for_role(client, "admin", "admin-prof-search@example.com")
    first = create_professional(
        client,
        headers,
        1,
        nome_completo="Profissional Busca Alfa",
        conselho_numero="ABC123",
        especialidade_principal="Pediatria",
        outras_especialidades=["Neonatologia"],
    )
    create_professional(client, headers, 2, nome_completo="Profissional Outro Beta")

    by_name = client.get("/api/v1/health-professionals?nome=busca", headers=headers)
    assert by_name.status_code == 200
    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["id"] == first["id"]

    by_cpf = client.get("/api/v1/health-professionals?cpf=000.000.000-01", headers=headers)
    assert by_cpf.status_code == 200
    assert by_cpf.json()["total"] == 1
    assert by_cpf.json()["items"][0]["id"] == first["id"]

    by_conselho = client.get("/api/v1/health-professionals?conselho=abc123", headers=headers)
    assert by_conselho.status_code == 200
    assert by_conselho.json()["total"] == 1
    assert by_conselho.json()["items"][0]["id"] == first["id"]

    by_specialty = client.get("/api/v1/health-professionals?especialidade=neonatologia", headers=headers)
    assert by_specialty.status_code == 200
    assert by_specialty.json()["total"] == 1
    assert by_specialty.json()["items"][0]["id"] == first["id"]


def test_create_health_professional_with_valid_user_link(client):
    headers = headers_for_role(client, "admin", "admin-prof-link@example.com")
    user_id = create_user_for_link("vinculo-valido@example.com")

    response = client.post(
        "/api/v1/health-professionals",
        headers=headers,
        json=professional_payload(1, user_id=user_id),
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == user_id


def test_create_rejects_duplicate_user_id(client):
    headers = headers_for_role(client, "admin", "admin-prof-user-dup@example.com")
    user_id = create_user_for_link("vinculo-duplicado@example.com")
    create_professional(client, headers, 1, user_id=user_id)

    response = client.post(
        "/api/v1/health-professionals",
        headers=headers,
        json=professional_payload(2, user_id=user_id),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Usuário já vinculado a outro profissional de saúde."


@pytest.mark.parametrize("role_code", ["medico", "enfermeiro", "recepcionista", "laboratorio", "farmacia"])
def test_allowed_roles_can_read_health_professionals(client, role_code):
    admin_headers = headers_for_role(client, "admin", f"admin-prof-{role_code}-seed@example.com")
    professional = create_professional(client, admin_headers, 1)
    headers = headers_for_role(client, role_code, f"{role_code}-prof-read@example.com")

    response = client.get(f"/api/v1/health-professionals/{professional['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == professional["id"]


@pytest.mark.parametrize("role_code", ["medico", "enfermeiro", "recepcionista", "laboratorio", "farmacia"])
def test_read_only_roles_cannot_create_health_professionals(client, role_code):
    headers = headers_for_role(client, role_code, f"{role_code}-prof-create-blocked@example.com")

    response = client.post("/api/v1/health-professionals", headers=headers, json=professional_payload(1))

    assert response.status_code == 403
    assert response.json()["detail"]["required_permissions"] == ["health_professionals:create"]


def test_paciente_role_cannot_access_health_professionals(client):
    admin_headers = headers_for_role(client, "admin", "admin-prof-paciente-seed@example.com")
    professional = create_professional(client, admin_headers, 1)
    paciente_headers = headers_for_role(client, "paciente", "paciente-prof-blocked@example.com")

    response = client.get(f"/api/v1/health-professionals/{professional['id']}", headers=paciente_headers)

    assert response.status_code == 403
    assert response.json()["detail"]["required_permissions"] == ["health_professionals:read"]


def test_user_without_permission_is_forbidden(client):
    headers = headers_without_permission()

    response = client.get("/api/v1/health-professionals", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"]["required_permissions"] == ["health_professionals:read"]


def test_missing_health_professional_returns_404(client):
    headers = headers_for_role(client, "admin", "admin-prof-not-found@example.com")

    response = client.get("/api/v1/health-professionals/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Profissional de saúde não encontrado."
