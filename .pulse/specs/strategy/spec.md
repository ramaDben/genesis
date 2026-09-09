
<!-- change:4-c-feat-strategy-contrato-plugin-inspector-compartido-componentes -->
<!-- change:4-c-feat-strategy-contrato-plugin-inspector-compartido-componentes -->
# Specification: Contrato plugin `StrategyCandidate` + Inspector compartido + componentes comunes (Issue #4 / C)

SSoT: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` (en adelante «el spec») — §2.1, §2.2,
§2.5, §5.1, §8, §9, §11.1. Este documento formaliza `idea.md` y `proposal.md` de este Change en
requisitos verificables. Los gates G/C/P/T del spec **nunca se relajan**; ningún requisito de este
documento puede contradecirlos.

Convención de rutas: el spec usa pseudocódigo `python/strategy/...` (§5.1); el repo real usa
`src/genesis/strategy/...` (`[project] name = "genesis"` en `pyproject.toml`). Todas las rutas de
este documento son las reales del repo.

Este Change resuelve normativamente **PA-3** (firma Python del contrato, `docs/SPEC...v1.2.md`
§11.1) y **PA-4** (mecanismo de enforcement de `LookaheadError`, mismo §), ambas heredadas del spec
promovido de Issue A (`.pulse/specs/docs/spec.md` R2.1–R2.5).

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Construir el núcleo agnóstico a la estrategia de la capa 2 (`src/genesis/strategy/`): el contrato
plugin `StrategyCandidate` (`contract.py`), el guard mínimo de disciplina forward-only (`clock.py`
+ `errors.py`), el embudo de viabilidad compartido (`inspector.py`) y dos componentes comunes
reutilizables por el Candidato A (`common/vwap_engine.py` portado, `common/zones.py` nuevo). Esto
desbloquea Issues D (`smc_engine`), E (Candidato B completo), F (Candidato A completo) y G
(simulador), que dependen todos del contrato de este Change (spec §11, tabla de issues).

### 1.2. Alcance IN

- `src/genesis/strategy/contract.py`: `StrategyCandidate` (`Protocol`, `@runtime_checkable`),
  `EntryIntent` (dataclass frozen), `Direction` (`StrEnum`), registro de candidatos
  (`CANDIDATE_REGISTRY` + `register_candidate`), `CONFIG_VERSION = "genesis-strategy/1"`.
- `src/genesis/strategy/errors.py`: `GenesisStrategyError` (raíz) y `LookaheadError`.
- `src/genesis/strategy/clock.py`: `BarClock`, el objeto mínimo de vista incremental que expone el
  guard de `LookaheadError` (PA-4), desacoplado del diseño del simulador real (Issue G).
- `src/genesis/strategy/inspector.py`: `inspect()`, `InspectorVerdict`, `RejectionReason`
  (`StrEnum`), `InspectorFunnelConfig`, consumiendo exclusivamente puertos ya existentes de
  `genesis.data` (`SymbolFigure`, `FirmProfile`, `news_windows`).
- `src/genesis/strategy/inspector_config.json` (recurso empaquetado, patrón
  `genesis.data.profiles.the5ers.json`): namespace `inspector.*` poblado con defaults; el
  namespace `candidates.<letra>.*` **no** se puebla en este Change.
- `src/genesis/strategy/common/vwap_engine.py`: porte de
  `C:\Users\bbrav\ABON\vwap-smc-inspector\python\vwap_engine.py` — algoritmo íntegro de
  `update_vwap`/`is_new_anchor`/`AnchorMode`/`VWAPState`/`VWAPResult` sin cambios funcionales;
  `VwapAnchorConfig` como subconjunto renombrado de `InspectorConfig` de la fuente (ver §3.5).
- `src/genesis/strategy/common/zones.py`: implementación nueva, `classify_zone()` + `Zone`
  (`StrEnum`: `PRO`, `MID`, `CT`), con cortes numéricos configurables (§3.6).
- `src/genesis/strategy/__init__.py`: `__all__` mínimo y curado, patrón de
  `genesis.data.__init__.py`.
- `tests/strategy/`: `conftest.py`, `fakes.py` (`FakeStrategyCandidate`), `fixtures/`,
  `tests/strategy/common/` (tests portados de `vwap_engine` + golden de `zones`), replicando el
  patrón de `tests/data/`.
- Test de propiedad central del spec §9 (`hypothesis`, ≥1000 ejemplos): ningún output de
  `on_bar(t)` cambia si se mutan barras posteriores a `t`, verificado sobre `BarClock` +
  `FakeStrategyCandidate`.

### 1.3. Alcance OUT (YAGNI explícito)

- Lógica de negocio de cualquier candidato concreto: `candidate_a/` (`smc_engine`, gatillo CT,
  riesgo), `candidate_b/` (rango de apertura, gatillo de ruptura, sizing), `candidate_c/`
  (TSMOM) — Issues D, E, F, K respectivamente.
- El namespace `candidates.<letra>.*` de `inspector_config.json`: cada candidato consumidor lo
  puebla cuando construya su propio config (D/E/F).
- Los 14 campos de `InspectorConfig` de la fuente portada que pertenecen a `smc_engine`/`risk` de
  candidate_a (`fractal_n`, `eq_tolerance_atr`, `sweep_tolerance_atr`, `sweep_window_k`,
  `sweep_validity_m`, `free_path_radius_sigma`, `ct_zscore_min`, `min_rr`, `sl_buffer_atr`,
  `tp_ct_mode`, `trail_timeframe`, `risk_percent`, `atr_period`, `session_filter`) — se documentan
  como deferred a `candidates.A.*` (Issues D/F), no se portan en este Change.
- El fixture `fixtures/mql5_reference.csv` y los tests de paridad MQL5↔Python marcados
  `@pytest.mark.mql5_parity` en la fuente (clase `TestLayer3MQL5Parity`) — no se portan; se
  documentan como deuda diferida (Rg-7, §7 de este documento).
- Todo `src/genesis/backtest/` (`simulator.py`, `costs.py`, `ledger.py`, `metrics.py`) — Issue G.
  El guard runtime completo de `LookaheadError` para un simulador real es responsabilidad de Issue
  G; este Change entrega solo el objeto `BarClock` mínimo y su contrato de test.
- Todo `src/genesis/validation/` — Issues H/I/J.
- Modificación de cualquier archivo bajo `src/genesis/data/` (Change B permanece intacto; ADR-8
  archivado confirma que `store.py` es forward-only por diseño de API, sin `LookaheadError`).
- `SESSION_CLOSED` como motivo de rechazo del Inspector: el cierre forzado por sesión
  (`SessionBoundaryError`) es invariante del Candidato B/simulador (spec §2.3, §8), no una
  validación de viabilidad pre-trade del embudo — queda fuera de `RejectionReason` en este Change.

---

## 2. Convenciones de esta especificación

- Los requisitos usan **DEBE** (MUST) y **DEBERÍA** (SHOULD), numerados `R1..Rn`, cada uno
  verificable por al menos un test o una aserción `rg`/`fd`.
- Nombres de funciones/clases/excepciones son **normativos** (deben existir exactamente con ese
  nombre, verificable por `rg`); firmas exactas (tipos de parámetros, orden) se resuelven en
  `design.md` respetando el comportamiento descrito aquí.
- Identificadores en inglés, docstrings y mensajes de error en español (convención del repo).
- `AnnotatedBar.timestamp_utc` (`src/genesis/data/store.py:31`) **es** el `confirmed_time`
  normativo del spec (§2.1): toda `AnnotatedBar` producida por `iter_bars` representa una vela M1
  ya cerrada, sin noción de "vela en curso" en esta capa. Este Change reutiliza `AnnotatedBar`
  directamente, sin alias ni wrapper (decisión de `proposal.md`, resuelve Rg-2 de `idea.md`).

---

## 3. Requisitos por módulo

### 3.1. `contract.py` — PA-3

**Responsabilidad**: interfaz mínima que todo candidato implementa, sin lógica de negocio,
respetando la regla de aislamiento del spec §2.1/§2.5 (ningún estado compartido entre candidatos).

**Requisitos**:

- **R1** (DEBE). `contract.py` DEBE definir `StrategyCandidate` como `typing.Protocol` decorado
  con `@runtime_checkable`, replicando el patrón de `genesis.data.calendar.EconomicCalendarSource`
  (`src/genesis/data/calendar.py:44-45`, único precedente de puerto inyectable del repo).
- **R2** (DEBE). `StrategyCandidate` DEBE declarar el atributo `candidate_id: str` y el método
  `on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]`, reutilizando
  `genesis.data.store.AnnotatedBar` sin adaptador (§2 de este documento).
- **R3** (DEBE). `contract.py` DEBE definir `EntryIntent` como `@dataclass(frozen=True, slots=True)`
  con exactamente los cuatro campos mínimos del spec §2.1: `direction: Direction`,
  `sizing_hint: float`, `candidate_id: str`, `config_version: str`.
- **R4** (DEBE). `contract.py` DEBE definir `Direction` como `StrEnum` con miembros `LONG = "long"`
  y `SHORT = "short"`, coherente con el único precedente de enum de dominio del repo
  (`genesis.data.calendar.ImpactLevel`, `src/genesis/data/calendar.py:26`).
- **R5** (DEBE). `contract.py` DEBE definir `CANDIDATE_REGISTRY: dict[str, type[StrategyCandidate]]`
  a nivel de módulo y un decorador `register_candidate(letter: str)` que registra la clase
  decorada bajo esa letra; DEBE lanzar un error explícito (con contexto) si `letter` ya está
  registrada (ninguna colisión silenciosa).
- **R6** (DEBE). `contract.py` DEBE definir `CONFIG_VERSION: str = "genesis-strategy/1"` a nivel de
  módulo, replicando el patrón de `genesis.data.metadata.CONFIG_VERSION`
  (`src/genesis/data/metadata.py:18`).
- **R7** (DEBE). `contract.py` NO DEBE importar `genesis.strategy.inspector` ni
  `genesis.strategy.common`: es la interfaz mínima, sin dependencia hacia el embudo ni hacia los
  componentes comunes (spec §2.1: separación de responsabilidades entre `contract.py` e
  `inspector.py`, §5.1).

### 3.2. `errors.py` + `clock.py` — PA-4 (enforcement de `LookaheadError`)

**Responsabilidad**: jerarquía de excepciones propia de la capa de estrategia y el guard mínimo de
disciplina forward-only, desacoplado del diseño del simulador real (Issue G), sin modificar
`genesis.data` (ADR-8 archivado de Change B).

**Decisión normativa (PA-4)**: el guard runtime completo se difiere a Issue G; este Change entrega
la excepción y un objeto de vista incremental mínimo (`BarClock`) suficiente para que el test de
propiedad central del spec §9 sea ejecutable en este Change.

**Requisitos**:

- **R8** (DEBE). `errors.py` DEBE definir `GenesisStrategyError(Exception)` como raíz de la
  jerarquía de excepciones de `genesis.strategy`. NO DEBE heredar de
  `genesis.data.errors.GenesisDataError` (jerarquías independientes por capa; ver decisión de
  `proposal.md`, sin precedente de raíz compartida `GenesisError` en el repo actual).
- **R9** (DEBE). `errors.py` DEBE definir `LookaheadError(GenesisStrategyError)`, con mensaje que
  incluya el timestamp solicitado y el `t_actual` vigente en el momento de la violación (fail-fast
  con contexto, spec §8).
- **R10** (DEBE). `clock.py` DEBE definir `BarClock` con, como mínimo:
  - un estado interno `current_time: datetime | None` (inicializado en `None`, "antes de la
    primera barra");
  - un método `advance(bar: AnnotatedBar) -> None` que actualiza `current_time` a
    `bar.timestamp_utc`, invocable únicamente por el consumidor que alimenta al candidato
    bar-a-bar (simulador real en Issue G, o el harness de test en este Change) — nunca por el
    candidato mismo;
  - un método `require(timestamp: datetime) -> None` que lanza `LookaheadError` si
    `timestamp > current_time`, o si `current_time is None` (ningún timestamp es válido antes de
    la primera barra).
- **R11** (DEBE). `BarClock.advance` DEBE rechazar (lanzar `LookaheadError`) un `bar.timestamp_utc`
  estrictamente anterior al `current_time` vigente (el reloj nunca retrocede), preservando la
  semántica forward-only también en el sentido de la fuente de barras.
- **R12** (DEBE). Ningún archivo de `src/genesis/data/` DEBE modificarse en este Change
  (`git diff --stat -- src/genesis/data` vacío) — el guard de `LookaheadError` vive enteramente en
  `genesis.strategy`, un nivel por encima de `store.py`.

### 3.3. `inspector.py` — embudo de viabilidad compartido

**Responsabilidad**: función pura que decide si un `EntryIntent` se autoriza o se rechaza contra
la ficha de símbolo/firma, agnóstica a qué candidato produjo la intención (spec §5.1: "viabilidad
R:R, lotaje contra fichas, restricciones de firma, motivos de rechazo tipificados").

**Requisitos**:

- **R13** (DEBE). `inspector.py` DEBE definir `inspect(intent, figure, firm_profile, news_events,
  config) -> InspectorVerdict`, consumiendo exclusivamente
  `genesis.data.symbols.SymbolFigure`, `genesis.data.profile.FirmProfile` y
  `genesis.data.calendar.news_windows` (verificable con
  `rg -n "from genesis.data" src/genesis/strategy/inspector.py`) — sin reimplementar validación
  de lotaje ni de ventanas de noticias.
- **R14** (DEBE). `inspector.py` DEBE definir `InspectorVerdict` como
  `@dataclass(frozen=True, slots=True)` con `authorized: bool` y
  `rejection_reason: RejectionReason | None` (`None` si y solo si `authorized is True`).
- **R15** (DEBE). `inspector.py` DEBE definir `RejectionReason` como `StrEnum` con exactamente
  tres miembros en este Change: `INSUFFICIENT_RR`, `LOT_SIZE_OUT_OF_BOUNDS`, `NEWS_WINDOW`.
  `SESSION_CLOSED` queda explícitamente excluido (§1.3 de este documento).
- **R16** (DEBE). `inspector.py` DEBE definir `InspectorFunnelConfig` como dataclass con, como
  mínimo, `min_rr: float` y los campos de lotaje/tolerancia necesarios para validar
  `EntryIntent.sizing_hint` contra `SymbolFigure.volume_step` — exclusivamente parámetros
  globales de embudo bajo el namespace `inspector.*` (spec §2.1), nunca parámetros de señal de un
  candidato concreto.
- **R17** (DEBE). `inspect()` DEBE retornar `authorized=False` con `rejection_reason=NEWS_WINDOW`
  cuando el timestamp implícito de la intención cae dentro de una ventana retornada por
  `news_windows(news_events, symbol, firm_profile)` (`src/genesis/data/calendar.py:69`).
- **R18** (DEBE). `inspector.py` NO DEBE importar ningún módulo de `genesis.strategy.candidate_a`,
  `candidate_b` ni `candidate_c` (el Inspector es agnóstico al candidato, spec §5.1).

### 3.4. `inspector_config.json` — namespace `inspector.*`

**Requisitos**:

- **R19** (DEBE). Este Change DEBE crear `src/genesis/strategy/inspector_config.json` (o recurso
  empaquetado equivalente, patrón `genesis.data.profiles.the5ers.json`,
  `src/genesis/data/profile.py:19-20`) con el namespace `inspector.*` poblado con valores default
  explícitos (como mínimo, el equivalente a `min_rr` de `InspectorFunnelConfig`).
- **R20** (DEBE). El archivo de R19 NO DEBE incluir ninguna clave bajo `candidates.<letra>.*`: ese
  namespace se puebla en los Changes consumidores (D/E/F) cuando construyan su propio config,
  evitando que C filtre configuración de un candidato concreto fuera de su alcance declarado
  (spec §2.1, §5.1).
- **R21** (DEBE). DEBE existir una función de carga (`load_inspector_funnel_config(path) ->
  InspectorFunnelConfig`, patrón `genesis.data.profile.load_firm_profile`) que falle explícitamente
  (excepción de dominio con contexto) si el archivo está incompleto o inválido — nunca degradación
  silenciosa (spec §8).

### 3.5. `common/vwap_engine.py` — porte

**Fuente**: `C:\Users\bbrav\ABON\vwap-smc-inspector\python\vwap_engine.py` (459 líneas) + suite de
tests en `python\tests\`.

**Requisitos**:

- **R22** (DEBE). El porte DEBE preservar sin cambios funcionales: `AnchorMode` (`IntEnum`:
  `NY_MIDNIGHT=0`, `SERVER_MIDNIGHT=1`, `CUSTOM_HOUR=2`), `VWAPState` (mutable, acumuladores
  `s_v`/`s_pv`/`s_p2v`/`bars_since_anchor`/`is_warmed_up`/`anchor_time`), `VWAPResult`
  (`frozen=True`), `is_new_anchor(bar_time, config)` con sus tres modos y la tabla DST, y
  `update_vwap(state, high, low, close, tick_volume, bar_closed, is_anchor, config) ->
  VWAPResult` con el algoritmo íntegro committed/current (acumuladores committed solo se
  actualizan si `bar_closed=True`; caso A — volumen total cero → `is_valid=False`; caso B —
  `sigma==0` → bandas colapsadas, `zscore=0`; clamp de varianza negativa por cancelación de punto
  flotante).
- **R23** (DEBE). `common/vwap_engine.py` DEBE definir `VwapAnchorConfig` (`@dataclass(frozen=True,
  slots=True)`) como el subconjunto de `InspectorConfig` de la fuente relevante al anclaje/warmup
  del VWAP: **exactamente** los campos `config_version: str`, `anchor_mode: AnchorMode`,
  `vwap_warmup_bars: int`, `custom_anchor_hour: int`, `server_to_utc_offset: int`. El docstring
  DEBE documentar explícitamente que es un subconjunto extraído de `InspectorConfig` de la fuente
  portada (`C:\Users\bbrav\ABON\vwap-smc-inspector\python\vwap_engine.py:48-122`), y que los 14
  campos restantes (`fractal_n`, `eq_tolerance_atr`, `sweep_tolerance_atr`, `sweep_window_k`,
  `sweep_validity_m`, `free_path_radius_sigma`, `ct_zscore_min`, `min_rr`, `sl_buffer_atr`,
  `tp_ct_mode`, `trail_timeframe`, `risk_percent`, `atr_period`, `session_filter`) pertenecen al
  namespace `candidates.A.*` (Issues D/F), fuera de alcance de este Change.
- **R24** (DEBE). `update_vwap`, `is_new_anchor`, `VWAPState` y `VWAPResult` DEBEN tipar su
  parámetro `config` como `VwapAnchorConfig` (renombrado del `InspectorConfig` de la fuente); esto
  es el único cambio de firma respecto a la fuente (renombrado de tipo, no de comportamiento) y
  DEBE documentarse explícitamente en el docstring del módulo como la única desviación del
  criterio "portado sin cambios funcionales" del spec §5.1.
- **R25** (DEBE). `default_vwap_anchor_config() -> VwapAnchorConfig` (renombrado de
  `default_config()` de la fuente) DEBE retornar los mismos 5 valores exactos de la fuente para
  los campos portados: `config_version="2.0.0"`, `anchor_mode=AnchorMode.NY_MIDNIGHT`,
  `vwap_warmup_bars=45`, `custom_anchor_hour=0`, `server_to_utc_offset=-999`.
- **R26** (DEBE). `load_vwap_anchor_config(path) -> VwapAnchorConfig` (renombrado de `load_config`
  de la fuente) DEBE preservar la validación de la fuente (`config_version` ausente o vacío →
  `ValueError`) acotada a los 5 campos portados; los campos ausentes se completan con los defaults
  de R25.
- **R27** (DEBE). `common/vwap_engine.py` NO DEBE importar `numpy` ni ninguna dependencia externa
  a `stdlib` (solo `math`, `dataclasses`, `datetime`, `zoneinfo`, `enum`, `json`, `pathlib`),
  preservando la propiedad de módulo de dominio puro de la fuente.
- **R28** (DEBE). `tests/strategy/common/test_vwap_engine_properties.py` DEBE portar, sin modificar
  sus aserciones respecto a la fuente (solo imports/rutas y el renombrado `InspectorConfig` →
  `VwapAnchorConfig`, `default_config` → `default_vwap_anchor_config`), las cinco propiedades
  `hypothesis` de `test_vwap_properties.py` de la fuente: CA6 (`sigma >= 0`), CA7 (reset en
  `is_anchor=True`), CA8 (`is_valid=False` con volumen total cero), CA9 (`zscore==0` y bandas
  colapsadas cuando `sigma==0`), CA11 (umbral de `is_warmed_up`), cada una con `@settings(
  max_examples=1000)` y marcada `pytestmark = pytest.mark.unit` (patrón de
  `tests/data/test_sessions.py:11`, `tests/data/test_mt5_export_pure.py:24` — no existe marcador
  `property` propio en `pyproject.toml`).
- **R29** (DEBE). `tests/strategy/common/test_is_new_anchor.py` DEBE portar la tabla completa de 10
  casos DST de `test_is_new_anchor.py` de la fuente (NY midnight con EDT/EST, server midnight,
  custom hour), sin modificar sus aserciones.
- **R30** (DEBE). `tests/strategy/common/test_vwap_parity.py` DEBE portar únicamente las Capas 1
  (`TestManualReference`, `TestDegenerateCA9`) y 2 (`TestLayer2InternalConsistency` sobre
  `fixtures/sample_m1.csv`, portado a `tests/strategy/fixtures/sample_m1.csv`) de la fuente,
  adaptando `TestDefaultConfig`/`TestLoadConfig` para verificar únicamente los 5 campos de
  `VwapAnchorConfig` (R25/R26) — no los 19 campos de `InspectorConfig` de la fuente. La Capa 3
  (`TestLayer3MQL5Parity`, marcada `@pytest.mark.mql5_parity`) NO DEBE portarse en este Change
  (ver Rg-7, §7).
- **R31** (DEBE). `uv run pytest tests/strategy/common/ -v` DEBE pasar en verde con las propiedades
  CA6/CA7/CA8/CA9/CA11, la tabla DST completa y las Capas 1–2 de paridad numérica.

### 3.6. `common/zones.py` — implementación nueva

**Confirmado (no porte)**: no existe `zones.py` ni lógica de clasificación PRO/MID/CT en ningún
repositorio inspeccionado (`genesis`, `ABON/vwap-smc-inspector` incluido su historial y
`reference/legacy-v1/`). Implementación nueva desde la descripción funcional del spec §2.2
("PRO/MID/CT desde VWAP + z-score").

**Requisitos**:

- **R32** (DEBE). `common/zones.py` DEBE definir `Zone` como `StrEnum` con miembros `PRO`, `MID`,
  `CT` (las 3 zonas genéricas se mantienen aunque la pierna PRO esté archivada para el Candidato A
  — spec §2.2: "la pierna PRO queda archivada (A2)" es una decisión de `candidate_a`, no una
  limitación del componente `common/`).
- **R33** (DEBE). `common/zones.py` DEBE definir
  `classify_zone(zscore: float, pro_zscore_max: float = 1.0, ct_zscore_min: float = 2.0) -> Zone`
  como función pura, **sin** leer ningún archivo de configuración ni depender de
  `VwapAnchorConfig`/`InspectorFunnelConfig` — los umbrales se reciben como parámetros explícitos
  con defaults, nunca hardcodeados sin posibilidad de override (evita colisión de namespace: el
  umbral real de producción para el Candidato A vive en `candidates.A.*`, fuera de este Change).
- **R34** (DEBE). `classify_zone` DEBE clasificar: `Zone.PRO` si `abs(zscore) < pro_zscore_max`;
  `Zone.MID` si `pro_zscore_max <= abs(zscore) < ct_zscore_min`; `Zone.CT` si
  `abs(zscore) >= ct_zscore_min`.
- **R35** (DEBE). `classify_zone` DEBE lanzar un error explícito (con contexto) si
  `pro_zscore_max >= ct_zscore_min` (configuración de umbrales inconsistente, fail-fast — spec
  §8), nunca clasificar silenciosamente con umbrales invertidos.
- **R36** (DEBE). `tests/strategy/common/test_zones.py` DEBE incluir, como mínimo, una tabla
  golden con casos construidos a partir de `VWAPResult` sintéticos (`zscore` límite exacto en cada
  frontera: `pro_zscore_max`, `ct_zscore_min`, y valores intermedios en cada zona), siguiendo el
  patrón de golden tests del spec §9 ("mini-datasets sintéticos").
- **R37** (DEBE). `uv run pytest tests/strategy/common/test_zones.py -v` DEBE pasar en verde.

### 3.7. Testing de contrato (`tests/strategy/`)

**Requisitos**:

- **R38** (DEBE). `tests/strategy/fakes.py` DEBE definir `FakeStrategyCandidate` (patrón
  `tests/data/fakes.py`): implementa `StrategyCandidate` con un `on_bar` cuyo comportamiento es
  parametrizable por el test (p. ej. una función inyectada), sin lógica de trading real.
- **R39** (DEBE). `tests/strategy/test_contract_lookahead_property.py` (o nombre equivalente) DEBE
  incluir al menos un test de propiedad `hypothesis` (`max_examples>=1000`) que verifique el
  invariante central del spec §9: para una secuencia de `AnnotatedBar` con `t_actual` fijado en
  una `BarClock`, el output de `FakeStrategyCandidate.on_bar(bar_t)` no cambia si se mutan
  (agregan/alteran) barras con `timestamp_utc > bar_t.timestamp_utc` en la secuencia de entrada.
- **R40** (DEBE). Al menos un test DEBE verificar que `BarClock.require(timestamp)` lanza
  `LookaheadError` cuando `timestamp > current_time` tras `advance(bar)`, y que no lanza cuando
  `timestamp <= current_time`.
- **R41** (DEBE). `uv run pytest tests/strategy/ -v` DEBE pasar en verde.
- **R42** (DEBERÍA). `tests/strategy/conftest.py` DEBERÍA exponer fixtures de conveniencia
  (`sample_annotated_bars`, `firm_profile_fixture`) reutilizando los fakes/fixtures ya existentes
  de `tests/data/` donde aplique, evitando duplicar construcción de `FirmProfile`/`SymbolFigure`.

---

## 4. Invariantes transversales

- **R43** (DEBE). Ningún módulo de este Change DEBE introducir estado compartido mutable entre
  candidatos (ni parámetros, ni contadores, ni caché a nivel de módulo indexada por candidato) —
  regla de aislamiento del spec §2.1/§2.5.
- **R44** (DEBE). Ningún output de `on_bar(t)` de un candidato (real o fake) DEBE depender, directa
  o indirectamente, de una `AnnotatedBar` con `timestamp_utc > t` (invariante forward-only, spec
  §2.1, §8, §9) — verificado por R39.
- **R45** (DEBE). Toda excepción de dominio nueva de este Change (`LookaheadError`, cualquier
  excepción futura del Inspector) DEBE heredar de `GenesisStrategyError` y llevar mensaje con
  contexto explícito (símbolo/timestamp/valores involucrados) — fail-fast, nunca degradación
  silenciosa (spec §8).
- **R46** (DEBE). `src/genesis/strategy/__init__.py` DEBE exportar un `__all__` mínimo y curado
  (patrón `src/genesis/data/__init__.py`), sin re-exportar símbolos internos de `common/`.
- **R47** (DEBE). `uv run mise run ci` (lint + `ty` + test) DEBE pasar en verde sobre
  `src/genesis/strategy/` y `tests/strategy/` nuevos.

---

## 5. Manejo de errores (resumen normativo, spec §8)

| Excepción | Módulo | Disparador | Efecto |
|---|---|---|---|
| `GenesisStrategyError` | `genesis.strategy.errors` | Raíz de la jerarquía de la capa 2 | — |
| `LookaheadError` | `genesis.strategy.errors` | `BarClock.require(timestamp)` con `timestamp > current_time` (o `current_time is None`) | Aborta la ejecución de `on_bar(t)` que la provocó |
| (fuera de alcance) `SessionBoundaryError` | — | Candidato B (Issue E), spec §2.3 | No se implementa en este Change |
| (fuera de alcance) errores del simulador (`AccountScopeError`-like para backtest) | — | Issue G | No se implementa en este Change |

---

## 6. Criterios de aceptación (evals ejecutables)

```
DADO   el archivo src/genesis/strategy/contract.py
CUANDO rg -n "class StrategyCandidate" src/genesis/strategy/contract.py
ENTONCES retorna >=1 coincidencia, y el decorador @runtime_checkable aparece en la línea
         inmediatamente anterior
```

```
DADO   el archivo src/genesis/strategy/contract.py
CUANDO rg -n "class EntryIntent" src/genesis/strategy/contract.py
       y rg -n "direction|sizing_hint|candidate_id|config_version" src/genesis/strategy/contract.py
ENTONCES la primera retorna >=1 coincidencia; la segunda retorna >=4 coincidencias (una por campo)
```

```
DADO   el archivo src/genesis/strategy/errors.py
CUANDO rg -n "class GenesisStrategyError" src/genesis/strategy/errors.py
       y rg -n "class LookaheadError" src/genesis/strategy/errors.py
ENTONCES ambas retornan >=1 coincidencia y LookaheadError hereda de GenesisStrategyError
```

```
DADO   una BarClock recién construida (current_time=None) y un timestamp cualquiera
CUANDO se invoca BarClock.require(timestamp)
ENTONCES se lanza LookaheadError (ningún timestamp es válido antes de la primera barra)
```

```
DADO   una BarClock con advance(bar_t0) ya invocado (current_time=bar_t0.timestamp_utc)
CUANDO se invoca BarClock.require(timestamp) con timestamp > bar_t0.timestamp_utc
ENTONCES se lanza LookaheadError con un mensaje que incluye ambos timestamps
```

```
DADO   una secuencia de AnnotatedBar y un FakeStrategyCandidate determinista
CUANDO se ejecuta on_bar(bar_t) y luego se mutan (o agregan) barras con timestamp_utc > bar_t.timestamp_utc
       en la secuencia de entrada, re-ejecutando on_bar(bar_t) con el estado previo al punto t
ENTONCES el resultado (list[EntryIntent]) de ambas ejecuciones es idéntico (>=1000 ejemplos hypothesis)
```

```
DADO   el archivo src/genesis/strategy/inspector.py
CUANDO rg -n "def inspect" src/genesis/strategy/inspector.py
       y rg -n "from genesis.data" src/genesis/strategy/inspector.py
ENTONCES la primera retorna >=1 coincidencia; la segunda retorna >=1 coincidencia con symbols/profile/calendar
```

```
DADO   un EntryIntent cuyo timestamp implícito cae dentro de una ventana de news_windows()
CUANDO se invoca inspect(intent, figure, firm_profile, news_events, config)
ENTONCES el InspectorVerdict resultante tiene authorized=False y rejection_reason=RejectionReason.NEWS_WINDOW
```

```
DADO   el archivo src/genesis/strategy/common/vwap_engine.py
CUANDO rg -n "class VwapAnchorConfig" src/genesis/strategy/common/vwap_engine.py
ENTONCES retorna >=1 coincidencia con exactamente 5 campos (config_version, anchor_mode,
         vwap_warmup_bars, custom_anchor_hour, server_to_utc_offset)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/strategy/common/ -v
ENTONCES pasa en verde, incluyendo las propiedades CA6/CA7/CA8/CA9/CA11 y la tabla DST de 10 casos
         de is_new_anchor, sin marcador mql5_parity presente en la suite
```

```
DADO   el archivo src/genesis/strategy/common/zones.py
CUANDO rg -n "def classify_zone" src/genesis/strategy/common/zones.py
ENTONCES retorna >=1 coincidencia con parámetros pro_zscore_max y ct_zscore_min con defaults
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/strategy/common/test_zones.py -v
ENTONCES pasa en verde con >=1 tabla golden de clasificación PRO/MID/CT
```

```
DADO   el diff del commit que cierra este Change
CUANDO git diff --stat -- src/genesis/data
ENTONCES no retorna ninguna línea (Change B permanece intacto)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/strategy/ -v
ENTONCES pasa en verde (exit code 0)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run mise run ci
ENTONCES lint + ty + test pasan en verde (exit code 0)
```

```
DADO   el archivo src/genesis/strategy/inspector_config.json (o recurso empaquetado equivalente)
CUANDO rg -n "candidates\." src/genesis/strategy/inspector_config.json
ENTONCES retorna 0 coincidencias (namespace candidates.<letra>.* no poblado en este Change)
```

---

## 7. Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| Rg-1 | El diseño de `BarClock` de este Change podría no encajar con el diseño real del simulador de Issue G (aún no existe). | Retrabajo en G si el objeto de "vista incremental" definido aquí no es el que el simulador necesita. | Mantener `BarClock` mínimo y desacoplado (excepción + `advance`/`require`), documentado explícitamente en `design.md` como sujeto a extensión (no ruptura) en Issue G. |
| Rg-2 | `InspectorFunnelConfig` (namespace `inspector.*`) y `VwapAnchorConfig` (`common/vwap_engine.py`) podrían confundirse por nombre con el `InspectorConfig` de la fuente portada. | Ambigüedad de mantenimiento si un futuro contribuidor asume que `VwapAnchorConfig` es un espejo completo de la fuente. | Docstring explícito de R23 documentando el subconjunto y el destino de los 14 campos restantes; `design.md` debe referenciar esta tabla. |
| Rg-3 | Los cortes numéricos de `classify_zone` (`pro_zscore_max=1.0`, `ct_zscore_min=2.0`) son una hipótesis de este spec, no un valor cerrado por el spec global (§2.2 solo dice "desde VWAP + z-score"). | Si el Candidato A (Issue F) necesita cortes distintos, este Change ya los expone como parámetros con override, sin requerir cambio de firma. | R33 exige que sean parámetros explícitos con defaults, nunca constantes hardcodeadas sin override — mitiga el riesgo por diseño. |
| Rg-4 | `RejectionReason` con solo 3 miembros (`INSUFFICIENT_RR`, `LOT_SIZE_OUT_OF_BOUNDS`, `NEWS_WINDOW`) podría resultar insuficiente cuando D/E/F integren validaciones específicas de candidato. | Necesidad de extender el `StrEnum` en un Change posterior. | `StrEnum` es extensible sin romper compatibilidad (nuevos miembros no invalidan el contrato existente); documentado como lista mínima, no cerrada, en R15. |
| Rg-5 | Sin `tests/strategy/` previo, no hay patrón de fakes/fixtures ya validado para esta capa. | Mayor esfuerzo de diseño de testing desde cero. | R38/R42 replican explícitamente el patrón ya validado de `tests/data/` (conftest, fakes, fixtures). |
| Rg-6 | Ausencia de jerarquía de excepciones compartida entre capas (`genesis.data` vs `genesis.strategy`). | Código consumidor no puede capturar errores de forma agregada entre capas con un único `except`. | Decisión explícita (R8) de mantener jerarquías independientes por capa — no hay precedente de raíz compartida y unificarla ahora es alcance no pedido por el spec; revisar en un Change futuro si se vuelve necesario. |
| Rg-7 | `fixtures/mql5_reference.csv` no existe en la fuente portada; los tests de paridad MQL5↔Python de Capa 3 (`TestLayer3MQL5Parity`, `@pytest.mark.mql5_parity`) no pueden ejecutarse sin una fuente MQL5 real. | El criterio "paridad MQL5↔Python ≤ 1e-9" citado en el docstring de la fuente queda como criterio de diseño no verificado por un test golden real en este Change. | **Deuda diferida, explícitamente aceptada**: R30 excluye la Capa 3 del porte; el criterio de aceptación de este Change se acota a las Capas 1–2 (referencia manual + consistencia interna sobre `sample_m1.csv`). Si en el futuro se genera una fuente MQL5 real (fuera del alcance de un Change de Python puro), un Change posterior puede portar la Capa 3 sin romper compatibilidad. |

---

## 8. Preguntas abiertas (no bloquean este Change)

- Diseño exacto de cómo el simulador de Issue G invocará `BarClock.advance`/`require` en su loop
  event-driven (spec §5.2 `simulator.py`): este Change deja el contrato mínimo; la integración
  concreta se decide en el `design.md` de Issue G.
- Si `InspectorFunnelConfig` necesitará más campos de lotaje/tolerancia específicos cuando el
  primer candidato real (Candidato B, Issue E) ejercite `inspect()` con datos reales — este Change
  fija el mínimo verificable (R16); extensiones son aditivas, no rompen el contrato.
- Nombre exacto del archivo/recurso de `inspector_config.json` (¿archivo plano en
  `src/genesis/strategy/` o recurso empaquetado vía `importlib.resources` como
  `genesis.data.profiles.the5ers.json`?) — se resuelve en `design.md` siguiendo el patrón ya
  validado de `genesis.data.profile.load_firm_profile` (R19 solo fija el namespace, no la
  mecánica exacta de carga).

---

## 9. Referencias

- Issue: https://github.com/bbenja11/genesis/issues/4
- `idea.md` / `proposal.md` de este Change (fases explore/propose).
- Spec vigente: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` — §2.1 (contrato
  normativo), §2.2 (Candidato A, componentes, archivo de pierna PRO), §2.5 (higiene del torneo,
  aislamiento), §5.1 (`python/strategy/`), §8 (manejo de errores), §9 (testing EDD/TDD), §11.1
  (PA-3, PA-4).
- Spec promovido (Issue A): `.pulse/specs/docs/spec.md` — R2.1–R2.5.
- Spec promovido (Change B): `.pulse/specs/data/spec.md` — R28–R33 (`store.py` forward-only por
  diseño, R33 explícito "NO DEBE lanzar `LookaheadError` en este Change").
- ADR-8 (Change B archivado):
  `.pulse/changes/archive/2-b-feat-data-capa-de-datos-export-mt5-calendario-sesiones-calidad/design.md`.
- Código de la capa de datos consumido: `src/genesis/data/store.py` (`AnnotatedBar:28`,
  `iter_bars:68`), `src/genesis/data/errors.py` (`GenesisDataError:4`),
  `src/genesis/data/symbols.py` (`SymbolFigure:12`, `SymbolSpec:32`), `src/genesis/data/profile.py`
  (`FirmProfile:32`, `load_firm_profile:64`, `firm_profile_hash:100`), `src/genesis/data/calendar.py`
  (`EconomicCalendarSource:45`, `news_windows:69`, `ImpactLevel:26`), `src/genesis/data/metadata.py`
  (`CONFIG_VERSION:18`), `src/genesis/data/__init__.py` (patrón `__all__`).
- Fuente externa portada (`vwap_engine`): `C:\Users\bbrav\ABON\vwap-smc-inspector\python\
  vwap_engine.py`, `python\inspector_config.json`, `python\tests\{conftest.py,
  test_vwap_properties.py, test_vwap_parity.py, test_is_new_anchor.py,
  fixtures\sample_m1.csv}` (sin `fixtures\mql5_reference.csv`).
- Fuente funcional para `zones.py` (implementación nueva, no porte):
  `C:\Users\bbrav\ABON\vwap-smc-inspector\docs\trading_rules.md`,
  `C:\Users\bbrav\ABON\vwap-smc-inspector\reference\legacy-v1\Python\backtest\vwap_bands.py`.
- Tests de referencia (patrón a replicar): `tests/data/conftest.py`, `tests/data/fakes.py`,
  `tests/data/fixtures/`, `tests/data/test_sessions.py:11` (patrón de marcador `unit` para tests
  `hypothesis`).
- `pyproject.toml`: markers registrados (`unit`, `integration`, `e2e`, `statistical`, `slow`) —
  no existe marcador `property` ni `mql5_parity`; este Change no registra marcadores nuevos
  (Rg-7).
- Reglas de proceso: `.agents/rules/architecture-conventions.md`,
  `.agents/rules/eval-tdd-conventions.md`, `.agents/rules/tooling-conventions.md`.
- `AGENTS.md` (raíz) — invariantes de código citados textualmente del spec.
- `CLAUDE.md` (raíz) — arquitectura de 4 capas, comandos, flujo SDD.

<!-- change:8-e-feat-strategy-candidato-b-completo-rango-de-apertura-gatillo-s -->
# Specification: Candidato B completo — rango de apertura, gatillo de ruptura, sizing vol-targeting, cierre forzado (Issue #8 / E)

SSoT: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` (en adelante «el spec») — §2.1,
§2.3, §2.x, §3, §5.1, §6.2, §8, §9, §11, §11.1. Este documento formaliza `idea.md` y
`proposal.md` de este Change en requisitos verificables, y **continúa** la numeración `R#` del
delta-spec vigente del dominio `strategy` (`.pulse/specs/strategy/spec.md`, R1–R47, promovido de
Issue C) sin colisionar con ella: este documento empieza en **R48**. Los gates G/C/P/T del spec
**nunca se relajan**; ningún requisito de este documento puede contradecirlos.

Convención de rutas: real del repo, `src/genesis/strategy/...` (no el pseudocódigo
`python/strategy/...` del spec §5.1).

Este Change resuelve normativamente los 6 riesgos que `proposal.md` (§"Riesgos que specify debe
acotar") delega explícitamente a esta fase (fórmula/período ATR, `tp_rr_multiple` default,
excepción de estado sin señal pendiente, tolerancia de doji, nombre/ubicación de excepciones de
config, y ubicación del test de integración), y fija con precisión matemática la interacción
rango-congelado↔gatillo (Decisión 3 de `proposal.md`, cuya redacción original dejaba una
ambigüedad de índice que aquí se elimina — ver §3.2).

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Construir el primer candidato real del torneo: `src/genesis/strategy/candidate_b/`, paquete que
implementa `StrategyCandidate` (`genesis.strategy.contract`, Issue C, cerrado) **y**
`RiskLevelsProvider` (`genesis.backtest.simulator`, Issue G, cerrado, ADR-G3) en una única clase
`CandidateB`, agnóstica a los demás candidatos, sin reabrir ningún módulo de `genesis.data`,
`genesis.strategy.{contract,inspector,clock}` ni `genesis.backtest/`. Esto desbloquea el primer
eslabón real del camino crítico A→B→C→{E,G}→H (Issue H, WFA + Monte Carlo, no puede arrancar sin
al menos un `StrategyCandidate` real).

### 1.2. Alcance IN

- `src/genesis/strategy/candidate_b/__init__.py`: `__all__` mínimo y curado (patrón
  `src/genesis/strategy/__init__.py`).
- `src/genesis/strategy/candidate_b/candidate.py`: `CandidateB` (`@register_candidate("B")`),
  rango de apertura como estado incremental forward-only, dirección de referencia con tolerancia
  de doji, gatillo de ruptura confirmado por cierre, ATR-Wilder-14 incremental propio, sizing
  vol-targeting con balance de referencia fijo, `risk_levels(intent)`.
- `src/genesis/strategy/candidate_b/config.py`: `CandidateBConfig`, `load_candidate_b_config()`.
- Extensión aditiva de `src/genesis/strategy/inspector_config.json`: namespace `candidates.B.*`
  (hoy reservado y vacío por C, R20 del delta-spec de C).
- Extensión aditiva de `src/genesis/strategy/errors.py`: `CandidateBConfigError`,
  `CandidateBStateError` (ambas heredan `GenesisStrategyError`).
- `tests/strategy/candidate_b/`: unit, property (`hypothesis`), golden, integración con el
  `Simulator` real de Issue G.

### 1.3. Alcance OUT (YAGNI explícito)

- Cualquier modificación de `src/genesis/data/`, `src/genesis/strategy/{contract.py, clock.py,
  inspector.py}` o `src/genesis/backtest/` — todos cerrados (Issues B, C, G); este Change se apoya
  exclusivamente en sus superficies públicas ya existentes.
- El espacio de búsqueda IS completo (grid 3×3×3 = 27 combinaciones del spec §6.2): este Change
  fija un **constructor parametrizable** y **un único punto de referencia** en
  `candidates.B.*`; el diseño del muestreo (grid lineal, log-lineal, Sobol) y su materialización
  completa es responsabilidad de Issue H (spec §6.2 literal).
- `candidate_a/` (Issue D/F) y `candidate_c/` (Issue K): fuera de alcance total.
- Cualquier mecanismo de cierre forzado propio del candidato: ya resuelto de facto por
  `Simulator._enforce_session_close_and_guard` (Issue G, cerrado) — este Change solo documenta la
  resolución (§3.7), no diseña nada nuevo.
- Cualquier puerto inyectable nuevo para balance de cuenta en vivo (`AccountBalanceProvider`-like):
  descartado explícitamente (Decisión 5 de `proposal.md`; §3.4 de este documento fija el balance
  de referencia como parámetro de construcción fijo).
- Reintentos de señal tras una ruptura fallida dentro del mismo `trading_day`: máximo una señal
  por sesión/símbolo sin excepciones (§3.2).
- Un archivo de config propio nuevo para `candidate_b/` (fuera del `inspector_config.json`
  existente) y un `errors.py` propio scoped a `candidate_b/`: ambos descartados (§3.6).

---

## 2. Convenciones de esta especificación

- Los requisitos usan **DEBE** (MUST) y **DEBERÍA** (SHOULD), numerados `R48..Rn`, continuando sin
  colisión la numeración de `.pulse/specs/strategy/spec.md` (R1–R47). Cada requisito es
  verificable por al menos un test o una aserción `rg`/`fd`.
- Nombres de funciones/clases/excepciones son **normativos**; firmas exactas de tipos ya fijadas
  aquí (constructor de `CandidateB`, `CandidateBConfig`) no se reabren en `design.md` salvo
  justificación explícita.
- Identificadores en inglés, docstrings y mensajes de error en español (convención del repo).
- `bar.in_session: bool` y `bar.trading_day: date` (`genesis.data.store.AnnotatedBar`,
  `src/genesis/data/store.py:31-38`) son la **única** fuente de verdad de sesión/día para
  `CandidateB` — este Change NO DEBE reimplementar ninguna lógica de calendario/DST
  (`genesis.data.sessions.session_window`, ya resuelto por Issue B).
- `on_bar` recibe **toda** barra M1 cerrada que el `Simulator`/harness le entregue, incluidas las
  que caen fuera de la sesión de contado (`bar.in_session=False`, p. ej. horas extendidas de
  índices CFD); `CandidateB` DEBE ignorarlas para su lógica de señal (§3.2) pero puede
  incorporarlas o no a su estado ATR según se fija en §3.3.

---

## 3. Requisitos por módulo

### 3.1. Ubicación y forma del paquete

**Requisitos**:

- **R48** (DEBE). El árbol destino DEBE ser `src/genesis/strategy/candidate_b/` como paquete
  (`__init__.py` + `candidate.py` + `config.py`), no un módulo plano — coherente con la tabla
  normativa del spec §5.1 y con `.pulse/specs/strategy/spec.md` §1.3/§5.1 (R20).
- **R49** (DEBE). `candidate_b/config.py` NO DEBE crear ningún recurso de configuración nuevo:
  `load_candidate_b_config()` DEBE leer el namespace `candidates.B.*` del **mismo** recurso
  empaquetado `src/genesis/strategy/inspector_config.json` ya reservado por Issue C (R20 del
  delta-spec de C), replicando el patrón `importlib.resources` de
  `load_inspector_funnel_config` (`src/genesis/strategy/inspector.py:117-143`).
- **R50** (NO DEBE). `src/genesis/strategy/candidate_b/candidate.py` NO DEBE importar
  `genesis.backtest` en ningún punto (`rg -n "genesis.backtest" src/genesis/strategy/candidate_b/candidate.py`
  DEBE retornar 0 coincidencias): `RiskLevelsProvider` es un `Protocol` estructural
  (`@runtime_checkable`, `src/genesis/backtest/simulator.py:59-70`) — `CandidateB` lo satisface
  por **duck typing** (mismo nombre de método, misma firma) sin importar el símbolo, preservando
  la dependencia unidireccional capa 2 → capa 1 (nunca capa 2 → capa 3).

### 3.2. `candidate.py` — `CandidateB`, estado de sesión y gatillo

**Responsabilidad**: implementar `StrategyCandidate` (Issue C, cerrado) manteniendo el aislamiento
del spec §2.1/§2.5 (ningún estado compartido entre candidatos ni entre símbolos).

**Requisitos**:

- **R51** (DEBE). `candidate.py` DEBE definir `class CandidateB` decorada
  `@register_candidate("B")` (línea inmediatamente anterior a la declaración de clase), con
  `candidate_id: str = "B"` como atributo de **clase** fijo (no parámetro de constructor): la
  letra de registro y el atributo normativo DEBEN coincidir por construcción, sin forma de
  instanciar `CandidateB` con un `candidate_id` distinto de `"B"`.
- **R52** (DEBE). `CandidateB` DEBE implementar el método `risk_levels(self, intent: EntryIntent)
  -> tuple[float, float]` en la misma clase que `on_bar`, satisfaciendo estructuralmente
  `RiskLevelsProvider` (`isinstance(CandidateB(...), RiskLevelsProvider)` DEBE retornar `True`, R50).
- **R53** (DEBE). El constructor DEBE ser:

  ```python
  def __init__(
      self,
      *,
      figure: SymbolFigure,
      reference_balance: float,
      n_minutes: int,
      risk_pct: float,
      atr_stop_frac: float | None = None,
      atr_period: int = 14,
      tp_rr_multiple: float = 3.0,
      config_version: str = CONFIG_VERSION,
  ) -> None
  ```

  con los 3 parámetros del grid IS del spec §6.2 (`n_minutes`, `atr_stop_frac`, `risk_pct`)
  aceptados de forma **explícita y directa** (sin defaults ocultos que oculten qué punto del
  grid corre una instancia dada — Decisión 7 de `proposal.md`, resuelve Rg-6 de `idea.md`).
  `figure` y `reference_balance` son obligatorios (sin default): una instancia de `CandidateB`
  está ligada implícitamente a un único símbolo del universo (US500/NAS100/US30/GER40) y a un
  balance de referencia fijo — el docstring de la clase DEBE documentar explícitamente que
  **nunca** debe compartirse una misma instancia entre streams de más de un símbolo (mismo
  patrón que `Simulator`, un orquestador por `(candidate, symbol)`,
  `src/genesis/backtest/simulator.py:203-204`).
- **R54** (DEBE). El estado interno mutable de `CandidateB` DEBE incluir, como mínimo:
  `_current_trading_day: date | None`, `_range_high: float | None`, `_range_low: float | None`,
  `_reference_direction: Direction | None`, `_signal_emitted_today: bool`,
  `_minute_index: int` (contador de barras `in_session=True` vistas en el `trading_day` vigente,
  0-indexado, reseteado a `0` en el primer bar `in_session` de cada nuevo día), y el estado ATR de
  §3.3 (`_atr_value`, `_atr_bars_seen`, `_atr_last_close`, estos tres **no** reseteados por día).
- **R55** (DEBE). `on_bar(bar)` DEBE ejecutar, en este orden exacto, por cada `AnnotatedBar`
  recibida:
  1. **Reset diario**: si `bar.trading_day != self._current_trading_day`, resetear
     `_current_trading_day`, `_range_high`, `_range_low`, `_reference_direction`,
     `_signal_emitted_today=False`, `_minute_index=0` (el estado ATR de §3.3 **no** se resetea).
  2. **Actualización ATR** (§3.3): si `bar.in_session`, actualizar el estado ATR con esta barra
     — incondicionalmente, incluso si ya se emitió la señal del día o si la barra aún no
     participa en la formación del rango.
  3. **Filtro de sesión**: si `not bar.in_session`, retornar `[]` sin tocar ningún otro estado
     (ni rango, ni dirección, ni flag de señal) — R55 termina aquí para esa barra.
  4. **Dirección de referencia** (§3.2.1): si `self._minute_index == 0` (primera barra
     `in_session` del día), fijar `_reference_direction` según R56, luego continuar al paso 5
     sin retornar todavía (esta barra también participa en la formación del rango, R57).
  5. **Formación del rango** (§3.2.2): si `self._minute_index < n_minutes`, actualizar
     `_range_high = max(_range_high or bar.high, bar.high)`,
     `_range_low = min(_range_low or bar.low, bar.low)`; incrementar `_minute_index`; retornar
     `[]` (el rango aún no está congelado, ningún gatillo se evalúa en esta rama).
  6. **Gatillo de ruptura** (§3.2.3): si `self._minute_index >= n_minutes` (rango ya congelado
     — congelación implícita: ninguna barra con `_minute_index >= n_minutes` vuelve a entrar en
     el paso 5): si `self._signal_emitted_today` o `_reference_direction is None`, incrementar
     `_minute_index` y retornar `[]`; en caso contrario, evaluar R58; si dispara, construir el
     `EntryIntent`, calcular y guardar niveles de riesgo (§3.3/§3.4), marcar
     `_signal_emitted_today = True`, incrementar `_minute_index`, retornar `[intent]`; si no
     dispara, incrementar `_minute_index` y retornar `[]`.
- **R56** (DEBE). La dirección de referencia (PA normativa 1 del issue §11.1) DEBE fijarse a
  partir de **una única** `AnnotatedBar`: la primera con `bar.in_session=True` del `trading_day`
  vigente (`_minute_index == 0`), comparando `bar.close` contra `bar.open` de esa misma barra:
  - `Direction.LONG` si `bar.close - bar.open > epsilon`;
  - `Direction.SHORT` si `bar.open - bar.close > epsilon`;
  - **ninguna dirección** (`_reference_direction` permanece `None` toda la sesión, fail-safe
    explícito — no se emite ninguna señal ese `trading_day`) si `abs(bar.close - bar.open) <=
    epsilon` (doji, dentro de tolerancia).
  - `epsilon = 0.5 * 10 ** (-figure.digits)` (medio tick del símbolo, la mínima unidad de precio
    representable por `figure.digits`, `src/genesis/data/symbols.py:12-27`): por debajo de este
    umbral, cualquier diferencia `close - open` se considera ruido de representación de punto
    flotante/redondeo, no una dirección real observable en el mercado (resuelve el riesgo 4 de
    `proposal.md`).
  - **Ejemplo numérico** (`figure.digits = 2`, `epsilon = 0.005`): `open=4500.00, close=4500.003`
    → `abs(diff) = 0.003 <= 0.005` → doji, sin dirección. `open=4500.00, close=4500.01` →
    `abs(diff) = 0.01 > 0.005` → `Direction.LONG`.
- **R57** (DEBE). La ventana de formación del rango comprende exactamente las primeras
  `n_minutes` barras `in_session` del día, `_minute_index` en `[0, n_minutes)` (0-indexado): la
  barra con `_minute_index == 0` (la misma que fija la dirección de referencia, R56) SÍ participa
  en la formación del rango. `_range_high`/`_range_low` son el `max`/`min` de `bar.high`/`bar.low`
  de exactamente esas `n_minutes` barras — ninguna barra posterior las modifica.
- **R58** (DEBE). El gatillo de ruptura (PA normativa 2 del issue §11.1, resuelve la ambigüedad de
  índice de Decisión 3 de `proposal.md`) DEBE evaluarse **por primera vez** en la barra con
  `_minute_index == n_minutes` (la `(n_minutes + 1)`-ésima barra `in_session` del día, la primera
  que **no** participó en la formación del rango, R57) y en toda barra posterior mientras
  `not self._signal_emitted_today`. Dispara si, y solo si, el cierre de la barra evaluada rompe
  **estrictamente** el extremo del rango congelado en la dirección de `_reference_direction`:
  - `Direction.LONG`: dispara si `bar.close > self._range_high` (estricto; `bar.close ==
    self._range_high` NO dispara).
  - `Direction.SHORT`: dispara si `bar.close < self._range_low` (estricto).
  - Ninguna barra con `_minute_index < n_minutes` (barra formadora) puede disparar el gatillo:
    por construcción, una barra formadora nunca puede romper un extremo que ella misma ayuda a
    definir (`high = max(...)` que la incluye), eliminando cualquier circularidad geométrica —
    la primera barra en la que la ruptura es lógicamente posible es, exactamente, la primera que
    ya no actualiza el rango (`_minute_index == n_minutes`), que es la misma barra desde la que
    R58 empieza a evaluar. No existe ninguna barra "intermedia" excluida ni ningún salto de
    índice adicional.
  - **Ejemplo numérico** (`n_minutes=15`): barras `_minute_index=0..14` (15 barras) forman el
    rango; supóngase `_range_high=4505.0`, `_range_low=4498.0`, `_reference_direction=LONG`. La
    barra `_minute_index=15` (16.ª barra `in_session` del día) con `bar.close=4506.2` dispara
    (`4506.2 > 4505.0`); con `bar.close=4505.0` exacto, NO dispara (igualdad, no ruptura); con
    `bar.close=4503.0`, NO dispara (dentro del rango).
- **R59** (DEBE). `CandidateB` DEBE emitir como máximo **un** `EntryIntent` por `trading_day`
  (PA "una señal por sesión/día como máximo" del issue), independientemente del resultado
  observable aguas abajo (autorizado/rechazado por el Inspector, ganador/perdedor si se abre, o si
  el precio regresa dentro del rango sin tocar el stop) — `CandidateB` no tiene visibilidad de
  ese resultado (`on_bar` no recibe ningún callback, contrato de C es unidireccional) y por tanto
  NO DEBE intentar inferirlo ni reintentar. `_signal_emitted_today` es el único flag de control
  (Decisión 9 de `proposal.md`, resuelve la pregunta abierta 9 de `idea.md`).
- **R60** (NO DEBE). `on_bar` NO DEBE mutar ni consultar ningún estado con `bar.timestamp_utc`
  futuro respecto al `bar` recibido en la llamada actual (invariante forward-only del spec §9,
  §8), verificado por R71 y R83.

### 3.3. ATR-Wilder-14 incremental (rama alternativa del stop)

**Decisión**: implementación mínima propia dentro de `candidate_b/` (no diferida, resuelve el
riesgo 1 de `proposal.md`: el spec §6.2 cuenta explícitamente `atr_stop_frac ∈ {0.5, 1.0, 1.5}`
como 9 de las 27 combinaciones del presupuesto de trials ya fijado como definitivo — diferir esta
rama bloquearía silenciosamente 2/3 del espacio de búsqueda de stop).

**Requisitos**:

- **R61** (DEBE). El estado ATR (`_atr_value: float | None`, `_atr_bars_seen: int`,
  `_atr_last_close: float | None`) DEBE ser **continuo across días**: NO se resetea en el reset
  diario de R55.1. Se actualiza únicamente con barras `bar.in_session=True` (R55.2) — las barras
  fuera de sesión NUNCA contribuyen al true range, evitando que un gap nocturno/de fin de semana
  (entre el cierre de una sesión y la apertura de la siguiente) distorsione el ATR intradía que
  informa el tamaño del stop.
- **R62** (DEBE). El *true range* de una barra `in_session` DEBE calcularse como:

  ```
  TR = max(bar.high - bar.low, |bar.high - last_close|, |bar.low - last_close|)   si last_close is not None
  TR = bar.high - bar.low                                                          si last_close is None (primera barra in_session vista jamás por la instancia)
  ```

  donde `last_close` es `_atr_last_close` **antes** de actualizarse con `bar.close` en esta misma
  barra (incluye el cierre de la última barra `in_session` del día anterior si la barra actual es
  la primera `in_session` de un nuevo día — el `TR` cruza la frontera de día sin reiniciarse).
- **R63** (DEBE). El ATR DEBE calcularse con suavizado de Wilder y período `atr_period` (default
  `14`, parámetro del constructor):
  - **Calentamiento**: mientras `_atr_bars_seen < atr_period`, `_atr_value` permanece `None`
    (ATR "no calentado", ATR aún no disponible); tras acumular exactamente `atr_period` valores de
    `TR`, `_atr_value` se fija por primera vez como la **media aritmética simple** de esos
    `atr_period` valores de `TR`.
  - **Suavizado posterior**: para cada barra `in_session` subsiguiente,
    `_atr_value = ((_atr_value_anterior * (atr_period - 1)) + TR) / atr_period`.
  - **Ejemplo numérico** (`atr_period=14`): 14 barras `in_session` consecutivas con
    `TR=10.0` cada una → `_atr_value` tras la 14.ª = `10.0` (media simple de 14 valores de 10.0).
    Barra 15 con `TR=24.0` → `_atr_value = ((10.0 * 13) + 24.0) / 14 = 154.0 / 14 = 11.0`.
- **R64** (DEBE). Si `atr_stop_frac is not None` pero `_atr_value is None` (ATR aún no calentado,
  `_atr_bars_seen < atr_period`) al momento de calcular `risk_levels`, `CandidateB` DEBE usar la
  **regla primaria** (extremo opuesto del rango, R66) como *fallback* explícito — nunca lanzar una
  excepción ni bloquear la emisión de la señal por falta de calentamiento del ATR.
- **R65** (DEBE). `candidate.py` NO DEBE importar ningún módulo de `common/` para el ATR (ni crear
  uno): el acumulador ATR es estado **propio** de `CandidateB`, sin componente compartido — ningún
  otro candidato del torneo lo necesita hoy (YAGNI, mismo criterio que evitó portar los 14 campos
  de `smc_engine` fuera de alcance en el delta-spec de C).

### 3.4. `risk_levels(intent)` — stop, take-profit y sizing

**Requisitos**:

- **R66** (DEBE). El stop_loss DEBE calcularse, en el momento en que `on_bar` detecta la ruptura
  (R58), a partir de `entry_reference = bar.close` de esa misma barra (idéntica referencia que usa
  `Simulator._compute_rr` para `proposed_rr`, `src/genesis/backtest/simulator.py:188-200`,
  `bar.close` — garantiza consistencia entre el R:R que ve el candidato y el que evalúa el
  Inspector):
  - **Regla primaria** (siempre disponible, se usa si `atr_stop_frac is None` o si R64 aplica):
    `stop_loss = self._range_low` si `Direction.LONG`; `stop_loss = self._range_high` si
    `Direction.SHORT` (extremo opuesto del rango congelado).
  - **Regla alternativa** (si `atr_stop_frac is not None` y `_atr_value is not None`, R63):
    `stop_loss = self._range_low - atr_stop_frac * self._atr_value` si `Direction.LONG`;
    `stop_loss = self._range_high + atr_stop_frac * self._atr_value` si `Direction.SHORT`
    (extiende el stop más allá del extremo opuesto del rango por `atr_stop_frac × ATR`, en la
    dirección adversa).
  - **Ejemplo numérico** (regla alternativa, `Direction.LONG`, `_range_low=4498.0`,
    `_atr_value=11.0`, `atr_stop_frac=1.0`): `stop_loss = 4498.0 - 1.0 * 11.0 = 4487.0`.
- **R67** (DEBE). `distancia_stop = abs(entry_reference - stop_loss)` DEBE ser estrictamente
  positiva; si `distancia_stop <= 0` (invariante interno violado — no debería ocurrir dada la
  geometría de R58/R66), `risk_levels` DEBE lanzar `CandidateBStateError` con contexto
  (`entry_reference`, `stop_loss`, `direction`) antes de dividir por ella en R69 — fail-fast, spec
  §8.
- **R68** (DEBE). `take_profit` (no definido por el spec §2.3, que solo define stop; la salida
  real del Candidato B es el cierre forzado de sesión, §3.7) DEBE calcularse como:

  ```
  take_profit = entry_reference + tp_rr_multiple * distancia_stop   si Direction.LONG
  take_profit = entry_reference - tp_rr_multiple * distancia_stop   si Direction.SHORT
  ```

  con `tp_rr_multiple: float = 3.0` como parámetro **propio** de `CandidateB`
  (`CandidateBConfig`), **no** derivado de `InspectorFunnelConfig.min_rr`
  (`src/genesis/strategy/inspector.py:58-68`) — acoplar un candidato concreto al namespace
  `inspector.*` violaría el espíritu de separación de namespaces de R16/R20 del delta-spec de C
  (resuelve el riesgo 2 de `proposal.md`). `tp_rr_multiple` NO forma parte del grid IS del spec
  §6.2 y este Change NO DEBE tratarlo como tal.
  - **Ejemplo numérico** (regla primaria, `Direction.LONG`, `entry_reference=4506.2`,
    `stop_loss=4498.0`, `tp_rr_multiple=3.0`): `distancia_stop = 8.2`;
    `take_profit = 4506.2 + 3.0 * 8.2 = 4506.2 + 24.6 = 4530.8`.
- **R69** (DEBE). El `sizing_hint` del `EntryIntent` (que el `Simulator` usa directamente como
  **lotes**, no como fracción — `Simulator._floating_pnl`,
  `src/genesis/backtest/simulator.py:332-336`: `points * position.sizing_hint *
  figure.value_per_point`) DEBE calcularse en el momento de la ruptura como:

  ```
  sizing_hint = (risk_pct * reference_balance) / (distancia_stop * figure.value_per_point)
  ```

  `figure.value_per_point == figure.tick_value / figure.tick_size` (dinero por punto de precio y
  por lote). Hasta el Change #55, esta fórmula usaba `figure.tick_value` crudo, lo que
  sobre-estimaba el lote ~100× en los 4 índices reales (Issue #55).

  usando el `figure`/`reference_balance` fijos del constructor (R53) — **nunca** el balance real
  evolutivo de `Simulator.account.balance` (Decisión 5 de `proposal.md`, resuelve el riesgo 2 de
  `idea.md`: sizing estático por diseño, no vol-targeting dinámico intra-run, coherente con la
  fórmula normativa del spec §2.3 que no menciona reajuste por trade).
  - **Ejemplo numérico** (`risk_pct=0.00375`, `reference_balance=100000.0`, `distancia_stop=8.2`,
    `figure.tick_value=1.0, figure.tick_size=1.0`): `sizing_hint = (0.00375 * 100000.0) /
    (8.2 * 1.0) = 375.0 / 8.2 ≈ 45.7317...` (float sin redondear).
- **R70** (NO DEBE). `CandidateB` NO DEBE redondear `sizing_hint` a `figure.volume_step` ni
  clampear contra `min_lot`/`max_lot`: esa validación es responsabilidad exclusiva del Inspector
  (`InspectorFunnelConfig`, `RejectionReason.LOT_SIZE_OUT_OF_BOUNDS`,
  `src/genesis/strategy/inspector.py:29-82`, ya cerrado por C) — `CandidateB` produce su mejor
  estimación sin re-implementar esa lógica (Decisión 5 de `proposal.md`).
- **R71** (DEBE). `risk_levels(intent)` DEBE retornar el par `(stop_loss, take_profit)` calculado
  y guardado en `_pending_risk_levels` **durante el mismo `on_bar`** que emitió `intent` (asociación
  síncrona por atributo mutable, sin necesitar identidad explícita en `EntryIntent` — el
  `Simulator` invoca `on_bar` → `risk_levels` inmediatamente, sin bar intermedio,
  `src/genesis/backtest/simulator.py:463-491`). Si `risk_levels` se invoca sin una señal pendiente
  asociada (`_pending_risk_levels is None`, caso defensivo que no debería ocurrir dado el orden de
  `_process_new_entries` de G), DEBE lanzar `CandidateBStateError` con contexto (resuelve el
  riesgo 3 de `proposal.md`: se elige una excepción de dominio nueva, no un `AssertionError`
  genérico, siguiendo el patrón de excepciones tipificadas con contexto ya establecido en todo el
  repo — `LookaheadError`, `SessionBoundaryError`, `BacktestConfigError`).

### 3.5. `config.py` — `CandidateBConfig` y namespace `candidates.B.*`

**Requisitos**:

- **R72** (DEBE). `config.py` DEBE definir `CandidateBConfig` como
  `@dataclass(frozen=True, slots=True)` con exactamente los campos: `n_minutes: int`,
  `atr_stop_frac: float | None`, `risk_pct: float`, `atr_period: int`, `tp_rr_multiple: float`.
- **R73** (DEBE). `config.py` DEBE definir `load_candidate_b_config(path: Path | None = None) ->
  CandidateBConfig` que lea `payload["candidates"]["B"]` del recurso `inspector_config.json`
  (R49), replicando el patrón fail-fast de `load_inspector_funnel_config`
  (`src/genesis/strategy/inspector.py:117-143`): lanza `CandidateBConfigError` con contexto
  (campo faltante + fuente) si el JSON no tiene la clave `candidates.B` o algún campo es
  inválido — nunca degradación silenciosa.
- **R74** (DEBE). `src/genesis/strategy/inspector_config.json` DEBE extenderse aditivamente (sin
  modificar `inspector.*`) con:

  ```json
  {
    "inspector": { "min_rr": 2.0, "min_lot": 0.01, "max_lot": 50.0 },
    "candidates": {
      "B": {
        "n_minutes": 15,
        "atr_stop_frac": 1.0,
        "risk_pct": 0.00375,
        "atr_period": 14,
        "tp_rr_multiple": 3.0
      }
    }
  }
  ```

  como **un único** punto de referencia (coincidente con el punto medio de cada eje del grid
  3×3×3 del spec §6.2), usado por `load_candidate_b_config()` para tests de
  integración/smoke — **no** el espacio completo de 27 combinaciones (Decisión 7 de
  `proposal.md`, resuelve la pregunta abierta 7 de `idea.md`: el diseño del muestreo IS completo
  es responsabilidad de Issue H, spec §6.2 literal, no de este Change).
- **R75** (DEBE). El constructor de `CandidateB` (R53) DEBE ser instanciable con cualquier punto
  del grid del spec §6.2 (`n_minutes ∈ {5,15,30}`, `atr_stop_frac ∈ {0.5,1.0,1.5}`, `risk_pct ∈
  {0.0025, 0.00375, 0.005}`) pasando los 3 parámetros directamente, sin depender de
  `load_candidate_b_config()` — Issue H instancia `CandidateB` una vez por punto del grid, sin
  reabrir este Change (resuelve Rg-6 de `idea.md`).

### 3.6. Excepciones nuevas

**Requisitos**:

- **R76** (DEBE). `src/genesis/strategy/errors.py` (archivo **compartido** existente, no un
  `errors.py` propio de `candidate_b/` — resuelve el riesgo 5 de `proposal.md`: no hay precedente
  en el repo de excepciones scoped a un candidato concreto, y el patrón ya establecido de
  `InspectorConfigError`/`DuplicateCandidateError` vive en el `errors.py` de la capa, no por
  módulo) DEBE extenderse aditivamente con:
  - `CandidateBConfigError(GenesisStrategyError)`: configuración de `candidates.B.*` inválida o
    incompleta (R73).
  - `CandidateBStateError(GenesisStrategyError)`: invariante interno violado —
    `risk_levels()` invocado sin señal pendiente (R71), o `distancia_stop <= 0` (R67).
- **R77** (DEBE). Ambas excepciones nuevas de R76 DEBEN llevar mensaje con contexto explícito
  (campo/valor involucrado), heredando de `GenesisStrategyError` (fail-fast, spec §8, mismo
  patrón que `LookaheadError`/`DuplicateCandidateError`/`InspectorConfigError` ya existentes).

### 3.7. Cierre forzado de sesión — documentación de resolución ya cerrada por G

**Requisitos**:

- **R78** (NO DEBE). `CandidateB` NO DEBE implementar ningún mecanismo propio de cierre de
  posición, ni emitir ningún `EntryIntent` ni señal equivalente de "cerrar" — el cierre forzado
  proactivo al alcanzar `close_utc` de `session_window(symbol, trading_day)` y el guard
  `SessionBoundaryError` (`Simulator._enforce_session_close_and_guard`,
  `src/genesis/backtest/simulator.py:408-432`, ya cerrado por Issue G, agnóstico a
  `candidate_id`) son responsabilidad **exclusiva** del `Simulator` (PA normativa 3 del issue
  §11.1, ya resuelta de facto — este Change solo documenta la resolución, no diseña un mecanismo
  nuevo).
- **R79** (DEBE). El docstring de `CandidateB` DEBE citar explícitamente esta resolución (R78) y
  referenciar `Simulator._enforce_session_close_and_guard` como el mecanismo real, para que un
  futuro contribuidor no intente reabrir esta decisión dentro de `candidate_b/`.

### 3.8. Testing (`tests/strategy/candidate_b/`)

**Requisitos**:

- **R80** (DEBE). `tests/strategy/candidate_b/` DEBE existir como paquete de test
  (`__init__.py`), con `conftest.py`/`fakes.py`/`fixtures/` propios únicamente si se necesitan
  helpers específicos de sesión sintética no cubiertos por `tests/strategy/fakes.py`
  (`make_annotated_bar`) — sin duplicar los ya existentes.
- **R81** (DEBE). Un test dedicado DEBE verificar
  `isinstance(CandidateB(...), RiskLevelsProvider)` como **primer** test del Change (resuelve el
  riesgo 1 de `idea.md`, patrón `tests/backtest/test_simulator_contract.py`).
- **R82** (DEBE). `tests/strategy/candidate_b/` DEBE incluir tests unitarios, como mínimo, de:
  construcción y congelamiento del rango (R57/R58), gatillo por dirección con los 3 casos de
  R58 (ruptura válida, igualdad exacta al extremo, dentro del rango), tolerancia de doji (R56, los
  2 casos numéricos del ejemplo), reset por `trading_day` (R55.1), ATR incremental con la tabla
  golden calculada a mano de R63 (calentamiento + suavizado de Wilder), sizing (R69, ejemplo
  numérico de R69), y `tp_rr_multiple` (R68, ejemplo numérico de R68).
- **R83** (DEBE). `tests/strategy/candidate_b/` DEBE incluir al menos un test de propiedad
  (`hypothesis`, `max_examples>=1000`, marcado `pytest.mark.unit`) que verifique, sobre `CandidateB`
  real (no solo `FakeStrategyCandidate`): el invariante central del spec §9 — ningún output de
  `on_bar(t)` cambia si se mutan/agregan barras con `timestamp_utc > t` — y la cita textual del
  spec §9 "el rango de los primeros N minutos no cambia con barras posteriores", verificado
  directamente sobre `_range_high`/`_range_low` congelados tras la ventana de formación (R57).
- **R84** (DEBE). `tests/strategy/candidate_b/` DEBE incluir, como mínimo, 3 golden tests de
  sesión sintética: `(a)` ruptura confirmada por cierre → exactamente un `EntryIntent`, con
  `stop_loss`/`take_profit` coincidentes byte a byte con el ejemplo numérico de R66/R68; `(b)`
  falsa ruptura intrabar (precio rompe el extremo dentro de una vela pero cierra dentro del
  rango) → cero `EntryIntent` esa barra (ruptura confirmada por cierre, no intrabar, spec §2.3
  literal); `(c)` doji exacto en la primera barra de la sesión (`abs(close-open) <= epsilon`,
  R56) → cero `EntryIntent` en toda la sesión.
- **R85** (DEBE). `tests/strategy/candidate_b/test_integration_simulator.py` (ubicación fijada
  aquí — resuelve el riesgo 6 de `proposal.md`: vive en `tests/strategy/candidate_b/`, co-ubicado
  con el resto de la suite del candidato, no en `tests/backtest/`; `tests/` es un árbol de
  paquetes Python con `__init__.py` en cada subcarpeta, lo que permite reutilizar
  `tests.backtest.fakes`/`tests.backtest.conftest` por import directo sin duplicar fixtures de
  `RawParquetStore`/`FirmProfile`) DEBE, marcado `pytest.mark.integration`: `(a)` repetir el test
  de R81 sobre una instancia real; `(b)` verificar que `Simulator(candidate=CandidateB(...),
  symbol="US500", ...)` no lanza `BacktestConfigError` al construirse; `(c)` ejecutar
  `Simulator.run(frame)` sobre un dataset sintético de al menos una sesión completa y verificar
  que el `Ledger` resultante contiene al menos un `FillRecord` o `RejectionRecord` asociado a
  `candidate_id="B"`.
- **R86** (DEBE). `uv run pytest tests/strategy/candidate_b/ -v` DEBE pasar en verde (exit code 0).

---

## 4. Invariantes transversales

- **R87** (DEBE). Ninguna instancia de `CandidateB` DEBE compartirse entre streams de más de un
  símbolo del universo (US500/NAS100/US30/GER40): una instancia por `(candidato, símbolo)`, mismo
  patrón que `Simulator` (R53) — `AnnotatedBar` no porta `symbol`
  (`src/genesis/data/store.py:28-38`), así que el estado incremental de una instancia compartida
  se corrompería silenciosamente entre símbolos si se entrelazaran streams.
- **R88** (DEBE). Ningún output de `on_bar(t)` de `CandidateB` DEBE depender, directa o
  indirectamente, de una `AnnotatedBar` con `timestamp_utc > t` (invariante forward-only, spec
  §2.1, §8, §9) — verificado por R83.
- **R89** (DEBE). `git diff --stat -- src/genesis/data src/genesis/backtest
  src/genesis/strategy/contract.py src/genesis/strategy/inspector.py
  src/genesis/strategy/clock.py` DEBE quedar vacío al cerrar este Change: la única modificación
  fuera de `src/genesis/strategy/candidate_b/` permitida es la extensión aditiva de
  `src/genesis/strategy/errors.py` (R76) y de `src/genesis/strategy/inspector_config.json` (R74).
- **R90** (DEBE). `uv run mise run ci` (lint + `ty` + test) DEBE pasar en verde sobre
  `src/genesis/strategy/candidate_b/` y `tests/strategy/candidate_b/` nuevos.

---

## 5. Manejo de errores (resumen normativo, spec §8)

| Excepción | Módulo | Disparador | Efecto |
|---|---|---|---|
| `CandidateBConfigError` | `genesis.strategy.errors` | `load_candidate_b_config()` con `candidates.B.*` ausente o inválido en `inspector_config.json` | Aborta la carga de config antes de construir `CandidateB` desde el punto de referencia |
| `CandidateBStateError` | `genesis.strategy.errors` | `risk_levels(intent)` invocado sin `_pending_risk_levels` asociado, o `distancia_stop <= 0` al calcular niveles de riesgo | Aborta el `_process_new_entries` del `Simulator` que la provocó (defensivo, no debería ocurrir en el flujo normal de G) |
| (fuera de alcance, ya resuelto por G) `SessionBoundaryError` | `genesis.backtest.errors` | Posición del Candidato B viva tras el cierre proactivo de sesión | No se implementa en este Change; ver R78/R79 |
| (fuera de alcance, ya resuelto por G) `BacktestConfigError` | `genesis.backtest.errors` | `CandidateB` no implementa `RiskLevelsProvider` (no debería ocurrir dado R52) | No se implementa en este Change |

---

## 6. Criterios de aceptación (evals ejecutables)

```
DADO   el archivo src/genesis/strategy/candidate_b/candidate.py
CUANDO rg -n "class CandidateB" src/genesis/strategy/candidate_b/candidate.py
ENTONCES retorna >=1 coincidencia, con @register_candidate("B") en la línea inmediatamente anterior
```

```
DADO   el archivo src/genesis/strategy/candidate_b/candidate.py
CUANDO rg -n "genesis.backtest" src/genesis/strategy/candidate_b/candidate.py
ENTONCES retorna 0 coincidencias (R50: satisface RiskLevelsProvider por duck typing, sin importarlo)
```

```
DADO   una instancia CandidateB(figure=..., reference_balance=100000.0, n_minutes=15, risk_pct=0.00375)
CUANDO se evalúa isinstance(instancia, genesis.backtest.simulator.RiskLevelsProvider)
ENTONCES retorna True (R52, primer test del Change)
```

```
DADO   Simulator(candidate=CandidateB(...), symbol="US500", ...)
CUANDO se construye el Simulator
ENTONCES no se lanza BacktestConfigError (R85b)
```

```
DADO   una sesión sintética con n_minutes=15, 15 barras in_session formando el rango
       (_range_high=4505.0, _range_low=4498.0) y reference_direction=LONG
CUANDO la barra 16.ª (_minute_index=15) cierra en bar.close=4506.2
ENTONCES on_bar retorna exactamente un EntryIntent, y risk_levels(intent) retorna
         stop_loss=4498.0, take_profit=4530.8 (regla primaria, tp_rr_multiple=3.0, R58/R66/R68)
```

```
DADO   la misma sesión sintética, pero la barra 16.ª rompe intrabar (high > 4505.0)
       y cierra dentro del rango (close=4503.0)
CUANDO se invoca on_bar sobre esa barra
ENTONCES retorna [] (ruptura confirmada por cierre, no intrabar, spec §2.3 literal)
```

```
DADO   la primera AnnotatedBar in_session de una sesión con open=4500.00, close=4500.003,
       figure.digits=2 (epsilon=0.005)
CUANDO se invoca on_bar sobre esa barra
ENTONCES _reference_direction permanece None (doji dentro de tolerancia, R56) y ninguna
         señal se emite el resto de esa sesión
```

```
DADO   14 barras in_session consecutivas con TR=10.0 cada una, seguidas de una 15.ª con TR=24.0
       (atr_period=14)
CUANDO se recalcula el estado ATR incremental de CandidateB tras cada barra
ENTONCES _atr_value tras la 14.ª es 10.0 (media simple) y tras la 15.ª es 11.0
         (suavizado de Wilder: ((10.0*13)+24.0)/14, R63)
```

```
DADO   Direction.LONG, entry_reference=4506.2, stop_loss=4498.0, atr_stop_frac=None,
       risk_pct=0.00375, reference_balance=100000.0, figure.tick_value=1.0, figure.tick_size=1.0
CUANDO se invoca risk_levels(intent) tras el on_bar que emitió intent
ENTONCES intent.sizing_hint == (0.00375 * 100000.0) / (8.2 * 1.0) (R69, sin redondear a volume_step, R70)
```

```
DADO   una CandidateB con atr_stop_frac=1.0 y _atr_value=11.0 ya calentado
CUANDO ocurre una ruptura LONG con _range_low=4498.0
ENTONCES stop_loss = 4498.0 - 1.0 * 11.0 = 4487.0 (regla alternativa, R66)
```

```
DADO   una CandidateB con atr_stop_frac=1.0 pero _atr_bars_seen < atr_period (ATR no calentado)
CUANDO ocurre una ruptura
ENTONCES stop_loss se calcula con la regla primaria (extremo opuesto del rango), no con ATR (R64)
```

```
DADO   una secuencia de AnnotatedBar y una CandidateB real, determinista
CUANDO se ejecuta on_bar(bar_t) y luego se mutan/agregan barras con timestamp_utc > bar_t.timestamp_utc,
       re-ejecutando on_bar(bar_t) desde el mismo estado previo al punto t
ENTONCES el resultado (list[EntryIntent]) de ambas ejecuciones es idéntico (>=1000 ejemplos hypothesis, R83)
```

```
DADO   una CandidateB tras congelar su rango en una sesión sintética
CUANDO se agregan barras posteriores a la ventana de formación con valores extremos de high/low
ENTONCES _range_high/_range_low permanecen sin cambios (cita literal spec §9, R83)
```

```
DADO   un EntryIntent ya emitido en un trading_day (self._signal_emitted_today == True)
CUANDO llega una nueva barra ese mismo trading_day con precio que también rompería el rango
ENTONCES on_bar retorna [] (máximo una señal por sesión/símbolo, R59)
```

```
DADO   risk_levels(intent) invocado sin ninguna señal pendiente asociada
CUANDO se ejecuta la llamada
ENTONCES se lanza CandidateBStateError con contexto (R71, R76)
```

```
DADO   el archivo src/genesis/strategy/inspector_config.json
CUANDO rg -n "\"B\"" src/genesis/strategy/inspector_config.json
ENTONCES retorna >=1 coincidencia bajo la clave "candidates" con los 5 campos n_minutes,
         atr_stop_frac, risk_pct, atr_period, tp_rr_multiple (R74)
```

```
DADO   el diff del commit que cierra este Change
CUANDO git diff --stat -- src/genesis/data src/genesis/backtest src/genesis/strategy/contract.py
       src/genesis/strategy/inspector.py src/genesis/strategy/clock.py
ENTONCES no retorna ninguna línea (R89)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/strategy/candidate_b/ -v
ENTONCES pasa en verde (exit code 0, R86)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/strategy/ tests/backtest/ -v
ENTONCES pasa en verde (exit code 0, sin regresiones en las suites de C/G)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run mise run ci
ENTONCES lint + ty + test pasan en verde (exit code 0, R90)
```

---

## 7. Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| Rg-1 | El acumulador ATR (R61-R64) es estado nuevo sin precedente exacto en el repo (VWAPState es el precedente más cercano, pero no calcula true range). | Bajo-medio: superficie de bug nueva si el suavizado de Wilder se implementa mal. | R63 fija la fórmula exacta con ejemplo numérico verificable byte a byte; R82 exige tabla golden calculada a mano. |
| Rg-2 | El punto de referencia único en `candidates.B.*` (R74) podría no coincidir con el que Issue H eligiera como "punto medio" real del grid si H define el grid con otra convención (p. ej. escala log en `risk_pct`). | Bajo: solo afecta el default de smoke tests de este Change, no bloquea a H (R75 garantiza instanciación directa con cualquier punto). | Documentado explícitamente en R74 como un punto de referencia, no una imposición sobre el diseño de muestreo de H. |
| Rg-3 | `epsilon` de doji (R56, medio tick) es una elección de este documento, no un valor cerrado por el spec §2.3 (que no menciona doji en absoluto). | Bajo: si en producción se observa que medio tick es demasiado estricto/laxo, requiere un Change de ajuste de parámetro, no de arquitectura. | `epsilon` se deriva de `figure.digits` (dato ya disponible, no hardcodeado), documentado con justificación explícita en R56. |
| Rg-4 | El ATR nunca se resetea por día (R61); si el histórico de barras `in_session` de una instancia es muy corto (p. ej. un backtest de pocos días con `n_minutes` grande), el ATR puede tardar varios días en calentar. | Bajo: R64 ya cubre el fallback a la regla primaria mientras no está calentado — ninguna señal se bloquea por esto. | Documentado en R64; aceptado como comportamiento esperado de un estimador incremental "cold start". |
| Rg-5 | La ubicación de `test_integration_simulator.py` bajo `tests/strategy/candidate_b/` (R85) importa fakes/fixtures de `tests.backtest` cruzando el árbol de paquetes de test; si en el futuro `tests/` deja de tener `__init__.py` por subcarpeta, este import se rompe. | Bajo: hoy `tests/{backtest,strategy,data}/__init__.py` existen y son parte del patrón ya establecido del repo. | Riesgo aceptado explícitamente; si el patrón de test cambia, es una decisión de infraestructura de testing fuera de alcance de este Change. |

---

## 8. Preguntas abiertas (no bloquean este Change)

- Nombres exactos de los archivos de test dentro de `tests/strategy/candidate_b/` (más allá de
  `test_integration_simulator.py`, fijado por R85): `design.md` puede proponer
  `test_range.py`/`test_trigger.py`/`test_sizing.py`/`test_atr.py`/`test_forward_only_property.py`
  u otra organización equivalente, siempre que cubra R82-R84.
- Si Issue H, al instanciar el grid completo de 27 combinaciones, necesitará una función de
  conveniencia adicional (p. ej. `iter_grid_points()`) en `candidate_b/config.py` — este Change
  no la incluye (R75 solo garantiza instanciación directa); se decide en el `design.md`/`propose`
  de Issue H si resulta necesaria.
- Comportamiento exacto si `figure.digits` no está disponible o es `0` en un dataset real (caso
  degenerado no observado en los datos de Issue B hasta la fecha) — no bloqueante, `epsilon`
  degeneraría a `0.5` en ese caso, comportamiento aceptable pero no ejercitado por ningún golden
  test de este Change.

---

## 9. Referencias

- Issue: https://github.com/bbenja11/genesis/issues/8
- `idea.md` / `proposal.md` de este Change (fases explore/propose) — 9 preguntas abiertas, 6
  riesgos Rg-1..Rg-6, 10 decisiones y 6 riesgos delegados a specify, resueltos en este documento.
- Spec vigente: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` — §2.1 (`EntryIntent`),
  §2.3 (Candidato B, definición normativa completa, tabla de sesiones UTC), §2.x (universo
  cerrado), §3 (arquitectura 4 capas), §5.1 (`candidate_b/`), §6.2 (grid IS, N_trials_IS=27, 9
  configuraciones de señal sobre `atr_stop_frac`), §8 (manejo de errores), §9 (testing: propiedad
  forward-only, invariante del rango, golden de sesión sintética), §11 (Issue E, camino crítico
  A→B→C→{E,G}→H), §11.1 (las 3 PA normativas resueltas en R56/R58/R78-R79).
- Delta-spec promovido de Issue C (cerrado): `.pulse/specs/strategy/spec.md` — R1-R7 (contrato),
  R13-R21 (Inspector, namespace `candidates.<letra>.*`), R38-R42 (patrón de testing). Este
  documento continúa la numeración en R48 sin colisión.
- Delta-spec promovido de Issue G (cerrado): `.pulse/specs/backtest/spec.md` — R20-R24
  (`RiskLevelsProvider`, requisito duro `isinstance`), R23/R24 (cierre forzado proactivo +
  `SessionBoundaryError`).
- Código de la capa de estrategia consumido (Issue C, cerrado): `src/genesis/strategy/contract.py`
  (`StrategyCandidate`, `EntryIntent`, `Direction`, `CANDIDATE_REGISTRY`, `register_candidate`,
  `CONFIG_VERSION`), `src/genesis/strategy/inspector.py:29-143` (`RejectionReason`,
  `InspectorVerdict`, `InspectorFunnelConfig`, `inspect`, `load_inspector_funnel_config`),
  `src/genesis/strategy/errors.py:1-27` (`GenesisStrategyError`, `LookaheadError`,
  `DuplicateCandidateError`, `InspectorConfigError`).
- Código de la capa de backtest consumido (Issue G, cerrado): `src/genesis/backtest/simulator.py`
  (`RiskLevelsProvider:59-70`, `Simulator.__init__:213-280` — verificación `isinstance:229-235`,
  `_compute_rr:188-200`, `_floating_pnl:332-336`, `_resolve_entry_fill:169-185`,
  `_enforce_session_close_and_guard:408-432`, `_process_new_entries:463-491`,
  `_open_position:493-547` — caso "vela única" línea 543), `src/genesis/backtest/errors.py:1-31`
  (`GenesisBacktestError`, `SessionBoundaryError`, `BacktestConfigError`),
  `tests/backtest/fakes.py::FakeRiskCandidate` (patrón de asociación `on_bar`→`risk_levels`
  síncrona, replicado en R71).
- Código de la capa de datos consumido (Issue B, cerrado): `src/genesis/data/sessions.py`
  (`SessionSpec:15`, `SESSIONS:23-49`, `session_window:60-83`), `src/genesis/data/store.py`
  (`AnnotatedBar:28-38` — `in_session:103`, `trading_day`), `src/genesis/data/symbols.py`
  (`SymbolFigure:12-27` — `tick_value`, `digits`, `volume_step`).
- Design + ADRs de Change C (archivado):
  `.pulse/changes/archive/4-c-feat-strategy-contrato-plugin-inspector-compartido-componentes/design.md`.
- Design + ADRs de Change G (archivado):
  `.pulse/changes/archive/6-g-feat-backtest-simulador-equity-intrad-a-fills-por-ticks-cierre/design.md`
  — ADR-G3 (`RiskLevelsProvider` requisito duro), ADR-G4 (breaches continuables vs
  `SessionBoundaryError` fail-fast).
- Tests de referencia (patrón a replicar): `tests/strategy/{conftest.py, fakes.py,
  test_contract_lookahead_property.py}`, `tests/backtest/{fakes.py::FakeRiskCandidate,
  test_simulator_session_close.py, test_simulator_fills.py, test_simulator_contract.py}`.
- Reglas de proceso: `.agents/rules/architecture-conventions.md`,
  `.agents/rules/eval-tdd-conventions.md`, `.agents/rules/tooling-conventions.md`.
- `AGENTS.md` (raíz) — invariantes de código citados textualmente del spec.
- `CLAUDE.md` (raíz) — arquitectura de 4 capas, comandos, flujo SDD.

<!-- change:16-d-feat-strategy-smc-engine-diagn-stico-de-se-al-desnuda-kill-swi -->
<!-- change:16-d-feat-strategy-smc-engine-diagn-stico-de-se-al-desnuda-kill-swi -->
# Specification: `smc_engine` + diagnóstico de señal desnuda (kill-switch del Candidato A) — Issue #16 / D

SSoT: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` (en adelante «el spec») — §2.2, §2.2.1,
§2.x (universos, en particular "Universo del Candidato A"), §2.5, §3, §4, §5.1, §6/§6.1, §8, §9,
§11/§11.1 (PA-1..PA-5), §11.2. Este documento formaliza `idea.md` y `proposal.md` de este Change en
requisitos verificables. Los gates G/C/P/T del spec **nunca se relajan**; ningún requisito de este
documento puede contradecirlos.

Convención de rutas: el spec usa pseudocódigo `python/...` (§3, §5.1, §6); el repo real usa
`src/genesis/...` (`[project] name = "genesis"` en `pyproject.toml`). Todas las rutas de este
documento son las reales del repo.

Numeración: continúa la numeración acumulada de `.pulse/specs/strategy/spec.md` (Issues C/E, hasta
R90). Este Change usa **R91 en adelante**.

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Construir `smc_engine` (estructura de mercado: fractales con doble timestamp, agregación M1→TF,
EQH/EQL, máquina de estados de sweep de 5 estados, "camino libre") sobre los componentes comunes ya
cerrados en Issue C (`common/vwap_engine.py`, `common/zones.py`), y ejecutar con él el **diagnóstico
de señal desnuda** (§2.2.1): un kill-switch mecánico que decide, sin ningún filtro del embudo y antes
de construir `risk`/gatillo del Candidato A (Issue F), si el edge condicional bruto de un sweep
confirmado en zona CT supera el coste round-trip real. Este Change resuelve normativamente las
preguntas que el issue #16 delega explícitamente a specify (semántica de doble timestamp/camino
libre, umbral `ct_zscore_min` y TF de diagnóstico, definición de "distancia de stop típica", forma
del bootstrap, formato del informe y alcance de la ejecución real, patrón de metadata, layout de
`candidate_a/`, gap de universo de sesiones) y dos preguntas adicionales de arquitectura descubiertas
en esta fase (ubicación de capa del módulo de diagnóstico con coste de ticks; ver §3.9).

### 1.2. Alcance IN

- `src/genesis/data/sessions.py`: extensión aditiva (nunca ruptura) para soportar la ventana de
  solapamiento Londres–NY de XAUUSD/EURUSD/GBPUSD/USDJPY (§2.x).
- `src/genesis/strategy/candidate_a/smc/`: motor de estructura de mercado completo — agregación
  M1→TF, fractales con doble timestamp, EQH/EQL con mitigación, máquina de estados de sweep de 5
  estados, "camino libre", ATR-Wilder incremental multi-TF.
- `src/genesis/strategy/candidate_a/config.py`: `CandidateAConfig` (`smc: SmcEngineConfig` +
  `diagnostics: DiagnosticsConfig`) + `load_candidate_a_config`, namespace `candidates.A.*` de
  `inspector_config.json`.
- `src/genesis/strategy/candidate_a/diagnostics.py`: núcleo estadístico puro del diagnóstico §2.2.1
  (evento CT, retornos condicionales por horizonte, tasa de toque de VWAP antes de la distancia de
  stop típica, bootstrap por bloques `numpy` puro) — **sin** dependencia de ticks/costos reales.
- `src/genesis/strategy/candidate_a/errors.py`: jerarquía propia (`CandidateAConfigError`,
  `SmcEngineStateError`).
- `src/genesis/validation/signal_diagnostic.py` (nuevo): orquestación de capa 4 que combina el
  núcleo estadístico de `candidate_a/diagnostics.py` con el coste round-trip real (spread de ticks
  vía `genesis.backtest.ticks`), aplica el criterio mecánico de archivo/continuación, construye
  `SignalDiagnosticReport` (JSON + Markdown, reproducible) y expone el CLI `diagnose`.
- `src/genesis/validation/errors.py`: `SignalDiagnosticConfigError`.
- Placeholders explícitamente no-autoritativos de `SymbolFigure` para XAUUSD/EURUSD/GBPUSD/USDJPY,
  con guard fail-fast que exige una bandera explícita para usarlos.
- Nuevo script `genesis-validate` (`[project.scripts]`) con subcomando `diagnose --candidate
  --firm`, patrón `argparse`/`add_subparsers` de `mt5_export.py`.
- Testing según §9: unit+property (`hypothesis`), golden, integración (pipeline en CI sobre
  dataset de muestra), estadístico (bootstrap contra edge sintético conocido).

### 1.3. Alcance OUT (YAGNI explícito)

- **`risk` del Candidato A** (SL banda-vs-swing + buffer ATR+spread, TP `FIXED_RR`/`STRUCT_TRAIL`/
  `STATIC`/`DYNAMIC`) y el **gatillo CT** de entrada/salida: Issue F, condicional al veredicto de
  este diagnóstico (§11 tabla de issues). Este Change **no** registra `"A"` en
  `CANDIDATE_REGISTRY` (`contract.py:register_candidate`): `smc_engine`/`diagnostics.py` son
  módulos de análisis, no un `StrategyCandidate` ejecutable.
- Los campos `sl_buffer_atr`, `tp_ct_mode`, `trail_timeframe`, `risk_percent`, `min_rr` (los 5
  restantes de los 14 recortados por ADR-C5 de Issue C que aún faltan) permanecen **fuera** de
  `candidates.A.*` en este Change; siguen reservados a Issue F.
- Confirmación definitiva de `SymbolFigure` (tick_value/volume_step/etc.) de oro y majors contra la
  cuenta demo real de The5ers: sigue pendiente de una extensión futura de Issue B o de Issue F. Este
  Change solo entrega placeholders explícitos, guardados detrás de una bandera (R107).
- Extensión de `profiles/the5ers.json` (`symbols.*`, tabla de alias MT5): fuera de este Change. La
  extensión de `sessions.py` (§3.1) es suficiente y necesaria para que `iter_bars` produzca barras
  anotadas de los 4 símbolos nuevos; `profile.symbols` no lo consulta `iter_bars`/`session_window`
  (`src/genesis/data/store.py:68-115` no referencia `profile.symbols` en ningún punto) — la tabla de
  alias solo es relevante para la resolución MT5 real de `mt5_export.py`, un paso operativo diferido.
- Adición de `scipy`/`statsmodels` a `pyproject.toml`: el bootstrap de este Change es `numpy` puro
  (§3.6); ningún consumidor real de `scipy` se introduce en este Change (§11.2 del spec los da por
  asumidos, pero ninguna necesidad concreta lo exige aquí).
- Ejecución del Candidato B (Issue E, cerrado): no depende de este diagnóstico.
- Un CLI unificado `genesis` con todos los verbos de §6 (`export`/`quality`/`diagnose`/`backtest`/
  `wfa`/`mc`/`prop-sim`/`full-validation`/`verdict`): este Change solo entrega el script
  `genesis-validate diagnose`; la consolidación en un único entrypoint queda para un Change futuro
  de la capa `validation` (no bloquea a este).
- Reafinar el solapamiento Londres-NY con intersección real de sesiones (ver §3.1, Riesgos): la
  ventana fija en UTC (12:00–17:00, "aprox.") es la decisión normativa de este Change.

---

## 2. Convenciones de esta especificación

- **DEBE / NO DEBE / PUEDE** (RFC 2119, informal): obligación, prohibición, opción.
- Cada requisito cita el `file:line` del hallazgo que lo origina cuando aplica.
- "Capa 2" = `genesis.strategy`; "capa 3" = `genesis.backtest`; "capa 4" = `genesis.validation`;
  "capa 1" = `genesis.data`. La dirección de dependencia es unidireccional: 4→3,2,1; 3→2,1; 2→1;
  1→∅ (spec §3 diagrama de 4 capas; invariante explícita en
  `src/genesis/strategy/candidate_b/candidate.py:3-8`, R50 heredado).

---

## 3. Decisiones normativas fijadas en este Change

Esta sección responde punto por punto a las preguntas que el issue #16 delega a specify. Los
requisitos ejecutables correspondientes están en §4.

### 3.1. Gap de universo — extensión de `sessions.py` (capa 1)

**Decisión**: se extiende `src/genesis/data/sessions.py` (opción (a) del proposal), no se define una
tabla de sesión local en `candidate_a/`. Confirmado en código: `session_window(symbol, date)`
(`sessions.py:60-83`) hoy asume un único par open/close por símbolo/día y lanza `KeyError` para
cualquier símbolo fuera de `SESSIONS` (`sessions.py:24-49`, 4 filas: US500/NAS100/US30/GER40).

La extensión es **aditiva**: se añade un segundo tipo de entrada al mapa `SESSIONS`,
`FixedUtcWindowSpec` (ventana dada directamente en UTC), distinto de `SessionSpec` (ventana en hora
local del mercado subyacente, resuelta vía `zoneinfo`). Motivo de la distinción: el spec (§2.x) da la
tabla de solapamiento Londres–NY directamente en UTC ("12:00–17:00 UTC aprox."), a diferencia de la
tabla de sesiones de contado de índices (§2.3), que se da en hora local del mercado subyacente. Usar
un tipo distinto evita forzar una intersección de dos `SessionSpec` (Londres + Nueva York) cuyas
horas de "sesión FX/metal" no están normadas en ningún lugar del spec ni del repo — inventar esa
descomposición sería especular sin base normativa, mientras que la ventana fija en UTC ya está dada.

**Trade-off aceptado y documentado (Riesgo, §8)**: `FixedUtcWindowSpec` no resuelve DST del "lado
Londres" ni del "lado Nueva York" por separado; es una ventana UTC fija todo el año, coherente con
el "aprox." del propio SSoT. Los 4 símbolos existentes (`SessionSpec`) no se tocan.

### 3.2. Placeholders de `SymbolFigure` — no autoritativos, con guard explícito

**Decisión**: no se extiende `profiles/the5ers.json` (que no tiene una noción de "ficha numérica de
símbolo": `FirmProfile.symbols` solo mapea alias, `src/genesis/data/profile.py:31-48`). Se definen
placeholders de `SymbolFigure` (`src/genesis/data/symbols.py:11-28`) para XAUUSD/EURUSD/GBPUSD/
USDJPY **dentro del namespace `candidates.A.diagnostics.*`** de `inspector_config.json` (capa 2,
ámbito exclusivo del diagnóstico), explícitamente marcados como no confirmados contra una cuenta
real. El CLI (§4.6) exige una bandera explícita (`--allow-placeholder-figures`) para usarlos; sin
ella, `diagnose` rechaza con `SignalDiagnosticConfigError` los símbolos sin ficha confirmada. Esto
resuelve el bloqueo operativo (idea.md pregunta 2) sin reabrir el esquema autoritativo de Issue B ni
fingir que el valor es real.

### 3.3. `smc_engine` — base normativa citada, clean-room

**Decisión**: se adopta `C:\Users\bbrav\ABON\vwap-smc-inspector\docs\specs\VWAP_SMC_Inspector_Spec_v2.md`
§4 como base normativa **citada** (no copiada, no importada como código — confirmado que no existe
implementación de `SMC_Engine.mqh` en ese repo, ni en MQL5 ni en Python, cero tests) para: fractales
con doble timestamp (§4.1), agregación M1→TF (§4.2), EQH/EQL con tolerancia ATR (§4.3), máquina de
estados de sweep de 5 estados (§4.4), "camino libre" (§4.5). Los defaults exactos de esa fuente
(`fractal_n=3`, `eq_tolerance_atr=0.15`, `sweep_tolerance_atr=0.05`, `sweep_window_k=5`,
`sweep_validity_m=30`, `free_path_radius_sigma=1.0`, `atr_period=14`) se adoptan como defaults de
`SmcEngineConfig` (§4.4 de este documento). Motivo: es la única fuente ya cuantificada; re-derivar
desde cero con solo el SSoT (§2.2/§2.2.1, más escueto) introduciría parámetros arbitrarios sin
grounding, y el propio SSoT delega esta semántica a Issue D.

### 3.4. `ct_zscore_min` y TF(s) del evento de diagnóstico

**Decisión**: `ct_zscore_min = 2.0` (perfil base de la fuente externa) como default de
`SmcEngineConfig`, ajustable vía config (perfil conservador `3.0` documentado como alternativa, no
default). El diagnóstico corre sobre **sweeps confirmados en M1** (el evento normativo de §2.2 es
"sweep confirmado... por símbolo y sesión", y el contrato `StrategyCandidate.on_bar` de Issue C solo
recibe `AnnotatedBar` M1 — `contract.py:58-59` — por lo que la futura señal ejecutable de Issue F
también operará en M1). M15/H1 se construyen y mantienen internamente por `smc_engine` **solo** para
resolver la jerarquía de "camino libre" (§4.5 de la fuente externa: H1 > M15 > M1); no se emite un
informe de diagnóstico separado por TF. Esto responde la pregunta 4 de idea.md: no son "tres
diagnósticos", es un diagnóstico M1 que consume estructura multi-TF internamente.

### 3.5. Definición operativa de "distancia de stop típica"

**Decisión**: se deriva de estructura SMC (opción preferida del proposal), **no** de `sl_buffer_atr`
(reservado a Issue F, §1.3). Se define un campo nuevo, propio de este Change y sin acoplamiento al
futuro namespace de riesgo: `diagnostics.stop_distance_atr_buffer_multiple` (default `1.0`). La
distancia de stop típica para un evento CT es:

```
distancia_stop = |precio_extremo_del_sweep − nivel_barrido| + stop_distance_atr_buffer_multiple × ATR(atr_period, M1)
```

donde `nivel_barrido` es el precio del nivel de liquidez (EQH/EQL o swing) que produjo el sweep
confirmado (§4.4 de la fuente externa) y `precio_extremo_del_sweep` es el `high`/`low` de la vela que
lo tocó. Es una heurística de **medición**, agnóstica al veredicto de riesgo real (que no existe
todavía): reutiliza la misma forma conceptual que usará el `risk` de Issue F (banda/estructura +
buffer ATR) sin definir su campo de configuración final, evitando coupling prematuro con F.

### 3.6. Bootstrap — `numpy` puro

**Decisión**: se reutiliza el patrón de bloques temporales de
`genesis.validation.montecarlo._block_resample`/`_block_bootstrap_paths`
(`src/genesis/validation/montecarlo.py:129-167`) y su convención de RNG explícito
(`numpy.random.default_rng(seed)`, nunca estado global — `montecarlo.py:8`). No se introduce
`scipy.stats`. Confirmado en `pyproject.toml:1-13`: `dependencies` no incluye `scipy`/`statsmodels`
hoy; este Change no es su primer consumidor real.

### 3.7. Formato del informe y alcance de la ejecución real

**Decisión (formato)**: dual **JSON + Markdown**, replicando el patrón ya establecido de
`genesis.validation.verdict` (`render_tearsheet` produce Markdown puro desde el mismo payload que
`verdict_result_to_manifest_json` serializa a JSON — `src/genesis/validation/verdict.py:826-1026`,
`write_verdict_artifacts` escribe ambos — `verdict.py:1039-1076`). El JSON es la fuente canónica
(reproducible, con metadata); el Markdown se renderiza del mismo payload, sin I/O propio.

**Decisión (alcance de ejecución)**: este Change **entrega y ejecuta** el pipeline completo
(`store → smc_engine → diagnostics → signal_diagnostic`) contra el dataset de muestra ya versionado
en el repo (mismo patrón que `tests/strategy/fixtures/sample_m1.csv`, usado por los golden tests de
`candidate_b`), produciendo al menos un `SignalDiagnosticReport` real y determinista en CI (criterio
de éxito verificable, §6). La ejecución **definitiva** sobre el histórico completo real de The5ers
(vía `mt5-export` contra la cuenta de datos, spec §4.1) — la que produce la decisión de negocio real
archivar/continuar que desbloquea Issue F — es una tarea operativa posterior que usa el mismo CLI
`genesis-validate diagnose`, fuera de la autoría de este Change SDD (no hay acceso a cuenta MT5 real
desde este entorno de agente). Se documenta como Pregunta abierta operativa (§8).

### 3.8. Patrón de metadata del informe

**Decisión**: `SignalDiagnosticReport` (capa 4, `signal_diagnostic.py`) **compone** (no hereda, no
reimplementa) `genesis.data.metadata.ArtifactMetadata` (`src/genesis/data/metadata.py:51-99`) como
campo `data_metadata: ArtifactMetadata`, reutilizando `sha256_of`/`current_git_commit` sin duplicar
lógica de hash — la dirección capa 4 → capa 1 ya está permitida. Se le añaden campos propios de
capa 2/4 que `ArtifactMetadata` no modela: `candidate_id`, `symbol`, `session_label`,
`horizons_minutes`, `bootstrap_seed`, `bootstrap_resamples`, y el veredicto (`verdict`,
`ArchiveOrContinue`). Esto evita el patrón "ligero" puro de H/I/J (que no llevan `ArtifactMetadata`)
porque este informe sí necesita la reproducibilidad institucional completa de capa 1 (dataset_hash,
firm_profile_hash) al ser un punto de decisión de negocio real (§2.2.1), no solo un resultado
intermedio de validación.

### 3.9. Ubicación de capa del módulo de diagnóstico (hallazgo de esta fase, no anticipado por el issue)

**Hallazgo**: §5.1 del spec dice literalmente "`candidate_a/` | `smc_engine` + gatillo CT + riesgo
propio (§2.2). **Incluye el módulo del diagnóstico §2.2.1**" — es decir, el spec ubica todo el
diagnóstico dentro de la capa 2. Pero §2.2.1 exige el coste round-trip "con spread de ticks reales en
el momento del sweep", y `ticks.py`/`has_sufficient_tick_coverage`/`ticks_in_bar_window` viven en
`genesis.backtest` (capa 3). `candidate_b/candidate.py:3-8` fija como invariante explícita que
`genesis.strategy.candidate_*` **nunca** importa `genesis.backtest` (dirección de dependencia 2→1,
nunca 2→3). Además, §6 lista `diagnose` junto a `wfa`/`mc`/`prop-sim`/`verdict` como verbos del CLI de
**capa 4**, y el diagrama de flujo §6.1 sitúa "diagnóstico señal desnuda §2.2.1" en el mismo nivel que
"WFA por candidato", ambos consumiendo el Parquet versionado de calidad — es decir, es un paso de
**validación**, no de estrategia pura.

**Decisión (resuelve la tensión sin contradecir el spec)**: se divide el diagnóstico en dos módulos,
preservando la dirección de dependencia:

- `candidate_a/diagnostics.py` (capa 2): el **núcleo estadístico puro** de §2.2.1 — detección del
  evento CT, agregación de retornos condicionales por horizonte, tasa de toque de VWAP antes de la
  distancia de stop típica, bootstrap. Depende solo de capa 1 (`AnnotatedBar`) y capa 2
  (`smc_engine`, `common.zones`) + `numpy`. Sigue viviendo, literalmente, "en `candidate_a/`" —
  honra §5.1.
- `genesis/validation/signal_diagnostic.py` (capa 4, nuevo): la **orquestación** que añade el coste
  real de ticks (`genesis.backtest.ticks`), aplica el criterio mecánico de archivo (§2.2.1), arma
  `SignalDiagnosticReport` y expone el CLI. Consume `candidate_a.diagnostics` (2), `genesis.backtest.
  ticks` (3) y `genesis.data.*` (1) — dirección 4→3,2,1, sin violar ninguna capa.

Esta división es análoga a cómo `genesis.validation.verdict` combina insumos de múltiples capas
inferiores sin que ninguna de ellas conozca a `validation`. Se documenta como decisión elevada, no
como reinterpretación libre de §5.1: el "módulo del diagnóstico" sigue existiendo en `candidate_a/`
(la parte que no requiere costes), y la parte que sí los requiere se ubica donde la arquitectura de 4
capas ya la exige.

### 3.10. Layout de `candidate_a/`

**Decisión** (fijada aquí pese a que proposal.md la marcaba "no bloquea specify", por instrucción
explícita de esta fase): submódulo `candidate_a/smc/` para el motor de estructura (fractales +
agregación + EQH/EQL + sweep + camino libre — sustancialmente mayor que `candidate_b/candidate.py`,
único módulo de referencia de un candidato completo), y archivos planos para el resto:

```
src/genesis/strategy/candidate_a/
├── __init__.py
├── smc/
│   ├── __init__.py       # API pública re-exportada (SmcEngineState, update_smc_engine, tipos)
│   └── ...                # split interno (p. ej. timeframe.py, fractals.py, liquidity.py,
│                           #  sweep.py, atr.py) a discreción de design — detalle no bloqueante
├── config.py               # CandidateAConfig + load_candidate_a_config
├── diagnostics.py           # núcleo estadístico puro de §2.2.1 (§3.9)
└── errors.py                # CandidateAConfigError, SmcEngineStateError
```

El split de archivos **dentro** de `smc/` queda a discreción de design (detalle de implementación no
bloqueante); la decisión fijada aquí es únicamente submódulo-vs-plano al nivel de `candidate_a/`.

---

## 4. Requisitos por módulo

### 4.1. `sessions.py` — extensión de ventana fija en UTC (capa 1)

- **R91** (DEBE). `sessions.py` DEBE añadir un tipo `FixedUtcWindowSpec` (`dataclass(frozen=True,
  slots=True)`, campos `symbol: str`, `open_utc: time`, `close_utc: time`), sin modificar
  `SessionSpec` (`sessions.py:14-22`) ni las 4 entradas existentes de `SESSIONS`.
- **R92** (DEBE). `SESSIONS` DEBE ampliar su anotación de tipo a `Mapping[str, SessionSpec |
  FixedUtcWindowSpec]` y añadir 4 entradas nuevas: `XAUUSD`, `EURUSD`, `GBPUSD`, `USDJPY`, cada una
  `FixedUtcWindowSpec(symbol=..., open_utc=time(12, 0), close_utc=time(17, 0))` (§2.x del spec:
  "Solapamiento Londres–NY (12:00–17:00 UTC aprox.)").
- **R93** (DEBE). `session_window(symbol, session_date)` DEBE despachar por `isinstance(spec,
  FixedUtcWindowSpec)`: si es `FixedUtcWindowSpec`, construir `open_utc`/`close_utc` combinando
  `session_date` con las horas directamente en `UTC` (sin `zoneinfo` de mercado subyacente); si es
  `SessionSpec`, preservar el comportamiento exacto actual (`sessions.py:71-83`, sin cambios).
- **R94** (NO DEBE). `session_window` NO DEBE lanzar `KeyError` para ninguno de los 8 símbolos del
  universo del Candidato A (§2.x) tras esta extensión; el mensaje de `KeyError` para símbolos no
  soportados DEBE seguir listando las claves válidas (ahora 8), sin cambiar su formato.

### 4.2. Placeholders de `SymbolFigure` (capa 2, ámbito diagnóstico)

- **R95** (DEBE). `inspector_config.json` DEBE añadir, bajo `candidates.A.diagnostics.
  symbol_figures_placeholder`, una entrada `SymbolFigure`-compatible (mismos 9 campos de
  `symbols.py:11-28`) por cada uno de XAUUSD/EURUSD/GBPUSD/USDJPY, con valores plausibles de un
  broker MT5 estándar (documentados en el propio JSON o en el docstring del loader como no
  confirmados).
- **R96** (DEBE). `candidate_a/config.py` DEBE exponer una función de carga de estos placeholders
  (p. ej. `load_placeholder_symbol_figures`) que retorne `Mapping[str, SymbolFigure]`, separada de
  `load_candidate_a_config` (separación de responsabilidad: parámetros de señal vs. fichas de
  contrato).
- **R107** (DEBE). El CLI `diagnose` (§4.6) DEBE rechazar, con `SignalDiagnosticConfigError` (mensaje
  con el símbolo afectado), cualquier ejecución sobre XAUUSD/EURUSD/GBPUSD/USDJPY que no incluya
  explícitamente la bandera `--allow-placeholder-figures`; con la bandera, DEBE registrar en
  `SignalDiagnosticReport` que la ficha usada es un placeholder no confirmado.

### 4.3. `smc_engine` — motor de estructura de mercado (`candidate_a/smc/`, capa 2)

- **R97** (DEBE). `smc/` DEBE definir `Timeframe` (`StrEnum`: `M1`, `M15`, `H1`) y una función/estado
  de agregación M1→TF que solo emite una vela agregada de un TF cuando su última M1 componente
  cierra, alineada al ancla estándar (minuto 0/15/30/45 para M15; minuto 0 para H1), sin pedir jamás
  series nativas M15/H1 (base normativa: fuente externa §4.2, citada en §3.3 de este documento).
- **R98** (DEBE). `smc/` DEBE definir un tipo `Swing` (`frozen`, `slots`) con campos `timeframe:
  Timeframe`, `direction` (`StrEnum` `HIGH`/`LOW`), `price: float`, `pivot_time: datetime`,
  `confirmed_time: datetime`.
- **R99** (DEBE). Un `Swing` HIGH en un TF se confirma cuando la vela pivote tiene `high` estrictamente
  mayor que las `fractal_n` velas anteriores y las `fractal_n` posteriores del mismo TF (simétrico
  para `Swing` LOW con `low` estrictamente menor); `confirmed_time` es el cierre de la N-ésima vela
  posterior del mismo TF.
- **R100** (NO DEBE). Ningún `Swing` DEBE entrar al estado público del motor (visible a
  `diagnostics.py` o a cualquier consumidor) antes de su propia `confirmed_time`: la invariante es
  **estructural** (el motor solo agrega el swing a su mapa de niveles en la vela de confirmación),
  no un chequeo posterior sobre timestamps ya expuestos.
- **R101** (DEBE). `SmcEngineState` DEBE componer una instancia interna de `BarClock`
  (`clock.py:14-67`), avanzada en cada llamada a la función de actualización con la barra M1
  recibida; cualquier consulta interna de vigencia de un nivel/swing DEBE pasar por
  `BarClock.require`, reutilizando `LookaheadError` (`errors.py:12-17`) sin duplicar su lógica.
- **R102** (DEBE). `smc/` DEBE definir `LiquidityLevel` (EQH/EQL): dos o más `Swing` del mismo TF
  forman un nivel si la diferencia entre sus precios extremos es ≤ `eq_tolerance_atr × ATR(atr_period)`
  del TF correspondiente (ATR incremental, R106); el precio del nivel es el máximo (EQH) o mínimo
  (EQL) del grupo. Un nivel se marca `mitigated=True` cuando una vela posterior del mismo TF cierra
  más allá del nivel; los niveles mitigados salen del mapa de consulta activo.
- **R103** (DEBE). `smc/` DEBE definir `SweepState` (`StrEnum`: `ARMADO`, `TOCADO`, `BARRIDO`,
  `EXPIRADO`, `MITIGADO`) y una función de transición pura, simétrica para liquidez superior/
  inferior:
  - `ARMADO`: el nivel existe y no está mitigado.
  - `TOCADO`: una vela M1 hace `high > nivel + sweep_tolerance_atr × ATR(14, M1)` (o `low <` para
    inferior).
  - `BARRIDO`: dentro de `sweep_window_k` velas M1 desde el toque (incluida la del toque), una vela
    M1 CIERRA de vuelta dentro del nivel.
  - `EXPIRADO`: el estado `BARRIDO` habilita entradas durante `sweep_validity_m` velas M1; agotado
    ese plazo sin nueva confirmación, el nivel vuelve a `ARMADO`.
  - `MITIGADO`: si en cualquier momento una vela CIERRA más allá del nivel sin volver dentro de la
    ventana `sweep_window_k`, el nivel se marca mitigado y sale del mapa.
- **R104** (DEBE). `smc/` DEBE definir la función de "camino libre": para un sweep candidato en M1,
  buscar liquidez macro no mitigada (EQH/EQL o `Swing` de H1/M15) dentro de un radio
  `free_path_radius_sigma × sigma_t` (sigma del VWAP vigente, provisto por el caller desde
  `common.vwap_engine`) desde el precio extremo del sweep; si existe, el sweep válido DEBE ser el del
  nivel macro (jerarquía H1 > M15 > M1); si no existe, se acepta el sweep M1 directamente.
- **R105** (NO DEBE). `smc/` NO DEBE importar `numpy`, `pandas` ni ningún paquete de `genesis.backtest`
  o `genesis.validation` (dominio puro, mismo criterio que `common/vwap_engine.py:1-4`; `rg -n
  "^import numpy|^import pandas|genesis\.backtest|genesis\.validation" src/genesis/strategy/
  candidate_a/smc/` DEBE retornar 0 coincidencias).
- **R106** (DEBE). `smc/` DEBE mantener un ATR-Wilder incremental por `Timeframe` (M1/M15/H1),
  generalizando el patrón `_update_atr` de `candidate_b/candidate.py:136-162` (continuo cross-día,
  nunca reseteado), consumido por R102/R103.

### 4.4. `candidates.A.*` — configuración de estructura y diagnóstico (capa 2)

- **R108** (DEBE). `inspector_config.json` DEBE poblar `candidates.A.smc` con exactamente los 8
  campos de estructura (`fractal_n`, `eq_tolerance_atr`, `sweep_tolerance_atr`, `sweep_window_k`,
  `sweep_validity_m`, `free_path_radius_sigma`, `ct_zscore_min`, `atr_period`) con los defaults de
  §3.3, y `candidates.A.diagnostics` con `horizons_minutes` (`[5, 15, 30, 60]`),
  `bootstrap_resamples`, `bootstrap_block_size` (nullable, mismo criterio que `_default_block_size`
  de `montecarlo.py:111-114`), `bootstrap_seed`, `stop_distance_atr_buffer_multiple` (default `1.0`,
  §3.5) y `symbol_figures_placeholder` (R95).
- **R109** (NO DEBE). `candidates.A.*` NO DEBE incluir en este Change ninguno de los 5 campos
  reservados a Issue F (`sl_buffer_atr`, `tp_ct_mode`, `trail_timeframe`, `risk_percent`, `min_rr`);
  `rg -n "sl_buffer_atr|tp_ct_mode|trail_timeframe|risk_percent" src/genesis/strategy/
  inspector_config.json` DEBE retornar 0 coincidencias.
- **R110** (DEBE). `candidate_a/config.py` DEBE definir `SmcEngineConfig` y `DiagnosticsConfig`
  (`frozen`, `slots`) más una función compuesta `load_candidate_a_config` que replica el patrón
  fail-fast de `load_candidate_b_config` (`candidate_b/config.py:36-66`): recurso empaquetado
  `genesis.strategy/inspector_config.json` por defecto, `path` explícito opcional, lanza
  `CandidateAConfigError` con el campo/fuente faltante ante cualquier esquema inválido o incompleto.

### 4.5. `candidate_a/diagnostics.py` — núcleo estadístico puro (capa 2, §3.9)

- **R111** (NO DEBE). `diagnostics.py` NO DEBE importar `genesis.backtest` ni `genesis.validation`
  (mismo criterio que R50 de `candidate_b/candidate.py:3-8`; `rg -n "genesis\.backtest|genesis\.
  validation" src/genesis/strategy/candidate_a/diagnostics.py` DEBE retornar 0 coincidencias).
- **R112** (DEBE). `diagnostics.py` DEBE definir el evento CT: para cada barra M1 con
  `zones.classify_zone(zscore, ct_zscore_min=config.smc.ct_zscore_min) == Zone.CT` (reutilizando
  `common/zones.py:21-53` sin reimplementar el umbral, per idea.md) y un `SmcEngineResult` con sweep
  vigente (`BARRIDO`/`EXPIRADO`, R103) sobre el nivel resuelto por "camino libre" (R104), producir un
  `ConditionalReturnEvent` (símbolo, sesión, timestamp del evento, dirección esperada de reversión).
- **R113** (DEBE). Para cada `ConditionalReturnEvent`, `diagnostics.py` DEBE calcular el retorno
  forward a 5/15/30/60 minutos (o el subconjunto de `horizons_minutes` disponible antes de que la
  serie de barras se agote) frente a la distribución incondicional del mismo símbolo/sesión (misma
  ventana temporal, sin filtro CT), y la tasa de toque del VWAP (`vwap_engine.VWAPResult.vwap`)
  **antes** de recorrer la distancia de stop típica (§3.5).
- **R114** (DEBE). `diagnostics.py` DEBE producir intervalos por bootstrap de bloques temporales,
  reimplementado localmente con el mismo patrón de `montecarlo._block_resample`
  (`montecarlo.py:129-148`) — `numpy.random.default_rng(seed)` explícito, nunca estado global — en
  vez de importar `genesis.validation` (que violaría R111); ADR-H5 (Change I) ya documenta que
  reimplementar localmente entre Changes distintos es preferible a acoplar.
- **R115** (DEBE). `diagnostics.py` DEBE retornar una estructura agnóstica al coste (`RawEdgeSummary`
  o similar): retornos condicionales por horizonte (media, intervalo bootstrap), tasa de toque de
  VWAP, distancia de stop típica calculada, y el conteo de eventos CT usados — sin aplicar todavía el
  criterio de archivo (eso vive en capa 4, R118).

### 4.6. `genesis/validation/signal_diagnostic.py` — orquestación, coste, veredicto, CLI (capa 4, §3.9)

- **R116** (DEBE). `signal_diagnostic.py` DEBE consumir `genesis.backtest.ticks.iter_ticks`/
  `ticks_in_bar_window`/`has_sufficient_tick_coverage` (`ticks.py:58-132`) para estimar el spread
  round-trip real en el instante del sweep (`(T-60s, T]`, mismo criterio de borde que el motor de
  fills — `ticks.py:93-100`).
- **R117** (DEBE). Si no hay cobertura suficiente de ticks para un evento CT (`has_sufficient_
  tick_coverage` retorna `False`), `signal_diagnostic.py` DEBE excluir ese evento del cómputo de
  coste y reportarlo explícitamente en `SignalDiagnosticReport` (conteo de eventos excluidos por
  falta de ticks) — nunca degradarlo silenciosamente a un spread promedio (§2.2.1: "no promedio").
- **R118** (DEBE). El criterio de archivo mecánico DEBE comparar el edge bruto condicional (límite
  inferior del intervalo bootstrap de `RawEdgeSummary`, R115) contra el coste round-trip estimado
  (R116): si el edge bruto es inferior al coste, el veredicto es `ARCHIVE`; si lo supera, `CONTINUE`.
  Sin discrecionalidad humana en la decisión (criterio de éxito 4 del proposal).
- **R119** (DEBE). `SignalDiagnosticReport` (`frozen`, `slots`) DEBE componer `data_metadata:
  ArtifactMetadata` (§3.8) y añadir `candidate_id`, `symbol`, `session_label`, `horizons_minutes`,
  `bootstrap_seed`, `bootstrap_resamples`, `verdict` (`ArchiveOrContinue`, `StrEnum`:
  `ARCHIVE`/`CONTINUE`), `excluded_events_no_tick_coverage` (R117), y
  `symbol_figure_is_placeholder: bool` (R107).
- **R120** (DEBE). `signal_diagnostic.py` DEBE exponer `render_signal_diagnostic_markdown(report) ->
  str` (Markdown puro, sin I/O, mismo patrón que `render_tearsheet` — `verdict.py:877-960`) y
  `signal_diagnostic_report_to_json(report) -> str` (mismo payload serializado, `json.dumps(...,
  sort_keys=True)`), y una única función de escritura (`write_signal_diagnostic_artifacts`) que
  persiste ambos en un directorio de salida (mismo patrón que `write_verdict_artifacts` —
  `verdict.py:1039-1076`).
- **R121** (DEBE). `signal_diagnostic.py` DEBE exponer un CLI `diagnose --candidate A --firm the5ers
  [--allow-placeholder-figures]`, registrado como `genesis-validate` en `[project.scripts]` de
  `pyproject.toml`, con `argparse` + `add_subparsers(dest="command", required=True)` (mismo patrón
  estructural que `mt5_export.py:640-684`).
- **R122** (DEBE). `genesis.validation.errors` DEBE añadir `SignalDiagnosticConfigError`
  (`GenesisValidationError`, mismo criterio de mensaje con contexto que las excepciones hermanas —
  `errors.py:1-93`).

### 4.7. Testing (§9 del spec)

- **R123** (DEBE). Unit + property (`hypothesis`) para: doble timestamp de fractales (ningún `Swing`
  es visible antes de `confirmed_time`, sobre secuencias generadas), la máquina de estados de sweep
  de 5 estados (transiciones válidas exhaustivas, ninguna transición fuera de las 5 definidas),
  EQH/EQL (agrupación por tolerancia ATR, mitigación). Propiedad central del spec §9: **ningún output
  de una actualización de `smc_engine` en `t` cambia si se mutan barras posteriores a `t`**
  (property test explícito, análogo a `tests/strategy/test_contract_lookahead_property.py`).
- **R124** (DEBE). Golden tests: dataset sintético fijo de sweep de libro (EQH conocido, toque, cierre
  de vuelta, expiración) reproduce exactamente el `SweepState`/`LiquidityLevel` esperado; golden test
  del `SignalDiagnosticReport` completo con semilla de bootstrap fija reproduce byte a byte el mismo
  JSON en dos ejecuciones.
- **R125** (DEBE). Estadístico: el criterio de archivo mecánico (R118) DEBE dispararse correctamente
  sobre datasets sintéticos con edge conocido positivo (veredicto `CONTINUE`) y edge conocido nulo/
  negativo (veredicto `ARCHIVE`), sin ajuste manual del umbral entre ambos casos.
- **R126** (DEBE). Integración: pipeline completo `store.iter_bars → smc_engine → diagnostics →
  signal_diagnostic` sobre el dataset de muestra del repo (mismo patrón que
  `tests/strategy/fixtures/sample_m1.csv`) en CI, en segundos, para al menos un símbolo del universo
  de índices (US500/NAS100/US30/GER40, con `SessionSpec` ya existente) y, con
  `--allow-placeholder-figures`, para al menos uno de XAUUSD/EURUSD/GBPUSD/USDJPY (verifica R91-R94 +
  R95-R107 end-to-end).

---

## 5. Invariantes transversales

- **Aislamiento entre candidatos** (spec §2.1/§2.5): `smc_engine`/`diagnostics.py` nunca comparten
  estado entre símbolos; una instancia de `SmcEngineState` está ligada a un único símbolo/TF-set de
  construcción (mismo patrón que `CandidateB`, `candidate_b/candidate.py:38-52`).
- **Forward-only / anti-lookahead** (spec §3, §8): ningún output de `smc_engine` en el instante `t`
  puede depender de barras con `timestamp_utc > t` (R100, R101, R123).
- **Determinismo byte a byte** (spec §3, §8): misma semilla + dataset + config + ficha de firma ⇒
  `SignalDiagnosticReport` idéntico (R124).
- **Fail-fast tipificado, nunca degradación silenciosa** (spec §8): configuración incompleta →
  `CandidateAConfigError`/`SignalDiagnosticConfigError`; cobertura de ticks insuficiente → exclusión
  explícita reportada (R117), nunca un promedio sustituto; símbolo sin ficha confirmada → rechazo
  explícito salvo bandera (R107).
- **Dirección de dependencia unidireccional** (spec §3): `candidate_a/smc/` y `candidate_a/
  diagnostics.py` (capa 2) nunca importan `genesis.backtest`/`genesis.validation` (R105, R111);
  `genesis/validation/signal_diagnostic.py` (capa 4) es el único punto que cruza a capa 3 para el
  coste real de ticks (§3.9).

---

## 6. Manejo de errores (resumen normativo, spec §8)

| Excepción | Módulo | Disparador |
|---|---|---|
| `LookaheadError` (reusada) | `smc/` | Consulta de vigencia de nivel/swing posterior al `current_time` del `BarClock` interno (R101) |
| `CandidateAConfigError` (nueva) | `candidate_a/errors.py` | `candidates.A.smc`/`candidates.A.diagnostics` faltante o inválido en `inspector_config.json` (R110) |
| `SmcEngineStateError` (nueva) | `candidate_a/errors.py` | Invariante interna imposible del motor (p. ej. ATR consultado antes de calentamiento, mismo criterio que `CandidateBStateError`) |
| `SignalDiagnosticConfigError` (nueva) | `genesis.validation.errors` | Símbolo sin ficha confirmada sin bandera (R107); config de horizontes/bootstrap inválida |
| `BacktestConfigError` (reusada, capa 3) | — | Se propaga sin envolver desde `ticks.py` (mismo criterio R5 de `validation/errors.py:11-13`) |

---

## 7. Criterios de aceptación (evals ejecutables)

1. **DADO** `sessions.SESSIONS` tras esta implementación, **CUANDO** se invoca
   `session_window("XAUUSD", session_date)` para cualquier `session_date`, **ENTONCES** retorna
   `(open_utc, close_utc)` con `open_utc.time() == time(12, 0)` y `close_utc.time() == time(17, 0)`,
   sin lanzar `KeyError` (verifica R91-R94).
   - Assertion ejecutable: `rg -n "XAUUSD|EURUSD|GBPUSD|USDJPY" src/genesis/data/sessions.py` DEBE
     retornar ≥ 4 coincidencias.
2. **DADO** una secuencia de barras M1 sintéticas con un swing high conocido en la posición `i`,
   **CUANDO** se alimentan al motor bar a bar hasta la posición `i + fractal_n`, **ENTONCES** el
   `Swing` correspondiente NO es visible en el estado público del motor hasta la barra
   `i + fractal_n` inclusive (verifica R98-R100).
   - Assertion ejecutable: property test `hypothesis` con `@given` sobre secuencias de barras;
     `assert swing not in engine.active_swings(timeframe)` para todo índice `< i + fractal_n`.
3. **DADO** un nivel EQH `ARMADO`, **CUANDO** una vela M1 hace `high > nivel + sweep_tolerance_atr *
   atr` y, dentro de `sweep_window_k` velas, una vela cierra de vuelta bajo el nivel, **ENTONCES** el
   estado transiciona `ARMADO → TOCADO → BARRIDO` y, tras `sweep_validity_m` velas sin nueva
   confirmación, retorna a `ARMADO` (verifica R103).
   - Assertion ejecutable: golden test con secuencia fija de barras produce exactamente la traza de
     estados `[ARMADO, TOCADO, BARRIDO, EXPIRADO, ARMADO]` esperada.
4. **DADO** un dataset sintético con edge condicional positivo conocido (retornos forward
   sistemáticamente favorables tras el evento CT) y coste round-trip sintético bajo, **CUANDO** se
   ejecuta `signal_diagnostic` completo, **ENTONCES** `SignalDiagnosticReport.verdict ==
   ArchiveOrContinue.CONTINUE`; con el mismo dataset y coste round-trip sintético alto (o edge nulo),
   **ENTONCES** `verdict == ArchiveOrContinue.ARCHIVE` (verifica R118, R125).
5. **DADO** el CLI `genesis-validate diagnose --candidate A --firm the5ers` ejecutado dos veces con
   la misma semilla sobre el mismo dataset de muestra, **ENTONCES** el JSON producido por
   `signal_diagnostic_report_to_json` es byte a byte idéntico en ambas ejecuciones (verifica R124).
   - Assertion ejecutable: `diff <(genesis-validate diagnose ...) <(genesis-validate diagnose ...)`
     (o equivalente `pytest` comparando dos runs) DEBE retornar sin diferencias.
6. **DADO** `--candidate A --firm the5ers` sin `--allow-placeholder-figures` sobre XAUUSD,
   **ENTONCES** el CLI termina con `SignalDiagnosticConfigError` (código de salida ≠ 0) sin producir
   ningún `SignalDiagnosticReport` (verifica R107).
7. **DADO** un día de `trading_day` sin chunk de ticks persistido para un evento CT detectado,
   **ENTONCES** ese evento aparece en `SignalDiagnosticReport.excluded_events_no_tick_coverage` y no
   contribuye al coste round-trip promedio reportado (verifica R117).
8. **DADO** el árbol `src/genesis/strategy/candidate_a/smc/` y `diagnostics.py`, **ENTONCES**
   `rg -n "genesis\.backtest|genesis\.validation" src/genesis/strategy/candidate_a/` retorna 0
   coincidencias (verifica R105, R111).
9. **DADO** el pipeline de integración de R126, **CUANDO** se ejecuta en CI, **ENTONCES** completa en
   segundos (no minutos) para al menos un índice y al menos un símbolo con placeholder de figura,
   sin degradación silenciosa (excepción tipificada o exclusión reportada ante historia/tick
   insuficiente).

---

## 8. Riesgos

- **Aproximación de la ventana Londres–NY sin DST** (§3.1): `FixedUtcWindowSpec` no distingue
  horario de verano/invierno de Londres o Nueva York por separado; el propio SSoT acepta esta
  imprecisión ("aprox."), pero si el diagnóstico revela sensibilidad material del edge a los bordes
  exactos de la ventana, una futura iteración debería derivar la intersección real de dos sesiones
  con `zoneinfo` (documentado como decisión revisable, no como deuda oculta).
- **Placeholders de `SymbolFigure` no confirmados** (§3.2): el coste round-trip para XAUUSD/EURUSD/
  GBPUSD/USDJPY calculado con placeholders puede diferir materialmente del real; el guard (R107)
  hace la limitación visible, pero cualquier decisión de negocio real sobre esos símbolos requiere
  confirmación contra la cuenta demo antes de asignar capital.
- **Ejecución diferida sobre histórico real** (§3.7): la decisión de negocio definitiva
  archivar/continuar para producción depende de una ejecución posterior fuera de este Change (sin
  acceso a MT5 real desde este entorno); Issue F no debería arrancar hasta que esa ejecución operativa
  se complete con datos reales, aunque el pipeline ya esté demostrado end-to-end sobre el dataset de
  muestra.
- **División de capas del diagnóstico (§3.9)**: el spec (§5.1) dice literalmente que `candidate_a/`
  "incluye" el diagnóstico; la división en dos módulos (2 y 4) es una interpretación razonada, no
  una cita literal — si un humano revisando design/PR prefiere una ubicación única (todo en capa 4,
  o relajar la invariante de aislamiento 2→3 solo para este caso), esta decisión debe revisarse
  explícitamente antes de `APPLY` (bloqueante de diseño, no de este documento).
- **Presupuesto de grid y trials**: `smc_engine`/`diagnostics.py` no generan trials WFA (Issue H);
  el diagnóstico de este Change no cuenta contra `N_trials_IS = 27` (§6.2), pero si design decide
  barrer `ct_zscore_min` (2.0 vs 3.0) como parte del diagnóstico, esa búsqueda debe declararse y
  contarse en la gobernanza de trials de Issue H/I para no contaminar el DSR del candidato.

---

## 9. Preguntas abiertas (no bloquean este Change)

- Confirmación definitiva de `SymbolFigure` de oro/majors contra la cuenta demo real de The5ers
  (extiende PA-1, Issue B/F).
- Ejecución operativa del diagnóstico sobre el histórico completo real (fuera de la autoría SDD de
  este Change, §3.7/§8).
- Si el edge observado en la ejecución real resulta sensible a los bordes exactos de la ventana de
  solapamiento Londres–NY, evaluar una intersección real de sesiones con DST (§8).
- Consolidación futura de un único entrypoint `genesis` con todos los verbos de §6 (`export`,
  `quality`, `diagnose`, `backtest`, `wfa`, `mc`, `prop-sim`, `full-validation`, `verdict`) — fuera
  de alcance de este Change.

---

## 10. Referencias

- Issue: https://github.com/bbenja11/genesis/issues/16
- `idea.md`, `proposal.md` de este Change:
  `.pulse/changes/16-d-feat-strategy-smc-engine-diagn-stico-de-se-al-desnuda-kill-swi/`
- Spec vigente: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` — §2.2, §2.2.1, §2.x, §2.5,
  §3, §4, §5.1, §6/§6.1, §8, §9, §11/§11.1, §11.2.
- Spec promovido de la capa strategy (R1-R90 de Issues C/E): `.pulse/specs/strategy/spec.md`.
- Fuente funcional externa (clean-room, citada, no portada):
  `C:\Users\bbrav\ABON\vwap-smc-inspector\docs\specs\VWAP_SMC_Inspector_Spec_v2.md` §2-§4,
  `C:\Users\bbrav\ABON\vwap-smc-inspector\python\inspector_config.json`.
- Código de capa 1 consumido/extendido: `src/genesis/data/sessions.py`, `store.py`, `symbols.py`,
  `metadata.py`, `profile.py`, `profiles/the5ers.json`.
- Código de capa 2 consumido: `src/genesis/strategy/contract.py`, `clock.py`, `errors.py`,
  `inspector.py`, `common/vwap_engine.py`, `common/zones.py`, `candidate_b/candidate.py`,
  `candidate_b/config.py`, `inspector_config.json`.
- Código de capa 3 consumido: `src/genesis/backtest/ticks.py`.
- Código de capa 4 consumido/extendido: `src/genesis/validation/montecarlo.py`, `prop_sim.py`,
  `verdict.py`, `errors.py`.
- Precedente de CLI: `src/genesis/data/mt5_export.py`, `pyproject.toml` (`[project.scripts]`).
- Tests de referencia: `tests/strategy/candidate_b/`, `tests/strategy/common/test_zones.py`,
  `tests/strategy/test_contract_lookahead_property.py`, `tests/strategy/fixtures/sample_m1.csv`.
- Reglas de proceso: `.agents/rules/architecture-conventions.md`,
  `.agents/rules/eval-tdd-conventions.md`, `.agents/rules/tooling-conventions.md`.

<!-- change:39-fix-strategy-los-protocolos-de-config-declaran-miembros-mutables -->
# Specification: fix(strategy) — protocolos de config con miembros de solo lectura y registro de candidatos genérico (Issue #39)

> **Fase Specify del ciclo SDD.** Formaliza `idea.md` + `proposal.md` en requisitos verificables.
> SSoT: `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` (§2.1/§11.1, PA-3). Este Change es
> **exclusivamente correctivo de anotaciones de tipo**: no altera ningún gate G/C/P/T, ninguna regla
> de negocio ni ningún artefacto de reproducibilidad.

Numeración: continúa la del dominio `strategy` en `.pulse/specs/strategy/spec.md` (máximo vigente
`R126`) → este Change define **R127-R135**.

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Que el contrato estático declarado por los protocolos de configuración de `candidate_a/smc/` y por el
registro de candidatos de `strategy/contract.py` describa lo que el código realmente hace (solo
lectura de config; registro de subtipos de `StrategyCandidate`), de modo que `ty` 0.0.64 no reporte
diagnóstico alguno y el PR #29 (bump `ty` 0.0.48 → 0.0.64) sea mergeable sin relajar nada.

### 1.2. Alcance IN

| Archivo | Cambio |
|---|---|
| `src/genesis/strategy/candidate_a/smc/engine.py` | 8 miembros de `SmcEngineConfigProtocol` → properties de solo lectura |
| `src/genesis/strategy/candidate_a/smc/sweep.py` | 3 miembros de `SweepConfigProtocol` → properties de solo lectura |
| `src/genesis/strategy/contract.py` | `register_candidate` → decorador genérico PEP 695 acotado a `StrategyCandidate` |
| `tests/strategy/candidate_b/test_trigger.py` | quitar 1 `# ty: ignore[invalid-type-form]` (línea 22) |
| `tests/strategy/candidate_b/test_direction_doji.py` | quitar 1 (línea 16) |
| `tests/strategy/candidate_b/test_golden_session.py` | quitar 2 (líneas 19 y 31) |
| `tests/strategy/candidate_b/test_sizing.py` | quitar 1 (línea 28) |
| `tests/strategy/candidate_b/test_integration_simulator.py` | quitar 1 (línea 54) |

### 1.3. Alcance OUT (YAGNI explícito)

1. `src/genesis/strategy/candidate_a/config.py`: **no se toca**. `SmcEngineConfig`,
   `DiagnosticsConfig` y `CandidateAConfig` siguen `@dataclass(frozen=True, slots=True)`.
2. Lógica de negocio: FSM de sweep, ATR incremental, fractales, liquidez, VWAP, diagnóstico de señal
   desnuda, simulador, validación: **cero cambios**.
3. `StrategyCandidate.candidate_id` (`contract.py:56`): sigue siendo variable mutable. El defecto
   latente queda documentado (§6, Rg-39-3), no corregido en este Change.
4. `RiskLevelsProvider` (`backtest/simulator.py:59-70`): no tiene el defecto (solo miembro método).
5. `uv.lock` / bump de `ty`: pertenece al PR #29. Este Change no modifica dependencias (R135).
6. Reducir `SmcEngineConfigProtocol` a los miembros efectivamente leídos vía el protocolo
   (`ct_zscore_min` se declara y se consume por otra vía, `config.smc.ct_zscore_min` en
   `diagnostics.py:134`): fuera de alcance; cambiar la superficie del protocolo no hace falta para
   cerrar #39.
7. Reescritura de fakes de test, migración a `pydantic`, o cualquier refactor de estilo.

---

## 2. Convenciones de esta especificación

- **DEBE** = requisito verificable por un eval de §5; **NO DEBE** = prohibición verificable.
- "Property de solo lectura" = miembro de `Protocol` declarado como
  `@property def <nombre>(self) -> <T>: ...` (sin setter).
- "Diagnóstico" = cualquier línea emitida por `ty check`, de severidad `error`, `warning` o `info`.
- Baseline de referencia: HEAD `1e426de` (`main`), árbol limpio, 19 errores con `ty` 0.0.64, 639 tests
  recolectados (638 pasan + 1 skip).

---

## 3. Requisitos

### 3.1. `smc/engine.py`

- **R127** (DEBE). `SmcEngineConfigProtocol` DEBE declarar sus **8** miembros como properties de solo
  lectura, conservando nombre y tipo exactos: `fractal_n: int`, `eq_tolerance_atr: float`,
  `sweep_tolerance_atr: float`, `sweep_window_k: int`, `sweep_validity_m: int`,
  `free_path_radius_sigma: float`, `ct_zscore_min: float`, `atr_period: int`. NO DEBE agregar,
  quitar ni renombrar miembros, ni cambiar sus tipos.
- **R128** (DEBE). El protocolo DEBE conservar el decorador `@runtime_checkable` y su docstring DEBE
  seguir explicando (a) por qué existe el protocolo en lugar de importar `candidate_a.config`, y
  (b) que es superconjunto estructural de `sweep.SweepConfigProtocol`; DEBE agregar la razón de las
  properties (los configs consumidos son `frozen`, de solo lectura).
- **R129** (DEBE). El subtipado estructural ancho → angosto DEBE preservarse: `update_smc_engine`
  (`engine.py:187`) sigue pasando un `SmcEngineConfigProtocol` donde `transition_sweep` espera
  `SweepConfigProtocol`, sin `cast` ni supresión.

### 3.2. `smc/sweep.py`

- **R130** (DEBE). `SweepConfigProtocol` DEBE declarar sus **3** miembros (`sweep_tolerance_atr:
  float`, `sweep_window_k: int`, `sweep_validity_m: int`) como properties de solo lectura,
  conservando `@runtime_checkable` y el sentido de su docstring.

### 3.3. `strategy/contract.py`

- **R131** (DEBE). `register_candidate` DEBE estar tipado de forma que (a) el valor asignado en
  `CANDIDATE_REGISTRY[normalized]` sea asignable a `type[StrategyCandidate]` sin supresión, y (b) el
  tipo de la clase decorada se **preserve** (el nombre decorado sigue siendo utilizable como forma de
  tipo y como constructor con sus propios parámetros). Forma normativa: función genérica PEP 695 con
  variable de tipo acotada a `StrategyCandidate`.
- **R132** (NO DEBE). NO DEBE cambiar el comportamiento en runtime de `register_candidate`:
  normalización `letter.upper()`, detección de colisión con `DuplicateCandidateError` (mensaje con
  letra + `__qualname__` de la clase ya registrada) y retorno de la clase decorada sin envolverla.

### 3.4. Supresiones y limpieza

- **R133** (DEBE). Las **6** supresiones `# ty: ignore[invalid-type-form]` sobre anotaciones
  `CandidateB` (`test_trigger.py:22`, `test_direction_doji.py:16`, `test_golden_session.py:19,31`,
  `test_sizing.py:28`, `test_integration_simulator.py:54`) DEBEN eliminarse, porque R131 las vuelve
  innecesarias y `ty` reporta `unused-ignore-comment` con exit code 1.
- **R134** (NO DEBE). NO DEBE introducirse ninguna supresión nueva (`# ty: ignore`, `# type: ignore`,
  `# noqa`) en `src/` ni en `tests/`. La supresión ajena `test_config.py:29`
  (`# ty: ignore[invalid-assignment]`, escritura deliberada sobre un config frozen) se conserva
  intacta.

### 3.5. Alcance cerrado

- **R135** (NO DEBE). NO DEBE modificarse `pyproject.toml`, `uv.lock`, `mise.toml`,
  `.github/workflows/`, `candidate_a/config.py`, ni ningún archivo fuera de la tabla §1.2.

---

## 4. Invariantes transversales

1. **Comportamiento idéntico.** El cambio es de anotaciones: ninguna ruta de ejecución cambia. Los
   protocolos no se verifican en runtime y las properties de un `Protocol` nunca se ejecutan (los
   objetos reales son los dataclasses).
2. **`isinstance` invariante.** Con `@runtime_checkable`, `isinstance` compara presencia de
   atributos; una property en el cuerpo del protocolo produce el mismo resultado que la variable
   anotada (verificado en Python 3.14.6). Los asserts `isinstance(...)` de
   `tests/strategy/test_contract.py:66`, `tests/strategy/test_fakes.py:16`,
   `tests/backtest/test_simulator_contract.py:44-45` siguen valiendo.
3. **Aislamiento de capas (spec §2.1/§2.5).** `smc/` sigue sin importar `candidate_a.config`,
   `numpy`, `pandas`, `genesis.backtest` ni `genesis.validation`
   (`test_engine.py::test_layering_smc_no_importa_numpy_pandas_backtest_ni_validation`).
4. **Reproducibilidad.** No cambia ningún `CONFIG_VERSION`, `dataset_hash`, `firm_profile_hash`,
   `risk_profile_hash` ni esquema de artefacto. Ningún golden fixture se regenera.
5. **Inmutabilidad de la config.** Los dataclasses de `config.py` siguen `frozen=True, slots=True`
   (la corrección va en el protocolo, no en el productor).

---

## 5. Criterios de aceptación (evals ejecutables)

Todos desde la raíz del repo, con el entorno de `mise run setup`.

| # | Comando | Resultado exigido |
|---|---|---|
| E1 | `uvx ty@0.0.64 check --python .venv` | `All checks passed!`, exit 0, **0 diagnósticos** (baseline: 19 errores) |
| E2 | `uv run ty check` (0.0.48, pin de la rama) | `All checks passed!`, exit 0 |
| E3 | `uv run pytest` | `639 passed, 1 skipped`, exit 0 |
| E4 | `uv run ruff check .` | `All checks passed!` |
| E5 | `uv run ruff format --check .` | `186 files already formatted` (0 reformateos) |
| E6 | `uv run vulture` | sin hallazgos |
| E7 | `uv run bandit -c pyproject.toml -r src/` + `uv run deptry src/` | sin hallazgos |
| E8 | `git diff --stat` | exactamente 3 archivos en `src/genesis/strategy/` + 5 en `tests/strategy/candidate_b/`; **ninguna** línea de `candidate_a/config.py`, `pyproject.toml` ni `uv.lock` |
| E9 | `rg -n "ty: ignore\[invalid-type-form\]" src tests` | 0 resultados |
| E10 | `rg -n '^    [a-z_]+: (int\|float)$' src/genesis/strategy/candidate_a/smc/engine.py src/genesis/strategy/candidate_a/smc/sweep.py` | 0 resultados (ningún miembro de protocolo quedó como variable anotada; los campos homónimos de `config.py` siguen intactos) |
| E11 | `git diff -- tests/` | solo eliminación de comentarios: ninguna línea de assert, expectativa, fixture o lógica de test modificada |
| E12 | CI del PR #29 tras el merge de #39 | verde (los 8 pasos de `.github/workflows/ci.yml`) |

Prueba de tipos explícita (opcional pero recomendada, E1 la cubre indirectamente): un archivo de
verificación temporal con `reveal_type(CandidateB)` DEBE reportar `<class 'CandidateB'>`, no
`type[StrategyCandidate]`.

---

## 6. Riesgos

| Id | Riesgo | Mitigación |
|---|---|---|
| Rg-39-1 | La conversión a properties oculta un consumidor que sí escribe en el config. | Verificado por búsqueda: los únicos accesos son lecturas (`engine.py:86,110,113,115`, `sweep.py:102,138,147,177`). E1+E3 lo confirman. |
| Rg-39-2 | PEP 695 en `contract.py` exige Python ≥ 3.12. | El proyecto exige ≥ 3.14 (`pyproject.toml:6`, `.python-version`); `target-version = "py314"` en ruff. Sin riesgo. |
| Rg-39-3 | `StrategyCandidate.candidate_id` queda con el mismo defecto latente (fuera de alcance). | Documentado aquí y en `design.md`; verificado que hoy no produce error (CandidateB y los fakes son clases normales) y que el arreglo futuro es seguro. Candidato a issue de seguimiento. |
| Rg-39-4 | R131 empieza a verificar el bound de las clases decoradas: un candidato/fake que no satisfaga `StrategyCandidate` produciría un error nuevo. | Verificado: `CandidateB` y los 3 fakes decorados en `tests/strategy/test_contract.py` satisfacen el puerto, incluso con `candidate_id = "Q"` sin anotar (`ty` ensancha a `str`). E1/E2 lo cubren. |
| Rg-39-5 | El CI de la rama corre `ty` 0.0.48 y no detectaría una regresión de 0.0.64. | E1 es obligatorio y su salida se adjunta al PR; el cierre real lo valida el CI de #29 (E12). |

---

## 7. Preguntas abiertas (no bloquean este Change)

1. ¿Se abre un issue de seguimiento para `StrategyCandidate.candidate_id` (Rg-39-3) y para achicar
   `SmcEngineConfigProtocol` a los miembros efectivamente leídos?
2. ¿Conviene fijar en `[tool.ty.rules]` una regla que convierta `unused-ignore-comment` en `error`,
   para que la deuda de supresiones no se acumule en silencio?

---

## 8. Referencias

- `idea.md` (problema + inventario medido), `proposal.md` (enfoque + 6 alternativas + evidencia).
- Código: `src/genesis/strategy/candidate_a/smc/engine.py:34-51,72-115,187`,
  `smc/sweep.py:48-61,72-102`, `candidate_a/config.py:23-49`, `candidate_a/diagnostics.py:113,134`,
  `strategy/contract.py:46-86`, `backtest/simulator.py:59-70,229`.
- Tests: `tests/strategy/candidate_a/smc/test_engine.py`, `test_sweep.py`, `test_sweep_property.py`,
  `test_smc_lookahead_property.py`, `tests/strategy/test_contract.py`,
  `tests/strategy/candidate_b/*.py`.
- Issue #39; PR #29 (CI run 30420132741, `Found 19 diagnostics`).
- `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` §2.1/§9/§11.1 y PA-3;
  `.agents/rules/architecture-conventions.md`, `.agents/rules/eval-tdd-conventions.md`.

<!-- change:98-redise-o-institucional-del-candidato-b-market-intraday-momentum -->
# Specification: Rediseño institucional del Candidato B (Market Intraday Momentum Gao et al. 2018 + Filtro RVOL)

SSoT: `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` — §2.1, §2.3, §3, §5.1, §8, §9.
Este documento formaliza `idea.md` y `proposal.md` en requisitos normativos verificables y **continúa** la numeración `R#` del delta-spec de `strategy` (`.pulse/specs/strategy/spec.md`, que llega hasta R135) empezando en **R136**.

---

## 1. Objetivo y Alcance

### 1.1 Objetivo
Sustituir la heurística de sesgo direccional de 1 minuto en `CandidateB` por el modelo microestructural de **Gao et al. (2018, *Market Intraday Momentum*)** con filtro de régimen por volumen relativo institucional ($\text{RVOL} \ge 1.50$), garantizando viabilidad frente a los costos de fricción del exchange.

### 1.2 Alcance IN
- `src/genesis/strategy/candidate_b/candidate.py`: Rediseño de `CandidateB` implementando `StrategyCandidate` y `RiskLevelsProvider`.
- `src/genesis/strategy/candidate_b/config.py`: Parámetros `opening_window_minutes`, `rvol_threshold` y `rvol_lookback_days`.
- `tests/strategy/candidate_b/`: Pruebas unitarias, property tests con `hypothesis` y tests de invarianza temporal (§9 del spec).

### 1.3 Alcance OUT
- Modificaciones al simulador de capa 3 (`simulator.py`) o a la lógica de trailing Chandelier (gobernadas por Change #97).
- Optimización automática de hiperparámetros (Decisión D1: ensayo único registrado).

---

## 2. Requisitos Normativos

### 2.1 Lógica de Señal y Ventana de Apertura

- **R136 (DEBE). Determinación de Dirección por Retorno Acumulado de Apertura ($R_{\text{open}}$):**
  `CandidateB` DEBE acumular las primeras $M$ barras M1 de la sesión ($t \in [0, M-1]$, default $M=30$).
  En el minuto $M$, la dirección se calcula como:
  $$R_{\text{open}} = \ln\left(\frac{C_{M-1}}{O_0}\right)$$
  - Si $R_{\text{open}} > 10^{-7}$: Dirección `OrderSide.BUY`.
  - Si $R_{\text{open}} < -10^{-7}$: Dirección `OrderSide.SELL`.
  - Si $|R_{\text{open}}| \le 10^{-7}$: Dirección indefinida; ninguna orden DEBE ser emitida en la sesión.

- **R137 (DEBE). Filtro de Volumen Relativo Institucional ($\text{RVOL}$):**
  `CandidateB` DEBE mantener un buffer rodante forward-only con los volúmenes totales de apertura de los últimos $K$ días operativos cerrados (default $K=20$).
  En el minuto $M$, DEBE calcular:
  $$\text{RVOL} = \frac{V_{\text{open}, d}}{\text{Mediana}(V_{\text{open}, d-K \dots d-1})}$$
  - Si $\text{RVOL} \ge 1.50$: La sesión queda habilitada para operar.
  - Si $\text{RVOL} < 1.50$: La sesión se clasifica como *baja liquidez* y `on_bar` DEBE retornar `None` para todas las barras restantes de la jornada.

- **R138 (DEBE). Inicialización y Manejo de Warmup:**
  Durante los primeros $K$ días operativos del activo ($d < K$), `CandidateB` DEBE acumular los volúmenes de apertura sin emitir señales (`on_bar` retorna `None`), asegurando que la mediana se calcule sobre exactamente $K$ observaciones previas.

- **R139 (DEBE). Gatillo de Ruptura Intradía ($t \ge M$):**
  Una vez cumplida la condición $\text{RVOL} \ge 1.50$ y con dirección establecida:
  - Para `BUY`: Si `bar.close > H_open`, emitir `EntryIntent(side=BUY, ...)`.
  - Para `SELL`: Si `bar.close < L_open`, emitir `EntryIntent(side=SELL, ...)`.
  - `CandidateB` DEBE emitir a lo sumo **1 `EntryIntent` por sesión**.

- **R140 (DEBE). Niveles de Riesgo (`RiskLevelsProvider`):**
  Inmediatamente tras emitir `EntryIntent`, `CandidateB.risk_levels(intent)` DEBE retornar:
  - Para `BUY`: `stop_loss = L_open` (o derivado por ATR según config), `take_profit = entry + RR * (entry - stop_loss)`.
  - Para `SELL`: `stop_loss = H_open` (o derivado por ATR según config), `take_profit = entry - RR * (stop_loss - entry)`.

### 2.2 Configuración y Contratos

- **R141 (DEBE). Extensión de `CandidateBConfig`:**
  `CandidateBConfig` DEBE incluir los siguientes campos inmutables:
  - `opening_window_minutes: int = 30` (validado $\ge 5$).
  - `rvol_threshold: float = 1.50` (validado $> 0.0$).
  - `rvol_lookback_days: int = 20` (validado $\ge 5$).

- **R142 (DEBE). Invarianza Temporal y Anti-anticipación (§9 Spec):**
  Cualquier mutación de barras con timestamp $t' > t$ NO DEBE alterar la salida de `on_bar(t)`.
  El cálculo de $R_{\text{open}}$ y $\text{RVOL}$ DEBE depender exclusivamente de las barras $[0, M-1]$ de la sesión actual y de los días $[d-K, d-1]$ previos cerrados.

- **R143 (DEBE). Disciplina Estadística (Decisión D1):**
  Esta formulación constituye **1 único ensayo** formal para el ledger de validación de Genesis.
