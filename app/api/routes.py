from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    return {"message": "JARVIS Medical Platform API"}


@router.get("/saúde")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
