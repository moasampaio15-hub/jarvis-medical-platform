# Repository notes for OpenHands

- Backend FastAPI code lives under `app/`; routers are registered in `app/main.py`.
- SQLAlchemy models use `app.database.base.Base` and should be exported from `app/models/__init__.py` so Alembic metadata and tests see them.
- Alembic env imports models from `app.models`; add new models there before migration validation.
- Tests use temporary SQLite databases by setting `DATABASE_URL`, clearing `get_engine`/`get_session_factory` caches, and running `Base.metadata.create_all(engine)`.
- RBAC defaults are defined in `app/auth/authorization.py`; update both permission definitions and role mappings when adding protected endpoints.
