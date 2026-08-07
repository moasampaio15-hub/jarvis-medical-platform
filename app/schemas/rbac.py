from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class RoleRead(BaseModel):
    id: int
    codigo: str
    nome: str
    descricao: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionRead(BaseModel):
    id: int
    codigo: str
    nome: str
    descricao: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CurrentUserAuthorizationRead(BaseModel):
    id: int
    nome: str
    email: EmailStr
    ativo: bool
    superuser: bool
    roles: list[str]
    permissions: list[str]


class UserRoleAssignmentRead(BaseModel):
    user_id: int
    email: EmailStr
    roles: list[str]
    permissions: list[str]
