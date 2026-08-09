# CLAUDE.md — genesis

## Qué es este proyecto

Pipeline de validación institucional para prop firms: un **torneo de candidatos de estrategia** (A: CT sweep-fade, B: ORB intradía en índices — prioridad, C: TSMOM — diferido) bajo gates mecánicos idénticos (G/C/P/T). **SSoT**: `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` — todo cambio de alcance se valida contra el spec, los gates nunca se relajan.

**Visión de largo plazo** (contexto para decidir alcance, no alcance vigente): las 4 capas son agnósticas a la estrategia, así que genesis es un **evaluador de caja negra** — el torneo A/B/C es el primer caso de uso, no el techo. El destino es una búsqueda automatizada de candidatos, condicionada a un **ledger de ensayos persistente** ([#53](https://github.com/ramaDben/genesis/issues/53)) que alimente el `n_trials` del DSR: hoy solo cuenta la grilla interna de una corrida, y sin ese contador honesto G4 dejaría de proteger en silencio. El ledger va antes que el arquitecto. Ver el README para los dos invariantes ya decididos (genoma declarativo, señal de retorno sin OOS).

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
| `mise run docker:pull` | pull de `ghcr.io/bajmein/pulse/mcp-pulse` — **no usar para cerrar changes**: la `:latest` publicada es la v0.13.0 y falla en `promote_delta`. Construir desde `main` (ver README) |

Dependencias siempre vía `uv` (`uv add`, `uv sync`, `uv run`). Python 3.14. Búsquedas con `rg`/`fd`/`ast-grep`, no `grep`/`find`.

Perfilado del diagnóstico (no bloquea CI): `uv run python scripts/bench_diagnose.py --from-store US500.cash`.

## Entorno de desarrollo

**Linux o WSL2, no Windows nativo.** El repo de trabajo vive en el filesystem de Linux
(`~/genesis`); trabajar desde `/mnt/c/...` cruza la frontera de filesystems y es más lento.
El engine de pulse requiere POSIX (`$(id -u)`, `$(git rev-parse --show-toplevel)`) y en
Windows nativo el gate determinista se cuelga.

Al editar desde una sesión de Claude Code en Windows, el repo de WSL se alcanza por UNC
(`\\wsl$\Ubuntu\home\<usuario>\genesis\`) y los comandos se lanzan con
`wsl -d Ubuntu -- bash -lc "..."` — el login shell es obligatorio para tener `uv` y `mise`
en el `PATH`.

## Flujo SDD (plugin pulse)

El ciclo de vida lo orquesta el MCP `pulse-engine` (Docker, workspace montado en `/work`) con las skills del plugin `pulse`:

`/pulse:explore` → `/pulse:propose` → `/pulse:specify` → `/pulse:design` → `/pulse:break-to-tasks` → `/pulse:apply` → `/pulse:review` → `/pulse:close`

- **Gate humano obligatorio**: solo un humano llama `approve_design` (en design o break-to-tasks). Nunca auto-aprobar.
- Estado del proyecto en GitHub: issues/labels codifican las fases (`state:1-explore` … `state:8-close`).
- Cadena de issues del spec: A (spec definitivo, bloquea al resto) → B (data) → C (contrato+Inspector) → {D/E paralelos, G} → H → I → J → K.

## Memoria entre sesiones (Serena MCP)

Lo que deba sobrevivir al fin de una sesión va a las **memorias de Serena**
(`write_memory` / `read_memory`), versionadas en `.serena/memories/`. Son el mecanismo por el
que un agente que arranca sin contexto entiende el estado real del proyecto.

- **Al inicio de cada sesión, y de nuevo cuando llega una instrucción sobre un área que todavía
  no exploraste**, listar las memorias (`list_memories`) y leer las que el nombre señale como
  relevantes, **antes** de tocar código o responder.
- **Qué guardar**: decisiones con su porqué, mediciones y sus condiciones, restricciones del
  entorno, trampas ya pagadas e hipótesis que los datos refutaron. Una memoria por tema, con
  nombre descriptivo; enlazar entre ellas con `` `mem:nombre` ``.
- **Qué NO guardar**: lo que el repo ya registra (estructura del código, historial de git, este
  archivo) ni lo que solo importa dentro de la conversación en curso.
- Las memorias son **observaciones fechadas, no estado vivo**: si una cita un archivo, una
  función o una cifra, verificarlo contra el código actual antes de afirmarlo. Cuando algo
  cambie, actualizar la memoria existente en vez de acumular duplicados.

## Convenciones

- Commits: `<type>(<domain>): <subject>`, cerrando issues con `Refs #<n>`.
- Testing según spec §9: unit+property (`hypothesis`), golden tests, integración, estadístico. Propiedad central: ningún output de `on_bar(t)` cambia si se mutan barras posteriores a `t`.
- Docs y docstrings en español; identificadores en inglés.
- Reglas detalladas en `.agents/rules/` y plantillas en `.agents/templates/`.
