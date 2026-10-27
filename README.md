# uMarket

La tienda del estudiante: cada estudiante que vende en su campus publica su tienda, y quien
compra escribe lo que se le antoja (*"algo dulce por menos de 5 mil pa las 12 en el 19"*) y ve qué
vendedores lo tienen **en stock**, dónde y a qué hora. Pide con clics, el vendedor aprueba con un
toque y el pago es en persona.

> **El modelo interpreta lenguaje, el código verifica hechos, una persona decide.**

- Qué y por qué: [`PLAN-Y-DECISIONES.md`](PLAN-Y-DECISIONES.md) · idea original: [`Idea-uMarket.pdf`](Idea-uMarket.pdf)
- Cómo está construido: [`PLAN-TECNICO.md`](PLAN-TECNICO.md) · decisiones: [`docs/DECISIONES.md`](docs/DECISIONES.md)
- Evals de la IA: [`backend/evals/README.md`](backend/evals/README.md)

## Qué hay

| | |
| --- | --- |
| `backend/` | FastAPI + SQLAlchemy + PostgreSQL. Monolito modular hexagonal: `identidad`, `campus`, `catalogo`, `pedidos`, `reputacion`, `notificaciones`, `busqueda`, la plataforma `ia/` (puerto LLM heredado de QuickDev) y el `worker` (vencimientos y outbox). |
| `web/` | Next.js 16 (App Router, Cache Components) + Tailwind, PWA. Cliente tipado generado desde el OpenAPI. |
| `backend/contratos/` | JSON Schemas del intérprete y OpenAPI, **generados desde el código** y protegidos por tests golden; contrato de producto del componente de IA. |
| `backend/evals/` | Dataset, catálogo fixture, runner, resultados versionados (baseline vs Gemini) y regresiones. |

## Arranque local (Windows, macOS o Linux)

Requisitos: Docker, Python 3.13+ con [`uv`](https://docs.astral.sh/uv/) y Node 24.

```bash
docker compose up -d --wait                  # Postgres 17 local (puerto 5433)

cd backend
uv sync                                      # dependencias exactas (uv.lock)
cp .env.example .env                         # y ajusta lo que necesites
uv run alembic upgrade head                  # migraciones
uv run python scripts/sembrar_datos.py --demo   # campus demo + 7 tiendas con turnos para HOY
uv run uvicorn umarket.arranque:app --factory --port 8000
uv run umarket-worker                        # en otra terminal: vencimientos y avisos

cd ../web
npm install
npm run dev                                  # http://localhost:3000
```

Para entrar, usa cualquier correo `@demo.edu.co`; con `CODIGO_ACCESO_FIJO=123456` en local el
código es siempre ese (en producción está prohibido y el código llega por correo). Las vendedoras
del catálogo demo entran con `<slug-de-la-tienda>@demo.edu.co`, por ejemplo
`empanadas-dona-rosa@demo.edu.co`.

## Verificación

```bash
cd backend
uv run python scripts/verificar.py            # ruff, import-linter, pyright, pytest, regresiones
uv run python scripts/exportar_contratos.py --verificar
uv run python -m evals correr --interprete palabras          # baseline de la búsqueda
uv run pytest -m llm                          # smoke contra Gemini real (gasta cuota)

cd ../web
npm run tipos && npm run lint && npm test && npm run build
DATABASE_URL=postgresql+psycopg://umarket:umarket@localhost:5433/umarket_e2e \
  uv run --directory ../backend python scripts/preparar_e2e.py
npx playwright test                           # E2E en viewport de celular
```

Estado al 2026-10-27: **283 tests backend** (1 `llm` deseleccionado), **20/20 regresiones**,
**6 tests unitarios web**, **3 E2E**, build de producción en verde. La CI
(`.github/workflows/ci.yml`) corre todo eso sin clave de LLM.

## La IA, en una tabla

| | Sin IA (por defecto) | Con Gemini |
| --- | --- | --- |
| `BUSQUEDA_INTERPRETE` | `palabras` | `intencion` (siempre con respaldo) o `ab` |
| acierto@5 en intención | 42 % | 92 % |
| p95 de interpretación | ~0 s | 23 s con la clave actual |

Gemini **no entra todavía** porque no supera el umbral acordado (D-22). El modelo nunca toca
precios, stock ni el orden de las tiendas: el contrato `ConsultaInterpretada` no tiene campos para
eso, y cada filtro que propone se verifica contra el texto (`consulta-v2`).

Cambiar de proveedor es un adaptador en `backend/src/umarket/ia/adaptadores/` más una línea en
`PROVEEDORES`, y pasar `tests/ia/test_contrato_llm.py`.

## Neon

En `backend/.env`: `DATABASE_URL` con la cadena **pooled** (`-pooler`) y `DATABASE_URL_DIRECTA`
con la directa; Alembic usa la directa. `config.py` acepta el `postgresql://` que entrega Neon.
Fuera de local, `ENTORNO=preview|produccion` exige `SECRETO_SERVIDOR` propio, `COOKIE_SEGURA=true`
y prohíbe `CODIGO_ACCESO_FIJO`.
