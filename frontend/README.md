# Frontend — JARVIS Medical Platform

Aplicação web em React, TypeScript e Vite. Este primeiro incremento entrega autenticação integrada à API, restauração de sessão, verificação de saúde do backend e a estrutura visual do portal profissional.

## Desenvolvimento

```bash
npm install
npm run dev
```

Por padrão, o Vite encaminha `/auth`, `/api`, `/rbac` e `/saúde` para `http://127.0.0.1:8000`. Copie `.env.example` para `.env` se precisar alterar o destino.

## Validação

```bash
npm run lint
npm run build
```

Tokens permanecem apenas em `sessionStorage` e são removidos ao sair ou quando a restauração da sessão falha. Uma estratégia baseada em cookies `HttpOnly` deve ser avaliada antes do uso em produção.
