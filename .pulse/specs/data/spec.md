
<!-- change:2-b-feat-data-capa-de-datos-export-mt5-calendario-sesiones-calidad -->
# Specification: Capa de datos — export MT5, calendario, sesiones, calidad, store (Issue #2 / B)

SSoT: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` (en adelante «el spec»). Este
documento formaliza el `proposal.md` de este Change en requisitos verificables. Los gates G/C/P/T
del spec **nunca se relajan**; ningún requisito de este documento puede contradecirlos.

Convención de rutas: el spec usa pseudocódigo `python/data/...` (§3, §4); el repo real usa
`src/genesis/data/...` (`[project] name = "genesis"` en `pyproject.toml`). Todas las rutas de este
documento son las reales del repo.

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Construir los 5 módulos de `src/genesis/data/` (`mt5_export.py`, `sessions.py`, `calendar.py`,
`quality.py`, `store.py`) como la capa 1 del pipeline (spec §3, §4): agnóstica a la estrategia,
desacoplada I/O-vs-lógica-pura, reproducible y libre de lookahead por construcción, que desbloquea
Issue C (contrato `StrategyCandidate` + Inspector) y el resto del camino crítico
`A → B → C → {E, G} → H → I → J`.

### 1.2. Alcance IN

- Los 5 módulos listados arriba, en `src/genesis/data/`, con la API pública descrita en §3 de este
  documento.
- Puertos `Protocol` inyectables para el SDK `MetaTrader5` (`mt5_export.py`) y para la fuente de
  calendario económico (`calendar.py`), con implementaciones reales e implementaciones fake de test.
- Excepciones de dominio: `AccountScopeError`, `DayBoundaryError` (spec §8); `QualityError` (nueva,
  ver R21) para fallos fail-fast del contrato de calidad.
- `prop_profile.json` (o artefacto equivalente) con los valores versionados de §1.3 del spec
  (`daily_reset_time`, `daily_loss_limit`) y la tabla de símbolos MT5 esperados de §1.3/§2.x, más
  el subcomando `mt5-export confirm-firm-profile` (o nombre equivalente fijado en design) para
  confirmarlos contra una cuenta demo real cuando esté disponible.
- Adición de `MetaTrader5` (marcador `sys_platform == 'win32'`), `pandas`, `pyarrow`, `numpy` a
  `dependencies` de `pyproject.toml` vía `uv add`.
- Suite de tests unit + property (`hypothesis`) que cubra el 100% de la lógica pura sin terminal
  MT5 ni red, más golden tests con mini-datasets sintéticos y un test de integración
  export→quality en segundos (spec §9).

### 1.3. Alcance OUT (YAGNI explícito)

- Código de `src/genesis/strategy/` (contrato plugin, Inspector, candidatos A/B/C) — Issue C y
  siguientes.
- Código de `src/genesis/backtest/` (simulador, costos, ledger, métricas) — Issue G.
- Código de `src/genesis/validation/` (WFA, Monte Carlo, DSR/PBO, `prop_sim`, veredicto) — Issues
  H/I/J.
- Enforcement definitivo de `LookaheadError`: es PA-4 de Issue C (spec §11.1). Este Change solo
  deja `store.py` diseñado forward-only (sin API que permita leer una barra futura o por índice
  absoluto), sin lanzar la excepción él mismo.
- Actualización definitiva de §1.3/§2.x del spec con símbolos MT5 confirmados: solo ocurre si se
  ejecuta `confirm-firm-profile` contra una cuenta demo real; no es un entregable garantizado.
- Esquema exacto de particionado de Parquet (por símbolo/año/mes vs. columnar único) y el detalle
  binario del formato de metadata por chunk: se fija en `design.md`, respetando los invariantes
  normativos de este spec (hash por chunk, metadata de reproducibilidad, cache-first).
- Cualquier workflow de CI (`.github/workflows/`): no existe hoy en el repo; no es prerequisito de
  este Change (los tests deben poder correr localmente sin terminal MT5, lo cual ya cubre la
  necesidad de CI futura sin requerir crearla ahora).
- El veredicto real de los gates G (incluido G1, ≥300 trades OOS) — eso ocurre en Issues H/I/J
  sobre el backtest real. `quality.py` solo produce un **proxy de cobertura histórica** (ver R23);
  no calcula trades OOS (no existe backtest en esta capa).
- Fuentes de datos de terceros para reconciliar historia insuficiente de The5ers (spec §4.1,
  último párrafo) — solo aplica si `quality.py` reporta insuficiencia; la reconciliación en sí es
  un issue futuro, no de este Change.

---

## 2. Convenciones de esta especificación

- Los requisitos usan **DEBE** (MUST), **DEBERÍA** (SHOULD) y **PUEDE** (MAY), numerados `R1..Rn`,
  cada uno verificable por al menos un test o una aserción `rg`/`fd`.
- Nombres de funciones/clases/excepciones son **normativos** (deben existir exactamente con ese
  nombre, verificable por `rg`); firmas exactas (tipos de parámetros, orden) se resuelven en
  `design.md` respetando el comportamiento descrito aquí.
- Identificadores en inglés, docstrings y mensajes de error en español (convención del repo).

---

## 3. Requisitos por módulo

### 3.1. `mt5_export.py`

**Responsabilidad**: adaptador delgado sobre el SDK `MetaTrader5`, expuesto también como CLI
(`mt5-export`, spec §6), que descarga M1 OHLCV + `tick_volume`, ticks (`copy_ticks_range`) y la
ficha extendida del símbolo, con separación estricta de cuenta (spec §4.1).

**API pública (nombres normativos, firma exacta en design)**:
- `class Mt5Terminal(Protocol)`: puerto con la superficie mínima usada del SDK (`initialize`,
  `shutdown`, `last_error`, `account_info`, `symbols_get`, `symbol_info`, `copy_rates_range`,
  `copy_ticks_range`).
- `class RealMt5Terminal`: implementa `Mt5Terminal` importando `MetaTrader5` de forma perezosa
  (dentro de sus métodos o `__init__`, nunca a nivel de módulo).
- `class AccountScopeError(Exception)`.
- `def resolve_symbol_alias(conventional_name, available_symbols, expected_table) -> str`: función
  pura.
- `def plan_chunks(start, end, granularity) -> list[...]`: función pura de troceo/planificación.
- `def backoff_delay(attempt: int) -> float`: función pura.
- CLI `mt5-export export ...` y `mt5-export confirm-firm-profile ...` (subcomandos, spec §6).

**Entradas/salidas**: entradas = rango temporal, símbolo(s) convencionales, `Mt5Terminal` inyectado;
salidas = Parquet crudo por chunk + metadata JSON adjunta (ficha extendida del símbolo, hash,
rango, fuente, config_version, commit).

**Errores**: `AccountScopeError` (guard de cuenta); error ruidoso (no adivinado) si
`resolve_symbol_alias` no encuentra coincidencia ni en el símbolo esperado ni en los alias
documentados.

**Invariantes**: ninguna llamada de descarga ocurre antes de validar el guard de cuenta; un chunk
ya persistido con su hash no se vuelve a pedir al terminal; nunca se importa `MetaTrader5` a nivel
de módulo.

**Requisitos**:

- **R1** (DEBE). `mt5_export.py` DEBE definir `Mt5Terminal` como `typing.Protocol` con, al menos,
  los métodos `initialize`, `shutdown`, `last_error`, `account_info`, `symbols_get`,
  `symbol_info`, `copy_rates_range`, `copy_ticks_range`.
- **R2** (DEBE). `RealMt5Terminal` DEBE importar el paquete `MetaTrader5` de forma perezosa (no en
  el nivel de módulo de `mt5_export.py`), de modo que importar `genesis.data.mt5_export` no
  falle en una plataforma donde `MetaTrader5` no está instalado.
- **R3** (DEBE). Tras `initialize()` y antes de la primera petición de datos (`copy_rates_range`,
  `copy_ticks_range`, `symbols_get`), el exportador DEBE validar que `account_info()` corresponde
  a una cuenta demo/investor (p. ej. `trade_mode` distinto de cuenta real con permiso de trading
  activo); si la validación falla, DEBE lanzar `AccountScopeError` **sin haber realizado ninguna
  llamada de descarga**.
- **R4** (DEBE). La descarga DEBE ser secuencial y troceada: M1 por meses vía `copy_rates_range`,
  ticks por días vía `copy_ticks_range`, un símbolo a la vez (spec §4.1).
- **R5** (DEBE). `plan_chunks(start, end, granularity)` DEBE ser una función pura (sin I/O) que
  produce una lista ordenada y sin solapamientos de sub-rangos que cubre exactamente
  `[start, end]`.
- **R6** (DEBE). Entre peticiones sucesivas al terminal DEBE aplicarse una pausa configurable
  (0.5–2 s por defecto) y, ante error de servidor, `backoff_delay(attempt)` DEBE crecer de forma
  monótona con `attempt` (backoff exponencial).
- **R7** (DEBE). Cada chunk descargado DEBE persistirse a Parquet junto con un hash `sha256`
  calculado sobre el contenido crudo del chunk, antes de considerarse completo.
- **R8** (DEBE). Un re-run que encuentre un chunk cuyo hash ya está persistido en el store de cache
  NO DEBE volver a solicitarlo al terminal (runs reanudables, cache-first).
- **R9** (DEBE). `resolve_symbol_alias(conventional_name, available_symbols, expected_table)` DEBE
  intentar primero el símbolo esperado (tabla §1.3/§2.x del spec) y, si no existe en
  `available_symbols`, DEBE probar la lista de alias documentada; si ninguno coincide, DEBE fallar
  ruidosamente (lanzar excepción con contexto), nunca adivinar o devolver un símbolo no verificado.
- **R10** (DEBE). Cada export DEBE capturar y persistir la ficha extendida del símbolo
  (`tick_value`, `tick_size`, `volume_step`, `stops_level`, `freeze_level`, `digits`,
  `swap_long`, `swap_short`, `swap_rollover_day`) como metadata adjunta al Parquet. `tick_value` y
  `tick_size` se persisten **crudos** tal como los reporta el terminal (`trade_tick_value`,
  `trade_tick_size`); la conversión punto→dinero (`$/punto = tick_value / tick_size`) es derivada y
  NO DEBE aplicarse antes de persistir (Change #55).
- **R11** (DEBERÍA). La ejecución preferente DEBERÍA poder programarse en fin de semana u horas de
  baja actividad (parámetro de configuración, no bloqueante para el resto de requisitos).

### 3.2. `sessions.py`

**Responsabilidad**: materializar la tabla normativa de sesiones de contado por índice (spec §2.3)
con `zoneinfo`, resolviendo el DST del mercado subyacente (no el del operador).

**API pública**:
- Estructura de datos inmutable con la tabla de sesiones (símbolo → zona horaria del mercado,
  hora de apertura/cierre en horario estándar).
- `def session_window(symbol: str, session_date: date) -> tuple[datetime, datetime]`: función pura,
  retorna apertura/cierre en UTC ya resueltos para esa fecha (incluyendo DST).

**Entradas/salidas**: entrada = símbolo convencional + fecha; salida = tupla `(open_utc, close_utc)`
con `tzinfo=UTC`.

**Errores**: símbolo no soportado por la tabla → excepción explícita (`KeyError` o excepción de
dominio dedicada, a fijar en design).

**Invariantes**: sin I/O; determinista; no depende de ningún estado externo mutable.

**Requisitos**:

- **R12** (DEBE). `sessions.py` DEBE materializar, al menos, las 4 filas de la tabla de sesiones de
  contado del spec §2.3: US500 (14:30–21:00 UTC estándar, `America/New_York`), NAS100 (idéntico a
  US500), US30 (idéntico a US500), GER40 (08:00–16:30 UTC estándar, `Europe/Berlin`).
- **R13** (DEBE). `session_window(symbol, session_date)` DEBE usar `zoneinfo` para resolver el
  desplazamiento DST del **mercado subyacente** (`America/New_York` o `Europe/Berlin`), no la zona
  horaria del sistema operativo ni la del operador.
- **R14** (DEBE). Para una fecha en horario de verano de EE. UU. (EDT), `session_window("US500", d)`
  DEBE retornar 13:30–20:00 UTC; para una fecha en horario estándar (EST), DEBE retornar
  14:30–21:00 UTC. Análogamente para GER40 con CEST/CET (07:00–15:30 UTC / 08:00–16:30 UTC).
- **R15** (DEBE). `session_window` DEBE ser determinista: para el mismo `(symbol, session_date)`
  invocado repetidamente, sin mutación de estado externo, DEBE retornar siempre el mismo resultado
  (invariante verificable con `hypothesis`).

### 3.3. `calendar.py`

**Responsabilidad**: ingesta de calendario económico normalizada a ventanas UTC por
símbolo/divisa, insumo de `news_restrictions` (spec §1.3: bracketing prohibido) y del filtro de
entradas del Candidato B.

**API pública**:
- `class EconomicCalendarSource(Protocol)`: puerto con `fetch_events(start, end) -> list[EconomicEvent]`.
- `class EconomicEvent`: modelo de un evento (divisa/índice afectado, timestamp UTC, nivel de
  impacto).
- `def news_windows(events, symbol, firm_profile) -> list[tuple[datetime, datetime]]` (nombre
  indicativo; función pura de normalización evento→ventana prohibida por símbolo).

**Entradas/salidas**: entrada = rango temporal + fuente inyectada; salida = lista de ventanas UTC
prohibidas por símbolo.

**Errores**: fuente indisponible o evento sin timestamp UTC → excepción explícita, nunca ventana
vacía silenciosa cuando la fuente falló (distinto de "sin eventos en el rango", que sí es una
lista vacía legítima).

**Invariantes**: la lógica de normalización (mapeo evento→ventana, filtro por umbral de impacto)
no depende de la fuente concreta; es testeable con una fuente fake.

**Requisitos**:

- **R16** (DEBE). `calendar.py` DEBE definir `EconomicCalendarSource` como `Protocol` con, al
  menos, el método `fetch_events(start, end)`, de forma que la lógica de normalización sea
  testeable inyectando una fuente fake, sin red ni dependencia externa.
- **R17** (DEBE). La fuente concreta (API/CSV/scraping/adaptador) NO DEBE fijarse en el nivel de
  import del módulo (mismo principio de import perezoso que R2), permitiendo sustituir el
  adaptador sin tocar la lógica de normalización.
- **R18** (DEBE). `news_windows` DEBE producir, para cada evento de impacto alto relevante a un
  símbolo, una ventana UTC (inicio, fin) que cubra el bracketing prohibido alrededor del evento
  (spec §1.3); eventos de impacto no configurado como alto NO DEBEN generar ventana.
- **R19** (DEBE). La normalización DEBE ser una función pura sobre la lista de eventos ya obtenida
  (sin I/O dentro de `news_windows`), separada de la obtención vía `EconomicCalendarSource`.
- **R20** (DEBERÍA). La fuente concreta de datos de calendario económico para producción DEBERÍA
  decidirse en `design.md` (ver Preguntas abiertas, §8 de este documento); no bloquea la
  implementación de la interfaz ni de la normalización en este Change.

### 3.4. `quality.py`

**Responsabilidad**: contrato de calidad fail-fast y ruidoso (spec §4, §8) sobre el Parquet crudo
de `mt5_export.py`: gaps anómalos, duplicados, velas corruptas, cobertura, y registro explícito de
la ventana real de disponibilidad de ticks (PA-2).

**API pública**:
- `class QualityError(Exception)`.
- `class QualityReport`: estructura con, al menos, `symbol`, `gaps: list[...]`,
  `duplicates_count: int`, `corrupt_bars_count: int`, `m1_coverage_window: tuple[date, date]`,
  `ticks_coverage_window: tuple[date, date] | None`, `sufficiency_verdict: bool`,
  `sufficiency_reason: str`.
- `def check_quality(raw_frame, symbol_spec) -> QualityReport`: función pura.

**Entradas/salidas**: entrada = frame crudo (M1/ticks) + ficha del símbolo; salida =
`QualityReport`.

**Errores**: `QualityError` para condiciones que impiden emitir siquiera un reporte (p. ej. frame
vacío o esquema inválido); un símbolo con historia insuficiente NO lanza excepción — se reporta
como `sufficiency_verdict=False` con `sufficiency_reason` explícito (fail-fast informativo, no
fail-silent).

**Invariantes**: `check_quality` no depende del SDK MT5; nunca interpola, nunca rellena datos
faltantes, nunca silencia una anomalía detectada.

**Requisitos**:

- **R21** (DEBE). `quality.py` DEBE definir `QualityError` como excepción de dominio dedicada para
  fallos que impiden producir un `QualityReport` (esquema inválido, frame vacío).
- **R22** (DEBE). `check_quality` DEBE detectar y reportar, como mínimo: gaps anómalos (huecos de
  M1 mayores al esperado por la tabla de sesiones), duplicados (misma marca de tiempo repetida),
  y velas corruptas (OHLC inconsistente, p. ej. `low > high` o `close` fuera de `[low, high]`).
- **R23** (DEBE). `check_quality` DEBE calcular y registrar en el reporte la ventana real de
  cobertura de M1 (`m1_coverage_window`) y, si hay ticks disponibles, la ventana real de
  disponibilidad de ticks (`ticks_coverage_window`), como proxy de PA-2 (spec §4.1, §11.1). Esta
  ventana es la que consumirá `costs.py` (capa 3, fuera de alcance) para el modelo de spread por
  hora.
- **R24** (DEBE). `check_quality` DEBE emitir un `sufficiency_verdict` por símbolo basado en un
  criterio de cobertura temporal documentado en `sufficiency_reason` (p. ej. número mínimo de
  sesiones de contado completas disponibles). Este veredicto es un **proxy de historia
  disponible**, no el gate G1 real (≥300 trades OOS, spec §7.1) — el veredicto definitivo de G1 se
  calcula en Issues H/I sobre el backtest real; `quality.py` solo debe dejar constancia expresa de
  esta distinción en su docstring/reporte para no inducir a interpretar `sufficiency_verdict` como
  el gate G1 en sí.
- **R25** (DEBE). Cuando `sufficiency_verdict` es `False`, el símbolo DEBE marcarse explícitamente
  como excluido en el reporte — `quality.py` NUNCA DEBE interpolar, rellenar o sintetizar barras
  faltantes para alcanzar la suficiencia (spec §8: los gates nunca se relajan).
- **R26** (DEBE). Ninguna anomalía detectada (gap, duplicado, vela corrupta) DEBE quedar fuera del
  `QualityReport` de forma silenciosa; toda anomalía detectada aparece contada o listada en el
  reporte.
- **R27** (DEBERÍA). `check_quality` DEBERÍA ser testeable con mini-datasets sintéticos
  (`pandas.DataFrame` construidos a mano en el test) sin depender de un export real.

### 3.5. `store.py`

**Responsabilidad**: lectura normalizada tz-servidor → UTC, iterador de barras/ticks con marcas de
corte de día (`daily_reset_time` de la ficha de firma) y marcas de sesión (`sessions.py`).

**API pública**:
- `class DayBoundaryError(Exception)`.
- Iterador/lector de barras (nombre indicativo `BarStore` o función generadora) que expone
  iteración **monotónica hacia adelante únicamente** (sin acceso por índice absoluto, sin método
  de "adelantar el cursor" o "espiar" filas futuras).
- Cada barra/tick emitido DEBE incluir su timestamp ya en UTC y su marca de sesión asociada
  (dentro/fuera de sesión de contado, según `sessions.py`).

**Entradas/salidas**: entrada = Parquet normalizado (salida de `mt5_export.py`/`quality.py`) +
ficha de firma (`daily_reset_time`); salida = secuencia iterable de barras/ticks anotados.

**Errores**: `DayBoundaryError` si el corte de día calculado es inconsistente con
`daily_reset_time` de la ficha activa (p. ej. una barra cruza el corte sin marca de día nuevo).

**Invariantes**: forward-only por diseño de API (no por excepción activa, ver Alcance OUT); tz de
origen (servidor MT5) siempre convertida a UTC vía `zoneinfo` antes de emitirse.

**Requisitos**:

- **R28** (DEBE). Toda barra/tick emitido por `store.py` DEBE estar en UTC, convertido desde la
  zona horaria del servidor MT5 de origen usando `zoneinfo` (nunca offsets hardcodeados).
- **R29** (DEBE). El corte de día aplicado por el store DEBE derivarse de `daily_reset_time` de la
  ficha de firma activa (`00:00 America/New_York` por defecto, spec §1.3), no de la medianoche UTC
  ni de la medianoche del servidor MT5.
- **R30** (DEBE). Si el store detecta una inconsistencia entre el corte de día calculado y
  `daily_reset_time` de la ficha activa, DEBE lanzar `DayBoundaryError` y abortar el run (spec §8).
- **R31** (DEBE). Cada barra/tick emitido DEBE llevar una marca de sesión (dentro/fuera de la
  sesión de contado del símbolo) derivada de `sessions.py.session_window`, no de una tabla
  duplicada dentro de `store.py`.
- **R32** (DEBE). La API pública de iteración de `store.py` NO DEBE exponer ningún método que
  permita leer una barra por índice absoluto ni "mirar hacia adelante" del punto de lectura
  secuencial actual (diseño forward-only, preparación para PA-4 de Issue C sin resolverla).
- **R33** (DEBE). `store.py` NO DEBE lanzar `LookaheadError` en este Change (PA-4 es de Issue C);
  su ausencia de este módulo en Issue B no es un defecto sino una decisión explícita de alcance.

---

## 4. Invariantes transversales

- **R34** (DEBE). Todo adaptador de I/O externo (`mt5_export.py` sobre el SDK `MetaTrader5`,
  `calendar.py` sobre la fuente de calendario) DEBE exponerse detrás de un `Protocol` inyectable,
  de forma que la lógica de negocio sea 100% testeable con una implementación fake, sin conexión
  real (principio de separación I/O-vs-lógica-pura, por analogía con
  `.agents/rules/architecture-conventions.md`).
- **R35** (DEBE). El import de paquetes externos con restricciones de plataforma o de entorno
  (`MetaTrader5`) DEBE ser perezoso (dentro de función/método, nunca a nivel de módulo), para que
  `import genesis.data.mt5_export` no falle en una plataforma sin ese paquete instalado.
- **R36** (DEBE). Todo Parquet persistido por `mt5_export.py` DEBE ser cache-first: identificado
  por un hash de su contenido crudo, de forma que un re-run con el mismo rango temporal produzca
  el mismo Parquet bit-idéntico y nunca re-descargue silenciosamente lo ya persistido (spec §3,
  §8: determinismo total, runs reanudables).
- **R37** (DEBE). La descarga de `mt5_export.py` DEBE ser secuencial y troceada (un símbolo a la
  vez, M1 por meses, ticks por días), con pausa configurable y backoff exponencial ante error de
  servidor (spec §4.1, patrón "buen ciudadano").
- **R38** (DEBE). Toda condición de dataset sin calidad, config inválida o ficha incompleta DEBE
  abortar de forma explícita con contexto (mensaje que identifique símbolo/rango/causa) — nunca
  degradación silenciosa (spec §8, fail-fast con contexto).
- **R39** (DEBE). Todo artefacto de salida de esta capa (Parquet de `mt5_export.py`, reporte de
  `quality.py`) DEBE registrar en su metadata, como mínimo: `config_version`, hash del dataset/
  chunk, ficha de firma (o su hash), rango temporal cubierto y el commit de git vigente (spec §3:
  reproducibilidad institucional).
- **R40** (DEBE). Toda conversión de zona horaria en esta capa (`sessions.py`, `store.py`) DEBE
  usar `zoneinfo` de la librería estándar (no `pytz` ni offsets fijos hardcodeados), y DEBE
  resolver el DST del **mercado subyacente**, nunca el DST del huso horario local del operador.
- **R41** (DEBE). El corte de día por `daily_reset_time` (R29) y las marcas de sesión por DST (R40)
  DEBEN ser consistentes entre sí: una barra que cae dentro de la sesión de contado según
  `sessions.py` no puede quedar marcada en un día distinto al que le correspondería por
  `daily_reset_time` sin que `store.py` lo señale (o bien es coherente, o bien dispara
  `DayBoundaryError`, R30) — no hay un tercer estado silencioso.

---

## 5. Manejo de PA-1 / PA-2 / `daily_reset_time`

- **R42** (DEBE). El repo DEBE incluir un artefacto versionado (`prop_profile.json` o equivalente)
  con los valores "default conservador" del spec §1.3 como defaults explícitos:
  `daily_reset_time = 00:00 America/New_York`, `daily_loss_limit = 5%` (doble base: equity
  flotante intradía y balance del día anterior, la más estricta gana), y la tabla de símbolos MT5
  esperados de §1.3/§2.x (US500→`US500`, NAS100→`US100`, US30→`US30`, GER40→`GER40`, con sus alias
  documentados).
- **R43** (DEBE). El pipeline (export, sesiones, store) DEBE funcionar correctamente usando
  únicamente estos valores por defecto, sin requerir acceso a una cuenta demo real (Issue B no se
  bloquea por PA-1/PA-2/confirmación de firma — decisión explícita del proposal).
- **R44** (DEBE). DEBE existir un subcomando de CLI (`mt5-export confirm-firm-profile` o el nombre
  que fije `design.md`) que, ejecutado contra una cuenta demo real, compare `symbols_get()` del
  terminal contra la tabla esperada de R42 y reporte discrepancias explícitamente (no las corrige
  automáticamente — la actualización de §1.3/§2.x del spec es un paso humano documentado, fuera de
  alcance de este Change).
- **R45** (DEBE). La ejecución de `confirm-firm-profile` sin cuenta demo disponible (o sin terminal
  MT5 conectado) DEBE fallar con un mensaje explícito que indique que es un paso diferido y no
  bloqueante, nunca con un traceback opaco sin contexto.
- **R46** (DEBE). La profundidad real de historia de ticks (PA-2) DEBE quedar registrada
  automáticamente en la metadata de `quality.py` (R23) en cualquier corrida real del export, sin
  requerir la ejecución de un subcomando separado.

---

## 6. Manejo de errores (resumen normativo, spec §8)

| Excepción | Módulo | Disparador | Efecto |
|---|---|---|---|
| `AccountScopeError` | `mt5_export.py` | Cuenta con permiso de trading real/challenge detectada al conectar | Aborta antes de cualquier descarga |
| `DayBoundaryError` | `store.py` | Corte de día inconsistente con `daily_reset_time` de la ficha activa | Aborta el run |
| `QualityError` | `quality.py` | Frame crudo inválido/vacío que impide producir un `QualityReport` | Aborta antes de emitir reporte |
| (fuera de alcance) `LookaheadError` | — | PA-4, Issue C | No se implementa en este Change |
| (fuera de alcance) `SessionBoundaryError` | — | Candidato B (Issue E), spec §2.3 | No se implementa en este Change (no hay estrategia aún) |

- **R47** (DEBE). Las tres excepciones de este Change (`AccountScopeError`, `DayBoundaryError`,
  `QualityError`) DEBEN heredar de `Exception` (o de una jerarquía de excepciones de dominio propia
  de `genesis.data`), llevar un mensaje con contexto suficiente para diagnosticar la causa (símbolo,
  rango, valor esperado vs. observado) y ser importables desde el módulo donde se documentan en
  este spec.

---

## 7. Testing (spec §9, `.agents/rules/eval-tdd-conventions.md`)

- **R48** (DEBE). Cada tarea que module código en `src/genesis/data/` DEBE seguir TDD test-first
  (RED → GREEN → refactor), según `.agents/rules/eval-tdd-conventions.md`.
- **R49** (DEBE). La suite `unit` (marcador `pytest.mark.unit`, spec §9 / `pyproject.toml`) DEBE
  cubrir, sin terminal MT5 ni red: `plan_chunks`, `backoff_delay`, `resolve_symbol_alias`,
  `session_window` (con `hypothesis`, invariante de determinismo por fecha, R15), y
  `check_quality` contra mini-datasets sintéticos (gaps, duplicados, velas corruptas,
  insuficiencia de historia).
- **R50** (DEBE). `mt5_export.py` DEBE ser testeable end-to-end de su lógica de orquestación (guard
  de cuenta, troceo, cache-first) inyectando un `FakeMt5Terminal` determinista definido en
  `tests/`, sin que ningún test `unit`/`property` importe el paquete `MetaTrader5`.
- **R51** (DEBE). Todo test que ejercite `RealMt5Terminal` contra un terminal MT5 real DEBE
  marcarse `integration` y/o `slow` (spec §9, markers de `pyproject.toml`) y DEBE saltarse
  automáticamente (p. ej. `pytest.importorskip("MetaTrader5")` o fixture de detección de
  plataforma/terminal) en un entorno sin `MetaTrader5` instalado o sin terminal conectado.
- **R52** (DEBE). DEBE existir al menos un test de integración (marcador `integration`) que corra
  export→quality sobre un dataset de muestra en segundos, ejecutable en CI sin terminal real (spec
  §9).
- **R53** (DEBERÍA). Las propiedades de `hypothesis` DEBERÍAN cubrir, como mínimo: determinismo de
  `session_window` por fecha (R15), y que `plan_chunks` cubre el rango completo `[start, end]` sin
  huecos ni solapamientos para cualquier partición válida.
- **R54** (DEBE). `uv run pytest tests/` (suite completa, sin marcar `slow`/`integration` con
  terminal real) DEBE pasar en verde en una máquina sin terminal MT5 conectado.

---

## 8. Dependencias

- **R55** (DEBE). `pyproject.toml` DEBE declarar `MetaTrader5` en `dependencies` con marcador de
  entorno PEP 508 `sys_platform == 'win32'`, de forma que `uv sync` en una plataforma no-Windows no
  intente instalarlo.
- **R56** (DEBE). `pyproject.toml` DEBE declarar `pandas`, `pyarrow` y `numpy` en `dependencies`
  (sin restricción de plataforma), con versiones mínimas compatibles con Python 3.14, añadidas vía
  `uv add` (no editadas a mano sin regenerar `uv.lock`).
- **R57** (DEBE). `hypothesis` y `pytest` ya presentes en `dependency-groups.dev` DEBEN seguir
  cubriendo los tests de esta capa; no se requiere añadir dependencias de test nuevas para cumplir
  este spec (`pytest-mock` ya disponible si se necesitan spies/contadores de llamadas, R60).
- **R58** (DEBE). Tras el `uv add` de R55/R56, `mise run ci` (lint + `ty` + test) DEBE seguir
  pasando, en particular `deptry` no DEBE reportar falsos positivos sobre `MetaTrader5` (ya
  anticipado en `[tool.deptry].package_module_name_map`).

---

## 9. Criterios de aceptación (evals ejecutables)

```
DADO    un `FakeMt5Terminal` configurado con `account_info().trade_mode` en modo NO-demo
CUANDO  se invoca el flujo de export de `mt5_export.py` sobre ese terminal
ENTONCES se lanza `AccountScopeError` y el contador de llamadas de descarga del fake
         (`copy_rates_range`/`copy_ticks_range`) permanece en 0
```

```
DADO    el archivo src/genesis/data/mt5_export.py
CUANDO  rg "class Mt5Terminal" src/genesis/data/mt5_export.py
ENTONCES retorna >=1 coincidencia
```

```
DADO    el archivo src/genesis/data/mt5_export.py
CUANDO  rg "class AccountScopeError" src/genesis/data/mt5_export.py
ENTONCES retorna >=1 coincidencia
```

```
DADO    el archivo src/genesis/data/store.py
CUANDO  rg "class DayBoundaryError" src/genesis/data/store.py
ENTONCES retorna >=1 coincidencia
```

```
DADO    el archivo src/genesis/data/quality.py
CUANDO  rg "class QualityError" src/genesis/data/quality.py
ENTONCES retorna >=1 coincidencia
```

```
DADO    un mini-dataset sintético M1 con historia insuficiente para el proxy de suficiencia (R24)
CUANDO  se invoca `check_quality(raw_frame, symbol_spec)`
ENTONCES el `QualityReport` resultante tiene `sufficiency_verdict is False`, `sufficiency_reason`
         no vacío, y ninguna barra fue interpolada/rellenada (el frame de entrada y la cuenta de
         filas del reporte de cobertura coinciden)
```

```
DADO    una fecha en horario de verano de EE. UU. (EDT) y otra en horario estándar (EST)
CUANDO  se invoca `session_window("US500", fecha)` para ambas fechas
ENTONCES la primera retorna (13:30 UTC, 20:00 UTC) y la segunda retorna (14:30 UTC, 21:00 UTC)
```

```
DADO    el archivo pyproject.toml tras `uv add` de las dependencias de esta capa
CUANDO  rg "sys_platform" pyproject.toml
ENTONCES retorna >=1 coincidencia asociada a MetaTrader5
```

```
DADO    un entorno sin terminal MT5 conectado y sin el paquete MetaTrader5 instalado
CUANDO  se ejecuta `uv run pytest tests/` (sin forzar markers `slow`/`integration` con terminal real)
ENTONCES la suite completa pasa en verde (exit code 0)
```

```
DADO    el repositorio tras completar este Change
CUANDO  se ejecuta `mise run ci`
ENTONCES lint + ty + test pasan en verde (exit code 0)
```

```
DADO    un entorno sin cuenta demo de The5ers disponible
CUANDO  se ejecuta el subcomando `mt5-export confirm-firm-profile`
ENTONCES el comando termina con un mensaje explícito indicando que el paso es diferido/no
         bloqueante (no un traceback sin contexto), y con código de salida distinto de éxito
```

```
DADO    dos chunks generados por dos ejecuciones independientes de `mt5_export.py` sobre el mismo
        rango temporal y el mismo `FakeMt5Terminal` determinista
CUANDO  se comparan los archivos Parquet resultantes
ENTONCES son bit-idénticos (mismo hash sha256)
```

```
DADO    un chunk ya persistido con su hash en el store de cache
CUANDO  se re-ejecuta el export sobre el mismo rango con el mismo `FakeMt5Terminal`
ENTONCES el contador de llamadas de descarga del fake para ese chunk es 0 (no se re-descarga)
```

---

## 10. Riesgos (heredados del proposal, sin mitigación adicional en este Change)

- Sin cuenta demo real, PA-1 (símbolos MT5 exactos) y PA-2 (profundidad de ticks) quedan sin
  confirmar; mitigado por defaults versionados (R42) + subcomando de confirmación (R44) que no
  bloquean el Change (R43).
- `MetaTrader5` es Windows-only; mitigado por el puerto inyectable (R34) + marcador de plataforma
  (R55), que permiten cubrir el 100% de la lógica de negocio sin el SDK instalado.
- Si la historia real de The5ers no alcanza la suficiencia proxy de `quality.py` (R24), el símbolo
  se excluye (R25) — el riesgo de que una implementación "rellene" datos se mitiga con R25/R26
  como requisitos verificables, no solo como intención de diseño.
- La fuente concreta de `calendar.py` no está decidida (ver Preguntas abiertas); el puerto
  `EconomicCalendarSource` (R16/R17) aísla esa decisión de la lógica de normalización.

---

## 11. Preguntas abiertas (no bloquean este Change, ver R43/R20)

- PA-1 (símbolos MT5 exactos de The5ers) — se resuelve, si se resuelve, vía R44 (subcomando
  `confirm-firm-profile`), no como parte obligatoria de este Change.
- PA-2 (profundidad real de historia de ticks) — se registra automáticamente vía R23/R46 en
  cualquier corrida real; no requiere acción adicional de este Change.
- Confirmación de `daily_reset_time`/`daily_loss_limit` contra términos vigentes de The5ers — igual
  que PA-1, vía R44, no bloqueante.
- Fuente concreta de `calendar.py` (API/CSV/scraping) — a decidir en `design.md` (R20); la interfaz
  (R16/R17) y la normalización (R18/R19) no dependen de esa decisión.
- Esquema exacto de particionado de Parquet y formato binario de metadata por chunk — a decidir en
  `design.md`, respetando R7/R8/R36/R39 (hash por chunk, cache-first, campos mínimos de
  reproducibilidad).
- Mecanismo exacto de skip de tests `integration`/`slow` sin terminal MT5 (R51) —
  `pytest.importorskip` vs. fixture de detección de plataforma — a decidir en `design.md`.

---

## 12. Trazabilidad (requisito → sección del SSoT)

| Requisitos | Sección del spec |
|---|---|
| R1–R11, R34–R37, R55 | §4 (tabla de componentes), §4.1 (política de extracción, `AccountScopeError`) |
| R12–R15, R40 | §2.3 (sesiones de contado por índice, DST) |
| R16–R20 | §4 (tabla de componentes: `calendar.py`), §1.3 (`news_restrictions`) |
| R21–R27, R23/R46 | §4 (`quality.py`), §4.1 (realidad de profundidad de ticks, PA-2), §7.1 (G1) |
| R28–R33, R41 | §4 (`store.py`), §8 (`DayBoundaryError`) |
| R38, R39 | §8 (fail-fast, determinismo), §3 (reproducibilidad institucional) |
| R42–R46 | §1.3 (ficha The5ers, tabla de símbolos, defaults "confirmar en Issue B"), §11.1 (PA-1, PA-2) |
| R47 | §8 (manejo de errores) |
| R48–R54 | §9 (testing EDD/TDD), `.agents/rules/eval-tdd-conventions.md` |
| R55–R58 | §11.2 (dependencias de runtime vía `uv`) |
| Alcance OUT (LookaheadError) | §11.1 PA-4, §8 |
| Alcance OUT (universos A/C, G1 real) | §2.x, §7.1, §11 (tabla de issues) |

<!-- change:55-fix-data-symbolfigure-no-captura-tick-size-el-sizing-costos-asum -->
# Specification — `SymbolFigure` captura `tick_size`; la conversión punto→dinero usa `tick_value / tick_size`

Change #55 (Issue #55). Formaliza `idea.md` (Explore) + `proposal.md` (Propose): `SymbolFigure`
(capa 1, `src/genesis/data/symbols.py:11-28`) persiste hoy `tick_value` como el
`trade_tick_value` crudo del SDK MT5, sin su contraparte `trade_tick_size`. Los tres sitios de
capa 3 que convierten distancia de precio en dinero multiplicando por `figure.tick_value` asumen
implícitamente que ese campo ya es "$/punto" — pero `$/punto = trade_tick_value /
trade_tick_size`, y para los 4 índices del Candidato B el valor crudo persistido difiere ~100× del
valor real, causando 100 % de rechazos `lot_size_out_of_bounds` en backtests con datos reales.

## Objetivo

Que `SymbolFigure` capture ambos términos crudos del cociente MT5 (`tick_value`, `tick_size`) y
que los tres sitios de capa 3 que hoy multiplican por `figure.tick_value` asumiendo $/punto
obtengan el $/punto real vía `tick_value / tick_size`, sin relajar ningún gate G/C/P/T (SSoT
`docs/SPEC_GENESIS_v1.4_...md`) y sin tocar `max_lot`, `trade_contract_size`, ni las fichas
placeholder de Candidato A.

## Alcance

### IN

1. Agregar `tick_size: float` a `SymbolFigure`, capturado desde `raw.trade_tick_size` en
   `_coerce_symbol_figure` (mismo patrón que `tick_value`).
2. Corregir los tres sitios confirmados de capa 3 que multiplican por `figure.tick_value` asumiendo
   $/punto, para que usen el cociente `tick_value / tick_size` (variante exacta —normalizar en
   ingesta vs. dividir en cada consumidor— es decisión de `design`, no de este spec).
3. Actualizar `R10` de `.pulse/specs/data/spec.md` (delta explícito, ver sección dedicada más
   abajo) para incorporar `tick_size` a la lista normativa de la ficha extendida.
4. Actualizar los fixtures/tests que instancian `SymbolFigure` directamente y el golden fixture de
   `signal_diagnostic` al esquema de 9 campos (lista exhaustiva en Riesgos/Referencias).
5. Re-exportar la ficha real de los 4 índices del Candidato B (`US500.cash`, `US100.cash`,
   `US30.cash`, `GER40.cash`) con `tick_size` capturado, como tarea de `apply` posterior al fix de
   esquema/fórmula (no bloqueante para el merge del fix, que se valida con fixtures sintéticas).

### OUT (YAGNI explícito — fuera de este Change)

- **`max_lot=50.0`** de `inspector_config.json:candidates.B.*` (`src/genesis/strategy/
  inspector_config.json:5`): no es la causa raíz (el bug es la conversión $/punto, no el techo de
  lote). Riesgo conocido documentado abajo: el residual algebraico tras el fix puede seguir
  excediendo `max_lot` en el peor día observado.
- **`trade_contract_size`**: los 4 símbolos confirmados tienen `contract_size=1.0`; generalizar la
  fórmula a `$/punto = contract_size × tick_value / tick_size` sin evidencia de un símbolo real
  con `contract_size != 1` es especulativo. Riesgo conocido documentado abajo.
- **Candidato A**: se beneficia estructuralmente del cambio de esquema (mismo value object), pero
  no se le inventa un `tick_size` placeholder plausible en este Change — sigue "no confirmado"
  (Issue B/F). `apply` decide cómo construye sus 4 fichas placeholder con el esquema nuevo.
- **Default de `tick_size` para deserialización retro-compatible**: decisión explícita de NO tener
  default (ver R2) — no es un OUT por alcance sino por diseño deliberado, se documenta aquí para
  que no se reabra en `design`.

## Delta explícito a `.pulse/specs/data/spec.md` (R10)

**Hallazgo verificado en esta sesión**: `.pulse/specs/data/spec.md:143-145` (R10 actual) enumera
los 8 campos de la ficha extendida (`tick_value`, `volume_step`, `stops_level`, `freeze_level`,
`digits`, `swap_long`, `swap_short`, `swap_rollover_day`) **sin** la cláusula "como mínimo"/"al
menos" que sí usa el precedente de Change #51 en otro spec normativo. Confirmado leyendo el texto
actual de R10: la lista es cerrada, no abierta. A diferencia de #51 (que no necesitó delta porque
su spec normativo sí tenía esa cláusula), **este Change SÍ requiere modificar R10 explícitamente**
para no dejar el spec normativo desincronizado del código tras agregar `tick_size`.

- **Texto actual de R10**: "Cada export DEBE capturar y persistir la ficha extendida del símbolo
  (`tick_value`, `volume_step`, `stops_level`, `freeze_level`, `digits`, `swap_long`,
  `swap_short`, `swap_rollover_day`) como metadata adjunta al Parquet."
- **Texto propuesto para R10** (a aplicar en `.pulse/specs/data/spec.md` durante `apply`, tras
  `design`): "Cada export DEBE capturar y persistir la ficha extendida del símbolo (`tick_value`,
  `tick_size`, `volume_step`, `stops_level`, `freeze_level`, `digits`, `swap_long`, `swap_short`,
  `swap_rollover_day`) como metadata adjunta al Parquet."
- Este delta es responsabilidad de `apply` (edición del spec normativo va junto con el código que
  lo satisface, mismo patrón que R91 en #51), pero queda fijado aquí como requisito de este Change
  para que no se pierda entre `design` y `apply`.

## Requisitos funcionales

- **R1** (mapea idea.md §"`SymbolFigure` no tiene tick_size", proposal "Hipótesis de solución").
  `SymbolFigure` (`src/genesis/data/symbols.py:11-28`) DEBE ganar un campo `tick_size: float`,
  documentado en su docstring junto a los 8 campos existentes, referenciando el R10 actualizado.
- **R2** (mapea proposal "Decisiones de alcance fijadas... SIN default"). El campo `tick_size` de
  R1 NO DEBE tener valor default: `SymbolFigure(**payload)` para cualquier payload de esquema
  viejo (sin `tick_size`) DEBE fallar con `TypeError` en vez de construirse con un valor inventado
  — ruptura deliberada, consistente con "fail-fast con contexto" (`CLAUDE.md`) y con R9
  (`resolve_symbol_alias`, "fallar ruidosamente... nunca adivinar"). Aplica a `ArtifactMetadata.
  from_json` (`src/genesis/data/metadata.py:73-92`) y a `signal_diagnostic._resolve_figure`
  (`src/genesis/validation/signal_diagnostic.py:319-326`): ambos deben seguir construyendo
  `SymbolFigure(**...)` sin pasar un default sintético para `tick_size`.
- **R3** (mapea idea.md/proposal "Contexto observado", `_coerce_symbol_figure`).
  `_coerce_symbol_figure` (`src/genesis/data/mt5_export.py:388-406`) DEBE leer
  `raw.trade_tick_size` y poblar `SymbolFigure.tick_size` con `float(raw.trade_tick_size)`, mismo
  patrón que el `tick_value` existente (`float(raw.trade_tick_value)`), para cualquier `raw` que
  no sea ya un `SymbolFigure` (rama de fakes de test preservada sin cambios).
- **R4** (mapea idea.md/proposal "Tres sitios confirmados", `candidate_b/candidate.py:220`). El
  cálculo de `sizing` en `_compute_risk_geometry`
  (`src/genesis/strategy/candidate_b/candidate.py:216-222`) DEBE usar el $/punto real derivado de
  `figure.tick_value` y `figure.tick_size` (fórmula `tick_value / tick_size`, aplicada en el sitio
  de consumo o ya normalizada en la ficha según decida `design`), en vez de `figure.tick_value`
  crudo, de modo que `stop_distance * ($/punto real)` sea la base correcta del sizing.
- **R5** (mapea idea.md/proposal "Tres sitios confirmados", `simulator.py:345`, `_floating_pnl`).
  `_floating_pnl` (`src/genesis/backtest/simulator.py:340-346`) DEBE usar el $/punto real
  (`tick_value / tick_size`) en vez de `self.figure.tick_value` crudo para convertir `points *
  sizing_hint` a dinero.
- **R6** (mapea idea.md/proposal "Tres sitios confirmados", `simulator.py:529`, costo de entrada).
  El cálculo de costo de entrada en dinero (`src/genesis/backtest/simulator.py:520-531`) DEBE usar
  el $/punto real (`tick_value / tick_size`) en vez de `self.figure.tick_value` crudo para
  convertir `points_total * sizing_hint` a dinero.
- **R7** (mapea idea.md "Impacto en serialización/reproducibilidad"). `RunProvenance`
  (`src/genesis/backtest/ledger.py:76`) NO DEBE modificarse: no embebe `SymbolFigure` ni ningún
  hash derivado de ella; queda fuera del alcance de este Change (confirmado, no afectado por R1).
- **R8** (mapea proposal "Delta explícito a R10"). `.pulse/specs/data/spec.md` R10 DEBE
  actualizarse (en `apply`, junto con el código) para incluir `tick_size` en la lista normativa de
  campos de la ficha extendida, con el texto exacto fijado en la sección "Delta explícito" de este
  documento.
- **R9** (mapea idea.md "`inspector_config.json`... `max_lot`", proposal "riesgo conocido"). Este
  Change NO DEBE modificar `max_lot` en `inspector_config.json`. El residual cuantificado (rango
  algebraico `[0.11, 1.33] × max_lot` tras el fix, extremo superior aún excede `max_lot=50`) queda
  documentado como riesgo conocido (ver Riesgos), no como requisito a resolver aquí.
- **R10** (mapea idea.md pregunta 4/proposal "Candidato A"). Este Change NO DEBE inventar un
  `tick_size` placeholder para las fichas de Candidato A (`XAUUSD`, `EURUSD`, `GBPUSD`,
  `USDJPY` en `src/genesis/strategy/candidate_a/config.py:load_placeholder_symbol_figures`). La
  construcción explícita de esas 4 fichas con el esquema de 9 campos (valor de `tick_size` a
  elegir) es detalle de `apply`, no de alcance.
- **R11** (mapea proposal "Re-exportar ficha real"). `apply` DEBE re-exportar la ficha real de los
  4 índices del Candidato B (`US500.cash`, `US100.cash`, `US30.cash`, `GER40.cash`) con
  `tick_size` capturado vía R3, como paso posterior al merge del fix de esquema/fórmula (que se
  valida primero con fixtures sintéticas, sin I/O a MT5).

## Criterios de aceptación (evals ejecutables)

- **A1**
  ```
  DADO  SymbolFigure(symbol="US500", tick_value=0.01, tick_size=0.01, volume_step=0.01,
        stops_level=10, freeze_level=5, digits=2, swap_long=-0.5, swap_short=-0.3,
        swap_rollover_day=2)
  CUANDO se construye el objeto
  ENTONCES no lanza excepción Y figure.tick_size == 0.01
  ```
  (test de pytest, `tests/data/test_symbols.py`, `pytest.mark.unit`; reemplaza el test de "8
  campos" por uno de 9 campos).

- **A2**
  ```
  DADO  un payload de deserialización (dict) para SymbolFigure sin la clave "tick_size"
        (esquema viejo de 8 campos)
  CUANDO se invoca SymbolFigure(**payload)
  ENTONCES lanza TypeError (ningún default silencia la ausencia del campo)
  ```
  (test de pytest, `tests/data/test_symbols.py`, `pytest.mark.unit`; verifica R2).

- **A3**
  ```
  DADO  un objeto raw sintético (namedtuple o SimpleNamespace) con
        trade_tick_value=0.0115435, trade_tick_size=0.01, volume_step=0.01,
        trade_stops_level=10, trade_freeze_level=5, digits=2, swap_long=-0.5,
        swap_short=-0.3, swap_rollover3days=2
  CUANDO se invoca _coerce_symbol_figure("GER40.cash", raw)
  ENTONCES el SymbolFigure resultante tiene tick_value == 0.0115435 Y tick_size == 0.01
  ```
  (test de pytest, `tests/data/test_mt5_export.py` o módulo equivalente existente,
  `pytest.mark.unit`; verifica R3).

- **A4**
  ```
  DADO  un CandidateB configurado con figure=SymbolFigure(..., tick_value=0.01, tick_size=0.01,
        ...) (caso US500 real: cociente == 1.0) y un stop_distance conocido D
  CUANDO se invoca _compute_risk_geometry y se compara el sizing resultante contra el sizing
        obtenido con figure=SymbolFigure(..., tick_value=1.0, tick_size=1.0, ...)
        (mismo cociente, distinto par de valores crudos)
  ENTONCES ambos sizing son iguales (el cociente, no el valor crudo de tick_value, determina el
       resultado)
  ```
  (test de pytest, `tests/strategy/candidate_b/test_candidate.py` o módulo equivalente,
  `pytest.mark.unit`; verifica R4 — el fix depende del cociente, no del valor absoluto).

- **A5**
  ```
  DADO  un CandidateB configurado con figure=SymbolFigure(..., tick_value=0.0115435,
        tick_size=0.01, ...) (caso GER40 real, cociente == 1.15435) y un stop_distance
        conocido D, balance B, risk_pct R
  CUANDO se invoca _compute_risk_geometry
  ENTONCES el sizing retornado == (R * B) / (D * 1.15435), no (R * B) / (D * 0.0115435)
  ```
  (test de pytest, mismo módulo que A4, `pytest.mark.unit`; distingue el bug —dividir por el
  valor crudo— del fix —dividir por el cociente—).

- **A6**
  ```
  DADO  un Simulator con figure=SymbolFigure(..., tick_value=0.01, tick_size=0.01, ...) y una
        OpenPosition con sizing_hint conocido, entry_price y price de cierre conocidos
  CUANDO se invoca _floating_pnl(position, price)
  ENTONCES el resultado == points * sizing_hint * (tick_value / tick_size), con
       (tick_value / tick_size) == 1.0 para este caso (no == tick_value == 0.01)
  ```
  (test de pytest, `tests/backtest/test_simulator.py`, `pytest.mark.unit`; verifica R5).

- **A7**
  ```
  DADO  un Simulator con figure=SymbolFigure(..., tick_value=0.01, tick_size=0.01, ...) y un
        EntryIntent con sizing_hint conocido, spread/slippage points conocidos
  CUANDO se resuelve el costo de entrada en dinero (flujo de _process_new_entries /
        _open_position)
  ENTONCES cost_points == points_total * sizing_hint * (tick_value / tick_size), con
       (tick_value / tick_size) == 1.0 para este caso
  ```
  (test de pytest, `tests/backtest/test_simulator.py`, `pytest.mark.unit`; verifica R6).

- **A8**
  ```
  DADO  el repositorio en el estado posterior a implementar R1-R6
  CUANDO rg -n "\.tick_value\b" src/genesis/
  ENTONCES ningún resultado en candidate_b/candidate.py, backtest/simulator.py multiplica
       figure.tick_value sin también referenciar figure.tick_size en la misma expresión
       (verificación de no-regresión: no queda ningún consumo crudo sin dividir)
  ```
  (eval `rg` manual/script, verificación de no-regresión de R4-R6).

- **A9**
  ```
  DADO  .pulse/specs/data/spec.md tras aplicar el delta de la sección "Delta explícito a R10"
  CUANDO rg -n "tick_size" .pulse/specs/data/spec.md
  ENTONCES aparece al menos una coincidencia dentro del texto de R10
  ```
  (eval `rg`, verificación de que R8 se ejecutó; a correr en `apply`, no en `specify`).

- **A10**
  ```
  DADO  tests/validation/fixtures/signal_diagnostic_report_golden.json actualizado al esquema
        de 9 campos (con tick_size)
  CUANDO se ejecuta la suite de tests de golden de signal_diagnostic
  ENTONCES pasa sin error de esquema (TypeError al reconstruir SymbolFigure)
  ```
  (test de pytest existente, `tests/validation/`, verificación de que R2 no rompe el flujo de
  golden tests tras la actualización de fixtures en `apply`).

## Riesgos

- **Riesgo 1 (residual de `max_lot`)**: la estimación algebraica del proposal
  (`sizing_correcto = sizing_erróneo × raw_tick_size`, con `raw_tick_size=0.01` para los 4
  índices) da un rango corregido `[0.11, 1.33] × max_lot=50`; el extremo superior (`≈66.5`) sigue
  excediendo `max_lot=50`. No es una re-medición empírica. Se recomienda que `apply` re-ejecute el
  backtest in-sample original tras el fix (con la ficha re-exportada de R11) para confirmar o
  refutar el residual; si persisten rechazos por sizing en el mismo orden, abrir Issue de
  seguimiento para recalibrar `max_lot` (fuera de este Change).
- **Riesgo 2 (`trade_contract_size`)**: la fórmula de este Change asume `contract_size == 1.0`
  (confirmado para los 4 símbolos del Candidato B). Si en el futuro se incorpora un símbolo con
  `contract_size != 1` (p. ej. futuros), la fórmula quedaría incompleta y debe revisarse
  (`$/punto = contract_size × tick_value / tick_size`).
- **Riesgo 3 (fixtures y golden tests a actualizar)**: la ruptura deliberada de R2 obliga a
  actualizar `tests/data/test_symbols.py`, `tests/data/fakes.py:43`
  (`_default_symbol_figure`, reutilizado por `tests/strategy/candidate_b/conftest.py:22` y por
  extensión `tests/strategy/candidate_b/test_golden_session.py`), `tests/data/test_metadata.py:49`,
  `tests/backtest/test_costs.py:25`, `tests/strategy/test_inspector.py:31`, y el golden fixture
  `tests/validation/fixtures/signal_diagnostic_report_golden.json`. Si `apply` omite alguno, la
  suite falla con `TypeError` en la construcción de `SymbolFigure` (comportamiento esperado de R2,
  no un bug oculto — pero requiere tocar todos los sitios listados).
- **Riesgo 4 (variante de diseño no decidida)**: R4-R6 fijan el resultado observable (el cociente
  correcto debe aplicarse) sin fijar si `design` normaliza en la ingesta (opción (a) de
  `idea.md`, un solo punto de cambio) o divide en cada consumidor (opción (b), tres puntos de
  cambio). Ambas satisfacen los criterios de aceptación A4-A7 (que verifican el resultado, no la
  ubicación del cálculo); `design` debe fijar una y documentar el trade-off ya identificado en
  `idea.md`.

## Preguntas abiertas

Ninguna pregunta de alcance queda abierta (resueltas en `proposal.md`). Quedan para `design`:

1. Variante (a) normalizar en ingesta vs. (b) dividir en cada consumidor (Riesgo 4).
2. Valor de construcción explícita (no deserialización) de `tick_size` para las 4 fichas
   placeholder de Candidato A (R10) — detalle de `apply`, no bloquea `design`.
3. Si la re-ejecución del backtest in-sample tras el fix (R11 + Riesgo 1) confirma o refuta el
   residual algebraico de `max_lot` — a resolver empíricamente en `apply`.

## Referencias

- Issue #55: https://github.com/ramaDben/genesis/issues/55
- `idea.md`, `proposal.md` de este Change — evidencia completa, sonda MT5 en vivo, decisiones de
  alcance.
- `src/genesis/data/symbols.py:11-28` — `SymbolFigure`.
- `src/genesis/data/mt5_export.py:388-406` — `_coerce_symbol_figure`.
- `src/genesis/strategy/candidate_b/candidate.py:216-222` — `_compute_risk_geometry`.
- `src/genesis/backtest/simulator.py:340-346,520-531` — `_floating_pnl` y costo de entrada.
- `src/genesis/backtest/costs.py:33-67` — sin el patrón, no requiere cambio.
- `src/genesis/data/metadata.py:60-92` (`ArtifactMetadata.to_json/from_json`),
  `src/genesis/validation/signal_diagnostic.py:319-326` (`_resolve_figure`) — roundtrip que se
  rompe deliberadamente sin default (R2).
- `.pulse/specs/data/spec.md:143-145` (R10) — delta fijado en este documento.
- `src/genesis/strategy/candidate_a/config.py`, `src/genesis/strategy/inspector_config.json` —
  fuera de alcance (Candidato A, `max_lot`), riesgos documentados.
- `src/genesis/backtest/ledger.py:76` (`RunProvenance`) — confirmado no afectado (R7).
- `tests/data/test_symbols.py`, `tests/data/fakes.py:43`, `tests/data/test_metadata.py:49`,
  `tests/backtest/test_costs.py:25`, `tests/strategy/test_inspector.py:31`,
  `tests/strategy/candidate_b/conftest.py:22`, `tests/strategy/candidate_b/test_golden_session.py`,
  `tests/validation/fixtures/signal_diagnostic_report_golden.json` — a actualizar en `apply`
  (Riesgo 3).
- `.pulse/changes/archive/51-fix-validation-.../spec.md` — referencia de formato/estructura usada
  para este documento.
