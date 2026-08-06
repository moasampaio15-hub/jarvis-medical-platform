from fastapi.testclient import TestClient

from app.database.connection import get_engine, get_session_factory
from app.main import app


def test_database_health_endpoint_uses_configured_database(monkeypatch, tmp_path):
    database_path = tmp_path / "jarvis_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    response = TestClient(app).get("/sa%C3%BAde/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}

    get_engine.cache_clear()
    get_session_factory.cache_clear()
