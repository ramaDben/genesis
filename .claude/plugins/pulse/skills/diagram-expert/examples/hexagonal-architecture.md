# Pulse — Arquitectura Hexagonal (ASCII)

Capas del motor (`src/pulse/`) y el boundary FastMCP que expone `.agents/` como Resources/Prompts. Top→bottom, dependencias siempre hacia adentro.

```text
                  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
                  ┃   LLM Client (Claude Code / Cursor / ...)    ┃
                  ┗━━━━━━━━━━━━━━━━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━┛
                                          │  MCP protocol (stdio)
                                          ▼
  ┌───────────────────────────────────────────────────────────────────────┐
  │ Infrastructure  ·  src/pulse/infrastructure/                          │
  │                                                                       │
  │   ┌──────────────────────┐  ┌───────────────────┐  ┌──────────────┐   │
  │   │  FastMCP Server      │  │ Settings          │  │  Adapters    │   │
  │   │  mcp.server          │  │ pydantic-settings │  │  (Anthropic, │   │
  │   │                      │  │ prefix=PULSE_     │  │   FS, ...)   │   │
  │   └──────────┬───────────┘  └─────────┬─────────┘  └──────┬───────┘   │
  └──────────────┼─────────────────────────┼───────────────────┼──────────┘
                 │                         │                   │
                 ▼                         ▼                   ▼
  ┌───────────────────────────────────────────────────────────────────────┐
  │ Application  ·  src/pulse/application/                                │
  │                                                                       │
  │   ┌──────────────────────┐         ┌───────────────────────────┐      │
  │   │  Use Cases /         │ ──────▶ │  FSM Engine               │      │
  │   │  Orchestrators       │         │  (SDD phase transitions)  │      │
  │   └──────────┬───────────┘         └───────────────┬───────────┘      │
  └──────────────┼─────────────────────────────────────┼──────────────────┘
                 │                                     │
                 ▼                                     ▼
  ┌───────────────────────────────────────────────────────────────────────┐
  │ Domain  ·  src/pulse/domain/                                          │
  │                                                                       │
  │   ┌──────────────────────┐         ┌───────────────────────────┐      │
  │   │  models.py           │ ◀─────▶ │  types.py / llm_types.py  │      │
  │   │  (Pydantic contracts)│         │                           │      │
  │   └──────────────────────┘         └───────────────────────────┘      │
  └───────────────────────────────────────────────────────────────────────┘


  ┌┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐
  ┆ .agents/  ·  passive data (no executable code)                        ┆
  ┆                                                                       ┆
  ┆   skills/*.md   rules/*.md   agents/*.md   templates/*.md             ┆
  ┆                                                                       ┆
  ┆        ▲                                                              ┆
  ┆        ┆ FastMCP reads & exposes as Resources / Prompts               ┆
  ┆        ┆ (línea punteada = lectura, no dependencia de código)         ┆
  └┄┄┄┄┄┄┄┄┆┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘
           └────────────────── reads from ─────────── FastMCP Server (arriba)
```

**Leyenda:**

- `┏━┓` (línea gruesa) → boundary externo / cliente.
- `┌─┐` (línea fina) → capas internas del motor.
- `┄ ┆` (punteada) → datos pasivos, no dependencias de código.
- `▶` / `▲` → dirección del flujo de datos o lectura.

**Invariantes que el diagrama refleja:**

- Dependencias hacia adentro: Infra → App → Domain (nunca al revés).
- `.agents/` no importa nada de `src/pulse/`.
- `Settings` se inyecta sólo en el borde (Infrastructure).
