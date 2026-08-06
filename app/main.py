from fastapi import FastAPI, HTTPException, status

from app.database.connection import check_database_connection

app = FastAPI(title="JARVIS Medical Platform")


@app.get("/saúde/db")
def database_health_check() -> dict[str, str]:
    if not check_database_connection():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    return {"status": "ok", "database": "connected"}
