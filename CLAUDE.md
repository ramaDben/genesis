# CLAUDE.md — genesis

## Qué es este proyecto

Pipeline de validación institucional para prop firms: un **torneo de candidatos de estrategia** (A: CT sweep-fade, B: ORB intradía en índices — prioridad, C: TSMOM — diferido) bajo gates mecánicos idénticos (G/C/P/T). **SSoT**: `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` — todo cambio de alcance se valida contra el spec, los gates nunca se relajan.

## Arquitectura (4 capas agnósticas a la estrategia, `src/genesis/`)

| Capa | Paquete | Responsabilidad |
|---|---|---|
| 1. Datos | `genesis/data/` | Export MT5 (M1+ticks), calendario económico, sesiones por índice, calidad, store |
| 2. Estrategia | `genesis/strategy/` | Contrato plugin `StrategyCandidate`, embudo Inspector compartido, candidatos |
| 3. Backtest | `genesis/backtest/` | Simulador event-driven M1, costos completos, ledger, métricas prop |
| 4. Validación | `genesis/validation/` | WFA, Monte Carlo, purged K-fold, DSR/PBO, prop_sim, veredicto de torneo |

Invariantes de diseño: estado incremental **forward-only** (anti-lookahead por construcción, `LookaheadError`), reproducibilidad institucional (config_version + hash de dataset + ficha de firma + semillas + commit en cada artefacto), fail-fast con contexto, determinismo total.

## Comandos

| Comando | Qué hace |
|---|---|
| `mise run setup` | `uv sync --all-groups` (entorno) |
| `mise run ci` | lint (ruff+bandit+vulture+deptry) + ty + test, en paralelo |
| `mise run test` / `t` | pytest |
| `mise run ty` / `tc` | `uv run ty check` |
| `mise run format` / `f` | ruff fix + format |
| `mise run docker:pull` | pull de `ghcr.io/bajmein/pulse/mcp-pulse` |

Dependencias siempre vía `uv` (`uv add`, `uv sync`, `uv run`). Python 3.14. Búsquedas con `rg`/`fd`/`ast-grep`, no `grep`/`find`.

## Flujo SDD (plugin pulse)

El ciclo de vida lo orquesta el MCP `pulse-engine` (Docker, workspace montado en `/work`) con las skills del plugin `pulse`:

`/pulse:explore` → `/pulse:propose` → `/pulse:specify` → `/pulse:design` → `/pulse:break-to-tasks` → `/pulse:apply` → `/pulse:review` → `/pulse:close`

- **Gate humano obligatorio**: solo un humano llama `approve_design` (en design o break-to-tasks). Nunca auto-aprobar.
- Estado del proyecto en GitHub: issues/labels codifican las fases (`state:1-explore` … `state:8-close`).
- Cadena de issues del spec: A (spec definitivo, bloquea al resto) → B (data) → C (contrato+Inspector) → {D/E paralelos, G} → H → I → J → K.

## Convenciones

- Commits: `<type>(<domain>): <subject>`, cerrando issues con `Refs #<n>`.
- Testing según spec §9: unit+property (`hypothesis`), golden tests, integración, estadístico. Propiedad central: ningún output de `on_bar(t)` cambia si se mutan barras posteriores a `t`.
- Docs y docstrings en español; identificadores en inglés.
- Reglas detalladas en `.agents/rules/` y plantillas en `.agents/templates/`.
