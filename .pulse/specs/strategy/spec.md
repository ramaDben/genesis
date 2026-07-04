
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
