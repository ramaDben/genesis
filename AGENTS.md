# AGENTS.md — genesis

Guía para agentes LLM trabajando en este repo. Complementa `CLAUDE.md` (comandos y convenciones) y `.agents/AGENTS.md` (arquitectura cognitiva).

## Fuente de verdad

`docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md` es el SSoT. Los umbrales go/no-go (gates G/C/P/T) son normativos: **nunca se relajan**; un NO-GO honesto es un éxito del proceso.

## Flujo de cambios

- Todo cambio que altere comportamiento o contrato bajo `src/genesis/**` va por rama → PR →
  revisión humana antes del merge: las decisiones de diseño se ven **antes** de estar en `main`.
- Vía rápida (`docs/`, `scripts/`, memorias, dependencias, CI): rama → PR → merge. No hay
  guardián mecánico de escritura; la disciplina es de proceso.
- Hidratar contexto desde los issues de GitHub antes de implementar.

## Toolchain MCP

- `serena` — navegación simbólica LSP, integridad y memorias de proyecto (`write_memory`).
  Su arranque puede exceder el timeout de 30 s en el health check y reconectar después.
- `memory` — knowledge graph en `.pulse/memory/knowledge-graph.jsonl`. Está en `.gitignore`:
  no sobrevive a un reinstall salvo por el respaldo del release `archive-2026-07-28`.
- A scope de usuario: `github`, `context7`, `sequential-thinking`, `superpowers`.

Preferencia operativa: las acciones sobre GitHub (PRs, issues, merges, releases) van por
`mcp__github__*`, **no** por la CLI `gh`. Cargar todas las tools necesarias en **una sola**
llamada a `ToolSearch`, con la forma `select:tool1,tool2,...`.

## Memoria entre sesiones

Las **memorias de Serena** (`.serena/memories/`, versionadas) son el canal de contexto entre
sesiones: lo que un agente nuevo necesita saber y no puede deducir del código.

**Obligatorio al arrancar**: `list_memories` y leer las relevantes **antes** de explorar el repo
o responder. Repetirlo cuando una instrucción entre en un área que no cubriste todavía —
llegar a una conclusión que una memoria ya contradecía es un fallo de proceso evitable.

**Al terminar un trabajo con hallazgos duraderos**, escribirlos con `write_memory`: la decisión
y su porqué, la medición y sus condiciones, la trampa que costó tiempo, la hipótesis que el dato
refutó. Actualizar la memoria existente en lugar de crear una nueva casi igual.

Son observaciones fechadas, no estado vivo: verificar contra el código actual toda cita de
archivo, símbolo o cifra antes de darla por vigente.

## Invariantes de código (del spec)

- Anti-lookahead estructural: `on_bar` es incremental y forward-only; leer datos con `confirmed_time > now` lanza `LookaheadError`.
- Errores tipificados y fail-fast: `DayBoundaryError`, `SessionBoundaryError`, `AccountScopeError`.
- Todas las métricas de riesgo en unidades del presupuesto de la firma (`prop_profile.json`).
- Determinismo: misma semilla + dataset + config + ficha + candidato ⇒ resultados bit-idénticos.
- Aislamiento del torneo: cada candidato cuenta sus propios trials; sin contaminación entre candidatos.
