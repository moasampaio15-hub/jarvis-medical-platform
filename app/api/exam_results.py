from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.exam_result import (
    ExamResultCreate,
    ExamResultList,
    ExamResultRead,
    ExamResultSearch,
    ExamResultUpdate,
)
from app.services.exam_results import (
    ExamResultDuplicateExamOrderError,
    ExamResultDuplicateOrderItemError,
    ExamResultExamOrderNotFoundError,
    ExamResultNotFoundError,
    ExamResultOrderItemMismatchError,
    ExamResultProfessionalNotFoundError,
    create_exam_result,
    get_exam_result,
    search_exam_results,
    update_exam_result,
)

router = APIRouter(prefix="/api/v1/exam-results", tags=["Resultados de Exames"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resultado de exame não encontrado.")


def _invalid_exam_order_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Solicitação de exame não encontrada ou cancelada.",
    )


def _invalid_professional_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Profissional de saúde não encontrado ou inativo.",
    )


def _duplicate_exam_order_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Solicitação de exame já possui resultado registrado.",
    )


def _invalid_item_exception(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@router.post(
    "",
    response_model=ExamResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar resultado de exame",
    description=(
        "Registra resultados/laudos vinculados a uma solicitação de exames. "
        "Protegido por `exames:gerenciar`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Solicitação, profissional ou itens inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `exames:gerenciar` ausente."},
        status.HTTP_409_CONFLICT: {"description": "Resultado de exame inválido ou duplicado."},
    },
)
def create_exam_result_endpoint(
    payload: ExamResultCreate,
    _: Annotated[User, Depends(require_permission("exames:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> ExamResultRead:
    try:
        exam_result = create_exam_result(db, payload)
    except ExamResultExamOrderNotFoundError as exc:
        raise _invalid_exam_order_exception() from exc
    except ExamResultProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except ExamResultDuplicateExamOrderError as exc:
        raise _duplicate_exam_order_exception() from exc
    except ExamResultOrderItemMismatchError as exc:
        raise _invalid_item_exception("Item de exame não pertence à solicitação informada.") from exc
    except ExamResultDuplicateOrderItemError as exc:
        raise _invalid_item_exception("Item de solicitação duplicado no resultado.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resultado de exame inválido.") from exc
    return ExamResultRead.model_validate(exam_result)


@router.get(
    "",
    response_model=ExamResultList,
    summary="Listar resultados de exames",
    description="Lista resultados com filtros por solicitação, paciente, profissional e status. Protegido por `exames:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `exames:ler` ausente."},
    },
)
def list_exam_results_endpoint(
    search: Annotated[ExamResultSearch, Depends()],
    _: Annotated[User, Depends(require_permission("exames:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> ExamResultList:
    exam_results, total = search_exam_results(db, search)
    return ExamResultList(
        items=[ExamResultRead.model_validate(exam_result) for exam_result in exam_results],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{exam_result_id}",
    response_model=ExamResultRead,
    summary="Consultar resultado de exame por ID",
    description="Retorna o resultado/laudo e seus itens. Protegido por `exames:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `exames:ler` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Resultado de exame não encontrado."},
    },
)
def get_exam_result_endpoint(
    exam_result_id: int,
    _: Annotated[User, Depends(require_permission("exames:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> ExamResultRead:
    try:
        exam_result = get_exam_result(db, exam_result_id)
    except ExamResultNotFoundError as exc:
        raise _not_found_exception() from exc
    return ExamResultRead.model_validate(exam_result)


@router.patch(
    "/{exam_result_id}",
    response_model=ExamResultRead,
    summary="Atualizar resultado de exame",
    description="Atualiza status, profissional, laudo, datas e itens do resultado. Protegido por `exames:gerenciar`.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Profissional ou itens inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `exames:gerenciar` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Resultado de exame não encontrado."},
        status.HTTP_409_CONFLICT: {"description": "Resultado de exame inválido."},
    },
)
def update_exam_result_endpoint(
    exam_result_id: int,
    payload: ExamResultUpdate,
    _: Annotated[User, Depends(require_permission("exames:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> ExamResultRead:
    try:
        exam_result = update_exam_result(db, exam_result_id, payload)
    except ExamResultNotFoundError as exc:
        raise _not_found_exception() from exc
    except ExamResultExamOrderNotFoundError as exc:
        raise _invalid_exam_order_exception() from exc
    except ExamResultProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except ExamResultOrderItemMismatchError as exc:
        raise _invalid_item_exception("Item de exame não pertence à solicitação informada.") from exc
    except ExamResultDuplicateOrderItemError as exc:
        raise _invalid_item_exception("Item de solicitação duplicado no resultado.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resultado de exame inválido.") from exc
    return ExamResultRead.model_validate(exam_result)
