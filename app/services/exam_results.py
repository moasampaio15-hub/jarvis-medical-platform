from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.exam_order import ExamOrder, ExamOrderItem
from app.models.exam_result import ExamResult, ExamResultItem
from app.models.health_professional import HealthProfessional
from app.schemas.exam_order import ExamOrderStatus
from app.schemas.exam_result import ExamResultCreate, ExamResultSearch, ExamResultStatus, ExamResultUpdate


class ExamResultNotFoundError(ValueError):
    pass


class ExamResultExamOrderNotFoundError(ValueError):
    pass


class ExamResultProfessionalNotFoundError(ValueError):
    pass


class ExamResultDuplicateExamOrderError(ValueError):
    pass


class ExamResultOrderItemMismatchError(ValueError):
    pass


class ExamResultDuplicateOrderItemError(ValueError):
    pass


def _status_value(status: ExamResultStatus | str) -> str:
    return status.value if isinstance(status, ExamResultStatus) else status


def _get_valid_exam_order(db: Session, exam_order_id: int) -> ExamOrder:
    statement = (
        select(ExamOrder)
        .options(selectinload(ExamOrder.items))
        .where(ExamOrder.id == exam_order_id)
    )
    exam_order = db.scalar(statement)
    if exam_order is None or exam_order.status == ExamOrderStatus.CANCELED.value:
        raise ExamResultExamOrderNotFoundError("Solicitação de exame não encontrada ou cancelada.")
    return exam_order


def _assert_professional_exists(db: Session, professional_id: int) -> None:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None or not professional.ativo:
        raise ExamResultProfessionalNotFoundError("Profissional de saúde não encontrado ou inativo.")


def _assert_unique_exam_order(db: Session, exam_order_id: int) -> None:
    exists = db.scalar(select(ExamResult.id).where(ExamResult.exam_order_id == exam_order_id))
    if exists is not None:
        raise ExamResultDuplicateExamOrderError("Solicitação de exame já possui resultado registrado.")


def _build_items(exam_order: ExamOrder, items: list[dict]) -> list[ExamResultItem]:
    order_items_by_id: dict[int, ExamOrderItem] = {item.id: item for item in exam_order.items}
    seen_item_ids: set[int] = set()
    result_items: list[ExamResultItem] = []

    for item in items:
        order_item_id = item["exam_order_item_id"]
        if order_item_id in seen_item_ids:
            raise ExamResultDuplicateOrderItemError("Item de solicitação duplicado no resultado.")
        seen_item_ids.add(order_item_id)

        order_item = order_items_by_id.get(order_item_id)
        if order_item is None:
            raise ExamResultOrderItemMismatchError("Item de exame não pertence à solicitação informada.")

        item_data = dict(item)
        item_data["nome_exame"] = order_item.nome_exame
        item_data["codigo"] = order_item.codigo
        result_items.append(ExamResultItem(**item_data))

    return result_items


def create_exam_result(db: Session, payload: ExamResultCreate) -> ExamResult:
    data = payload.model_dump()
    items_data = data.pop("items")
    exam_order = _get_valid_exam_order(db, data["exam_order_id"])
    _assert_professional_exists(db, data["professional_id"])
    _assert_unique_exam_order(db, exam_order.id)

    exam_result = ExamResult(
        **data,
        patient_id=exam_order.patient_id,
        status=ExamResultStatus.DRAFT.value,
    )
    exam_result.items = _build_items(exam_order, items_data)
    db.add(exam_result)
    db.commit()
    db.refresh(exam_result)
    return exam_result


def get_exam_result(db: Session, exam_result_id: int) -> ExamResult:
    statement = (
        select(ExamResult)
        .options(selectinload(ExamResult.items))
        .where(ExamResult.id == exam_result_id)
    )
    exam_result = db.scalar(statement)
    if exam_result is None:
        raise ExamResultNotFoundError("Resultado de exame não encontrado.")
    return exam_result


def search_exam_results(db: Session, search: ExamResultSearch) -> tuple[list[ExamResult], int]:
    statement = select(ExamResult)

    if search.exam_order_id is not None:
        statement = statement.where(ExamResult.exam_order_id == search.exam_order_id)
    if search.patient_id is not None:
        statement = statement.where(ExamResult.patient_id == search.patient_id)
    if search.professional_id is not None:
        statement = statement.where(ExamResult.professional_id == search.professional_id)
    if search.status is not None:
        statement = statement.where(ExamResult.status == _status_value(search.status))

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.options(selectinload(ExamResult.items))
        .order_by(ExamResult.created_at.desc(), ExamResult.id.desc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total


def update_exam_result(db: Session, exam_result_id: int, payload: ExamResultUpdate) -> ExamResult:
    exam_result = get_exam_result(db, exam_result_id)
    data = payload.model_dump(exclude_unset=True)
    items_data = data.pop("items", None)

    if "professional_id" in data and data["professional_id"] is not None:
        _assert_professional_exists(db, data["professional_id"])
    if "status" in data and data["status"] is not None:
        data["status"] = _status_value(data["status"])

    for field, value in data.items():
        setattr(exam_result, field, value)

    if items_data is not None:
        exam_order = _get_valid_exam_order(db, exam_result.exam_order_id)
        exam_result.items = _build_items(exam_order, items_data)

    db.commit()
    db.refresh(exam_result)
    return exam_result
