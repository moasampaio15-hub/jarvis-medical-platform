# Arquitetura do JARVIS Medical Platform

## Visão geral

O JARVIS Medical Platform é planejado como uma plataforma médica modular, com separação explícita entre interface, APIs, inteligência artificial, persistência de dados, automações e testes. A estrutura inicial favorece evolução incremental, rastreabilidade e governança técnica.

```text
Usuários e equipes clínicas
          │
          ▼
Frontend ───────► Backend/API ───────► Database
                    │   │
                    │   └────────────► Serviços externos
                    │
                    └────────────────► AI
```

## Camadas do sistema

### Frontend

A camada `frontend/` será responsável por entregar a experiência web da plataforma. Ela deve consumir APIs autenticadas, apresentar dados médicos de forma clara e evitar expor regras sensíveis no cliente.

Responsabilidades principais:

- Interfaces para usuários, administradores e perfis clínicos.
- Validação inicial de formulários e feedback visual.
- Consumo seguro das APIs do backend.
- Acessibilidade, responsividade e padronização visual.

### Backend

A camada `backend/` será o núcleo transacional da plataforma. Ela deve concentrar regras de negócio, autenticação, autorização, auditoria, integrações e orquestração entre módulos.

Responsabilidades principais:

- Exposição de APIs versionadas.
- Aplicação de regras de negócio.
- Controle de acesso por papéis e permissões.
- Validação de entrada e tratamento de erros.
- Auditoria de operações sensíveis.
- Integração com banco de dados, módulos de IA e serviços externos.

### AI

A pasta `AI/` será dedicada a recursos de inteligência artificial, como modelos, pipelines, avaliações, prompts e integrações com provedores externos.

Responsabilidades principais:

- Isolar lógica de IA do núcleo transacional.
- Registrar versões de modelos, prompts e estratégias de avaliação.
- Definir métricas de qualidade, segurança e viés.
- Suportar validação humana antes de qualquer uso clínico relevante.

Qualquer funcionalidade assistiva ou clínica baseada em IA deve ter trilha de auditoria, explicabilidade adequada ao contexto e validação por especialistas.

### Database

A pasta `database/` centralizará a evolução da camada de persistência.

Responsabilidades principais:

- Modelagem de entidades e relacionamentos.
- Migrações de banco de dados.
- Seeds para ambientes controlados.
- Documentação de políticas de retenção, backup e recuperação.
- Definição de dados sensíveis e regras de proteção.

### Scripts

A pasta `scripts/` armazenará automações operacionais e utilitários de desenvolvimento.

Exemplos de uso:

- Inicialização de ambiente local.
- Rotinas de manutenção.
- Verificações de qualidade.
- Tarefas de migração ou carga controlada de dados.

### Tests

A pasta `tests/` concentrará a suíte de validação automatizada.

Tipos de teste esperados:

- Testes unitários.
- Testes de integração.
- Testes de contrato de API.
- Testes de segurança e autorização.
- Testes end-to-end para fluxos críticos.

## Fluxo de dados inicial

1. O usuário interage com o `frontend/`.
2. O frontend envia requisições autenticadas para o `backend/`.
3. O backend valida entrada, identidade, permissões e regras de negócio.
4. O backend consulta ou persiste dados por meio da camada `database/`.
5. Quando necessário, o backend chama componentes em `AI/` ou serviços externos.
6. Todas as operações sensíveis devem gerar registros auditáveis.
7. A resposta é retornada ao frontend com o mínimo necessário de dados.

## Segurança, privacidade e conformidade

A plataforma deve tratar dados médicos como altamente sensíveis. Desde a fundação, a arquitetura deve considerar:

- Criptografia em trânsito e em repouso.
- Autenticação forte.
- Autorização RBAC com papéis, permissões e menor privilégio.
- Privilégios mínimos para serviços, usuários e integrações.
- Auditoria de acesso e alterações em dados sensíveis.
- Mascaramento de dados em logs.
- Gestão segura de segredos fora do repositório.
- Políticas alinhadas à LGPD e demais normas aplicáveis ao contexto de operação.

## Observabilidade

A arquitetura deve incluir telemetria desde as primeiras entregas:

- Logs estruturados.
- Métricas de aplicação e infraestrutura.
- Rastreamento de requisições.
- Alertas para falhas críticas e eventos de segurança.

## Estratégia de evolução

A estrutura inicial permite começar como um monorepo modular. Conforme o produto amadurecer, componentes com necessidades independentes de escala, deploy ou governança poderão ser extraídos para serviços separados.

Critérios para extração futura:

- Escala independente.
- Ciclo de deploy próprio.
- Requisitos de segurança distintos.
- Complexidade operacional justificada.
- Fronteiras de domínio bem definidas.

## Próximas decisões arquiteturais

- Stack do backend.
- Stack do frontend.
- Banco de dados primário.
- Estratégia de autenticação e autorização.
- Padrão de versionamento de APIs.
- Estratégia de migrações.
- Pipeline de CI/CD.
- Requisitos regulatórios por mercado-alvo.
