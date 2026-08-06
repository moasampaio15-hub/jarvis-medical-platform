# JARVIS Medical Platform

Backend inicial do JARVIS Medical Platform construído com Python 3.13 e FastAPI.

## Estrutura

```text
app/
├── main.py
├── api/
├── core/
├── auth/
├── database/
├── models/
├── schemas/
├── services/
└── utils/
```

## Requisitos

- Python 3.13
- Dependências listadas em `requirements.txt`

## Configuração local

Crie um ambiente virtual e instale as dependências:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copie o arquivo de exemplo de variáveis de ambiente:

```bash
cp .env.example .env
```

## Executando a API

```bash
uvicorn app.main:app --reload
```

A documentação interativa ficará disponível em:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Endpoints iniciais

- `GET /` — mensagem de boas-vindas da API.
- `GET /saúde` — verificação de saúde da aplicação.

## Testes

```bash
pytest
```
