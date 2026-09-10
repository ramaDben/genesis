# Change #97: Salida por Trailing Estructural (Chandelier) en Capa 3 y Roadmap Candidato B.1 (2026-09-09)

## 1. Contexto y Cierre del Change #97 (v0.4.0, PR #102)

El Change #97 (*Salida por trailing estructural Chandelier en la capa 3*, Issue #97) ha sido completado y cerrado exitosamente a través de todas las fases del ciclo SDD de Pulse (fases `proposal`, `specify`, `design`, `break-to-tasks`, `apply`, `review` y `close`), versionando la librería a **`v0.4.0`** y con PR en GitHub: [PR #102](https://github.com/ramaDben/genesis/pull/102).

### Componentes y Decisiones Técnicas Clave
1. **Promociones a `genesis.strategy.common`:**
   - `IncrementalAtr`, `BarAggregator` y `Timeframe` fueron promovidos desde `candidate_a/smc/` a la raíz de estrategia compartida.
   - Se implementó `RollingExtreme` (`src/genesis/strategy/common/rolling_extreme.py`): buffer circular acotado (`collections.deque`), forward-only, incremental O(1) amortizado, sin lookahead.
2. **Extensión de `RiskProfile` (Criterio A23):**
   - Incorporación de `trailing_lookback: int = 22` y `trailing_atr_mult: float = 3.0` (inmutables, frozen).
   - Ambos campos se agregaron obligatoriamente a `risk_profile_hash()`, evitando colisiones de `trial_id` en el ledger de ensayos institucionales.
3. **Motor de Política de Salida (`src/genesis/backtest/exit_policy.py`):**
   - Funciones puras `nivel(direction, extreme, atr, atr_mult)` y `ratchet(stop_previo, nivel, direction)` garantizan que el stop Chandelier sea estrictamente monótono (no retrocede ante aumentos súbitos de ATR ni movimientos adversos del mercado).
   - `_TrailingState`: administra el extremo rodante y el stop actual.
4. **Contratos de Simulación y Resolución H6 (`inspector.py`, `simulator.py`):**
   - `OpenPosition`: `position_id: str` posicional como primer argumento sin default (generado deterministamente como `{dataset_hash[:8]}-{counter}`).
   - `take_profit: float | None`: soporte de salidas estructurales sin objetivo prefijado.
   - `RiskLevelsProvider.risk_levels`: retorna `tuple[float, float | None]`.
   - **Resolución H6**: El `Inspector` condiciona el veto por R:R (`INSUFFICIENT_RR`) exclusivamente a `proposed_rr is not None and proposed_rr < config.min_rr`. Si `take_profit is None`, la señal no es vetada por R:R.
   - **Preservación de Lista en Simulator:** En `_manage_open_positions`, la mutación se realiza mediante slice assignment (`self.account.open_positions[:] = survivors`), eliminando bugs de `IndexError` y colisiones al remover elementos in-place.
5. **Agregación H1 y Anclaje Temporal en `Simulator`:**
   - Acumulador `BarAggregator(Timeframe.H1)` alimentado paso a paso por barras M1.
   - **Anclaje de sesión (A18):** Al cierre de sesión (`bar.timestamp_utc >= bar.session_close_utc`), el acumulador H1 se resetea a nuevo para impedir velas quiméricas que crucen el overnight.
   - **Ancla de apertura (A6, A19):** Las velas H1 solo alimentan el extremo rodante de una posición si `h1_bar.open_time >= position.entry_time`.
   - **Anti-anticipación (A4, A5):** La barra M1 en curso (`t`) no participa del cálculo del stop con el que se evalúa su propio fill.
6. **Registro en Auditoría (`TrailingStopMoved`):**
   - Se añadió `TrailingStopMoved(position_id, symbol, timestamp_utc, stop_previo, stop_nuevo)` al tipo suma `Decision` en `src/genesis/backtest/ledger.py`. Cada movimiento efectivo del stop queda registrado para reproducibilidad total de los fills.
7. **Suite de Verificación:**
   - 786 tests unitarios y de propiedades (Hypothesis) pasando en verde sin excepciones.
   - Verificación de tipos estricta (`ty check`) y linters (`ruff`, `bandit`, `deptry`, `vulture`) al 100%.

---

## 2. Operatoria y Toolchain de Pulse Engine

La interacción con la máquina de estados SDD de Pulse se realiza mediante el cliente stdio en WSL2:
```bash
python3 ~/pulse_call.py <tool> '<json_arguments>'
```
- **Imagen Docker:** `mcp-pulse:0.13.6` sobre `/home/bbenja11/genesis` montado en `/work`.
- **Esquemas Pydantic estrictos:**
  - `mark_tests_passed`: `{"input_data": {"slug": "<slug>", "passed": True}}` (no tolera campos extra).
  - `request_sdd_transition`: `{"input_data": {"target_phase": "<phase>", "evidence_artifacts": ["/work/.pulse/changes/<slug>/tasks.md"]}}` (las rutas de artefactos deben ser absolutas dentro del contenedor `/work`).
  - `close_change`: `{"input_data": {"slug": "<slug>"}}` (promueve deltas a `.pulse/specs/`, actualiza heurísticas y cierra el cambio).

---

## 3. Hoja de Ruta para la Siguiente Sesión: Candidato B.1

Con la infraestructura de Capa 3 capacitada para soportar salidas por trailing estructural Chandelier sin Take Profit fijo:

1. **Objetivo:** Formular el **Candidato B.1** (Opening Range Breakout - ORB en temporalidad horaria sobre el índice Nasdaq / `US100` / `NQ`).
2. **Filtro de Régimen Macro (D1):**
   - El Candidato B.1 incorporará un filtro direccional de régimen macro en D1 (sesgo por curva de tasas o bias macro institucional) para habilitar solo rupturas alineadas con el flujo macroeconómico.
3. **Mecanismo de Ejecución y Rol:**
   - La formulación del candidato estará a cargo del rol **Arquitecto**.
   - Se gestionará bajo la gobernanza estricta de Pulse, abriendo el issue correspondiente y ejecutando el ciclo SDD: `explore` → `propose` → `specify` → `design` → `break-to-tasks` → `apply` → `review` → `close`.
