# Autorização RBAC

O backend usa autorização baseada em papéis e permissões (RBAC) sobre a autenticação JWT existente.

## Modelo de dados

- `roles`: papéis disponíveis na plataforma.
- `permissions`: permissões que podem proteger endpoints e regras de negócio.
- `user_roles`: associação muitos-para-muitos entre usuários e papéis.
- `role_permissions`: associação muitos-para-muitos entre papéis e permissões.

As tabelas são criadas pela migração Alembic `202608061701_create_rbac_tables.py`.

## Papéis e permissões padrão

A migração cria os seguintes códigos padrão em `roles` e `permissions`:

| Código | Nome |
| --- | --- |
| `admin` | Administrador |
| `medico` | Médico |
| `enfermeiro` | Enfermeiro |
| `recepcionista` | Recepcionista |
| `laboratorio` | Laboratório |
| `farmacia` | Farmácia |
| `paciente` | Paciente |

Cada papel recebe a permissão homônima. O papel `admin` recebe todas as permissões padrão. Usuários com `superuser=True` também passam nas validações de autorização.

Novos usuários registrados pela API recebem o papel `paciente` por padrão.

## Proteção de endpoints

Use `require_permission()` como dependência FastAPI para proteger endpoints:

```python
from typing import Annotated

from fastapi import Depends

from app.auth import require_permission
from app.models.user import User


@router.get("/area-medica")
def read_medical_area(
    current_user: Annotated[User, Depends(require_permission("medico"))],
) -> dict[str, str]:
    return {"status": "authorized"}
```

Para exigir todas as permissões informadas, use `require_all=True`:

```python
Depends(require_permission("medico", "laboratorio", require_all=True))
```

Sem `require_all=True`, basta que o usuário tenha uma das permissões informadas.

## Decorators de autorização

Para funções de serviço ou handlers que recebem `current_user` ou `user` e `db` ou `session`, use `@requires_permission()` ou o alias `@authorization_required()`:

```python
from sqlalchemy.orm import Session

from app.auth import requires_permission
from app.models.user import User


@requires_permission("farmacia")
def dispense_medication(*, current_user: User, db: Session) -> None:
    ...
```

Para endpoints FastAPI, prefira a dependência `require_permission()`, porque ela preserva o fluxo nativo de injeção de dependências e documentação OpenAPI.

## Evolução esperada

Endpoints administrativos para criar papéis, conceder permissões e atribuir papéis a usuários devem reutilizar os modelos `Role`, `Permission`, `UserRole` e `RolePermission`, protegidos por `require_permission("admin")`.
