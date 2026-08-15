from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.clinical_note import ClinicalNoteCreate, ClinicalNoteList, ClinicalNoteRead, ClinicalNoteSearch, ClinicalNoteUpdate
from app.services.clinical_notes import (
    ClinicalNoteAppointmentMismatchError,
    ClinicalNoteAppointmentNotFoundError,
    ClinicalNoteEmptyContentError,
    ClinicalNoteMedicalRecordMismatchError,
    ClinicalNoteMedicalRecordNotFoundError,
    ClinicalNoteNotFoundError,
    ClinicalNotePatientNotFoundError,
    ClinicalNoteProfessionalNotFoundError,
    create_clinical_note,
    get_clinical_note,
    search_clinical_notes,
    update_clinical_note,
)

router = APIRouter(prefix="/api/v1/clinical-notes", tags=["Evoluções e Notas de Atendimento"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota clínica não encontrada.")


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _handle_validation_error(exc: ValueError) -> HTTPException:
    if isinstance(exc, ClinicalNotePatientNotFoundError):
        return _bad_request("Paciente não encontrado ou inativo.")
    if isinstance(exc, ClinicalNoteProfessionalNotFoundError):
        return _bad_request("Profissional de saúde não encontrado ou inativo.")
    if isinstance(exc, ClinicalNoteAppointmentNotFoundError):
        return _bad_request("Consulta não encontrada ou cancelada.")
    if isinstance(exc, ClinicalNoteAppointmentMismatchError):
        return _bad_request("Consulta não pertence ao paciente e profissional informados.")
    if isinstance(exc, ClinicalNoteMedicalRecordNotFoundError):
        return _bad_request("Prontuário médico não encontrado.")
    if isinstance(exc, ClinicalNoteMedicalRecordMismatchError):
        return _bad_request("Prontuário não pertence ao paciente informado.")
    if isinstance(exc, ClinicalNoteEmptyContentError):
        return _bad_request("Informe ao menos um campo clínico da nota.")
    return _bad_request("Nota clínica inválida.")


@router.post(
    "",
    response_model=ClinicalNoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar evolução ou nota de atendimento",
    description=(
        "Registra evolução/nota clínica vinculada ao paciente e profissional, com vínculo opcional "
        "a consulta e prontuário. Protegido por `evolucoes:gerenciar`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta, prontuário ou conteúdo inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `evolucoes:gerenciar` ausente."},
        status.HTTP_409_CONFLICT: {"description": "Nota clínica inválida."},
    },
)
def create_clinical_note_endpoint(
    payload: ClinicalNoteCreate,
    _: Annotated[User, Depends(require_permission("evolucoes:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> ClinicalNoteRead:
    try:
        note = create_clinical_note(db, payload)
    except ValueError as exc:
        raise _handle_validation_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nota clínica inválida.") from exc
    return ClinicalNoteRead.model_validate(note)


@router.get(
    "",
    response_model=ClinicalNoteList,
    summary="Listar evoluções e notas de atendimento",
    description="Lista notas clínicas com filtros por paciente, profissional, consulta, prontuário, tipo e período. Protegido por `evolucoes:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `evolucoes:ler` ausente."},
    },
)
def list_clinical_notes_endpoint(
    search: Annotated[ClinicalNoteSearch, Depends()],
    _: Annotated[User, Depends(require_permission("evolucoes:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> ClinicalNoteList:
    notes, total = search_clinical_notes(db, search)
    return ClinicalNoteList(
        items=[ClinicalNoteRead.model_validate(note) for note in notes],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{note_id}",
    response_model=ClinicalNoteRead,
    summary="Consultar evolução ou nota por ID",
    description="Retorna uma evolução/nota clínica. Protegido por `evolucoes:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `evolucoes:ler` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Nota clínica não encontrada."},
    },
)
def get_clinical_note_endpoint(
    note_id: int,
    _: Annotated[User, Depends(require_permission("evolucoes:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> ClinicalNoteRead:
    try:
        note = get_clinical_note(db, note_id)
    except ClinicalNoteNotFoundError as exc:
        raise _not_found_exception() from exc
    return ClinicalNoteRead.model_validate(note)


@router.patch(
    "/{note_id}",
    response_model=ClinicalNoteRead,
    summary="Atualizar evolução ou nota de atendimento",
    description="Atualiza conteúdo e vínculos da evolução/nota clínica. Protegido por `evolucoes:gerenciar`.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta, prontuário ou conteúdo inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `evolucoes:gerenciar` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Nota clínica não encontrada."},
        status.HTTP_409_CONFLICT: {"description": "Nota clínica inválida."},
    },
)
def update_clinical_note_endpoint(
    note_id: int,
    payload: ClinicalNoteUpdate,
    _: Annotated[User, Depends(require_permission("evolucoes:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> ClinicalNoteRead:
    try:
        note = update_clinical_note(db, note_id, payload)
    except ClinicalNoteNotFoundError as exc:
        raise _not_found_exception() from exc
    except ValueError as exc:
        raise _handle_validation_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nota clínica inválida.") from exc
    return ClinicalNoteRead.model_validate(note)
