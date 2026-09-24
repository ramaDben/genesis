# CLAUDE.md — genesis

## Qué es este proyecto

Validador de estrategias intradía sobre **futuros CME** para operar como **trader retail** en una
prop de futuros (MFFU Rapid EOD 50K), bajo gates mecánicos idénticos (G/C/P/T). **SSoT**:
`docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md` — todo cambio de alcance se valida contra
el spec, los gates nunca se relajan.

**Propósito (2026-09-24):** llegar al final del camino como trader retail y **dejar de creer que se
sabe algo que no está validado**. La meta CMF/inversionistas está **descartada**, no diferida. El
repo es público a propósito: lo pre-registrado ahí queda fechado. Ver
`mem:proposito-real-y-alcance-de-genesis`.

**Visión de largo plazo** (contexto para decidir alcance, no alcance vigente): las 4 capas son
agnósticas a la estrategia, así que genesis es un **evaluador de caja negra** que juzga pares
(estrategia, activo), sin elegir ganador. El **arquitecto adjudica, no busca**: transcribe a genomas
estrategias publicadas por terceros con nombre, es **feed-forward** (ningún resultado vuelve al que
propone) y no corre ensayos sobre CFDs (D-A/D-B/D-C, `docs/ROADMAP_ARQUITECTO.md`,
`mem:decision-arquitecto-adjudicador-2026-09-20`).

Sus dos prerrequisitos **ya están construidos**, y eso cambia el orden de trabajo que este archivo
declaraba antes:

- El **ledger de ensayos persistente** ([#53](https://github.com/ramaDben/genesis/issues/53),
  cerrado el 2026-08-11) alimenta el `n_trials` del DSR. `validation/trial_ledger.py` está cableado
  en `validation/verdict.py`, que suma `ledger_extra_trials` sobre la grilla interna de la corrida.
  Sin ese contador honesto G4 dejaría de proteger en silencio; ya no es el caso.
- El **arquitecto, Fase 1** ([#103](https://github.com/ramaDben/genesis/issues/103), mergeado el
  2026-09-10) trajo el compilador de genomas declarativos (`strategy/genome/`).

Lo que falta ya no es el orden, son los controles. El **Gate 0** de admisión teórica todavía no
tiene ejecutor mecánico ([#105](https://github.com/ramaDben/genesis/issues/105),
[#107](https://github.com/ramaDben/genesis/issues/107)): hoy conviven dos esquemas de metadata en
`candidates/specs/` y nada los valida. Y varias decisiones del RFC del laboratorio
([#57](https://github.com/ramaDben/genesis/issues/57)) siguen abiertas — **D2** incluida, que el
código resolvió por elusión (`CANDIDATE_REGISTRY` sigue indexado por letra y el camino de genomas
simplemente no lo usa). Ver `mem:auditoria-alineacion-issues-2026-09-14`.

Ver el README para los dos invariantes ya decididos (genoma declarativo, señal de retorno sin OOS).

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

## Hooks: los controles mecánicos del entorno

Activos desde el 2026-09-05 en `.claude/settings.json` (versionado). Todos pasan por
**`.agents/hooks/run_hook.sh`**, que detecta si la sesión corre en Windows y re-ejecuta dentro de
WSL. Ese rodeo no es opcional: ejecutar los hooks directamente sobre la ruta UNC hace que
`.pulse/state.sqlite` responda `database is locked`, el hook reporte fase `unknown` y **emita
contexto vacío sin fallar** — medido, no supuesto (y de paso el rodeo es más rápido: 1.45 s contra
3.81 s, porque el I/O por UNC cuesta más que arrancar WSL).

| Evento | Script | Qué hace |
|---|---|---|
| `SessionStart` | `session_context.py` | Inyecta el índice de memorias de Serena, rama y último commit, fase del engine, y los issues abiertos que **no** están reservados |
| `SessionStart` | `omega_welcome` (`mcp_tool`) | Briefing de OMEGA. Si su server MCP aún no conectó, no dispara — el bloque OMEGA del hook anterior lo avisa |
| `UserPromptSubmit` | `sdd_context_injector.py` | Recuerda la fase del ciclo en cada turno |
| `PreToolUse` | `sdd_validate_tool.py` | **Deniega** escrituras fuera de la fase. Cubre `Write`/`Edit`/`MultiEdit` y las herramientas de escritura de serena y filesystem |

El guardián de escritura permite siempre la **vía rápida** (`docs/`, `scripts/`, `.serena/memories/`,
`.agents/`, `.claude/`, `*.md`) y todo lo que caiga fuera del repo (scratchpad, `/tmp`). Para tocar
`src/**` o `tests/**` hace falta un change activo en fase `apply`. Si la fase no se puede leer,
**fail-closed**: sólo pasa la vía rápida.

Batería de humo: `bash .agents/hooks/smoke_test_guard.sh` (20 casos). Los tests de la librería:
`cd .agents/hooks/_lib && uv run pytest`.

**Debilidad aceptada a sabiendas:** `.agents/**` y `.claude/**` están en la vía rápida, así que un
agente puede editar los hooks que lo restringen. Se acepta porque bloquearlos haría imposible
mantenerlos y porque git deja el rastro; es la primera excepción que debería escalar al adjudicador
externo del [#87](https://github.com/ramaDben/genesis/issues/87).

## Flujo SDD (plugin pulse)

El ciclo de vida lo orquesta el MCP `pulse-engine` (Docker, workspace montado en `/work`) con las skills del plugin `pulse`:

`/pulse:explore` → `/pulse:propose` → `/pulse:specify` → `/pulse:design` → `/pulse:break-to-tasks` → `/pulse:apply` → `/pulse:review` → `/pulse:close`

- **Gate humano obligatorio**: solo un humano llama `approve_design` (en design o break-to-tasks). Nunca auto-aprobar.
  **Debilidad conocida y aceptada a sabiendas (2026-09-05):** en la práctica se aprobó sin leer,
  porque las decisiones llegan en un vocabulario que no es el del dueño del proyecto. La salida
  diseñada —separar política de adjudicación, con un adjudicador externo y un chequeo mecánico—
  está **reservada** en el hito *Gobernanza y política de decisión* (issues #86, #87). Se asume
  la debilidad mientras no haya capital real ni un candidato cerca de un GO. Ver
  `.serena/memories/reserva-de-gobernanza-2026-09.md`.
- Estado del proyecto en GitHub: issues/labels codifican las fases (`state:1-explore` … `state:8-close`).
- Cadena de issues del spec: A (spec definitivo, bloquea al resto) → B (data) → C (contrato+Inspector) → {D/E paralelos, G} → H → I → J → K.

### Dónde aplica el ciclo, y dónde no

**Obligatorio** para todo cambio que altere comportamiento o contrato bajo `src/genesis/**`:
firmas públicas, invariantes, gates, formato de artefactos, jerarquía de excepciones, módulos
nuevos. Ahí el gate humano protege algo real.

**Vía rápida** (rama → PR → merge, sin ciclo) para lo que no toca esa superficie:

| Vía rápida | Por qué |
|---|---|
| `scripts/` (runners, benchmarks) | Componen APIs ya publicadas; precedente de los `bench_*.py` |
| `docs/`, `.serena/memories/` | No ejecutan |
| Investigación, diagnóstico, mediciones | Exploratorio por naturaleza; no cabe en ocho fases |
| Dependencias, CI, formato | Mecánico |

**La zona gris se resuelve a favor del gate.** Si un cambio en `scripts/` obliga a tocar `src/`,
la parte de `src/` va por el ciclo aunque sea pequeña.

### Cerrar un change: la trampa que costó tres semanas

**`close_change` es lo único que cierra, y exige el change en `review`.** Nunca avanzar a `close`
con `request_sdd_transition`: esa llamada mueve la fase pero no cierra nada, e inhabilita la única
tool capaz de hacerlo. El SpecGate no deja retroceder (`close solo puede avanzar a la fase
siguiente`) y después de `close` no hay fase siguiente — el change queda inservible.

**Un change sin `closed_at` bloquea todos los demás.** La guarda G2 rechaza crear cualquier change
nuevo mientras exista uno activo sin cerrar. Un cierre a medias no deja un pendiente: para el
flujo entero.

Así se detuvo el SDD el **2026-08-11**, el día que el #55 quedó en ese estado. Se destrabó el
2026-08-29 revirtiendo `current_phase` a `review` en `.pulse/changes/<slug>/state.yaml` y en el
blob de `.pulse/state.sqlite`, y llamando `close_change` (ver #72). Señal de cierre completo:
`HeuristicsExtracted` en `.pulse/audit.jsonl` y el change movido a `.pulse/changes/archive/`.

**Precedente que originó esta regla (2026-08-29).** Los PR #68 y #69 modificaron `src/` sin pasar
por el ciclo. #69 añadió `strategy/factories.py`, una excepción nueva a la jerarquía de dominio y
cambió las firmas públicas de `run_wfa`/`build_signal_trial_matrix`/`run_sensitivity`, resolviendo
de paso la decisión **D2** del RFC del laboratorio — que ese mismo RFC marcaba como
**[DECISIÓN HUMANA]**. Una autorización conversacional para hacer el trabajo no sustituye al gate:
el gate existe para que la decisión de diseño se vea **antes** de estar en `main`, no después.

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

## Admisión Teórica de Candidatos (Gate 0)

Ninguna estrategia o hipótesis de trading se implementa ni se somete al pipeline sin superar el **Gate 0** documentado en `docs/PROTOCOLO_ADMISION_ESTRATEGIAS.md`.
Todo candidato requiere justificación en dos fuentes independientes antes de codificar:
1. **Academia canónica (SSRN/JFE/JF)**: Paper formal, autores y mecanismo económico/microestructural del edge.
2. **Cuantitativa libre (AQR/Man AHL/Alpha Architect)**: Operativa institucional, clusters de volatilidad y modos de falla.

## Convenciones

- Commits: `<type>(<domain>): <subject>`, cerrando issues con `Refs #<n>`.
- Testing según spec §9: unit+property (`hypothesis`), golden tests, integración, estadístico. Propiedad central: ningún output de `on_bar(t)` cambia si se mutan barras posteriores a `t`.
- Docs y docstrings en español; identificadores en inglés.
- Reglas detalladas en `.agents/rules/` y plantillas en `.agents/templates/`.

