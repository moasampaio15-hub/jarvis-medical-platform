# JARVIS Medical Platform

JARVIS Medical Platform é uma base inicial para uma plataforma médica modular, preparada para evoluir com segurança, rastreabilidade e separação clara entre backend, frontend, inteligência artificial, banco de dados e testes.

> Este projeto é uma plataforma de software em estágio inicial. Qualquer funcionalidade clínica, assistiva ou de suporte à decisão médica deve ser validada por especialistas, auditada e adequada às normas regulatórias aplicáveis antes de uso em produção.

## Objetivos

- Centralizar serviços médicos digitais em uma arquitetura modular.
- Facilitar a evolução independente de API, interface, módulos de IA e camada de dados.
- Priorizar segurança, privacidade, observabilidade e testabilidade desde a fundação.
- Criar uma estrutura clara para colaboração técnica e documentação contínua.

## Estrutura do projeto

```text
jarvis-medical-platform/
├── AI/                  # Módulos de inteligência artificial e experimentos controlados
├── backend/             # Serviços de API, regras de negócio e integrações
├── database/            # Modelagem, migrações, seeds e artefatos de banco de dados
├── docs/                # Documentação técnica e decisões arquiteturais
├── frontend/            # Aplicação web e componentes de interface
├── scripts/             # Scripts operacionais, automações e utilitários
├── tests/               # Testes automatizados e recursos de validação
├── .gitignore           # Regras de versionamento para projetos Python
├── LICENSE              # Licença MIT
└── README.md            # Visão geral do projeto
```

## Componentes principais

### Backend

Responsável por expor APIs, coordenar regras de negócio, autenticação, autorização, integrações externas e acesso controlado à camada de dados.

A API inclui autenticação JWT e autorização RBAC completa com papéis, permissões granulares, associação de papéis a usuários, associação de permissões a papéis e dependências FastAPI `require_permission()` e `require_role()`. Consulte [`docs/RBAC.md`](docs/RBAC.md) para detalhes de uso e matriz inicial de permissões.

### Frontend

Responsável pela experiência do usuário, visualização de dados médicos e consumo seguro das APIs do backend.

### AI

Área dedicada a modelos, pipelines, prompts, avaliação de resultados, governança e componentes de inteligência artificial. Qualquer uso clínico deve passar por validação técnica, médica e regulatória.

### Database

Centraliza artefatos relacionados a banco de dados, incluindo modelagem, migrações, seeds e documentação da camada persistente.

### Tests

Contém testes automatizados para backend, frontend, integrações, segurança e validação de fluxos críticos.

### Docs

Guarda a documentação técnica do projeto. Consulte [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) para a visão arquitetural inicial.

## Princípios de engenharia

- Segurança e privacidade por padrão.
- Separação clara de responsabilidades.
- Código simples, testável e observável.
- Decisões arquiteturais documentadas.
- Validação rigorosa para qualquer fluxo relacionado à saúde.

## Começando

Instale as dependências Python e execute os testes:

```bash
python -m pip install -r requirements.txt
python -m pytest
```

A evolução do banco de dados usa Alembic. Para aplicar as migrações no banco configurado em `DATABASE_URL`:

```bash
alembic upgrade head
```

Depois de iniciar a API, a documentação Swagger fica disponível em `/docs`. Os endpoints RBAC administrativos são:

- `GET /rbac/me`, protegido por `perfil:ler`.
- `GET /rbac/roles`, protegido por `rbac:roles:ler`.
- `GET /rbac/permissions`, protegido por `rbac:permissoes:ler`.
- `POST /rbac/users/{user_id}/roles/{role_code}`, protegido por `rbac:roles:atribuir`.
- `DELETE /rbac/users/{user_id}/roles/{role_code}`, protegido por `rbac:roles:atribuir`.

### Módulo de cadastro e gestão de pacientes

O backend inclui o módulo versionado de pacientes em `/api/v1/patients`, voltado somente a dados cadastrais e administrativos. Dados clínicos, prontuários e registros assistenciais não fazem parte deste módulo.

Endpoints disponíveis:

- `POST /api/v1/patients`, protegido por `patients:create`.
- `GET /api/v1/patients`, protegido por `patients:read`, com filtros `nome`, `cpf`, `cns` e paginação `page`/`page_size`.
- `GET /api/v1/patients/{patient_id}`, protegido por `patients:read`.
- `PATCH /api/v1/patients/{patient_id}`, protegido por `patients:update`.
- `DELETE /api/v1/patients/{patient_id}`, protegido por `patients:deactivate`; realiza inativação lógica (`ativo=false`) e não remove o registro fisicamente.

Regras principais:

- `cpf` e `cns` são únicos quando informados.
- `email` é validado quando informado.
- Índices existem para busca por `nome_completo`, `cpf` e `cns`.
- Papéis com acesso administrativo ao módulo: `admin` (todas as ações), `medico`, `enfermeiro` e `recepcionista` (ler, criar e atualizar), `laboratorio` (ler). `farmacia` e `paciente` não recebem acesso por padrão.

### Módulo de profissionais de saúde

O backend inclui o módulo versionado de profissionais de saúde em `/api/v1/health-professionals`, voltado ao cadastro administrativo de profissionais com vínculo opcional a uma conta de usuário autenticável. O modelo não armazena senha e não duplica dados de autenticação do `User`.

Endpoints disponíveis no Swagger (`/docs`):

- `POST /api/v1/health-professionals`, protegido por `health_professionals:create`.
- `GET /api/v1/health-professionals`, protegido por `health_professionals:read`, com filtros `nome`, `cpf`, `conselho`, `especialidade` e paginação `page`/`page_size`.
- `GET /api/v1/health-professionals/{professional_id}`, protegido por `health_professionals:read`.
- `PATCH /api/v1/health-professionals/{professional_id}`, protegido por `health_professionals:update`.
- `DELETE /api/v1/health-professionals/{professional_id}`, protegido por `health_professionals:deactivate`; realiza inativação lógica (`ativo=false`) e não remove o registro fisicamente.

Regras principais:

- `cpf` é único quando informado.
- `user_id` é opcional, referencia `users.id` e é único quando informado.
- `conselho_numero`, `conselho_tipo` e `conselho_uf` são únicos em conjunto.
- Tipos de conselho suportados inicialmente: `CRM`, `COREN`, `CRO`, `CRF`, `CREFITO`, `CRP` e `outro`.
- Índices existem para busca por `nome_completo`, `cpf` e conselho.
- Papéis com acesso ao módulo: `admin` (todas as ações), `medico`, `enfermeiro`, `recepcionista`, `laboratorio` e `farmacia` (leitura). `paciente` não recebe acesso administrativo por padrão.

### Módulo de agenda e consultas

O backend inclui o módulo versionado de agenda em `/api/v1/appointments`, conectando pacientes e profissionais de saúde para agendamentos administrativos.

Endpoints disponíveis no Swagger (`/docs`):

- `POST /api/v1/appointments`, protegido por `consultas:gerenciar`.
- `GET /api/v1/appointments`, protegido por `consultas:ler`, com filtros `start_at`, `end_at`, `patient_id`, `professional_id`, `status` e paginação `page`/`page_size`.
- `GET /api/v1/appointments/{appointment_id}`, protegido por `consultas:ler`.
- `PATCH /api/v1/appointments/{appointment_id}/status`, protegido por `consultas:gerenciar`.
- `POST /api/v1/appointments/{appointment_id}/cancel`, protegido por `consultas:gerenciar`; cancela logicamente a consulta e libera o horário para novo agendamento.

Regras principais:

- A consulta referencia um paciente ativo e um profissional de saúde ativo.
- O intervalo deve ter `end_at` posterior a `start_at`.
- Status suportados inicialmente: `scheduled`, `confirmed`, `canceled`, `completed` e `no_show`.
- Consultas `scheduled` e `confirmed` bloqueiam conflitos de horário por paciente e por profissional.
- Consultas canceladas não bloqueiam novos agendamentos no mesmo horário.
- Papéis com acesso padrão: `admin`, `medico` e `recepcionista` gerenciam consultas; `enfermeiro` consulta a agenda. `laboratorio`, `farmacia` e `paciente` não recebem acesso à agenda por padrão.

Fluxo recomendado para os próximos passos:

1. Definir stack do backend.
2. Definir stack do frontend.
3. Escolher banco de dados e estratégia de migração.
4. Definir padrões de autenticação, autorização e auditoria.
5. Criar suíte mínima de testes automatizados.
6. Documentar decisões técnicas em `docs/`.

## Licença

Este projeto está licenciado sob a licença MIT. Consulte o arquivo [`LICENSE`](LICENSE) para mais detalhes.
