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

Fluxo recomendado para os próximos passos:

1. Definir stack do backend.
2. Definir stack do frontend.
3. Escolher banco de dados e estratégia de migração.
4. Definir padrões de autenticação, autorização e auditoria.
5. Criar suíte mínima de testes automatizados.
6. Documentar decisões técnicas em `docs/`.

## Licença

Este projeto está licenciado sob a licença MIT. Consulte o arquivo [`LICENSE`](LICENSE) para mais detalhes.
