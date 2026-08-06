from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    role_permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    users: Mapped[list[User]] = relationship(secondary="user_roles", viewonly=True)
    permissions: Mapped[list[Permission]] = relationship(secondary="role_permissions", viewonly=True)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    role_permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )
    roles: Mapped[list[Role]] = relationship(secondary="role_permissions", viewonly=True)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="user_roles")
    role: Mapped[Role] = relationship(back_populates="user_roles")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    role: Mapped[Role] = relationship(back_populates="role_permissions")
    permission: Mapped[Permission] = relationship(back_populates="role_permissions")
