# genesis

Un validador de estrategias de trading intradía sobre **futuros CME**, para operar como **trader retail** en una prop firm de futuros (MyFundedFutures, plan Rapid EOD 50K). Cada estrategia se juzga bajo gates mecánicos idénticos (G/C/P/T), con un motor de backtest propio event-driven sobre M1 + ticks.

> **Software propietario.** Todos los derechos reservados. El acceso a este repositorio no concede licencia de uso. Ver [`LICENSE`](LICENSE).
>
> **El repositorio es público a propósito.** Lo que se escribe acá antes de correr una prueba queda con fecha y no se puede reescribir cuando el resultado no gusta. Esa es la función.

## Propósito

**Llegar al final del camino como trader retail, y dejar de creer que se sabe algo que no está validado.**

Genesis existe para someter a prueba lo que su autor aprendió mirando gráficos —velas, estructura de precio, regímenes— y lo que publican traders con nombre, y separar lo que resiste de lo que no. Un `GO` tiene que significar algo; un `NO-GO` tiene que decir por qué; y ninguna idea se da por buena porque "se vio funcionar".

Lo que el proyecto **no** es:

- No es una máquina de buscar estrategias hasta que alguna salga bien por suerte.
- No es la base de un negocio de asesoría ni de gestión de capital de terceros. Esa meta existió y quedó **descartada el 2026-09-24**.
- No despliega nada que no haya pasado los gates, y no afloja un gate para que algo pase.

## Qué está validado hoy

| | Estado |
|---|---|
| **Estrategias con veredicto `GO`** | **Ninguna.** Todavía no se corrió ningún ensayo sobre datos de futuros CME. |
| **Datos CME** | Fuente elegida y cotizada (Databento, [#126](https://github.com/ramaDben/genesis/issues/126)). Todavía no hay datos en el disco. |
| **Holdout** (historia apartada que se mira una sola vez) | Política y tamaño ratificados el 2026-09-21 ([`POLITICA_HOLDOUT.md`](docs/POLITICA_HOLDOUT.md)), **antes** de tener datos. **Sin implementar en código.** |
| **Gate 0** (admisión teórica antes de programar) | Protocolo escrito ([`PROTOCOLO_ADMISION_ESTRATEGIAS.md`](docs/PROTOCOLO_ADMISION_ESTRATEGIAS.md)). **Sin control mecánico** ([#105](https://github.com/ramaDben/genesis/issues/105), [#107](https://github.com/ramaDben/genesis/issues/107)). |
| **Pre-registro de hipótesis** | Pendiente ([#88](https://github.com/ramaDben/genesis/issues/88)). Es lo que convierte la publicidad del repo en un compromiso. |
| **Ledger de ensayos** (cuenta todos los intentos, también los fallidos) | Construido y demostrado ([#53](https://github.com/ramaDben/genesis/issues/53), PR #123). |

Todo resultado obtenido antes del 2026-09-14 corrió sobre CFDs de MT5, un universo que quedó fuera de alcance. No cuenta como evidencia de nada sobre futuros.

## Visión

Las cuatro capas son agnósticas a la estrategia. Eso hace de genesis un **evaluador de caja negra**: entra una estrategia, salen gates y veredicto. La unidad que se juzga es el par **(estrategia, activo)**: genesis juzga cada celda, no elige un ganador.

El **arquitecto** transcribe a genomas declarativos las estrategias que publican terceros con nombre, y deja que el evaluador las juzgue. Tres decisiones del 2026-09-20 lo acotan ([`ROADMAP_ARQUITECTO.md`](docs/ROADMAP_ARQUITECTO.md)):

- **Adjudica, no busca.** No genera hipótesis propias ni explora un espacio de parámetros.
- **Es feed-forward.** Ningún resultado del evaluador vuelve al que propone. Un buscador que ve los resultados y ajusta *se convierte* en el mecanismo de sobreajuste.
- **Ningún ensayo sobre CFDs.** Solo futuros CME; MT5 no se usa ni como paso previo.

El **ledger de ensayos persistente** es lo que mantiene honesto al Deflated Sharpe Ratio: `genesis.validation.trial_ledger` persiste un ensayo por `(candidato, símbolo)` en `ledger/trials.jsonl`, y `run_verdict` lo consume en G4 y T1 bajo un invariante verificado con property test: **el ledger solo puede endurecer un gate, nunca relajarlo**. El operador humano sigue siendo un canal de realimentación —elegir qué probar después de ver cómo le fue a lo anterior también es selección—, y por eso el pre-registro va antes de correr nada.

Los genomas son **declarativos**, sobre una gramática cerrada de primitivas forward-only, materializados por un ejecutor fijo. Nunca un `on_bar` escrito por un modelo: `LookaheadError` protege el framework, no la lógica que le metan adentro.

## Principios de diseño

- **Anti-lookahead por construcción**: el estado de estrategia es incremental y forward-only; violarlo levanta `LookaheadError` en vez de degradar en silencio. Propiedad central verificada con `hypothesis`: ningún output de `on_bar(t)` cambia si se mutan barras posteriores a `t`.
- **Reproducibilidad institucional**: cada artefacto registra `config_version`, hash de dataset, `firm_profile_hash`, semillas y commit de git. Un veredicto obtenido con datos de una firma **no es transferible** a otra.
- **Gates mecánicos**: los umbrales son constantes nombradas en código, comparadas contra números ya calculados. No se relajan para que un candidato pase.
- **Fail-fast con contexto** y determinismo total.

## Estado del proyecto

Las cuatro capas están construidas: **865 tests**, más lint (`ruff`, `bandit`, `vulture`, `deptry`) y type-check (`ty`) en CI. Versión actual: `0.5.0`. Que el motor esté construido **no** valida ninguna estrategia — ver [Qué está validado hoy](#qué-está-validado-hoy).

| Capa | Paquete | Estado |
|---|---|---|
| 1. Datos | `genesis/data/` | Calendario económico, sesiones, controles de calidad, store Parquet, ficha de firma. El export que existe es el de **MT5** (era CFD, fuera de alcance); el de **futuros CME** está por construir (casillas B.2–B.4 del roadmap) |
| 2. Estrategia | `genesis/strategy/` | Contrato plugin `StrategyCandidate`, Inspector compartido, componentes comunes (VWAP, zonas) |
| 3. Backtest | `genesis/backtest/` | Simulador event-driven, equity intradía, fills por tick, modelo de costos con stress, ledger append-only, métricas prop |
| 4. Validación | `genesis/validation/` | WFA, Monte Carlo (símbolo y portafolio), Purged K-Fold, DSR/PBO, sensibilidad, `prop_sim`, veredicto de torneo, tearsheet y manifest |

Candidatos (ninguno tiene veredicto sobre futuros CME):

| Candidato | Estrategia | Estado |
|---|---|---|
| **A** | CT sweep-fade | **Parcial.** `smc/` y `diagnostics.py` implementados, pero A **no** está en `CANDIDATE_REGISTRY`: aún no es un `StrategyCandidate` ejecutable. |
| **B** | ORB intradía | **Ejecutable**, y con genoma en [`candidates/specs/candidate_b1_orb.yaml`](candidates/specs/candidate_b1_orb.yaml). Su universo CME todavía no es declarable (casilla B.7), y su metadata de Gate 0 está en disputa ([#107](https://github.com/ramaDben/genesis/issues/107)). |
| **C1** | Oro, apertura de Londres | Genoma en [`candidates/specs/candidate_c1_gold_lob.yaml`](candidates/specs/candidate_c1_gold_lob.yaml), todavía declarado sobre `XAUUSD` (CFD). |

### Ausencia de evidencia ≠ NO-GO

El veredicto distingue un `NO-GO` por desempeño de un candidato que **nunca llegó a operar**
porque el sizer produjo lotes inviables: `intent_authorization_counts` (capa 3) clasifica los
intents propuestos, y la señal `sizing_evidence_insufficient` viaja por `SymbolGateOutcome` →
`CandidateGateSummary` → manifest y tearsheet. Sin relajar ningún gate G/C/P/T y sin ampliar
`VerdictKind` más allá de sus 4 miembros normativos (R91). Es también un prerrequisito de la
búsqueda automatizada: un generador que recibe `NO_GO` en vez de "sin evidencia" aprende de
ruido y descarta familias enteras que nunca se probaron.

### Rendimiento

El diagnóstico del Candidato A pasó de **35 min a 1,2 min por símbolo** (29×) sobre las 232.487
barras M1 reales de un índice; los 8 símbolos bajaron de 4,7 h a 9,6 min. Los 15.478 eventos CT
detectados son idénticos antes y después: la optimización no cambió la salida.

El cuello estaba en `detect_ct_events`, cuadrático porque `LiquidityMap` nunca purgaba los
niveles mitigados. Purgarlos reveló un segundo cuello que el primero ocultaba —44,8 M de
`dataclasses.replace` reconstruyendo `SweepTracker` idénticos—, y evitarlo por comparación de
identidad aportó dos tercios de la ganancia final. La lección quedó registrada en el
[issue #38](https://github.com/ramaDben/genesis/issues/38): perfilar antes de optimizar, y
volver a perfilar **después**. Medido con `scripts/bench_diagnose.py`.

## Requisitos

- **Linux nativo o WSL2** — el entorno soportado. Bajo WSL2, el repo debe vivir en el
  filesystem de Linux, no en `/mnt/c/...`.
- **Python 3.14** (gestionado por `mise`)
- [`mise`](https://mise.jdx.dev) y [`uv`](https://docs.astral.sh/uv/)
- **MetaTrader 5** — ya no hace falta. Solo lo usaba el export de la era CFD, que quedó fuera de
  alcance. Los tests usan fixtures sintéticas y el CI corre en Linux sin MT5.
- `gh` — opcional, para el listado de issues del hook de inicio de sesión. No hace falta para
  compilar, testear ni ejecutar el pipeline.

## Setup

```bash
git clone https://github.com/ramaDben/genesis.git
cd genesis

mise trust
mise install            # Python 3.14, uv, LSPs y utilidades CLI
cp .env.example .env    # mise carga .env; sin él, las tasks fallan
mise run setup          # uv sync --all-groups
mise run ci             # lint + ty + test
```

Los valores de `.env` son placeholders de las integraciones de desarrollo; el pipeline de backtest no lee ninguno. Nunca commitees `.env`.

Si el `.venv` queda inutilizable (`no Python executable was found`), renombralo y reconstruilo: `mv .venv .venv-old && uv sync --all-groups`.

## Comandos

| Comando | Qué hace |
|---|---|
| `mise run setup` / `s` | `uv sync --all-groups` |
| `mise run ci` | lint + ty + test en paralelo (réplica exacta del workflow de CI) |
| `mise run test` / `t` | `pytest` |
| `mise run ty` / `tc` | `ty check` |
| `mise run format` / `f` | `ruff check --fix` + `ruff format` |
| `mise run clean` | limpia cachés de herramientas (no toca `.pulse/` ni `.venv/`) |

Las dependencias se gestionan siempre vía `uv` (`uv add`, `uv sync`, `uv run`).

## CLI

Dos entry points, ambos con `--help`:

```bash
uv run genesis-validate diagnose          # diagnóstico de señal desnuda del Candidato A (kill-switch §2.2.1)
uv run mt5-export export                  # LEGADO, era CFD: descarga M1/ticks de MT5 a data/
uv run mt5-export confirm-firm-profile    # LEGADO, era CFD
```

El resto del pipeline (simulador, WFA, Monte Carlo, veredicto) se consume hoy como biblioteca desde `genesis.backtest` y `genesis.validation`; todavía no hay un CLI de torneo end-to-end.

Fuera del CLI, `scripts/bench_diagnose.py` cronometra y perfila las etapas del diagnóstico. Es
evidencia no-pytest, no bloquea el CI:

```bash
uv run python scripts/bench_diagnose.py --from-store US500.cash   # barras reales del store
uv run python scripts/bench_diagnose.py --bars 20000              # sintético, sin datos de MT5
uv run python scripts/bench_diagnose.py --from-store US500.cash --profile-stage detect
```

## Datos y reproducibilidad

**Los resultados de este repositorio no son reproducibles por un tercero, y es intencional.**

- `data/` y `out/` están fuera de control de versiones: los datos crudos son propiedad del proveedor, pesan demasiado, y la licencia de Databento no permite redistribuirlos.
- El insumo de la fase actual son **futuros CME vía Databento** ([#126](https://github.com/ramaDben/genesis/issues/126)); todavía no hay datos descargados.
- Un veredicto se registra siempre en su forma canónica `GO (candidato X, firma Y)`: cambiar de firma invalida el veredicto y exige re-corrida completa.
- La trazabilidad no depende de versionar los datos, sino de que cada artefacto lleve `config_version` + hash de dataset + `firm_profile_hash` + semillas + commit.

### Archivo de la era CFD

Todo lo que sigue es histórico: se conserva por trazabilidad, no se usa para ningún ensayo.

El export de FTMO se hizo con una cuenta de prueba **ya expirada**, así que no hay forma de
regenerarlo: los brokers sirven el historial de ticks en ventana móvil y una cuenta nueva
traería otra profundidad y otro `dataset_hash`. Por eso los 1,21 GB de particiones Parquet
están archivados como assets del release privado `dataset-ftmo-2026-08-01` (ocho símbolos más
los CSV y el manifest). Para restaurarlos:

```bash
gh release download dataset-ftmo-2026-08-01 -R ramaDben/genesis -D /tmp/ds
for f in /tmp/ds/*.tar.gz; do tar -xzf "$f"; done   # recrea data/ en la raíz del repo
```

Los bordes M1 y la profundidad de historial originales están en `history_depth.json` y
`m1_edge.json`, dentro del release `archive-2026-07-28`. Contrastá contra ellos cualquier
export nuevo antes de comparar resultados entre datasets.

## Documentación

- **SSoT vigente**: [`docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md`](docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md) — arquitectura, umbrales go/no-go definitivos, manejo de errores, estrategia de testing y gobernanza.
- Las versiones v1.1 a v1.4 se conservan en `docs/` solo como historial. **No las uses como referencia.**
- Roadmap y decisiones de rumbo: [`docs/ROADMAP_ARQUITECTO.md`](docs/ROADMAP_ARQUITECTO.md).
- Holdout: [`docs/POLITICA_HOLDOUT.md`](docs/POLITICA_HOLDOUT.md) y [`docs/DIMENSIONAMIENTO_HOLDOUT.md`](docs/DIMENSIONAMIENTO_HOLDOUT.md).
- Admisión de estrategias (Gate 0): [`docs/PROTOCOLO_ADMISION_ESTRATEGIAS.md`](docs/PROTOCOLO_ADMISION_ESTRATEGIAS.md).
- Investigación en curso (RFC, **no** normativo): [`docs/research/PROPUESTA_LABORATORIO_DE_ESTRATEGIAS.md`](docs/research/PROPUESTA_LABORATORIO_DE_ESTRATEGIAS.md) — propuesta para convertir el torneo en un laboratorio de estrategias publicadas, con la semántica de conteo de ensayos que el arquitecto necesita.
- Todo cambio de alcance se valida contra el spec; los gates no se relajan.
- Convenciones de trabajo: [`CLAUDE.md`](CLAUDE.md) · guía para agentes: [`AGENTS.md`](AGENTS.md) · reglas detalladas en `.agents/rules/`.

## Testing

Según spec §9: unit + property-based (`hypothesis`), golden tests, integración y tests estadísticos contra casos publicados. Marcadores disponibles: `unit`, `integration`, `e2e`, `statistical`, `slow`.

```bash
uv run pytest -m unit
uv run pytest -m statistical
```

## Licencia

Propietaria — todos los derechos reservados. Ver [`LICENSE`](LICENSE). No se concede permiso de uso, copia, modificación ni distribución sin autorización previa y por escrito del titular.

Este software es una herramienta de investigación cuantitativa. No es asesoría de inversión, y los resultados de backtest no predicen resultados futuros.
