# IPBCB — API RESTful

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.x-092E20?logo=django&logoColor=white)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.16-red?logo=django&logoColor=white)](https://www.django-rest-framework.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![JWT](https://img.shields.io/badge/Auth-JWT-000000?logo=jsonwebtokens&logoColor=white)](https://jwt.io)

API REST do sistema de gerenciamento da **Igreja Presbiteriana de Castelo Branco**, desenvolvida com Django e Django REST Framework. Gerencia membros, escala mensal, repertório musical e galeria de fotos.

---

## Tecnologias

- **Python 3.14** + **Django 6** + **Django REST Framework**
- **PostgreSQL 16** — banco de dados principal
- **SimpleJWT** — autenticação via tokens JWT
- **Google OAuth 2.0** — login social
- **drf-spectacular** — documentação OpenAPI/Swagger
- **Gunicorn + Uvicorn** — servidor ASGI
- **Docker / Docker Compose** — containerização

---

## Módulos

| App | Responsabilidade |
|---|---|
| `accounts` | Autenticação, cadastro e perfis de usuário |
| `members` | Diretório de membros da igreja |
| `songs` | Repertório, hinário e histórico de músicas tocadas |
| `schedule` | Geração automática da escala mensal |
| `gallery` | Álbuns e upload de fotos |

---

## Como Rodar

**Pré-requisito:** Docker Compose

```bash

git clone https://github.com/GabriellAfonso/ipb_castelo_branco-SERVER.git
cd ipb_castelo_branco-SERVER

# Renomeie o arquivo .env.example para .env 
cp .env.example .env

#Rode o docker compose para subir o ambiente
docker compose up --build
```

A API sobe em `http://localhost:8000`.

---

## Variáveis de ambiente

```env
DJANGO_SECRET_KEY=       # chave secreta do Django
DJANGO_ALLOWED_HOSTS=    # hosts permitidos
GOOGLE_CLIENT_ID=        # ID do app Google OAuth
POSTGRES_DB=             # nome do banco
POSTGRES_USER=           # usuário do banco
POSTGRES_PASSWORD=       # senha do banco
POSTGRES_HOST=           # host do banco
```

---

## Documentação da API

Com o servidor rodando, acesse:

| Interface | URL |
|---|---|
| Swagger UI | `/api/schema/swagger-ui/` |
| ReDoc | `/api/schema/redoc/` |
| Schema JSON | `/api/schema/` |

---

## Arquitetura

O projeto segue princípios de **Clean Architecture** com elementos de DDD:

```
server/
├── apps/          # Camada de apresentação (views, serializers, models)
├── core/
│   ├── domain/    # Entidades e interfaces
│   └── application/ # DTOs e serviços de aplicação
└── config/        # Configurações e roteamento
```

Injeção de dependência via `dependency-injector`. Repositórios abstraem o acesso a dados, e serviços de domínio orquestram a lógica de negócio.

---

## App Android

O aplicativo mobile que consome esta API está disponível em: [ipbcb-app](https://github.com/GabriellAfonso/ipb_castelo_branco-APP)

---

GNU General Public License v3.0 — veja [LICENSE](./LICENSE) para detalhes.
