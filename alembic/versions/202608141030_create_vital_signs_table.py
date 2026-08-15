"""create vital signs table

Revision ID: 202608141030
Revises: 202608140915
Create Date: 2026-08-14 10:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608141030"
down_revision: str | None = "202608140915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VITAL_SIGN_PERMISSIONS = (
    ("sinais_vitais:ler", "Ler sinais vitais", "Permite consultar sinais vitais e registros de triagem."),
    (
        "sinais_vitais:gerenciar",
        "Gerenciar sinais vitais",
        "Permite registrar e atualizar sinais vitais e registros de triagem.",
    ),
)

ROLE_PERMISSION_CODES = {
    "admin": ("sinais_vitais:ler", "sinais_vitais:gerenciar"),
    "medico": ("sinais_vitais:ler", "sinais_vitais:gerenciar"),
    "enfermeiro": ("sinais_vitais:ler", "sinais_vitais:gerenciar"),
}


def _tables() -> tuple[sa.TableClause, sa.TableClause, sa.TableClause]:
    roles = sa.table("roles", sa.column("id", sa.Integer), sa.column("codigo", sa.String))
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("codigo", sa.String),
        sa.column("nome", sa.String),
        sa.column("descricao", sa.String),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    return roles, permissions, role_permissions


def _upsert_permission(bind, permissions, codigo: str, nome: str, descricao: str) -> int:
    permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.codigo == codigo))
    if permission_id is None:
        bind.execute(permissions.insert().values(codigo=codigo, nome=nome, descricao=descricao))
        permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.codigo == codigo))
    else:
        bind.execute(permissions.update().where(permissions.c.codigo == codigo).values(nome=nome, descricao=descricao))
    return int(permission_id)


def _grant_permission(bind, role_permissions, role_id: int, permission_id: int) -> None:
    exists = bind.scalar(
        sa.select(role_permissions.c.role_id).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission_id,
        )
    )
    if exists is None:
        bind.execute(role_permissions.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    op.create_table(
        "vital_signs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("professional_id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("medical_record_id", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("pressao_sistolica", sa.SmallInteger(), nullable=True),
        sa.Column("pressao_diastolica", sa.SmallInteger(), nullable=True),
        sa.Column("frequencia_cardiaca", sa.SmallInteger(), nullable=True),
        sa.Column("frequencia_respiratoria", sa.SmallInteger(), nullable=True),
        sa.Column("temperatura_c", sa.Numeric(4, 1), nullable=True),
        sa.Column("spo2", sa.SmallInteger(), nullable=True),
        sa.Column("peso_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("altura_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("imc", sa.Numeric(5, 2), nullable=True),
        sa.Column("glicemia_capilar", sa.SmallInteger(), nullable=True),
        sa.Column("dor_escala", sa.SmallInteger(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("pressao_sistolica IS NULL OR pressao_sistolica BETWEEN 50 AND 300", name="ck_vital_signs_pressao_sistolica"),
        sa.CheckConstraint("pressao_diastolica IS NULL OR pressao_diastolica BETWEEN 30 AND 200", name="ck_vital_signs_pressao_diastolica"),
        sa.CheckConstraint("frequencia_cardiaca IS NULL OR frequencia_cardiaca BETWEEN 20 AND 250", name="ck_vital_signs_frequencia_cardiaca"),
        sa.CheckConstraint("frequencia_respiratoria IS NULL OR frequencia_respiratoria BETWEEN 5 AND 80", name="ck_vital_signs_frequencia_respiratoria"),
        sa.CheckConstraint("temperatura_c IS NULL OR temperatura_c BETWEEN 30 AND 45", name="ck_vital_signs_temperatura_c"),
        sa.CheckConstraint("spo2 IS NULL OR spo2 BETWEEN 0 AND 100", name="ck_vital_signs_spo2"),
        sa.CheckConstraint("peso_kg IS NULL OR peso_kg BETWEEN 0.5 AND 500", name="ck_vital_signs_peso_kg"),
        sa.CheckConstraint("altura_cm IS NULL OR altura_cm BETWEEN 30 AND 250", name="ck_vital_signs_altura_cm"),
        sa.CheckConstraint("imc IS NULL OR imc BETWEEN 5 AND 100", name="ck_vital_signs_imc"),
        sa.CheckConstraint("glicemia_capilar IS NULL OR glicemia_capilar BETWEEN 20 AND 1000", name="ck_vital_signs_glicemia_capilar"),
        sa.CheckConstraint("dor_escala IS NULL OR dor_escala BETWEEN 0 AND 10", name="ck_vital_signs_dor_escala"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["medical_record_id"], ["medical_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["health_professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vital_signs_appointment_id", "vital_signs", ["appointment_id"], unique=False)
    op.create_index("ix_vital_signs_medical_record_id", "vital_signs", ["medical_record_id"], unique=False)
    op.create_index("ix_vital_signs_patient_id", "vital_signs", ["patient_id"], unique=False)
    op.create_index("ix_vital_signs_professional_id", "vital_signs", ["professional_id"], unique=False)
    op.create_index("ix_vital_signs_recorded_at", "vital_signs", ["recorded_at"], unique=False)
    op.create_index("ix_vital_signs_patient_recorded", "vital_signs", ["patient_id", "recorded_at"], unique=False)
    op.create_index("ix_vital_signs_professional_recorded", "vital_signs", ["professional_id", "recorded_at"], unique=False)

    bind = op.get_bind()
    roles, permissions, role_permissions = _tables()
    role_ids = {code: bind.scalar(sa.select(roles.c.id).where(roles.c.codigo == code)) for code in ROLE_PERMISSION_CODES}
    permission_ids = {
        codigo: _upsert_permission(bind, permissions, codigo, nome, descricao)
        for codigo, nome, descricao in VITAL_SIGN_PERMISSIONS
    }

    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role_id = role_ids.get(role_code)
        if role_id is None:
            continue
        for permission_code in permission_codes:
            _grant_permission(bind, role_permissions, int(role_id), permission_ids[permission_code])


def downgrade() -> None:
    bind = op.get_bind()
    _, permissions, role_permissions = _tables()
    permission_codes = [codigo for codigo, _, _ in VITAL_SIGN_PERMISSIONS]
    permission_ids = list(bind.scalars(sa.select(permissions.c.id).where(permissions.c.codigo.in_(permission_codes))).all())
    if permission_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    bind.execute(permissions.delete().where(permissions.c.codigo.in_(permission_codes)))

    op.drop_index("ix_vital_signs_professional_recorded", table_name="vital_signs")
    op.drop_index("ix_vital_signs_patient_recorded", table_name="vital_signs")
    op.drop_index("ix_vital_signs_recorded_at", table_name="vital_signs")
    op.drop_index("ix_vital_signs_professional_id", table_name="vital_signs")
    op.drop_index("ix_vital_signs_patient_id", table_name="vital_signs")
    op.drop_index("ix_vital_signs_medical_record_id", table_name="vital_signs")
    op.drop_index("ix_vital_signs_appointment_id", table_name="vital_signs")
    op.drop_table("vital_signs")
