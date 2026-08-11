# Change #55 — apply completado (2026-08-11), `SymbolFigure.tick_size` + `value_per_point`

Observación fechada de la fase `apply` del Change
`55-fix-data-symbolfigure-no-captura-tick-size-el-sizing-costos-asum` (branch
`fix/55-symbolfigure-tick-size`, `design_approved_at=2026-08-11T16:33:26Z` por `bbenja11`).
Verificar contra el código si esta memoria envejece.

## Contexto de la sesión

Esta pasada de `apply` retomó un intento anterior interrumpido por un reinicio del equipo: el
working tree ya tenía, sin commitear, la implementación **completa** de T1-T10 de `design.md`
§6 (el `tasks.md` real del Change quedó como plantilla vacía — nunca se formalizó en
`break-to-tasks`; se reconstruyó desde `design.md` §6 en esta pasada y se dejó escrito en
`.pulse/changes/55-.../tasks.md`, gitignored). Se verificó **archivo por archivo** el diff
preexistente contra el plan técnico de `design.md` §5-§6 antes de conservarlo: coincide
exactamente, sin nada fuera de alcance. `ledger/README.md` y `.claude/settings.json`, mencionados
en la tarea como posiblemente contaminados por el Change #53, en realidad **no tenían diff** al
verificar (`git status` los mostraba en el enunciado de la tarea pero el working tree real ya no
los tenía modificados).

## Qué se corrigió en esta pasada (encima del trabajo heredado)

1. `tests/data/test_mt5_export_pure.py:156` — línea >100 columnas (ruff E501), envuelta.
2. `tests/backtest/test_simulator_money_conversion.py` — no estaba formateado con `ruff format`.
3. `tests/data/test_symbols.py:57` — comentario de supresión de tipo con sintaxis `mypy`
   (`# type: ignore[arg-type]`) en vez de `# ty: ignore[invalid-argument-type]` (trampa ya
   registrada en `mem:ledger-de-ensayos-decisiones-de-diseno`, se repitió en este Change).

## Resultado de la toolchain (esta pasada)

`ruff check` verde, `ruff format --check` verde, `ty check` verde, `pytest` **729 passed / 1
skipped** (baseline pre-Change en `main`: 720 → +9... no, +12 tests nuevos netos según diseño,
verificado con `git stash` + recollect: 720 tests en `main`/HEAD sin el diff). `deptry` reporta
1 hallazgo preexistente no relacionado (`DEP004` en `.agents/hooks/_lib/pulse_hooks_lib/schema.py`,
pydantic declarado como dev dependency — nada que ver con este Change). `bandit` y `vulture`
sin hallazgos.

## Trampa operativa nueva (2026-08-11): `git stash` durante `apply` con `.pulse/changes/` gitignored

Al intentar medir el conteo de tests baseline con `git stash && pytest --co && git stash pop`,
el `stash pop` falló silenciosamente por un conflicto con `uv.lock` (binario, modificado en
ambos lados) **y** con el archivo nuevo `tests/backtest/test_simulator_money_conversion.py`
(untracked, presente en ambos lados del stash) — el pop dejó el mensaje "no changes added" pero
en realidad **no aplicó los cambios tracked**, dejando el working tree en un estado a medio
camino (huérfano) hasta que se detectó vía `git status`/`git stash list` y se resolvió: `git
checkout -- uv.lock` (descartar el cambio local trivial de versión) + mover aparte el archivo
untracked conflictivo + `git stash pop stash@{0}` explícito (no `git stash pop` a ciegas) + mover
de vuelta el archivo. **Lección**: nunca usar `git stash`/`pop` para "medir algo rápido" en medio
de una sesión de `apply` con cambios sin commitear reales — usar `git worktree add` o clonar a un
directorio aparte para comparar contra otra rama/commit sin tocar el working tree activo.
`tasks.md` (y en general todo bajo `.pulse/changes/`) **no participa** de `git stash` porque está
en `.gitignore`; sobrevivió intacto al episodio.

## Trampa confirmada de nuevo: subagente de `apply` sin `pulse-engine`/`serena`(parcial) al lanzarse

`ToolSearch` no encontró ningún tool `mcp__pulse*` en esta sesión de subagente (probado con
queries `"pulse"`, `"mark_tests_passed"`, `"request_sdd_transition"`, `"view_project_dashboard"`,
`"change dashboard sdd approve"` — todas sin resultados), pese a que `serena` y `github` sí
respondieron. Coincide con la trampa ya registrada arriba ("un subagente que reporta 'MCP no
disponible' puede estar equivocado", 2026-08-09): el subagente no debe declarar el engine
inexistente de forma definitiva, sino reportarlo al hilo principal para que lo verifique/ejecute
él mismo la transición pendiente (`mark_tests_passed` + `request_sdd_transition(target_phase=
"review", ...)` para este Change).

## Estado dejado

Working tree con T1-T10 implementados y verificados, `tasks.md` reescrito con el desglose real
(T1-T11 marcadas `[x]`, T12/T13 `[ ]` no bloqueantes por diseño explícito, G7). Nada commiteado
en esta pasada (no se pidió). Pendiente para el hilo principal: verificar `pulse-engine`
disponible y ejecutar `mark_tests_passed` + `request_sdd_transition(target_phase="review")`.
