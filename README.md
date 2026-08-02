# genesis

Pipeline de validación institucional para prop firms: un **torneo de candidatos de estrategia** evaluado bajo gates mecánicos idénticos (G/C/P/T), con un motor de backtest propio event-driven sobre M1 + ticks.

> **Software propietario.** Todos los derechos reservados. El acceso a este repositorio no concede licencia de uso. Ver [`LICENSE`](LICENSE).

El objetivo no es "hacer backtests bonitos": es producir un veredicto **GO / NO-GO** reproducible y no negociable sobre si una estrategia sobrevive la economía real de un challenge de prop firm, con los costos completos y las reglas de la firma aplicadas.

## Principios de diseño

- **Anti-lookahead por construcción**: el estado de estrategia es incremental y forward-only; violarlo levanta `LookaheadError` en vez de degradar en silencio. Propiedad central verificada con `hypothesis`: ningún output de `on_bar(t)` cambia si se mutan barras posteriores a `t`.
- **Reproducibilidad institucional**: cada artefacto registra `config_version`, hash de dataset, `firm_profile_hash`, semillas y commit de git. Un veredicto obtenido con datos de una firma **no es transferible** a otra.
- **Gates mecánicos**: los umbrales son constantes nombradas en código, comparadas contra números ya calculados. No se relajan para que un candidato pase.
- **Fail-fast con contexto** y determinismo total.

## Estado del proyecto

Las cuatro capas están construidas y verificadas: **639 tests** en verde, más lint (`ruff`, `bandit`, `vulture`, `deptry`) y type-check (`ty`) limpios en CI.

| Capa | Paquete | Estado |
|---|---|---|
| 1. Datos | `genesis/data/` | Export MT5 (M1 + ticks), calendario económico, sesiones por índice, controles de calidad, store Parquet, ficha de firma |
| 2. Estrategia | `genesis/strategy/` | Contrato plugin `StrategyCandidate`, Inspector compartido, componentes comunes (VWAP, zonas) |
| 3. Backtest | `genesis/backtest/` | Simulador event-driven, equity intradía, fills por tick, modelo de costos con stress, ledger append-only, métricas prop |
| 4. Validación | `genesis/validation/` | WFA, Monte Carlo (símbolo y portafolio), Purged K-Fold, DSR/PBO, sensibilidad, `prop_sim`, veredicto de torneo, tearsheet y manifest |

Candidatos:

| Candidato | Estrategia | Estado |
|---|---|---|
| **A** | CT sweep-fade | **Parcial.** `smc/` (estructura de mercado) y `diagnostics.py` (diagnóstico de señal desnuda, kill-switch §2.2.1) están implementados, pero A **no** se registra en `CANDIDATE_REGISTRY`: aún no es un `StrategyCandidate` ejecutable. El gatillo CT queda condicionado al veredicto del diagnóstico. |
| **B** | ORB intradía en índices | **Ejecutable.** Implementa `StrategyCandidate` y `RiskLevelsProvider`. |
| **C** | TSMOM | Diferido, no implementado. |

Limitación conocida de rendimiento: el diagnóstico del Candidato A tarda **~26 min por símbolo**
sobre las 232.487 barras M1 reales de un índice, y **98,2%** de ese tiempo está en
`detect_ct_events` — el coste crece de forma cuadrática porque `LiquidityMap` nunca purga los
niveles mitigados. Medido con `scripts/bench_diagnose.py`; el plan de optimización está en el
[issue #38](https://github.com/ramaDben/genesis/issues/38).

## Requisitos

- **Linux o WSL2** — el entorno soportado. El código es portable, pero el flujo SDD exige POSIX
  y en Windows nativo el gate determinista del engine se cuelga. Bajo WSL2, el repo debe vivir
  en el filesystem de Linux (`~/genesis`), no en `/mnt/c/...`.
- **Python 3.14** (gestionado por `mise`)
- [`mise`](https://mise.jdx.dev) y [`uv`](https://docs.astral.sh/uv/)
- **MetaTrader 5** — solo para *exportar datos*, y solo corre en Windows. No se necesita para los
  tests: las fixtures son sintéticas y el CI corre en Linux sin MT5.
- Docker y `gh` — solo si vas a usar el flujo SDD interno (ver más abajo). No hacen falta para
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

Los valores de `.env` son placeholders y solo aplican al flujo SDD; el pipeline de backtest no lee ninguno. Nunca commitees `.env`.

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
uv run mt5-export export                  # descarga M1/ticks de símbolos MT5 a data/
uv run mt5-export confirm-firm-profile    # contrasta los símbolos esperados contra una cuenta demo real
uv run genesis-validate diagnose          # diagnóstico de señal desnuda del Candidato A (kill-switch §2.2.1)
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

- `data/` y `out/` están fuera de control de versiones: los datos crudos son propiedad del broker y pesan demasiado.
- El insumo es un export de MetaTrader 5 contra un **servidor de broker específico** (actualmente FTMO). El spread real de ticks es propio de ese par broker/servidor y alimenta tanto el criterio de archivo como los gates de economía prop.
- Por eso un veredicto se registra siempre en su forma canónica `GO (candidato X, firma Y)`: cambiar de firma invalida el veredicto y exige re-corrida completa.
- La trazabilidad no depende de versionar los datos, sino de que cada artefacto lleve `config_version` + hash de dataset + `firm_profile_hash` + semillas + commit.

Advertencia operativa: el servidor de FTMO usa NY+7 con regla DST de EE.UU., que **no** coincide con `Europe/Athens` en las ventanas de transición de octubre-noviembre y marzo. Esos días se excluyen del análisis.

### El dataset actual no se puede volver a exportar

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

- **SSoT vigente**: [`docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md`](docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md) — arquitectura, umbrales go/no-go definitivos, manejo de errores, estrategia de testing y gobernanza.
- Las versiones v1.1 a v1.3 se conservan en `docs/` solo como historial. **No las uses como referencia.**
- Todo cambio de alcance se valida contra el spec; los gates no se relajan.
- Convenciones de trabajo: [`CLAUDE.md`](CLAUDE.md) · flujo SDD: [`AGENTS.md`](AGENTS.md) · reglas detalladas en `.agents/rules/`.

## Testing

Según spec §9: unit + property-based (`hypothesis`), golden tests, integración y tests estadísticos contra casos publicados. Marcadores disponibles: `unit`, `integration`, `e2e`, `statistical`, `slow`.

```bash
uv run pytest -m unit
uv run pytest -m statistical
```

## Flujo SDD interno (opcional)

El ciclo de vida del desarrollo lo orquesta el plugin `pulse` (versionado en `.claude/plugins/pulse/`) contra un MCP en Docker:

`/pulse:explore → propose → specify → design → break-to-tasks → apply → review → close`

```bash
claude plugin marketplace add .
claude plugin install pulse@genesis
mise run mcp:list       # salud de los MCPs
```

Gate humano obligatorio: solo una persona llama `approve_design`. Los agentes nunca auto-aprueban. El estado de cada fase se codifica en labels de issues de GitHub.

### Requisitos del engine: Linux o WSL2

El `.mcp.json` del plugin usa `--user "$(id -u):$(id -g)"` y `$(git rev-parse --show-toplevel)`, así que **requiere un entorno POSIX**. En Windows nativo el engine no arranca con esa configuración, y el modo nativo (sin Docker) se cuelga al ejecutar el gate determinista.

Antes del primer `close_change` hacen falta dos pasos que no se pueden expresar en el `.mcp.json`:

**1. Construir la imagen desde el código actual del engine.** La imagen publicada `ghcr.io/bajmein/pulse/mcp-pulse:latest` es la v0.13.0 (2026-06-09), seis versiones atrás del `main` de pulse, y es anterior al hardening que hace `promote_delta` idempotente: un cierre con ella falla con `Delta duplicado` y deja efectos parciales.

```bash
gh repo clone Bajmein/pulse ~/pulse-src -- --depth 20
docker build -t mcp-pulse:0.13.6 ~/pulse-src
```

**2. Preparar los volúmenes con el owner correcto.** Docker crea los volúmenes nuevos como `root:root`; como el contenedor corre con tu UID, `uv` no puede inicializar su caché y los seis checks del gate fallan con `exit_code=2` en menos de un segundo.

```bash
for v in pulse-venv uv_warm_cache; do
  docker volume create "$v"
  docker run --rm --user 0:0 -v "$v:/vol" --entrypoint sh mcp-pulse:0.13.6 \
    -c "chown -R $(id -u):$(id -g) /vol"
done
```

El volumen `pulse-venv` es imprescindible: el `pyvenv.cfg` del `.venv` local apunta al Python gestionado por mise, ruta que no existe dentro del contenedor. Sin ese volumen el gate recrearía el venv con otro intérprete y rompería el entorno del host.

**3. Identidad git local al repo.** El Dockerfile del engine fija `HOME=/tmp`, así que git no ve la configuración global del host y el commit de release falla con `Author identity unknown`:

```bash
git config --local user.name "tu-nombre"
git config --local user.email "tu@email"
```

Configuración sugerida de Claude Code en [`.claude/settings.json.example`](.claude/settings.json.example) — revisala antes de renombrarla a `settings.json`, porque instala hooks que se ejecutan en cada prompt.

## Licencia

Propietaria — todos los derechos reservados. Ver [`LICENSE`](LICENSE). No se concede permiso de uso, copia, modificación ni distribución sin autorización previa y por escrito del titular.

Este software es una herramienta de investigación cuantitativa. No es asesoría de inversión, y los resultados de backtest no predicen resultados futuros.
