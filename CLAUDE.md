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

Dependencias siempre vía `uv` (`uv add`, `uv sync`, `uv run`). Python 3.14. Búsquedas con `rg`/`fd`/`ast-grep`, no `grep`/`find`.

Perfilado del diagnóstico (no bloquea CI): `uv run python scripts/bench_diagnose.py --from-store US500.cash`.

## Entorno de desarrollo

**Linux nativo o WSL2, no Windows nativo.** El entorno de trabajo actual es Linux nativo
(Fedora), con el repo donde se haya clonado — nada en el repo depende de una ruta fija. Bajo
WSL2, el repo debe vivir en el filesystem de Linux: trabajar desde `/mnt/c/...` cruza la
frontera de filesystems y es más lento.

Sólo si la sesión de Claude Code corre en Windows: el repo de WSL se alcanza por UNC
(`\\wsl$\Ubuntu\home\<usuario>\genesis\`) y los comandos se lanzan con
`wsl -d Ubuntu -- bash -lc "..."` — el login shell es obligatorio para tener `uv` y `mise`
en el `PATH`.

## Hooks

Configurados en `.claude/settings.json` (versionado). Pasan por **`.agents/hooks/run_hook.sh`**,
que detecta si la sesión corre en Windows y re-ejecuta dentro de WSL.

| Evento | Script | Qué hace |
|---|---|---|
| `SessionStart` | `session_context.py` | Inyecta el índice de memorias de Serena, rama y último commit, y los issues abiertos que **no** están reservados |
| `SessionStart` | `omega_welcome` (`mcp_tool`) | Briefing de OMEGA. Si su server MCP aún no conectó, no dispara — el bloque OMEGA del hook anterior lo avisa |

No hay guardián de escritura: el control sobre `src/**` es la revisión humana del PR (ver abajo).
Los tests de la librería de los hooks: `cd .agents/hooks/_lib && uv run pytest`.

## Flujo de cambios

**Revisión humana obligatoria** para todo cambio que altere comportamiento o contrato bajo
`src/genesis/**`: firmas públicas, invariantes, gates, formato de artefactos, jerarquía de
excepciones, módulos nuevos. Va por rama → PR → revisión humana → merge; nunca directo a `main`.

**Debilidad conocida y aceptada a sabiendas (2026-09-05):** en la práctica se aprobó sin leer,
porque las decisiones llegan en un vocabulario que no es el del dueño del proyecto. La salida
diseñada —separar política de adjudicación, con un adjudicador externo y un chequeo mecánico—
está **reservada** en el hito *Gobernanza y política de decisión* (issues #86, #87). Se asume
la debilidad mientras no haya capital real ni un candidato cerca de un GO. Ver
`.serena/memories/reserva-de-gobernanza-2026-09.md`.

Cadena de issues del spec: A (spec definitivo, bloquea al resto) → B (data) → C (contrato+Inspector) → {D/E paralelos, G} → H → I → J → K.

### Qué exige revisión, y qué no

**Vía rápida** (rama → PR → merge, sin revisión de diseño) para lo que no toca esa superficie:

| Vía rápida | Por qué |
|---|---|
| `scripts/` (runners, benchmarks) | Componen APIs ya publicadas; precedente de los `bench_*.py` |
| `docs/`, `.serena/memories/` | No ejecutan |
| Investigación, diagnóstico, mediciones | Exploratorio por naturaleza |
| Dependencias, CI, formato | Mecánico |

**La zona gris se resuelve a favor de la revisión.** Si un cambio en `scripts/` obliga a tocar
`src/`, la parte de `src/` va en un PR con decisión de diseño explícita aunque sea pequeña.

**Precedente que originó esta regla (2026-08-29).** Los PR #68 y #69 modificaron `src/` sin
revisión de diseño. #69 añadió `strategy/factories.py`, una excepción nueva a la jerarquía de
dominio y cambió las firmas públicas de `run_wfa`/`build_signal_trial_matrix`/`run_sensitivity`,
resolviendo de paso la decisión **D2** del RFC del laboratorio — que ese mismo RFC marcaba como
**[DECISIÓN HUMANA]**. Una autorización conversacional para hacer el trabajo no sustituye a la
revisión: existe para que la decisión de diseño se vea **antes** de estar en `main`, no después.

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

