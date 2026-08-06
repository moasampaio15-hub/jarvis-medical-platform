from typing import Annotated

import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission, requires_permission
from app.auth.authorization import get_user_permission_codes, get_user_role_codes
from app.auth.password import verify_password
from app.database.base import Base
from app.database.connection import get_engine, get_session_factory
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.main import app

STRONG_PASSWORD = "SenhaForte#123"


@app.get("/_tests/rbac/paciente")
def read_patient_test_area(
    current_user: Annotated[User, Depends(require_permission("paciente"))],
) -> dict[str, str]:
    return {"email": current_user.email}


@app.get("/_tests/rbac/admin")
def read_admin_test_area(
    current_user: Annotated[User, Depends(require_permission("admin"))],
) -> dict[str, str]:
    return {"email": current_user.email}


@pytest.fixture()
def client(monkeypatch, tmp_path):
    database_path = tmp_path / "jarvis_auth_test.db"
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


def register_payload(email: str = "ada@example.com") -> dict[str, str]:
    return {
        "nome": "Ada Lovelace",
        "email": email,
        "senha": STRONG_PASSWORD,
    }


def register_user(client: TestClient, email: str = "ada@example.com") -> dict:
    response = client.post("/auth/register", json=register_payload(email=email))
    assert response.status_code == 201
    return response.json()


def test_register_assigns_default_patient_role_and_permissions(client):
    register_user(client)

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        user = session.query(User).filter_by(email="ada@example.com").one()
        assert get_user_role_codes(session, user.id) == {"paciente"}
        assert get_user_permission_codes(session, user.id) == {"paciente"}


def test_require_permission_allows_patient_and_rejects_admin_area(client):
    registration = register_user(client)
    access_token = registration["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    patient_response = client.get("/_tests/rbac/paciente", headers=headers)
    assert patient_response.status_code == 200
    assert patient_response.json() == {"email": "ada@example.com"}

    admin_response = client.get("/_tests/rbac/admin", headers=headers)
    assert admin_response.status_code == 403
    assert admin_response.json()["detail"]["required_permissions"] == ["admin"]


def test_admin_role_grants_access_to_all_default_permissions(client):
    registration = register_user(client)
    access_token = registration["tokens"]["access_token"]

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        user = session.query(User).filter_by(email="ada@example.com").one()
        admin_role = session.scalar(select(Role).where(Role.codigo == "admin"))
        assert admin_role is not None
        session.add(UserRole(user_id=user.id, role_id=admin_role.id))
        session.commit()

    response = client.get(
        "/_tests/rbac/admin",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"email": "ada@example.com"}


def test_requires_permission_decorator_validates_service_function(client):
    register_user(client)

    @requires_permission("paciente")
    def patient_service(*, current_user: User, db: Session) -> str:
        return current_user.email

    @requires_permission("admin")
    def admin_service(*, current_user: User, db: Session) -> str:
        return current_user.email

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        user = session.query(User).filter_by(email="ada@example.com").one()
        assert patient_service(current_user=user, db=session) == "ada@example.com"
        with pytest.raises(HTTPException) as exc_info:
            admin_service(current_user=user, db=session)

    assert exc_info.value.status_code == 403


def test_register_creates_active_user_with_hashed_password(client):
    response = client.post("/auth/register", json=register_payload(email="ADA@Example.com"))

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["nome"] == "Ada Lovelace"
    assert body["user"]["ativo"] is True
    assert body["user"]["superuser"] is False
    assert "senha_hash" not in body["user"]
    assert body["tokens"]["token_type"] == "bearer"
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        user = session.query(User).filter_by(email="ada@example.com").one()
        assert user.senha_hash != STRONG_PASSWORD
        assert verify_password(STRONG_PASSWORD, user.senha_hash)


def test_register_rejects_weak_password(client):
    payload = register_payload()
    payload["senha"] = "fraca"

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_register_rejects_password_outside_security_policy(client):
    payload = register_payload()
    payload["senha"] = "senhafraca"

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 400
    assert "letra maiúscula" in " ".join(response.json()["detail"])
    assert "número" in " ".join(response.json()["detail"])


def test_register_rejects_password_longer_than_bcrypt_limit(client):
    payload = register_payload()
    payload["senha"] = "SenhaForte#123" + "A" * 60

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 400
    assert "72 bytes" in " ".join(response.json()["detail"])


def test_register_rejects_duplicate_email_case_insensitive(client):
    register_user(client, email="Ada@Example.com")

    response = client.post("/auth/register", json=register_payload(email="ada@example.com"))

    assert response.status_code == 409
    assert response.json()["detail"] == "E-mail já cadastrado."


def test_login_returns_tokens_and_me_returns_authenticated_user(client):
    register_user(client)

    login_response = client.post(
        "/auth/login",
        json={"email": "ADA@example.com", "senha": STRONG_PASSWORD},
    )

    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "ada@example.com"


def test_login_rejects_invalid_password(client):
    register_user(client)

    response = client.post(
        "/auth/login",
        json={"email": "ada@example.com", "senha": "SenhaErrada#123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "E-mail ou senha inválidos."


def test_refresh_issues_new_tokens_and_rejects_access_token(client):
    registration = register_user(client)
    access_token = registration["tokens"]["access_token"]
    refresh_token = registration["tokens"]["refresh_token"]

    invalid_refresh_response = client.post("/auth/refresh", json={"refresh_token": access_token})
    assert invalid_refresh_response.status_code == 401

    refresh_response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert refresh_response.status_code == 200
    refreshed_tokens = refresh_response.json()
    assert refreshed_tokens["access_token"] != access_token
    assert refreshed_tokens["refresh_token"] != refresh_token

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refreshed_tokens['access_token']}"},
    )
    assert me_response.status_code == 200


def test_me_requires_valid_bearer_token(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_openapi_documents_auth_endpoints_and_bearer_security(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()
    for path in ["/auth/register", "/auth/login", "/auth/refresh", "/auth/me"]:
        assert path in openapi["paths"]
    security_schemes = openapi["components"]["securitySchemes"].values()
    assert any(
        scheme["type"] == "http" and scheme["scheme"] == "bearer"
        for scheme in security_schemes
    )
