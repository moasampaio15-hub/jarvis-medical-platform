# Autorização RBAC

O backend usa autorização baseada em papéis e permissões (RBAC) integrada ao JWT existente. O token continua identificando o usuário autenticado; a autorização é calculada no servidor a partir das tabelas RBAC.

## Modelo de dados

- `roles`: papéis disponíveis na plataforma.
- `permissions`: permissões granulares que protegem endpoints e regras de negócio.
- `user_roles`: associação muitos-para-muitos entre usuários e papéis.
- `role_permissions`: associação muitos-para-muitos entre papéis e permissões.

As tabelas base são criadas pela migração `202608061701_create_rbac_tables.py`. A migração `202608071636_seed_granular_rbac_permissions.py` adiciona permissões granulares e os vínculos padrão por papel.

## Papéis padrão

| Código | Nome | Escopo padrão |
| --- | --- | --- |
| `admin` | Administrador | Administração total e todas as permissões cadastradas. |
| `medico` | Médico | Pacientes, leitura de profissionais de saúde, consultas, prontuários, exames e medicamentos em contexto clínico. |
| `enfermeiro` | Enfermeiro | Pacientes, leitura de profissionais de saúde, consultas, prontuários e medicamentos em contexto assistencial. |
| `recepcionista` | Recepcionista | Cadastro de pacientes, leitura de profissionais de saúde e gestão de consultas. |
| `laboratorio` | Laboratório | Leitura cadastral de pacientes, leitura de profissionais de saúde e exames. |
| `farmacia` | Farmácia | Leitura de profissionais de saúde, medicamentos e dispensação, sem acesso administrativo ao módulo versionado de pacientes por padrão. |
| `paciente` | Paciente | Perfil próprio e portal do paciente, sem acesso administrativo a pacientes ou profissionais de saúde por padrão. |

Novos usuários registrados pela API recebem o papel `paciente` por padrão.

## Permissões granulares padrão

Além das permissões homônimas aos papéis, mantidas por compatibilidade, o seed cria permissões no formato `recurso:ação`:

| Permissão | Uso |
| --- | --- |
| `perfil:ler` | Consultar o próprio perfil e contexto RBAC. |
| `rbac:roles:ler` | Listar papéis. |
| `rbac:permissoes:ler` | Listar permissões. |
| `rbac:roles:atribuir` | Conceder ou revogar papéis de usuários. |
| `pacientes:ler` | Consultar dados de pacientes em fluxos legados ou futuros. |
| `pacientes:criar` | Cadastrar pacientes em fluxos legados ou futuros. |
| `pacientes:atualizar` | Atualizar cadastro de pacientes em fluxos legados ou futuros. |
| `patients:read` | Consultar cadastros administrativos no módulo versionado `/api/v1/patients`. |
| `patients:create` | Cadastrar pacientes no módulo versionado, sem dados clínicos. |
| `patients:update` | Atualizar dados cadastrais no módulo versionado. |
| `patients:deactivate` | Inativar logicamente pacientes no módulo versionado. |
| `health_professionals:read` | Consultar cadastros administrativos no módulo versionado `/api/v1/health-professionals`. |
| `health_professionals:create` | Cadastrar profissionais de saúde no módulo versionado, com vínculo opcional a `users`. |
| `health_professionals:update` | Atualizar dados administrativos e vínculo opcional de profissionais de saúde. |
| `health_professionals:deactivate` | Inativar logicamente profissionais de saúde no módulo versionado. |
| `consultas:ler` | Consultar consultas. |
| `consultas:gerenciar` | Criar, reagendar ou cancelar consultas. |
| `prontuarios:ler` | Consultar prontuários. |
| `prontuarios:escrever` | Registrar evoluções ou anotações clínicas. |
| `exames:ler` | Consultar exames. |
| `exames:gerenciar` | Processar e publicar resultados de exames. |
| `medicamentos:ler` | Consultar prescrições e medicamentos. |
| `medicamentos:dispensar` | Registrar dispensação de medicamentos. |
| `portal_paciente:ler` | Consultar informações próprias no portal do paciente. |

Usuários com `superuser=True` passam nas validações. Usuários com papel `admin` também passam nas validações de papel e permissão.

## Proteção de endpoints por permissão

Use `require_permission()` como dependência FastAPI:

```python
from typing import Annotated

from fastapi import Depends

from app.auth import require_permission
from app.models.user import User


@router.get("/prontuarios")
def list_medical_records(
    current_user: Annotated[User, Depends(require_permission("prontuarios:ler"))],
) -> dict[str, str]:
    return {"status": "authorized"}
```

Para exigir todas as permissões informadas, use `require_all=True`:

```python
Depends(require_permission("pacientes:ler", "prontuarios:ler", require_all=True))
```

Sem `require_all=True`, basta que o usuário tenha uma das permissões informadas.

## Proteção de endpoints por papel

Use `require_role()` quando a regra for explicitamente baseada no papel, e não em uma permissão funcional:

```python
from typing import Annotated

from fastapi import Depends

from app.auth import require_role
from app.models.user import User


@router.get("/area-medica")
def read_medical_area(
    current_user: Annotated[User, Depends(require_role("medico"))],
) -> dict[str, str]:
    return {"status": "authorized"}
```

## Usuário autenticado e contexto de autorização

`get_current_user()` valida o Bearer JWT, busca o usuário ativo e carrega os atributos dinâmicos:

- `current_user.role_codes`
- `current_user.permission_codes`

Endpoints protegidos por `require_permission()` e `require_role()` reutilizam esse usuário autenticado e retornam `403` quando a autorização falha.

## Endpoints RBAC

Os endpoints aparecem no Swagger/OpenAPI com descrições das permissões exigidas:

| Endpoint | Permissão exigida |
| --- | --- |
| `GET /rbac/me` | `perfil:ler` |
| `GET /rbac/roles` | `rbac:roles:ler` |
| `GET /rbac/permissions` | `rbac:permissoes:ler` |
| `POST /rbac/users/{user_id}/roles/{role_code}` | `rbac:roles:atribuir` |
| `DELETE /rbac/users/{user_id}/roles/{role_code}` | `rbac:roles:atribuir` |
| `POST /api/v1/patients` | `patients:create` |
| `GET /api/v1/patients` | `patients:read` |
| `GET /api/v1/patients/{patient_id}` | `patients:read` |
| `PATCH /api/v1/patients/{patient_id}` | `patients:update` |
| `DELETE /api/v1/patients/{patient_id}` | `patients:deactivate` |
| `POST /api/v1/health-professionals` | `health_professionals:create` |
| `GET /api/v1/health-professionals` | `health_professionals:read` |
| `GET /api/v1/health-professionals/{professional_id}` | `health_professionals:read` |
| `PATCH /api/v1/health-professionals/{professional_id}` | `health_professionals:update` |
| `DELETE /api/v1/health-professionals/{professional_id}` | `health_professionals:deactivate` |

## Decorators de autorização

Para funções de serviço que recebem `current_user` ou `user` e `db` ou `session`, use `@requires_permission()` ou o alias `@authorization_required()`:

```python
from sqlalchemy.orm import Session

from app.auth import requires_permission
from app.models.user import User


@requires_permission("medicamentos:dispensar")
def dispense_medication(*, current_user: User, db: Session) -> None:
    ...
```

Para endpoints FastAPI, prefira as dependências `require_permission()` e `require_role()`, porque elas preservam o fluxo nativo de injeção de dependências e documentação OpenAPI.
