from __future__ import annotations

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.health_professional import HealthProfessional
from app.models.user import User
from app.schemas.health_professional import (
    HealthProfessionalCreate,
    HealthProfessionalSearch,
    HealthProfessionalUpdate,
)


class HealthProfessionalNotFoundError(ValueError):
    pass


class HealthProfessionalDuplicateError(ValueError):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"Profissional de saúde com {field} já cadastrado.")


class HealthProfessionalUserNotFoundError(ValueError):
    pass


def _professional_exists_with_field(
    db: Session,
    field_name: str,
    value: str | int | None,
    *,
    exclude_professional_id: int | None = None,
) -> bool:
    if value is None:
        return False

    column = getattr(HealthProfessional, field_name)
    statement = select(HealthProfessional.id).where(column == value)
    if exclude_professional_id is not None:
        statement = statement.where(HealthProfessional.id != exclude_professional_id)
    return db.scalar(statement) is not None


def _professional_exists_with_conselho(
    db: Session,
    *,
    conselho_numero: str,
    conselho_tipo: str,
    conselho_uf: str,
    exclude_professional_id: int | None = None,
) -> bool:
    statement = select(HealthProfessional.id).where(
        HealthProfessional.conselho_numero == conselho_numero,
        HealthProfessional.conselho_tipo == conselho_tipo,
        HealthProfessional.conselho_uf == conselho_uf,
    )
    if exclude_professional_id is not None:
        statement = statement.where(HealthProfessional.id != exclude_professional_id)
    return db.scalar(statement) is not None


def _assert_user_exists(db: Session, user_id: int | None) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise HealthProfessionalUserNotFoundError("Usuário vinculado não encontrado.")


def _assert_unique_identifiers(
    db: Session,
    *,
    cpf: str | None,
    user_id: int | None,
    conselho_numero: str,
    conselho_tipo: str,
    conselho_uf: str,
    exclude_professional_id: int | None = None,
) -> None:
    if _professional_exists_with_field(db, "cpf", cpf, exclude_professional_id=exclude_professional_id):
        raise HealthProfessionalDuplicateError("cpf")
    if _professional_exists_with_field(db, "user_id", user_id, exclude_professional_id=exclude_professional_id):
        raise HealthProfessionalDuplicateError("user_id")
    if _professional_exists_with_conselho(
        db,
        conselho_numero=conselho_numero,
        conselho_tipo=conselho_tipo,
        conselho_uf=conselho_uf,
        exclude_professional_id=exclude_professional_id,
    ):
        raise HealthProfessionalDuplicateError("conselho")


def create_health_professional(db: Session, payload: HealthProfessionalCreate) -> HealthProfessional:
    data = payload.model_dump()
    _assert_user_exists(db, data.get("user_id"))
    _assert_unique_identifiers(
        db,
        cpf=data.get("cpf"),
        user_id=data.get("user_id"),
        conselho_numero=data["conselho_numero"],
        conselho_tipo=data["conselho_tipo"],
        conselho_uf=data["conselho_uf"],
    )

    professional = HealthProfessional(**data)
    db.add(professional)
    db.commit()
    db.refresh(professional)
    return professional


def get_health_professional(db: Session, professional_id: int) -> HealthProfessional:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None:
        raise HealthProfessionalNotFoundError("Profissional de saúde não encontrado.")
    return professional


def update_health_professional(
    db: Session, professional_id: int, payload: HealthProfessionalUpdate
) -> HealthProfessional:
    professional = get_health_professional(db, professional_id)
    data = payload.model_dump(exclude_unset=True)

    user_id = data.get("user_id", professional.user_id)
    conselho_numero = data.get("conselho_numero", professional.conselho_numero)
    conselho_tipo = data.get("conselho_tipo", professional.conselho_tipo)
    conselho_uf = data.get("conselho_uf", professional.conselho_uf)

    _assert_user_exists(db, user_id)
    _assert_unique_identifiers(
        db,
        cpf=data.get("cpf", professional.cpf),
        user_id=user_id,
        conselho_numero=conselho_numero,
        conselho_tipo=conselho_tipo,
        conselho_uf=conselho_uf,
        exclude_professional_id=professional.id,
    )

    for field, value in data.items():
        setattr(professional, field, value)

    db.commit()
    db.refresh(professional)
    return professional


def deactivate_health_professional(db: Session, professional_id: int) -> HealthProfessional:
    professional = get_health_professional(db, professional_id)
    professional.ativo = False
    db.commit()
    db.refresh(professional)
    return professional


def search_health_professionals(
    db: Session, search: HealthProfessionalSearch
) -> tuple[list[HealthProfessional], int]:
    statement = select(HealthProfessional)

    if search.nome:
        nome = f"%{search.nome.strip().lower()}%"
        statement = statement.where(func.lower(HealthProfessional.nome_completo).like(nome))
    if search.cpf:
        statement = statement.where(HealthProfessional.cpf == search.cpf)
    if search.conselho:
        conselho = f"%{search.conselho.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(HealthProfessional.conselho_tipo).like(conselho),
                func.lower(HealthProfessional.conselho_numero).like(conselho),
                func.lower(HealthProfessional.conselho_uf).like(conselho),
            )
        )
    if search.especialidade:
        especialidade = f"%{search.especialidade.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(HealthProfessional.especialidade_principal).like(especialidade),
                func.lower(cast(HealthProfessional.outras_especialidades, String)).like(especialidade),
            )
        )

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.order_by(HealthProfessional.nome_completo.asc(), HealthProfessional.id.asc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total
