# CaseCellShop

Sistema MVP de e-commerce para venda de capinhas de celular. Desenvolvido para resolver os principais problemas de infraestrutura durante o período de hypercrescimento: **venda sem estoque (race condition)** e **dependência total do ERP legado**.

> This is a challenge by [Coodesh](https://coodesh.com/)

---

## Stack de Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.12 · FastAPI (async) |
| ORM | SQLAlchemy 2.x async · asyncpg |
| Banco próprio | PostgreSQL 16 |
| Resiliência | tenacity (circuit breaker + retry) |
| Logging | structlog (JSON estruturado) |
| Migrations | Alembic |
| Frontend | React 18 · TypeScript · Vite |
| Estado/Requests | TanStack Query v5 |
| Estilo | Tailwind CSS |
| Infra | Docker · Docker Compose |

---

## Como Executar

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose instalados
- Portas `5432`, `8000` e `5173` disponíveis

### 1. Clone o repositório

```bash
git clone <url-do-repo>
cd CaseCellShop
```

### 2. Suba os containers

```bash
docker compose up --build
```

Aguarde os três serviços ficarem saudáveis. O backend roda as migrations automaticamente via Alembic e sincroniza os produtos do ERP (mock) na inicialização.

### 3. Acesse a aplicação

- **Frontend:** http://localhost:5173
- **API (Swagger):** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

---

## Como Executar os Testes

### 1. Suba o banco de testes

```bash
docker compose -f docker-compose.test.yml up -d
```

Aguarde o container ficar healthy (usa `tmpfs` — sem I/O de disco, rápido).

### 2. Instale as dependências e rode os testes

```bash
cd backend
pip install -e ".[dev]"
TEST_DATABASE_URL=postgresql+asyncpg://test:test@localhost:5433/casecell_test pytest -v
```

### 3. Testes de concorrência

Os testes de race condition estão em `backend/tests/concurrent/test_race_conditions.py`. Eles são incluídos automaticamente no `pytest -v` acima e simulam 20 usuários tentando comprar o último item disponível simultaneamente.

---

## Arquitetura

```
┌──────────────────────────────────────────────────────┐
│                   Cliente (browser)                  │
└──────────────────────────┬───────────────────────────┘
                           │ HTTP
┌──────────────────────────▼───────────────────────────┐
│             Frontend (React + Vite)                  │
│   TanStack Query · Axios · Tailwind CSS              │
└──────────────────────────┬───────────────────────────┘
                           │ REST API
┌──────────────────────────▼───────────────────────────┐
│          Backend (FastAPI + Python 3.12)              │
│                                                      │
│  ┌─────────────────┐   ┌──────────────────────────┐  │
│  │  Routers (API)  │   │  Background Tasks         │  │
│  │  /products      │   │  · ERP sync (5 min)       │  │
│  │  /cart          │   │  · Cleanup TTL (60 s)     │  │
│  │  /orders        │   └──────────────────────────┘  │
│  └────────┬────────┘                                 │
│           │                                          │
│  ┌────────▼──────────────────────────────────────┐   │
│  │  Services                                      │   │
│  │  stock_service  → SELECT FOR UPDATE            │   │
│  │  order_service  → idempotency key check        │   │
│  │  erp_service    → circuit breaker + cache      │   │
│  └────────┬──────────────────────────────────────┘   │
└───────────┼──────────────────────────────────────────┘
            │
    ┌───────┴───────────────────────────┐
    │                                   │
    ▼                                   ▼
┌─────────────────┐         ┌──────────────────────┐
│  PostgreSQL 16  │         │  ERP MySQL (read-only │
│  (nosso banco)  │         │  ou MockERPService)   │
│  · products     │         │                       │
│  · stock        │         │  Fonte de dados de    │
│  · carts        │         │  produtos e estoque   │
│  · reservations │         │  inicial              │
│  · orders       │         └──────────────────────┘
└─────────────────┘
```

---

## Decisões de Arquitetura e Tradeoffs

### 1. Locking Pessimista (`SELECT FOR UPDATE`)

**Decisão:** Ao adicionar um item ao carrinho, adquirimos um lock exclusivo na linha de estoque do PostgreSQL antes de verificar disponibilidade.

**Por quê:** Quando dois usuários tentam comprar o último item simultaneamente, o lock serializa as transações. A segunda transação espera na fila e, ao adquirir o lock, vê `quantity_available = 0` e retorna HTTP 409.

**Tradeoff:** Locking pessimista reduz throughput sob alta contenção no mesmo produto. Uma alternativa seria locking **otimista** (coluna `version` + retry), que tem maior throughput mas exige lógica de retry na aplicação. Para o MVP, a simplicidade e a correção garantida do pessimista foram priorizadas. Em cenários de drops relâmpago com centenas de requests/segundo para um produto, o otimista seria mais eficiente.

### 2. Padrão de Reserva de Estoque com TTL

**Decisão:** Ao adicionar ao carrinho, o estoque é imediatamente reservado (movido de `quantity_available` para `quantity_reserved`) com validade de 15 minutos. A confirmação definitiva acontece apenas no checkout.

**Por quê:** Sem reserva, o estoque só seria decrementado no checkout, permitindo que muitos usuários vissem disponibilidade mas apenas um conseguisse comprar — experiência frustrante. Com reserva, o sistema é honesto sobre disponibilidade desde o carrinho.

**Tradeoff:** Reservas expiradas precisam ser liberadas por um background task. O `SKIP LOCKED` na query de cleanup evita que o processo de limpeza bloqueie checkouts em andamento.

### 3. PostgreSQL como Banco Próprio

**Decisão:** PostgreSQL 16 para o banco da aplicação (separado do MySQL do ERP).

**Por quê:** `SELECT FOR UPDATE`, transações ACID, `ON CONFLICT DO UPDATE` (upsert) para a sync do ERP, e `SKIP LOCKED` para o cleanup. SQLite não suporta `SELECT FOR UPDATE` e tem limitações em writes concorrentes — exatamente o problema que precisamos resolver.

**Tradeoff:** Adiciona um serviço extra no Docker Compose. SQLite seria mais simples de operar mas incorreria nos bugs de concorrência que são o problema central do projeto.

### 4. Circuit Breaker para o ERP

**Decisão:** O `MockERPService` implementa um state machine de três estados: `closed → open → half-open`. Após 5 falhas consecutivas, o circuito abre. Em estado aberto, retorna dados do cache em memória sem tentar conectar ao ERP.

**Por quê:** O ERP é um sistema legado com comportamento imprevisível. Lentidão no ERP não pode bloquear nossa API. Com circuit breaker, após N falhas, paramos de tentar e servimos do cache por 30s antes de tentar novamente.

**Tradeoff:** O cache em memória **não é compartilhado entre réplicas**. Em deploy com múltiplas instâncias, cada processo tem seu próprio estado. Para produção multi-réplica, substituir por Redis (detalhado em Próximos Passos).

### 5. Idempotência no Checkout

**Decisão:** O frontend gera um UUID v4 (`idempotency_key`) antes de fazer a requisição de checkout. O backend verifica se já existe um pedido com aquela chave antes de criar um novo.

**Por quê:** Redes são instáveis. Se a requisição timar out após o pedido ser criado no servidor, o usuário vai tentar de novo. Sem idempotência, criaria dois pedidos e decrementaria o estoque duas vezes.

**Como o frontend protege:** TanStack Query's `useMutation` + botão desabilitado via `mutation.isPending` impede cliques duplicados. O `useRef` garante que o mesmo `idempotency_key` é reenviado em retentativas da mesma sessão de checkout.

### 6. Monólito vs. Microserviços

**Decisão:** Monólito (frontend + backend + PostgreSQL).

**Por quê:** O problema principal (race condition de estoque) é mais fácil de resolver com transações de banco do que com mensageria distribuída. Microserviços com eventual consistency tornariam o overselling *mais difícil* de prevenir, não mais fácil.

**Tradeoff:** O monólito escala verticalmente. Para escala massiva, o gargalo seria o PostgreSQL — solução seria sharding ou fila distribuída (Kafka + eventos de reserva), documentado em Próximos Passos.

### 7. TanStack Query no Frontend

**Decisão:** TanStack Query v5 para gerenciamento de estado das requisições.

**Por quê:** Resolve os três requisitos do frontend de uma vez:
- **Deduplicação:** `useQuery` não dispara dois requests simultâneos com a mesma query key
- **Loading states:** `isLoading`/`isPending` prontos para uso sem boilerplate
- **Mutation lock:** `mutation.isPending` desabilita o botão de submit enquanto o request está em voo

**Tradeoff:** Bundle ligeiramente maior que fetch puro (~13KB gzip). Aceitável dado o DX e a correção que oferece.

### 8. Session Anônima via localStorage

**Decisão:** O carrinho é identificado por um `session_id` (UUID) gerado no frontend e persistido em `localStorage`.

**Por quê:** Evita autenticação no MVP, que adicionaria semanas de desenvolvimento para pouco valor no curto prazo.

**Tradeoff:** Se o usuário limpar o localStorage ou trocar de dispositivo, perde o carrinho. As reservas expiram em 15 minutos e o estoque é liberado automaticamente.

---

## Limitações do Sistema

| Limitação | Impacto | Caminho para resolução |
|-----------|---------|------------------------|
| Cache ERP em memória (não distribuído) | Em múltiplas réplicas, cache desincronizado | Redis compartilhado |
| Sem autenticação | Qualquer um pode criar carrinho e pedido | JWT + accounts |
| Drift de estoque entre syncs (5 min) | ERP pode atualizar entre cycles | Sync mais frequente + webhook do ERP |
| Sem write-back ao ERP | Pedidos não aparecem no ERP automaticamente | Kafka / API do ERP |
| Sem pagamento real | Apenas fluxo de pedido | Stripe / Mercado Pago |
| Circuit breaker não persistido | Reiniciar o serviço reseta o estado | Estado no Redis |

---

## Próximos Passos

### Curto prazo
- **Autenticação:** JWT com refresh token; vincular carrinho ao usuário autenticado
- **Write-back ao ERP:** Publicar eventos de pedido confirmado via Kafka para o ERP processar
- **Redis:** Substituir cache em memória para compartilhamento entre réplicas e circuit breaker distribuído

### Médio prazo
- **Integração de pagamento:** Stripe/Mercado Pago com webhook de confirmação
- **WebSocket para estoque em tempo real:** Notificar frontend quando estoque muda
- **Monitoramento:** Prometheus + Grafana para métricas de requests, stock locks e circuit breaker events
- **Testes de carga:** k6 ou Locust para validar comportamento sob alta carga

### Longo prazo
- **Event Sourcing para auditoria:** Todo evento de estoque vira um imutável event log
- **CQRS:** Separar reads (Redis/ElasticSearch) de writes (PostgreSQL) para escalar leitura de produto independentemente
- **Decomposição em serviços:** Stock Service, Order Service e Catalog Service separados quando cada um tiver times dedicados

---

## Estrutura do Projeto

```
CaseCellShop/
├── backend/
│   ├── app/
│   │   ├── main.py                   # App factory + lifespan (background tasks)
│   │   ├── config.py                 # Settings via pydantic-settings + .env
│   │   ├── database.py               # SQLAlchemy async engine
│   │   ├── models/                   # ORM: Product, Stock, Cart, Reservation, Order
│   │   ├── schemas/                  # Pydantic v2 request/response schemas
│   │   ├── routers/                  # FastAPI routers: /products, /cart, /orders
│   │   ├── services/
│   │   │   ├── stock_service.py      # SELECT FOR UPDATE — núcleo anti-oversell
│   │   │   ├── order_service.py      # Checkout com idempotência
│   │   │   ├── cart_service.py       # CRUD de carrinho
│   │   │   ├── erp_service.py        # MockERP + circuit breaker
│   │   │   ├── erp_sync.py           # Sync periódico ERP → PostgreSQL
│   │   │   └── reservation_cleanup.py # Background cleanup de TTL expirado
│   │   └── middleware/logging.py     # structlog JSON middleware
│   ├── alembic/                      # Migrations
│   ├── tests/
│   │   ├── unit/                     # Testes unitários por serviço/endpoint
│   │   └── concurrent/               # Testes de race condition com asyncio.gather
│   ├── pyproject.toml
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                      # Axios client + chamadas por recurso
│   │   ├── hooks/                    # useProducts, useCart, useCheckout, useSession
│   │   ├── pages/                    # ProductListPage, CartPage, CheckoutPage
│   │   └── components/               # ProductCard, CartItem, Navbar, LoadingSpinner...
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml                # Dev: postgres + backend + frontend
├── docker-compose.test.yml           # Testes: postgres_test (tmpfs)
└── README.md
```

---

## Variáveis de Ambiente

Copie `backend/.env.example` para `backend/.env` para desenvolvimento local sem Docker:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | `postgresql+asyncpg://casecell:casecell_pw@localhost:5432/casecell` | Banco principal |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://test:test@localhost:5433/casecell_test` | Banco de testes |
| `USE_MOCK_ERP` | `true` | Usar MockERPService (dev) ou MySQL real |
| `MOCK_ERP_DELAY_SECONDS` | `0.1` | Delay simulado das chamadas ao ERP |
| `MOCK_ERP_FAIL_RATE` | `0.0` | Taxa de falha simulada (0.0–1.0) para testar circuit breaker |
| `ERP_SYNC_INTERVAL_SECONDS` | `300` | Intervalo entre syncs com o ERP |
| `ERP_CIRCUIT_FAILURE_THRESHOLD` | `5` | Falhas antes de abrir o circuit breaker |
| `RESERVATION_TTL_MINUTES` | `15` | Tempo de vida das reservas de estoque |
| `CORS_ORIGINS` | `http://localhost:5173` | Origins permitidas pelo CORS |
