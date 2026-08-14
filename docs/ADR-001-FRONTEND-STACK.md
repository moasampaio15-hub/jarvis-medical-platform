# ADR-001: Stack inicial do frontend

- Status: aceita
- Data: 2026-08-14

## Contexto

O backend já oferece uma API FastAPI modular com autenticação JWT, autorização RBAC e contratos documentados pelo OpenAPI. O projeto precisava definir uma base web que preservasse tipagem, baixo acoplamento e uma evolução incremental por módulos.

## Decisão

Adotar React com TypeScript e Vite para o portal web. A camada inicial inclui:

- cliente HTTP centralizado e configurável por ambiente;
- autenticação contra `/auth/login` e restauração via `/auth/me`;
- sessão limitada à aba do navegador por `sessionStorage`;
- proxy de desenvolvimento para a API FastAPI;
- ESLint, TypeScript estrito e build de produção como verificações obrigatórias;
- interface responsiva e acessível, sem biblioteca visual externa nesta fase.

## Consequências

- Os módulos podem ser implementados gradualmente sem alterar a fundação.
- O frontend permanece independente do processo do backend.
- A ausência inicial de roteamento e gerenciamento de estado externo reduz complexidade, mas deverá ser revista quando os primeiros fluxos CRUD forem adicionados.
- Antes de produção, autenticação por cookies `HttpOnly`, política CSP, telemetria e testes end-to-end devem ser avaliados.
