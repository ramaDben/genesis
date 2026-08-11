# Spec Génesis v1.4 — Sistema de Trading Sistemático para Prop Firms (Torneo de Candidatos)

**Fecha**: 2026-07-12
**Estado**: definitivo (SSoT vigente). Reemplaza íntegramente al v1.3.
**Objetivo de negocio**: construir un pipeline de validación institucional que adjudique, mediante gates mecánicos, cuál de varios candidatos de estrategia (si alguno) rentabiliza bajo las reglas reales de una prop firm — y autorizar capital solo sobre esa evidencia.

### Changelog v1.3 → v1.4

El 2026-07-12 se ejecutó el sondeo operativo de la corrida D contra el terminal MT5 real de un
**FTMO Free Trial** (issue #20). Esta versión cierra los placeholders "default conservador — a
confirmar" de la ficha FTMO (§1.3.2) que v1.3 dejó deliberadamente abiertos, sustituyéndolos por los
valores confirmados por dos vías independientes: el sondeo del terminal (nombres de símbolo, offset
horario, profundidad de historia) y el dashboard FTMO del usuario (límites de pérdida). Backfill
doc-only: sin cambios en `src/genesis/`, sin gates tocados.

1. **§1.3.2 — `server_tz`**: pasa de `Europe/Prague` (placeholder) a **`Europe/Athens`** (offset base
   **+3** confirmado; sondeo corrida D, issue #20, 2026-07-12). La regla de cambio DST queda
   explícitamente **pendiente** (una sola observación de verano).
2. **§1.3.2 — `daily_reset_time`**: se corrige la atribución de zona — el reset del daily loss es
   medianoche **`Europe/Prague`** (términos vigentes de FTMO), zona **distinta** del reloj del
   servidor de datos (`server_tz` = `Europe/Athens`); el valor numérico y la equivalencia UTC no
   cambian. Confirmado (sondeo corrida D + dashboard FTMO, issue #20, 2026-07-12).
3. **§1.3.2 — `daily_loss_limit`**: **5%** confirmado (Free Trial 50.000 USD → 2.500 USD; dashboard
   FTMO del usuario, 2026-07-12). Sin cambio de valor.
4. **§1.3.2 — `max_loss_limit`**: **10% estático, ancla balance inicial** confirmado (Free Trial
   50.000 USD → 5.000 USD; dashboard FTMO del usuario, 2026-07-12). Sin cambio de valor.
5. **§1.3.2 — tabla de símbolos**: los 8 nombres/alias esperados en v1.3 quedan **confirmados**
   (patrón PA-1, sondeo corrida D, issue #20, 2026-07-12); coincidieron exactamente con los reales del
   terminal (incl. sufijo `.cash` en los 4 índices). Ningún nombre cambia.
6. **§1.3.2 — nota nueva "Historia disponible en el Free Trial (FTMO)"**: ticks con profundidad
   ≥12 meses para los 8 símbolos (con hueco puntual en `NAS100` el 2025-07-07); M1 solo desde
   ~2025-10-22 (índices + oro) y ~2025-11/12 (majors FX). Referencia cruzada breve desde §4.1.

**Placeholders que permanecen intactos** (sin evidencia empírica en este sondeo, conservan su marca
"a confirmar" de v1.3): `min_profitable_days`, Plazo, `news_restrictions`, `weekend_holding`,
`consistency_rule`, `profit_split`/`payout_cycle`, `challenge_cost`, `max_lots`/`max_positions`, EAs,
"Programa de referencia", `equity_basis`.

**Fuera de alcance** (heredado del issue #20): no se reconcilian veredictos de trading (bug de zona
horaria de `iter_ticks`, issue hermano #21); no se crea `profiles/ftmo.json` versionado; los gates
G/C/P/T (§7.1–7.4), el criterio mecánico de archivo (§2.2.1) y el condicionamiento por firma (§7.5)
quedan idénticos a v1.3; la regla DST de `server_tz` queda pendiente, no cerrada. Fuente auditable:
issue #20 (2026-07-12) y dashboard FTMO del usuario — no se citan rutas literales de `out/run_d/*`
(directorio ad-hoc no versionado; invariante de reproducibilidad institucional).

### Changelog v1.2 → v1.3

La cuenta de datos demo/trial de The5ers prevista por §4.1 quedó **inaccesible** el 2026-07-11
(cuentas 26412265 y 24088398 rechazadas con `Invalid account` en `FivePercentOnline-Real`; The5ers
ya no ofrece cuenta demo gratuita, solo challenge pagado). La corrida operativa del diagnóstico de
señal desnuda (§2.2.1, Issue D) pivota a un **FTMO Free Trial (MT5)**. El spread real de ticks
—insumo del criterio de archivo mecánico de §2.2.1— es específico del par broker/servidor, por lo
que un veredicto no es transferible entre firmas. Esta versión cierra el vacío normativo resultante:

1. **§1.3 — Fichas de firma candidatas**: la sección deja de describir una única "firma objetivo
   definitiva" y pasa a alojar dos fichas hermanas — The5ers (contenido de v1.2 sin cambios) y FTMO
   (nueva, con placeholders "default conservador — a confirmar").
2. **§1.3 — Tabla de símbolos MT5 esperados en FTMO**: nueva tabla para el universo combinado A+B
   (8 símbolos), mismo formato de columnas que la de The5ers; nombres esperados a confirmar por la
   corrida operativa.
3. **§4.1 — Cuenta de datos**: se generaliza de "una cuenta demo/trial de The5ers" a "una cuenta
   demo/trial de la firma de datos activa (The5ers o FTMO)", preservando el guard `AccountScopeError`.
4. **§7.5 — Condicionamiento por firma del veredicto**: todo artefacto/veredicto registra
   `firm_profile_hash`; un veredicto no es transferible entre firmas sin re-corrida completa;
   `GO (candidato X, firma Y)` es la forma canónica obligatoria.

**Alcance y no-objetivos de esta versión** (doc-only): no se crea `profiles/ftmo.json`;
`profiles/the5ers.json` e `inspector_config.json` permanecen intactos; no hay cambios en
`src/genesis/`. El gap heredado del `SymbolFigure` real de oro/majors (universo del Candidato A) no
se resuelve aquí para ninguna firma — ver nota en §2.x.

### Changelog v1.1 → v1.2

Los 7 puntos normativos que el v1.1 dejaba pendientes quedan cerrados en esta versión:

1. **§1.3 — Base del `daily_loss_limit`**: el v1.1 marcaba este campo como *verificar en Issue A si la base es equity, balance o el mayor de ambos*. El v1.2 lo cierra: base = el mayor de (equity flotante intradía) y (balance al cierre del día anterior); el gate P3 se evalúa sobre equity flotante.
2. **§1.3 — `daily_reset_time`**: el v1.1 no especificaba la zona horaria explícita. El v1.2 lo fija en `00:00 America/New_York` (default conservador — confirmar contra términos vigentes de The5ers en Issue B).
3. **§1.3 — Tabla de símbolos MT5**: el v1.1 no listaba los símbolos MT5 exactos de The5ers. El v1.2 añade la tabla de correspondencias nombre-convencional ↔ símbolo esperado en The5ers, a confirmar en Issue B.
4. **§2.1 — Contrato plugin normativo**: el v1.1 describía el contrato en términos breves. El v1.2 lo expande a especificación normativa completa: método `on_bar`, invariante forward-only, `LookaheadError`, campos de `EntryIntent`, regla de aislamiento, namespace de parámetros.
5. **§2.3 — Candidato B**: el v1.1 marcaba la tabla de definición normativa como *a fijar en Issue A*. El v1.2 cierra todos los campos: N, criterio de entrada, stop, sizing, sesiones de contado UTC, cierre forzado, noticias.
6. **§6 / §7 — Presupuesto de grid y umbrales**: el v1.1 marcaba los umbrales como *valores iniciales* y el presupuesto de grid como pendiente. El v1.2 los fija como definitivos: N_trials_IS = 27, DSR-IS como métrica de selección, sanity-checks de alcanzabilidad.
7. **§10 — Bandas de incubación**: el v1.1 dejaba las métricas de consistencia sin umbrales. El v1.2 las fija: 8 semanas, slippage/rechazo/Sharpe rolling con umbrales numéricos, criterio de violación de firma como invariante.

---

## 0. Principio rector

Una estrategia "robusta" que viola el límite de pérdida diaria de una prop firm no es robusta para este proyecto. Todas las métricas de riesgo se expresan en **unidades del presupuesto de la firma**. La validación responde tres preguntas, en este orden:

1. ¿Tiene cada candidato ventaja estadística real fuera de muestra? (gates G)
2. ¿Esa ventaja sobrevive y rentabiliza bajo la estructura de reglas y costes de la firma? (gates P)
3. ¿El candidato ganador sobrevive a la corrección por haber sido elegido entre varios? (gates T)

Elegir el mejor de N candidatos es, en sí mismo, data mining: el torneo se descuenta a sí mismo. Un NO-GO honesto y barato es un éxito del proceso. La infraestructura (capas 1, 3 y 4) es agnóstica a la estrategia: se construye una vez y se amortiza sobre todos los candidatos presentes y futuros.

---

## 1. Modelo de negocio y restricciones prop

### 1.1. Ficha de la firma (`prop_profile.json`)

Contrato de datos versionado, análogo a la ficha del símbolo. Campos mínimos:

| Campo | Descripción |
|---|---|
| `phases` | Fases del challenge: target de profit, días mínimos, plazo (o ilimitado) por fase |
| `daily_loss_limit` | Límite de pérdida diaria (% y base de cálculo: el mayor de equity flotante intradía y balance del día anterior) |
| `max_loss_limit` | DD máximo (% y tipo: estático o trailing; ancla del trailing) |
| `daily_reset_time` | Hora y zona horaria del corte diario |
| `equity_basis` | Base de evaluación del DD diario: `equity` (equity flotante — valor resuelto para The5ers v1); el corte diario también aplica la cota adicional de balance del día anterior |
| `consistency_rule` | Si existe: % máximo del profit total atribuible a un solo día |
| `news_restrictions` | Ventanas prohibidas alrededor de noticias de alto impacto (por fase) |
| `weekend_holding` | Permitido o no — **determina la elegibilidad del Candidato C** |
| `profit_split`, `payout_cycle` | Reparto y cadencia de retiros |
| `challenge_cost` | Coste de cada intento |
| `max_lots`, `max_positions` | Límites de exposición si existen |

Nota: el campo `equity_basis` queda resuelto como `equity` para The5ers v1. La evaluación del gate P3 de `prop_sim` usa equity flotante intradía como base primaria; adicionalmente, el límite se considera violado si la pérdida medida contra el balance al cierre del día anterior también lo cruza (cota más estricta de las dos). Ver §1.3 y §7.3.

### 1.2. Economía del embudo

```
E[negocio] = −coste_challenges × E[intentos]
             + P(fondeo) × E[payouts | fondeado, supervivencia]
```

La probabilidad de pasar es función del **Sharpe** de la trayectoria de equity, no de la expectancy por trade; sin límite de tiempo, reducir la volatilidad a Sharpe constante aumenta P(pasar) monótonamente. Corolarios de diseño que rigen todo el spec: (a) el Sharpe se fabrica con amplitud — muchas apuestas pequeñas poco correlacionadas; (b) el riesgo por trade se calibra contra los gates P, con política distinta por fase (challenge vs fondeado); (c) la diversificación entre candidatos no correlacionados (ensemble) es la vía más barata de subir el Sharpe del portafolio.

### 1.3. Fichas de firma candidatas

El pipeline admite **más de una firma de datos candidata** a la vez. Cada firma se especifica con el
patrón de campos de §1.1 (`prop_profile.json`) más su propia tabla de símbolos MT5. La firma activa de
una corrida se selecciona explícitamente (`--firm`/`--profile`, ver §4.1 y §7.5). A continuación, las
dos fichas candidatas de v1: **The5ers** (firma objetivo original) y **FTMO** (firma alternativa,
motivada por la inaccesibilidad de la demo de The5ers — ver changelog v1.2→v1.3).

#### 1.3.1. The5ers — ficha

| Campo | Valor definitivo |
|---|---|
| Plataformas | MT5 (hedge) y cTrader; el export usa MT5 |
| Programa de referencia | High Stakes: target 8% (fase 1) / 5% (fase 2) |
| `daily_loss_limit` | **5%** — base de evaluación: **el mayor de** (a) la pérdida medida contra el equity flotante intradía y (b) la pérdida medida contra el balance al cierre del día anterior. El límite se considera violado en cuanto cualquiera de las dos bases lo cruza. El gate P3 de `prop_sim` evalúa sobre equity flotante (base que dispara primero). La cota de balance del día anterior es la cota adicional. Default conservador — confirmar contra términos vigentes de The5ers en Issue B (cuenta demo / web). |
| `daily_reset_time` | **`00:00 America/New_York`** (medianoche hora de Nueva York, zona horaria explícita). Alineado al servidor MT5 de The5ers. Equivalencia UTC: 05:00 UTC en horario estándar (EST), 04:00 UTC en horario de verano (EDT). Default conservador — confirmar contra términos vigentes de The5ers en Issue B. |
| `equity_basis` | `equity` (equity flotante intradía, con cota adicional de balance del día anterior — ver §1.1) |
| `max_loss_limit` | 10% |
| `min_profitable_days` | **3 días con profit ≥ 0.5% por fase** — restricción activa para `prop_sim`: no basta cruzar el target, hay que cruzarlo con la distribución diaria correcta |
| Plazo | Sin límite de tiempo; cuentas inactivas >30 días expiran |
| `news_restrictions` | **Bracketing prohibido**: órdenes pendientes alrededor de noticias de alto impacto → el calendario (capa 1) debe suprimir entradas pendientes en esas ventanas (afecta al Candidato B) |
| `weekend_holding` | Permitido en índices, con swap alto (el cierre forzado del Candidato B lo hace irrelevante; relevante para el C) |
| EAs | Permitidos **si el trader posee el código fuente**; el sistema propio cumple por construcción. Prohibidos: HFT, tick scalping, arbitraje de latencia/reverso, EAs que exploten el feed en el rollover, copy trading, hedge arbitrage entre cuentas, "one-sided betting" sin análisis |
| Otras | Residentes de EE. UU. excluidos; payouts quincenales |

##### Símbolos MT5 esperados en The5ers

La siguiente tabla lista la correspondencia nombre-convencional ↔ símbolo esperado en la plataforma The5ers. Los nombres canónicos internos del pipeline son los de la columna *Nombre convencional*; `mt5_export.py` resuelve el alias real en Issue B contra la lista de símbolos del terminal MT5.

| Nombre convencional | Símbolo MT5 esperado en The5ers | Alias posibles | Subyacente |
|---|---|---|---|
| US500 | `US500` | `SP500`, `SPX500` | S&P 500 |
| NAS100 | `US100` | `NAS100`, `USTEC` | Nasdaq 100 |
| US30 | `US30` | `DJ30`, `DJIA` | Dow Jones 30 |
| GER40 | `GER40` | `DE40`, `DAX40` | DAX 40 |

Nota: los símbolos MT5 de la columna *Símbolo MT5 esperado* son los nombres esperados a confirmar en Issue B (cuenta demo de The5ers). Si el nombre real difiere, `mt5_export.py` usa el alias confirmado y actualiza esta tabla en Issue B.

#### 1.3.2. FTMO — ficha (firma alternativa)

Ficha candidata introducida en v1.3. Los valores marcados "default conservador — a confirmar" no han
sido verificados contra los términos vigentes de FTMO ni contra la corrida operativa; siguen el mismo
patrón de placeholder que The5ers usó en v1.1→v1.2 y se cierran en un change de backfill posterior,
sin bloquear esta versión.

| Campo | Valor |
|---|---|
| Plataformas | MT5 (Free Trial / Challenge). El export usa MT5. |
| Programa de referencia | FTMO Challenge (fase 1) → Verification (fase 2) → Funded; Free Trial sin objetivo de profit. *Default conservador — a confirmar contra términos vigentes de FTMO.* |
| `daily_loss_limit` | **5%** — base análoga a §1.3.1 (el mayor de la pérdida contra equity flotante intradía y contra el balance/equity de referencia del corte diario); P3 evalúa sobre equity flotante. **Confirmado** (Free Trial 50.000 USD → límite 2.500 USD; dashboard FTMO del usuario, 2026-07-12). |
| `daily_reset_time` | **`00:00` `Europe/Prague`** (CE(S)T, términos vigentes de FTMO) — zona **distinta** del reloj del servidor de datos (`server_tz` = `Europe/Athens`, fila siguiente); no colapsar ambas zonas en una sola. Equivalencia UTC: 23:00 UTC (CET, invierno) / 22:00 UTC (CEST, verano). Confirmado (sondeo corrida D + dashboard FTMO, issue #20, 2026-07-12). |
| `server_tz` | **Europe/Athens** (GMT+2/+3, estilo EET/EEST) — offset **+3** confirmado el 2026-07-12 (sondeo corrida D, issue #20): último tick de forex del viernes etiquetado 23:54 con cierre real 21:00 UTC; índices US a 23:49 con cierre real 20:49 UTC. Best-fit IANA usado por la corrida. **Pendiente**: la regla de cambio DST (fechas UE vs. EE. UU.) no es decidible con una sola observación de verano; se resuelve con probes M1 de la semana 2025-10-26 → 2025-11-02 (ver nota de historia disponible más abajo). |
| `equity_basis` | `equity` (equity flotante intradía, con cota adicional del balance de referencia del corte — ver §1.1). *A confirmar.* |
| `max_loss_limit` | **10%**, tipo **estático** (ancla: balance inicial). **Confirmado** (Free Trial 50.000 USD → límite 5.000 USD; dashboard FTMO del usuario, 2026-07-12). |
| `min_profitable_days` | *A confirmar (FTMO no exige mínimo de días con profit en Free Trial; sí días mínimos de trading en Challenge). Default conservador: no se asume restricción más laxa que The5ers.* |
| Plazo | Free Trial: sin límite; Challenge/Verification: según fase vigente. *A confirmar.* |
| `news_restrictions` | *Default conservador: se asume bracketing prohibido alrededor de noticias de alto impacto (igual que The5ers), pendiente de confirmar los términos reales de FTMO.* |
| `weekend_holding` | Permitido en índices con swap. *A confirmar.* |
| `consistency_rule` | *A confirmar contra términos vigentes de FTMO.* |
| `profit_split`, `payout_cycle` | *A confirmar (irrelevante para la firma de datos; documentado por completitud del patrón §1.1).* |
| `challenge_cost` | Free Trial: gratuito. Challenge: según plan. *A confirmar.* |
| `max_lots`, `max_positions` | *A confirmar contra términos vigentes de FTMO.* |
| EAs | Permitidos con código fuente propio; prohibiciones análogas a The5ers (HFT, tick scalping, arbitraje de latencia, copy trading). *A confirmar.* |

##### Símbolos MT5 esperados en FTMO

Universo combinado A+B (8 símbolos). Mismo criterio que The5ers: los nombres canónicos internos son
los de *Nombre convencional*; el símbolo real lo resuelve `mt5_export.py`/`probe_mt5.py` contra la
lista del terminal FTMO. Los nombres de la columna *Símbolo MT5 esperado en FTMO* fueron **confirmados (patrón PA-1, sondeo corrida D, issue #20, 2026-07-12)**; coinciden exactamente con los nombres esperados en v1.3.

| Nombre convencional | Símbolo MT5 esperado en FTMO | Alias posibles | Subyacente |
|---|---|---|---|
| US500 | `US500.cash` | `SP500`, `SPX500`, `US500` | S&P 500 |
| NAS100 | `US100.cash` | `NAS100`, `USTEC`, `US100` | Nasdaq 100 |
| US30 | `US30.cash` | `DJ30`, `DJIA`, `US30` | Dow Jones 30 |
| GER40 | `GER40.cash` | `DE40`, `DAX40`, `GER40` | DAX 40 |
| XAUUSD | `XAUUSD` | `GOLD`, `GOLDUSD` | Oro spot |
| EURUSD | `EURUSD` | `EURUSD.` | Major FX |
| GBPUSD | `GBPUSD` | `GBPUSD.` | Major FX |
| USDJPY | `USDJPY` | `USDJPY.` | Major FX |

Nota: los nombres y alias fueron **confirmados** por el sondeo de la corrida D (`probe_mt5.py`, issue #20, 2026-07-12) contra el terminal FTMO real; coincidieron exactamente con los esperados en v1.3 (incl. sufijo `.cash` en los 4 índices). La confirmación del `SymbolFigure` real de oro/majors sigue **fuera de alcance** — ver §2.x.

##### Historia disponible en el Free Trial (FTMO)

Confirmado por sondeo de la corrida D (`probe_depth.py`, issue #20, 2026-07-12): los **ticks** están disponibles con profundidad ≥12 meses para los 8 símbolos, con un hueco puntual observado (`NAS100`, sin ticks el 2025-07-07). El **M1** solo está disponible desde ~2025-10-22 para los 4 índices + `XAUUSD`, y desde ~2025-11 a ~2025-12 para los 3 majors FX (`EURUSD`, `GBPUSD`, `USDJPY`). Ventana material para cualquier corrida sobre esta firma — ver también §4.1.

---

## 2. Capa de estrategia: torneo de candidatos

### 2.1. Contrato plugin — especificación normativa

Todo candidato implementa la misma interfaz. Esta sección especifica el contrato normativamente; la firma Python ejecutable (Protocol o clase abstracta) se fija en Issue C.

#### Método mínimo requerido

`on_bar(bar) → list[EntryIntent]`

- **Semántica incremental**: el método solo puede consumir el estado de barras con `confirmed_time ≤ t_actual` (tiempo de confirmación de la barra en curso). Queda explícitamente prohibido acceder a barras con `confirmed_time > t_actual`.
- **Invariante forward-only** (contrato normativo): ningún output de `on_bar(t)` puede depender, directa o indirectamente, de barras con `confirmed_time > t`. Esta invariante es de diseño, no de disciplina del implementador.
- **`LookaheadError`** (enforcement → Issue C): cualquier intento de acceder a una barra con `confirmed_time > t_actual` durante la ejecución de `on_bar(t)` lanza `LookaheadError`. El mecanismo de enforcement se implementa en el simulador y/o el store de datos en Issue C; su existencia es normativa desde este spec.

El invariante forward-only se aplica a nivel de simulador: el reloj interno del simulador garantiza que ningún candidato puede observar el futuro, independientemente de si el candidato viola la invariante intencionalmente o por error.

#### Campos mínimos de `EntryIntent`

Cada `EntryIntent` producido por `on_bar` debe incluir como mínimo:

| Campo | Tipo | Descripción |
|---|---|---|
| `direction` | `long` \| `short` | Dirección de la entrada deseada |
| `sizing_hint` | fracción de riesgo o lotes | Indicación de tamaño (el Inspector puede ajustar o rechazar) |
| `candidate_id` | identificador del candidato (`A`, `B`, `C`, …) | Trazabilidad en el ledger |
| `config_version` | cadena de versión del config activo | Reproducibilidad institucional |

El `EntryIntent` es una **intención**, no una orden ejecutada. El embudo del Inspector puede rechazarla por cualquier motivo normativo (R:R insuficiente, lotaje fuera de límites, ventana de noticias, etc.) y registra el motivo de rechazo tipificado en el ledger. Un rechazo no es un error; es información del embudo.

#### Regla de aislamiento entre candidatos

Cada candidato registra sus propios trials de forma completamente aislada:

- No existe estado compartido entre candidatos (ni parámetros, ni ledger, ni contador de trials).
- El DSR de cada candidato se calcula exclusivamente con la historia de trials de ese candidato; ningún trial de otro candidato entra en su cómputo.
- La corrección de selección del gate T1 (deflación por el número de candidatos del torneo) se aplica al veredicto final, no contamina el DSR individual de cada candidato.

#### Namespace de parámetros

Cada candidato declara sus propios parámetros bajo el namespace `candidates.<letra>.*` en `inspector_config.json`:

- `candidates.A.*` — parámetros del Candidato A (CT sweep-fade)
- `candidates.B.*` — parámetros del Candidato B (ORB)
- `candidates.C.*` — parámetros del Candidato C (TSMOM)

No existen parámetros globales de señal compartidos entre candidatos. El Inspector sí tiene parámetros globales de embudo (umbrales de R:R, límites de lotaje) bajo `inspector.*`.

### 2.2. Candidato A — CT sweep-fade (VWAP+SMC, pierna CT)

**Hipótesis**: tras la confirmación de un barrido de liquidez (sweep de EQH/EQL) con `|Z| ≥ ct_zscore_min` respecto al VWAP anclado, el precio revierte hacia el VWAP con magnitud suficiente para superar los costes. Mecanismo: cascadas de stops agrupados en niveles salientes + reversión de inventario (Osler 2003/2005).

**Componentes**: `vwap_engine` (portado con sus tests), `smc_engine` (fractales con doble timestamp, agregación M1→TF, EQH/EQL, máquina de estados de sweep, camino libre), `zones` (PRO/MID/CT por VWAP + z-score), `risk` (SL banda vs swing + buffer ATR+spread; TP `FIXED_RR`/`STRUCT_TRAIL`/`STATIC`/`DYNAMIC`), gatillo CT.

**La pierna PRO queda archivada (A2)**: hipótesis sin grounding diferenciado y con grados de libertad que encarecen el DSR de todo el sistema. Podrá presentarse a un torneo futuro con sección normativa propia.

#### 2.2.1. Diagnóstico de señal desnuda (kill-switch, previo a `risk`/`triggers`)

Antes de construir la capa de riesgo y gatillos del Candidato A, se ejecuta un estudio de retornos condicionales **sin ningún filtro del embudo**:

- Evento: sweep confirmado con `|Z| ≥ umbral`, por símbolo y sesión.
- Medición: retornos forward a horizontes de 5/15/30/60 minutos vs distribución incondicional; tasa de toque del VWAP antes de recorrer la distancia de stop típica; intervalos por bootstrap.
- **Criterio de archivo**: si el edge bruto condicional (antes de costes) es inferior al coste round-trip estimado **en el momento del sweep** (spread de ticks reales en esos instantes, no promedio), el Candidato A se archiva sin construir el resto. La señal que no existe desnuda no se rescata con filtros: los filtros concentran edge, no lo crean.

### 2.3. Candidato B — Momentum intradía / Opening Range Breakout en índices ★ prioridad

**Hipótesis**: el impulso direccional de la apertura de contado persiste intradía (continuación del rango de apertura). Evidencia: Zarattini & Aziz 2023 (ORB QQQ, alfa ~33% anualizado neto, 2016–2023); Zarattini, Barbon & Aziz 2024 (Sharpe 2.81 en universo amplio; replicado independientemente por QuantConnect con Sharpe 2.4 y robustez paramétrica); mecanismo emparentado con revisión por pares en Gao, Han, Li & Zhou 2018 (momentum intradía de mercado, *JFE*). Las cifras publicadas se descuentan 30–60% por decay post-publicación: el descuento no cambia la prioridad, los gates emiten el veredicto.

**Definición normativa:**

| Elemento | Regla |
|---|---|
| Universo | CFDs de índices: US500, NAS100, US30, GER40 (apertura de contado de cada uno) — ver §2.x para símbolos MT5 |
| Rango de apertura | Primeros N minutos de la sesión de contado, con **N ∈ {5, 15, 30}** como espacio de búsqueda IS (parámetro del WFA) |
| Entrada | Ruptura **confirmada** con cierre de vela M1 fuera del extremo del rango (no ruptura intrabar), en la dirección de la primera vela de la sesión |
| Stop | Extremo opuesto del rango (regla primaria); parámetro alternativo `atr_stop_frac ∈ {0.5, 1.0, 1.5}` en el espacio de búsqueda IS |
| Sizing | Vol-targeting: riesgo fijo `risk_pct ∈ {0.25%, 0.375%, 0.5%}` (espacio de búsqueda IS) → lotes = riesgo / distancia de stop |
| Salida | Cierre forzado al **último tick de precio disponible antes del cierre de sesión de contado**; `SessionBoundaryError` si la posición sobrevive al corte |
| Noticias | Sin entrada en ventanas restringidas por la ficha de la firma según el calendario económico (`calendar.py`, capa 1) |

#### Tabla de sesiones de contado por índice (UTC, horario estándar)

| Índice | Apertura contado (UTC) | Cierre contado (UTC) | Nota DST |
|---|---|---|---|
| US500 | 14:30 | 21:00 | DST US (NY): en horario de verano (EDT) las horas UTC se desplazan −1 h (13:30–20:00 UTC) |
| NAS100 | 14:30 | 21:00 | DST US (NY): igual que US500 |
| US30 | 14:30 | 21:00 | DST US (NY): igual que US500 |
| GER40 | 08:00 | 16:30 | DST EU (Frankfurt): en horario de verano (CEST) las horas UTC se desplazan −1 h (07:00–15:30 UTC) |

Los horarios exactos, incluyendo el desplazamiento DST, se materializan en `sessions.py` (Issue B) usando `zoneinfo`. La tabla anterior es la referencia normativa en horario estándar (UTC sin DST).

**Propiedades estructurales**: ~700–1.000 apuestas/año en 4 índices (amplitud → G1 rápido, Sharpe por diversificación), riesgo definido desde la entrada (compatible con presupuesto diario), no usa volumen (inmune a la fragilidad del `tick_volume`), P6 trivial por construcción.

### 2.4. Candidato C — TSMOM H4/D1 multi-activo (diferido)

Momentum de serie temporal con vol-targeting sobre FX+metales+índices. La evidencia más longeva del quant sistemático (Moskowitz/Ooi/Pedersen 2012; un siglo+ en estudios posteriores). Encaje prop medio: overnight/weekend (elegible solo en firmas que lo permitan), DD largos en tensión con consistency rules, acumulación lenta de trades. **Rol**: sleeve diversificador post-veredicto de A/B; su correlación estructuralmente baja con estrategias intradía es su valor.

### 2.x. Universos por candidato

#### Universo del Candidato B (cerrado, sin extensión en v1)

| Nombre convencional | Símbolo MT5 esperado en The5ers | Alias posibles | Subyacente |
|---|---|---|---|
| US500 | `US500` | `SP500`, `SPX500` | S&P 500 |
| NAS100 | `US100` | `NAS100`, `USTEC` | Nasdaq 100 |
| US30 | `US30` | `DJ30`, `DJIA` | Dow Jones 30 |
| GER40 | `GER40` | `DE40`, `DAX40` | DAX 40 |

Los cuatro índices son el universo completo del Candidato B en v1. No se añaden símbolos adicionales en esta versión. Los símbolos MT5 esperados coinciden con la tabla de §1.3; la correspondencia explícita se documenta allí y se reutiliza aquí.

#### Universo del Candidato A (CT sweep-fade)

El universo del Candidato A está restringido por el mecanismo de sweeps: requiere sesiones con liquidez suficiente para generar estructuras de sweep válidas.

| Nombre convencional | Símbolo MT5 esperado en The5ers | Sesión aplicable | Nota |
|---|---|---|---|
| US500 | `US500` | Contado (14:30–21:00 UTC est.) | Índice US, misma tabla que B |
| NAS100 | `US100` | Contado (14:30–21:00 UTC est.) | Índice US |
| US30 | `US30` | Contado (14:30–21:00 UTC est.) | Índice US |
| GER40 | `GER40` | Contado (08:00–16:30 UTC est.) | Índice EU |
| XAUUSD | `XAUUSD` | Solapamiento Londres–NY (12:00–17:00 UTC aprox.) | Oro spot |
| EURUSD | `EURUSD` | Solapamiento Londres–NY (12:00–17:00 UTC aprox.) | Major FX |
| GBPUSD | `GBPUSD` | Solapamiento Londres–NY (12:00–17:00 UTC aprox.) | Major FX |
| USDJPY | `USDJPY` | Solapamiento Londres–NY (12:00–17:00 UTC aprox.) | Major FX |

El universo definitivo del Candidato A se cierra en Issue F (post-diagnóstico de señal desnuda en Issue D). Los símbolos MT5 de oro y majors son los nombres convencionales esperados en The5ers; a confirmar en Issue B.

> **No-objetivo de v1.3 (gap heredado del Change #16 / Issue D)**: el `SymbolFigure` real (tick_value,
> volume_step, stops_level, digits, swaps) de oro y majors (XAUUSD/EURUSD/GBPUSD/USDJPY, universo del
> Candidato A) **no se resuelve** en esta versión **para ninguna firma** — ni The5ers ni FTMO. El
> diagnóstico de señal desnuda (§2.2.1) corrió con `SymbolFigure` placeholder no autoritativos
> (`--allow-placeholder-figures`) y ninguna ficha de firma versionada cubre estos símbolos hoy. La
> tabla de símbolos FTMO de §1.3.2 hereda el mismo estado "a confirmar" que The5ers para oro/majors:
> documenta los nombres esperados, no cierra la ficha de símbolo real. Cerrar este gap sigue siendo
> responsabilidad de Issue F / de una revisión posterior de las fichas de firma, **fuera del alcance**
> de este change.

#### Universo del Candidato C (TSMOM — implementación diferida a Issue K)

El universo del Candidato C se fija aquí para que el DSR de torneo sea calculable aunque la implementación esté diferida. El universo es FX + metales + índices para TSMOM multi-activo.

| Nombre convencional | Símbolo MT5 esperado en The5ers | Clase de activo |
|---|---|---|
| EURUSD | `EURUSD` | FX major |
| GBPUSD | `GBPUSD` | FX major |
| USDJPY | `USDJPY` | FX major |
| AUDUSD | `AUDUSD` | FX major |
| USDCHF | `USDCHF` | FX major |
| USDCAD | `USDCAD` | FX major |
| XAUUSD | `XAUUSD` | Metal |
| XAGUSD | `XAGUSD` | Metal |
| US500 | `US500` | Índice |
| GER40 | `GER40` | Índice |
| US30 | `US30` | Índice |

El universo definitivo del Candidato C (TSMOM) se confirma en Issue K. La lista anterior es la referencia normativa para calcular el DSR de torneo en Issue J. Los símbolos MT5 son los nombres esperados en The5ers; a confirmar en Issue B.

### 2.5. Higiene del torneo

- **Aislamiento**: cada candidato registra sus propios trials; el DSR de cada uno se calcula solo con su historia.
- **Corrección de selección (gate T1)**: el veredicto final deflacta el DSR del candidato ganador por el número de candidatos del torneo. Elegir el mejor de 3 es un trial más.
- **Ensemble (gate T2)**: si ≥2 candidatos pasan G+C+P con correlación OOS de retornos diarios < 0.3, el ensemble (asignación por vol inversa) se valida como candidato adicional con su propio `prop_sim`. Si la correlación es mayor, se elige solo el de mejor economía P.

---

## 3. Arquitectura — cuatro capas

```
┌──────────────────────────────────────────────────────────┐
│  4. VALIDACIÓN          python/validation/               │
│     WFA · MC símbolo/portafolio · Purged K-Fold · DSR ·  │
│     PBO · sensibilidad · prop_sim · veredicto de torneo  │
├──────────────────────────────────────────────────────────┤
│  3. BACKTEST            python/backtest/                 │
│     Simulador event-driven M1: fills por ticks donde     │
│     existan, equity intradía con cortes de día prop,     │
│     costos completos, cierre forzado por sesión          │
├──────────────────────────────────────────────────────────┤
│  2. ESTRATEGIA          python/strategy/                 │
│     Contrato plugin · embudo Inspector compartido ·      │
│     candidatos A (CT sweep-fade) · B (ORB) · C (TSMOM)   │
├──────────────────────────────────────────────────────────┤
│  1. DATOS               python/data/                     │
│     Export MT5 (M1 + ticks) · calendario económico ·     │
│     horarios de sesión por índice · fichas símbolo/firma │
│     · Parquet versionado · calidad                       │
└──────────────────────────────────────────────────────────┘
```

Principios rectores (sin cambios de fondo respecto a v1.0):

- **Estado incremental forward-only**: anti-lookahead como invariante de diseño, no como disciplina.
- **Reproducibilidad institucional**: cada artefacto registra `config_version`, hash del dataset, ficha de firma, candidato, rango temporal, semillas y commit.
- **Núcleo propio, periferia pragmática**: simulador propio por la lógica stateful y el embudo como métrica de primera clase; periferia con `scipy`/`statsmodels`/`quantstats`/`matplotlib`.

---

## 4. Capa 1 — `python/data/`

| Componente | Responsabilidad |
|---|---|
| `mt5_export.py` | CLI sobre el paquete oficial `MetaTrader5`: (a) M1 OHLCV + `tick_volume`; (b) **ticks** (`copy_ticks_range`) donde el terminal los provea — insumo del modelo de spread, de los fills intrabar y del diagnóstico §2.2.1; (c) ficha del símbolo extendida: `tick_value`, `tick_size`, `volume_step`, `stops_level`, `freeze_level`, `digits`, `swap_long`, `swap_short`, `swap_rollover_day`. Parquet crudo + metadata. |
| `calendar.py` | Calendario económico (noticias de alto impacto por divisa/índice) → ventanas por símbolo. Insumo de cumplimiento (P6) y de stress de costos. |
| `sessions.py` | **Horarios de sesión de contado por índice** (apertura/cierre, con DST del mercado subyacente) — insumo del rango de apertura del Candidato B y del filtro de sesión del A. |
| `quality.py` | Contrato de calidad: gaps anómalos, duplicados, velas corruptas, cobertura, **suficiencia de historia** (un símbolo sin historia para G1 se excluye; nunca se relajan gates). Falla ruidosamente. |
| `store.py` | Lectura normalizada tz-servidor → UTC (`zoneinfo`), iterador de barras/ticks con marcas de corte de día según `daily_reset_time` de la firma y marcas de sesión según `sessions.py`. |

### 4.1. Política de extracción de datos (invariante de cuenta)

La pregunta "¿llamará la atención extraer ticks?" se vuelve irrelevante por diseño: **la cuenta de challenge/fondeada jamás ejecuta el exportador**. Separación estricta de roles:

- **Cuenta de datos**: una cuenta demo/trial de la **firma de datos activa (The5ers o FTMO)** sobre el mismo servidor MT5 (mismo feed de precios, mismos símbolos, mismas fichas) o, en su defecto, un login de solo lectura (investor password) en un terminal dedicado. Es la única cuenta que toca `mt5_export.py`.
- **Cuenta de capital**: solo la tocará el puente de ejecución post-GO. Nunca corre scripts de datos, nunca abre históricos masivos, nunca comparte terminal con el pipeline.
- **Guard en código (`AccountScopeError`)**: `mt5_export.py` verifica al conectar que `account_info().trade_mode == DEMO` o que el terminal no tiene permiso de trading; en caso contrario aborta. El invariante no es disciplina del operador: es una excepción.

Cortesía de cliente (aunque las descargas de histórico son operación estándar del terminal MT5 — todo gráfico abierto y todo run del strategy tester las hace — el exportador se comporta como un buen ciudadano):

- Descarga **secuencial y troceada**: M1 por meses, ticks por días; pausa configurable entre peticiones (0.5–2 s) y backoff exponencial ante errores del servidor.
- Un símbolo a la vez; ejecución preferente en fin de semana u horas de baja actividad.
- **Cache-first**: el terminal cachea el histórico localmente y cada chunk se persiste a Parquet con hash al recibirse; los re-runs leen del almacén y jamás re-descargan (extensión del principio de runs reanudables).
- **Realidad de profundidad de ticks**: los servidores MT5 suelen servir ticks solo para una ventana limitada (semanas–meses, dependiente del broker), mientras que el M1 llega más atrás. Plan: M1 profundo + ticks hasta donde existan; la ventana disponible queda registrada en la metadata y el modelo de spread por hora se construye sobre esa ventana. Si la historia M1 de The5ers no satisface el contrato de suficiencia (G1), se adelanta el issue de reconciliación con datos de terceros en lugar de relajar gates. Para FTMO, ver el detalle de ventana M1/ticks confirmado por sondeo en §1.3.2 ("Historia disponible en el Free Trial").

---

## 5. Capas 2–3 — estrategia y backtest

### 5.1. `python/strategy/`

| Componente | Responsabilidad |
|---|---|
| `contract.py` | Interfaz `StrategyCandidate` (§2.1) + registro de candidatos. |
| `inspector.py` | Embudo compartido: viabilidad R:R, lotaje contra fichas, restricciones de firma, motivos de rechazo tipificados. |
| `common/vwap_engine.py` | Portado con sus tests, sin cambios funcionales. |
| `common/zones.py` | PRO/MID/CT desde VWAP + z-score (usado por A). |
| `candidate_a/` | `smc_engine` + gatillo CT + riesgo propio (§2.2). Incluye el módulo del diagnóstico §2.2.1. |
| `candidate_b/` | Rango de apertura, gatillo de ruptura, sizing por vol, cierre forzado (§2.3). |
| `candidate_c/` | TSMOM (diferido, §2.4). |

### 5.2. `python/backtest/`

| Componente | Responsabilidad |
|---|---|
| `simulator.py` | Loop event-driven por vela M1: `on_bar` del candidato → Inspector → órdenes. Fills con ticks reales donde existan; fallback conservador (SL primero si SL y TP se tocan en la misma vela). **Equity intradía con P&L flotante** y cortes de día por ficha de firma. Soporta cierre forzado por sesión (B) y trailing estructural (A). Detecta en línea: breach diario, breach total, violación de noticias/weekend. |
| `costs.py` | Spread por hora del día muestreado de ticks reales (fallback fijo) + comisión + slippage + swap con triple rollover. Stress ×1.5/×2 como parámetro de primera clase. Sin costos no hay reporte. |
| `ledger.py` | Todas las decisiones (no solo trades) + motivo de rechazo + candidato + `config_version` + hash del dataset + ficha de firma. Serie de equity intradía por día. |
| `metrics.py` | Métricas clásicas + métricas prop: peor excursión diaria flotante, distancia mínima al límite diario, exposición concurrente máxima, tasa de rechazo por motivo. |

---

## 6. Capa 4 — `python/validation/`

| Componente | Responsabilidad |
|---|---|
| `wfa.py` | Walk-forward rolling por candidato: optimización IS (presupuesto de grid explícito; métrica de selección IS: DSR-IS) → congela → OOS → siguiente ventana. WFE sobre la curva OOS cosida. Conteo mecánico de trials por candidato. |
| `montecarlo.py` | Por símbolo: reshuffle + block bootstrap. De portafolio: bootstrap por bloques temporales sobre el ledger combinado (preserva correlación entre símbolos en los mismos días). |
| `prop_sim.py` | Aplica la ficha de la firma a las trayectorias del MC de portafolio: P(pasar por fase), distribución de intentos, P(breach diario/total) por mes, supervivencia mediana, payout neto a 12 m. Políticas de riesgo por fase. |
| `purged_cv.py` | Purged K-Fold con embargo. |
| `dsr_pbo.py` | DSR y PBO vía CSCV por candidato; **deflación de torneo** para el veredicto (T1). |
| `sensitivity.py` | Perturbación ±10% de parámetros; ejes obligatorios adicionales: stress de costos (×1.5/×2) y perturbación del proxy de volumen (solo A). |
| `verdict.py` | Evalúa G+C+P por candidato y firma, aplica T1/T2, emite veredicto de torneo + tearsheet + manifest. |

CLI: `export`, `quality`, `diagnose` (señal desnuda), `backtest`, `wfa`, `mc`, `prop-sim`, `full-validation`, `verdict` — todos con `--candidate` y `--firm`.

### 6.1. Flujo

```
mt5_export ──► quality ──► Parquet versionado (hash)
                              │
              ┌───────────────┴───────────────┐
              ▼ (solo A)                      ▼
   diagnóstico señal desnuda          WFA por candidato
   §2.2.1 → archiva A o continúa             │ OOS cosido + equity intradía
              │               ┌──────────────┼───────────────┬─────────────┐
              └──────────────►│              ▼               ▼             ▼
                        MC símbolo    Purged K-Fold     Sensibilidad   Ledger de
                              │          + PBO + DSR         │         canasta
                              │              │               │             ▼
                              │              │               │      MC portafolio
                              │              │               │             ▼
                              │              │               │         prop_sim
                              └──────────────┴───────────────┴─────────────┘
                                             ▼
                       verdict ──► T1 (deflación de torneo) ── T2 (ensemble)
                                             ▼
                          VEREDICTO por firma + tearsheet + manifest
```

Reglas sin excepción: solo trades OOS alimentan la validación; trials contados mecánicamente por candidato; gates P a nivel de cuenta, nunca por símbolo; manifest reproducible con un comando.

### 6.2. Presupuesto de grid IS y métrica de selección (definitivos)

#### Presupuesto de trials IS por candidato por ventana WFA

**`N_trials_IS = 27`** (grid completo 3×3×3) por candidato por ventana WFA.

Derivación para el Candidato B (3 parámetros libres):

| Parámetro | Espacio de búsqueda IS | Niveles |
|---|---|---|
| `N` (minutos del rango) | {5, 15, 30} | 3 |
| `atr_stop_frac` (fracción ATR del stop) | {0.5, 1.0, 1.5} | 3 |
| `risk_pct` (% de riesgo por trade) | {0.25%, 0.375%, 0.5%} | 3 |

Grid completo: 3 × 3 × 3 = **27 combinaciones**. Este es el presupuesto máximo de trials IS por candidato por ventana WFA. El diseño concreto del muestreo IS (grid lineal, log-lineal, Sobol) se decide en Issue H dentro de este presupuesto.

Nota: `risk_pct` es un parámetro de sizing que no altera la señal ni el conteo de trades; las configuraciones de señal distintas son 3 × 3 = 9. Para el conteo de trials del DSR (que penaliza la búsqueda sobre la **forma** de la señal) lo relevante son las 9 configuraciones de señal. Esta distinción se documenta aquí como restricción de diseño; el cálculo exacto del DSR se implementa en Issue I.

El techo de **N_trials_IS = 27** es una restricción de diseño del WFA que Issue H debe honrar. No se puede superar el presupuesto añadiendo parámetros o niveles sin actualizar este spec.

#### Métrica de selección IS: DSR-IS

La métrica de selección IS del WFA es **DSR-IS** (Deflated Sharpe Ratio calculado sobre los trials IS del candidato). Esta elección coincide con la que ya señalaba §6 del v1.1 y se confirma aquí como definitiva.

Justificación: DSR-IS penaliza la multiplicidad de comparaciones IS directamente en la métrica de selección, reduciendo el sesgo de overfitting IS antes de que llegue al OOS. Es coherente con el gate G4 (DSR OOS ≥ 0.95) al usar la misma familia de correcciones.

#### Coherencia presupuesto de trials con DSR ≥ 0.95

Con N_trials_IS = 27, la deflación del Sharpe por el término de corrección del DSR es modesta: `ln(27) ≈ 3.30`, muy por debajo de los cientos o miles de trials que erosionan el DSR por debajo de 0.95. El gate G4/T1 (DSR ≥ 0.95) es alcanzable con este presupuesto. Ver §7.2 para el sanity-check completo.

---

## 7. Umbrales go/no-go (definitivos)

Los umbrales de esta sección son **definitivos**. Riesgo por trade de referencia: 0.25–0.5%, calibrable por fase contra los gates P.

### 7.1. Gates G — robustez por símbolo y candidato (sobre OOS)

| # | Criterio | Umbral definitivo |
|---|---|---|
| G1 | Trades OOS totales | ≥ 300 |
| G2 | WFE (curva OOS cosida vs IS agregado) | ≥ 0.5 |
| G3 | PF OOS con costos completos (swap incluido) | ≥ 1.3 |
| G4 | DSR (trials del propio candidato) | ≥ 0.95 |
| G5 | PBO (CSCV) | < 25% |
| G6 | MC MaxDD p95 | ≤ 50% del `max_loss_limit` |
| G7 | P(breach del `max_loss_limit` en 12 m, MC) | < 5% |
| G8 | Degradación de PF al perturbar params ±10% | < 30%, sin acantilados |
| G9 | PF OOS con stress de costos ×1.5 | ≥ 1.15 |

### 7.2. Gates C — coherencia de canasta (por candidato)

| # | Criterio | Umbral definitivo |
|---|---|---|
| C1 | Símbolos del universo del candidato que pasan G1–G9 | ≥ 60% |
| C2 | PF OOS mínimo de los que no pasan | ≥ 0.8 |

### 7.3. Gates P — economía prop a nivel de cuenta (por candidato y firma)

| # | Criterio | Umbral definitivo |
|---|---|---|
| P1 | P(pasar challenge completo) | ≥ 50% |
| P2 | E[intentos hasta fondeo] | ≤ 2 |
| P3 | P(breach del límite diario en un mes fondeado) | < 2% — evaluado sobre **equity flotante intradía** (base que dispara primero). El breach también ocurre si la pérdida contra el balance del día anterior cruza el 5% (cota adicional, coherente con §1.3 D1). |
| P4 | Supervivencia mediana fondeada | ≥ 6 meses |
| P5 | Payout neto a 12 m, percentil 25 de la distribución MC | > 0 |
| P6 | Violaciones de reglas de firma en simulación OOS | = 0 |

### 7.4. Gates T — torneo

| # | Criterio | Umbral definitivo |
|---|---|---|
| T1 | DSR del candidato ganador, deflactado por el nº de candidatos del torneo | ≥ 0.95 |
| T2 | Ensemble: correlación OOS de retornos diarios entre candidatos que pasan | < 0.3 para validar ensemble; en caso contrario, solo el de mejor economía P |

### 7.5. Veredicto

- **GO (candidato X, firma Y)**: pasa C+P+T → incubación (§10) con ese candidato/universo/firma.
- **GO-ENSEMBLE**: ≥2 candidatos pasan con T2 → incubación del ensemble.
- **GO-PARCIAL**: pasa en subconjunto de símbolos → incubación restringida.
- **NO-GO**: ningún candidato pasa → revisar hipótesis, no parámetros. Se permite **una** iteración de política de riesgo/firma sin tocar parámetros de señal (registrada como trial para T1).

**Condicionamiento por firma de datos (normativo).** Todo artefacto y todo veredicto queda
condicionado a la firma de datos que lo produjo:

- **Registro obligatorio**: todo artefacto/veredicto registra `firm_profile_hash` (hash SHA-256
  determinista de la ficha de firma activa, `src/genesis/data/profile.py::firm_profile_hash`) como
  parte de su metadata de reproducibilidad, junto a `config_version`, hash de dataset, candidato,
  rango temporal, semillas y commit (§3). `firm_profile_hash` ya es parámetro obligatorio del veredicto
  en código (`src/genesis/validation/verdict.py`).
- **No-transferibilidad**: un veredicto **no es transferible entre firmas** sin re-corrida completa. Un
  GO obtenido con datos FTMO **no** es válido para The5ers ni viceversa, porque el spread real de ticks
  —insumo del coste round-trip del criterio de archivo de §2.2.1 y de los gates P— es específico del
  par broker/servidor. Cambiar de firma invalida el veredicto anterior.
- **Forma canónica obligatoria**: cuando existe más de una firma candidata (§1.3), la forma canónica
  del veredicto es **`GO (candidato X, firma Y)`** — nunca `GO (candidato X)` a secas. La firma es
  parte inseparable de la identidad del veredicto, no un metadato opcional.

*Trabajo futuro (no normado en esta versión)*: una eventual excepción `FirmMismatchError` que aborte al
intentar componer/comparar artefactos con `firm_profile_hash` distintos queda como nota de trabajo
futuro; no se crea en código ni se le asigna issue en este change (doc-only).

### 7.6. Sanity-checks de alcanzabilidad (G1 y G4/T1)

#### Sanity-check G1 ≥ 300 (alcanzabilidad de trades OOS totales)

El gate G1 exige ≥ 300 trades OOS en la curva OOS cosida sobre todas las ventanas WFA.

**Cálculo de referencia para el Candidato B:**

- Frecuencia operativa: ~700–1.000 apuestas/año repartidas en 4 índices (US500, NAS100, US30, GER40).
- Ventana OOS por paso del WFA rolling: 6–12 meses.
- Trades OOS por ventana cosida: 700–1.000 apuestas/año × 0.5–1.0 año = **350–1.000 trades OOS por ventana cosida**.

Como G1 cuenta trades OOS totales sobre la curva OOS cosida (suma de todas las ventanas), y la primera ventana anual ya produce 350–1.000 trades, el sanity-check concluye: **G1 ≥ 300 es holgadamente alcanzable sin ajuste de umbrales.**

Si un índice individual no alcanzara 300 trades OOS en la ventana de historia disponible de The5ers, la solución es extender la ventana temporal de M1 (documentado en `quality.py` como restricción de suficiencia de historia) o excluir ese índice del universo de ese candidato. **Los gates no se relajan.** Esta contingencia se gestiona en Issue B según la historia real disponible.

#### Sanity-check G4/T1 DSR ≥ 0.95 (coherencia con presupuesto de grid)

El gate G4 (y T1, que deflacta por el número de candidatos) exige DSR ≥ 0.95 tras el WFA.

**Análisis con N_trials_IS = 27:**

La corrección del DSR (Deflated Sharpe Ratio de Bailey & López de Prado) penaliza la búsqueda IS mediante el término `Φ⁻¹(1 − 1/T_trials)` donde `T_trials` es el número de trials evaluados. Con 27 trials:

- `ln(27) ≈ 3.30` (como referencia del crecimiento del término de corrección)
- La deflación esperada del Sharpe IS → OOS con 27 trials es modesta comparada con búsquedas de cientos o miles de trials.

**Conclusión**: con N_trials_IS = 27 (grid 3×3×3), el presupuesto de grid es suficientemente pequeño para que la deflación del DSR no haga el gate G4 ≥ 0.95 inalcanzable bajo condiciones normales de edge. **DSR ≥ 0.95 es alcanzable con este presupuesto.** El techo de 27 trials queda documentado como restricción de diseño del WFA (Issue H).

Si el edge IS observado fuera tan pequeño que la deflación lo llevara por debajo de 0.95, eso indica ausencia de ventaja estadística real — el gate cumpliría su función de NO-GO, no habría incoherencia.

---

## 8. Manejo de errores

- **Fail-fast con contexto**: dataset sin calidad, config inválida, ficha incompleta → aborto explícito. Nunca degradación silenciosa.
- **`LookaheadError`**: reloj interno del simulador; leer barra/tick/swing con `confirmed_time > now` lanza excepción. Cualquier candidato que intente acceder a barras futuras durante `on_bar(t)` viola la invariante forward-only y obtiene esta excepción. Ver §2.1.
- **`DayBoundaryError`**: inconsistencia entre cortes de día del store y `daily_reset_time` de la firma aborta el run.
- **`SessionBoundaryError`**: posición del Candidato B viva tras el cierre de sesión de contado aborta el run (el cierre forzado es invariante, no best-effort). Ver §2.3.
- **`AccountScopeError`**: el exportador detecta una cuenta con permisos de trading real/challenge y aborta antes de la primera petición (§4.1). El pipeline de datos y la cuenta de capital no se tocan jamás.
- **Determinismo total**: misma semilla + dataset + config + ficha + candidato ⇒ resultados bit-idénticos.
- **Runs reanudables**: ventanas WFA persistidas por hash de insumos.

---

## 9. Testing (EDD/TDD según `.agents/rules/`)

| Nivel | Qué cubre |
|---|---|
| Unit + property (`hypothesis`) | `smc_engine` (doble timestamp, sweeps, EQH/EQL), rango de apertura del B (invariante: el rango de los primeros N minutos no cambia con barras posteriores), riesgo y lotaje. Propiedad central: **ningún output de `on_bar(t)` cambia si se mutan barras posteriores a `t`**. Propiedad de equity: la serie intradía reconstruida del ledger es idéntica a la del simulador. |
| Golden tests | Mini-datasets sintéticos: sweep de libro, RR_FAIL conocido (A); sesión sintética con ruptura/falsa ruptura del rango y cierre forzado (B); escenarios de challenge calculados a mano para `prop_sim` (rozar/violar límites diario y total, trailing vs estático, triple rollover). |
| Integración | Pipeline completo sobre dataset de muestra: export→quality→backtest→métricas→prop-sim en segundos, en CI, por candidato. |
| Estadístico | `dsr_pbo` y `purged_cv` contra casos publicados de López de Prado. |

---

## 10. Post-GO: incubación y puente de ejecución

### 10.1. Duración y métricas de consistencia

El GO autoriza **incubación**, no un challenge: **mínimo 8 semanas** de forward test en demo con el candidato ganador (o ensemble), comparando ledger vivo vs expectativa del backtest.

Las siguientes métricas de consistencia actúan como criterios de salida por degradación durante la incubación. Se aplican de forma idéntica a todos los candidatos (A, B, ensemble); las métricas específicas por candidato (sweeps para A, aperturas para B) son **aditivas**, no sustitutivas.

#### (a) Distribución de slippage real vs backtest

- La mediana del slippage real por símbolo no debe exceder **1.5× el slippage modelado en backtest** sobre la misma ventana.
- **Criterio de breach de banda** de slippage en incubación: si el percentil 90 del slippage real supera **2.0×** el slippage modelado en backtest durante **≥ 2 semanas consecutivas**, se activa el criterio de salida por degradación de slippage.

#### (b) Tasa de rechazo del Inspector por símbolo

- La tasa de rechazo real del Inspector por símbolo no debe desviarse más de **±10 puntos porcentuales** respecto a la tasa de rechazo del backtest sobre la misma ventana temporal.
- Una desviación mayor indica que las condiciones de mercado reales difieren materialmente de las del backtest (spreads distintos, microestructura cambiada, restricciones de firma no modeladas).

#### (c) Sharpe rolling sobre la ventana de incubación

- El Sharpe rolling de **4 semanas** debe ser ≥ **0.5× el Sharpe OOS** de la validación (resultado del WFA).
- **Criterio de degradación**: si el Sharpe rolling de 4 semanas cae por debajo de ese piso durante **≥ 2 ventanas rolling consecutivas**, se activa el criterio de salida por degradación de Sharpe.

### 10.2. Criterio de salida por violación de firma (invariante)

Cualquier breach diario o total de la firma durante la incubación **cancela inmediatamente** el forward test. Este criterio no admite banda de tolerancia: una sola violación de firma en incubación es cancelación incondicional.

Lógica: una violación de firma en incubación indica que el sistema en condiciones reales viola las reglas de la prop firm. Si eso ocurre en demo, la probabilidad de violación en challenge/fondeado es inaceptable. El cancela forward test inmediatamente y el proceso requiere revisión de hipótesis antes de volver a iniciar incubación.

### 10.3. Puente de ejecución (fuera del alcance v1)

Una vez superada la incubación, el gate de salida (criterios §10.1 + §10.2 en verde durante las 8 semanas completas) habilita el diseño del **puente de ejecución hacia la plataforma de la firma** (MT5/cTrader), proyecto con cadena de issues propia.

---

## 11. Gobernanza SDD — descomposición en issues

| Issue | Alcance | Depende de |
|---|---|---|
| **A — `docs(spec)`** | Spec definitivo: contrato plugin, sección normativa del Candidato B (rango, sizing, sesiones), umbrales G/C/P/T finales, universos por candidato, fichas de firmas candidatas, presupuesto y métrica de selección del grid, bandas de incubación. **Bloquea al resto.** Cerrado por v1.2 (este documento). | — |
| **B — `feat(data)`** | Export MT5 (M1 + ticks + fichas extendidas) + calendario + sesiones + quality + store. Confirma símbolos MT5 exactos de The5ers (PA-1 de Issue A). | A |
| **C — `feat(strategy)`** | Contrato plugin + Inspector compartido + componentes comunes (`vwap_engine` portado, `zones`). | B |
| **D — `feat(strategy)`** | `smc_engine` + **diagnóstico de señal desnuda** (§2.2.1). Entregable: informe de distribución condicional por símbolo/sesión + decisión archivar/continuar el Candidato A. | C |
| **E — `feat(strategy)`** | Candidato B completo (rango, gatillo, sizing, cierre forzado). **Paralelo a D.** | C |
| **F — `feat(strategy)`** | Candidato A completo (riesgo + gatillo CT). **Condicional al resultado de D.** | D (pasa diagnóstico) |
| **G — `feat(backtest)`** | Simulador (equity intradía, fills por ticks, cierre por sesión, breaches) + costos + ledger + métricas. **Paralelo a D/E/F** (depende solo del contrato de C). | C |
| **H — `feat(validation)`** | WFA + Monte Carlo (símbolo y portafolio). Honra el techo N_trials_IS = 27 (§6.2). | G |
| **I — `feat(validation)`** | Purged K-Fold + DSR + PBO + sensibilidad. | H |
| **J — `feat(validation)`** | `prop_sim` + `verdict` con gates T + tearsheet + manifest. | I |
| **K — `feat(strategy)`** | Candidato C (TSMOM) + validación de ensemble. **Post-veredicto de A/B.** | J |

Camino crítico: A → B → C → {E, G} → H → I → J. El Candidato B puede llegar a veredicto aunque A se archive en D.

### 11.1. Preguntas abiertas para issues dependientes

Las siguientes preguntas heredadas de Issue A no bloquean este spec pero deben resolverse en los issues indicados:

- **PA-1 (Issue B)**: confirmar en la cuenta demo de The5ers los nombres de símbolo MT5 exactos para US500, NAS100 (esperado `US100`), US30 y GER40. El spec lista los nombres esperados; Issue B confirma o corrige y actualiza §1.3 y §2.x.
- **PA-2 (Issue B)**: profundidad de historia de ticks disponible en The5ers. Si la ventana de ticks es inferior a la necesaria para el modelo de spread por hora, `quality.py` debe reportarlo.
- **PA-3 (Issue C)**: la firma Python exacta del protocolo `StrategyCandidate` (tipado de `on_bar`, clase base o Protocol, sistema de registro). El spec fija la especificación normativa (§2.1); Issue C elige la forma Python.
- **PA-4 (Issue C)**: mecanismo de enforcement de `LookaheadError`: si es una guard en el método `on_bar` del simulador, en el store, o en ambos.
- **PA-5 (Issue H/I)**: forma concreta del grid IS para el Candidato B (grid lineal, log-lineal, Sobol) dentro del presupuesto N_trials_IS = 27.

### 11.2. Dependencias de runtime (vía `uv`)

`MetaTrader5`, `pandas`, `pyarrow`, `numpy`, `scipy`, `statsmodels`, `matplotlib`, `quantstats`. Dev: `hypothesis`, `pytest`. Versiones en Issue B.
