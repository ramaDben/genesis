# AGENTS.md — genesis

Guía para agentes LLM trabajando en este repo. Complementa `CLAUDE.md` (comandos y convenciones) y `.agents/AGENTS.md` (arquitectura cognitiva heredada de pulse).

## Fuente de verdad

`docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` es el SSoT. Los umbrales go/no-go (gates G/C/P/T) son normativos: **nunca se relajan**; un NO-GO honesto es un éxito del proceso.

## Ciclo SDD (8 fases, orquestado por pulse-engine)

| Fase | Skill | Label GitHub |
|---|---|---|
| 1. Explore | `/pulse:explore` | `state:1-explore` |
| 2. Propose | `/pulse:propose` | `state:2-propose` |
| 3. Specify | `/pulse:specify` | `state:3-specify` |
| 4. Design | `/pulse:design` | `state:4-design` |
| 5. Break-to-tasks | `/pulse:break-to-tasks` | `state:5-break-to-tasks` |
| 6. Apply | `/pulse:apply` | `state:6-apply` |
| 7. Review | `/pulse:review` | `state:7-review` |
| 8. Close | `/pulse:close` | `state:8-close` |

Reglas duras:

- El gate humano antes de apply es obligatorio: solo un humano ejecuta `approve_design`.
- Cada transición pasa por el FSM del engine (`request_sdd_transition`); no saltarse fases.
- El estado vive en `.pulse/` (SQLite + audit.jsonl) y en GitHub (issues/labels). Hidratar contexto desde issues antes de implementar.

## Toolchain MCP

- `pulse-engine` — máquina de estados SDD (Docker, `ghcr.io/bajmein/pulse/mcp-pulse`, workspace en `/work`).
- `serena` — navegación simbólica LSP e integridad.
- `filesystem`, `memory` — navegación y knowledge graph (`.pulse/memory/`).
- A scope de usuario: `github`, `context7`, `sequential-thinking`, `superpowers`.

## Invariantes de código (del spec)

- Anti-lookahead estructural: `on_bar` es incremental y forward-only; leer datos con `confirmed_time > now` lanza `LookaheadError`.
- Errores tipificados y fail-fast: `DayBoundaryError`, `SessionBoundaryError`, `AccountScopeError`.
- Todas las métricas de riesgo en unidades del presupuesto de la firma (`prop_profile.json`).
- Determinismo: misma semilla + dataset + config + ficha + candidato ⇒ resultados bit-idénticos.
- Aislamiento del torneo: cada candidato cuenta sus propios trials; sin contaminación entre candidatos.
