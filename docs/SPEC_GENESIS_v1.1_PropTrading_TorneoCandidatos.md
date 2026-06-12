# Spec Génesis v1.1 — Sistema de Trading Sistemático para Prop Firms (Torneo de Candidatos)

**Fecha**: 2026-06-10
**Estado**: génesis — documento fundacional del repositorio y **SSoT v1.1**. Reemplaza íntegramente al v1.0.
**Objetivo de negocio**: construir un pipeline de validación institucional que adjudique, mediante gates mecánicos, cuál de varios candidatos de estrategia (si alguno) rentabiliza bajo las reglas reales de una prop firm — y autorizar capital solo sobre esa evidencia.

### Changelog v1.0 → v1.1

1. El proyecto deja de validar **una** estrategia y pasa a ejecutar un **torneo de candidatos** bajo gates idénticos. La capa de estrategia se formaliza como contrato plugin.
2. VWAP+SMC se reduce a su pierna defendible: **Candidato A = CT sweep-fade**. La pierna PRO sale de la v1 y queda archivada como hipótesis futura (A2).
3. Se incorpora el **Candidato B: momentum intradía / Opening Range Breakout en índices** — la familia con mejor evidencia pública y mejor encaje prop — como prioridad de implementación.
4. **Candidato C (TSMOM H4/D1)** queda definido pero diferido a post-veredicto, solo para fichas de firma que permitan swing.
5. Nuevo **diagnóstico de señal desnuda** como kill-switch barato del Candidato A, previo a construir su capa de riesgo/gatillos.
6. Nuevos gates **T (torneo)**: deflación del DSR por selección entre candidatos y criterio de ensemble.
7. Cadena de issues reestructurada (A–K) con paralelismo entre candidatos.

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
| `daily_loss_limit` | Límite de pérdida diaria (% y base de cálculo: balance del día anterior vs equity) |
| `max_loss_limit` | DD máximo (% y tipo: estático o trailing; ancla del trailing) |
| `daily_reset_time` | Hora y zona horaria del corte diario |
| `equity_basis` | Si el DD diario se evalúa sobre equity flotante (lo habitual) o solo balance |
| `consistency_rule` | Si existe: % máximo del profit total atribuible a un solo día |
| `news_restrictions` | Ventanas prohibidas alrededor de noticias de alto impacto (por fase) |
| `weekend_holding` | Permitido o no — **determina la elegibilidad del Candidato C** |
| `profit_split`, `payout_cycle` | Reparto y cadencia de retiros |
| `challenge_cost` | Coste de cada intento |
| `max_lots`, `max_positions` | Límites de exposición si existen |

### 1.2. Economía del embudo

```
E[negocio] = −coste_challenges × E[intentos]
             + P(fondeo) × E[payouts | fondeado, supervivencia]
```

La probabilidad de pasar es función del **Sharpe** de la trayectoria de equity, no de la expectancy por trade; sin límite de tiempo, reducir la volatilidad a Sharpe constante aumenta P(pasar) monótonamente. Corolarios de diseño que rigen todo el spec: (a) el Sharpe se fabrica con amplitud — muchas apuestas pequeñas poco correlacionadas; (b) el riesgo por trade se calibra contra los gates P, con política distinta por fase (challenge vs fondeado); (c) la diversificación entre candidatos no correlacionados (ensemble) es la vía más barata de subir el Sharpe del portafolio.

### 1.3. Firma objetivo v1: The5ers (borrador de ficha — Issue A la verifica contra los términos vigentes)

| Campo | Valor preliminar |
|---|---|
| Plataformas | MT5 (hedge) y cTrader; el export usa MT5 |
| Programa de referencia | High Stakes: target 8% (fase 1) / 5% (fase 2) |
| `daily_loss_limit` | 5% del cierre del día anterior — **verificar en Issue A si la base es equity, balance o el mayor de ambos** (cambia `prop_sim`) |
| `max_loss_limit` | 10% |
| `min_profitable_days` | **3 días con profit ≥ 0.5% por fase** — restricción activa para `prop_sim`: no basta cruzar el target, hay que cruzarlo con la distribución diaria correcta |
| Plazo | Sin límite de tiempo; cuentas inactivas >30 días expiran |
| `news_restrictions` | **Bracketing prohibido**: órdenes pendientes alrededor de noticias de alto impacto → el calendario (capa 1) debe suprimir entradas pendientes en esas ventanas (afecta al Candidato B) |
| `weekend_holding` | Permitido en índices, con swap alto (el cierre forzado del Candidato B lo hace irrelevante; relevante para el C) |
| EAs | Permitidos **si el trader posee el código fuente**; el sistema propio cumple por construcción. Prohibidos: HFT, tick scalping, arbitraje de latencia/reverso, EAs que exploten el feed en el rollover, copy trading, hedge arbitrage entre cuentas, "one-sided betting" sin análisis |
| Otras | Residentes de EE. UU. excluidos; payouts quincenales |

---

## 2. Capa de estrategia: torneo de candidatos

### 2.1. Contrato plugin

Todo candidato implementa la misma interfaz:

- `on_bar(bar) → list[EntryIntent]` — incremental, forward-only, estructuralmente incapaz de mirar adelante.
- Esquema de parámetros propio bajo un namespace de `inspector_config.json` (`candidates.A.*`, `candidates.B.*`, …).
- Todo `EntryIntent` atraviesa el **embudo del Inspector compartido** (viabilidad R:R, lotaje contra fichas de símbolo y firma, restricciones de la firma) y produce `AUTHORIZED` o motivo de rechazo tipificado. El embudo, el ledger, el simulador y los gates son **idénticos** para todos los candidatos.
- Cada candidato corre el pipeline completo de forma aislada: su propio WFA, su propio conteo de trials, su propio DSR. **Sin contaminación entre candidatos.**

### 2.2. Candidato A — CT sweep-fade (VWAP+SMC, pierna CT)

**Hipótesis**: tras la confirmación de un barrido de liquidez (sweep de EQH/EQL) con `|Z| ≥ ct_zscore_min` respecto al VWAP anclado, el precio revierte hacia el VWAP con magnitud suficiente para superar los costes. Mecanismo: cascadas de stops agrupados en niveles salientes + reversión de inventario (Osler 2003/2005).

**Componentes**: `vwap_engine` (portado con sus tests), `smc_engine` (fractales con doble timestamp, agregación M1→TF, EQH/EQL, máquina de estados de sweep, camino libre), `zones` (PRO/MID/CT por VWAP + z-score), `risk` (SL banda vs swing + buffer ATR+spread; TP `FIXED_RR`/`STRUCT_TRAIL`/`STATIC`/`DYNAMIC`), gatillo CT.

**Universo reducido por mecanismo** (no canasta amplia): índices en horario de contado, oro, y majors solo en ventana de solapamiento Londres–NY. Filtro de sesión como parámetro de primera clase.

**La pierna PRO queda archivada (A2)**: hipótesis sin grounding diferenciado y con grados de libertad que encarecen el DSR de todo el sistema. Podrá presentarse a un torneo futuro con sección normativa propia.

#### 2.2.1. Diagnóstico de señal desnuda (kill-switch, previo a `risk`/`triggers`)

Antes de construir la capa de riesgo y gatillos del Candidato A, se ejecuta un estudio de retornos condicionales **sin ningún filtro del embudo**:

- Evento: sweep confirmado con `|Z| ≥ umbral`, por símbolo y sesión.
- Medición: retornos forward a horizontes de 5/15/30/60 minutos vs distribución incondicional; tasa de toque del VWAP antes de recorrer la distancia de stop típica; intervalos por bootstrap.
- **Criterio de archivo**: si el edge bruto condicional (antes de costes) es inferior al coste round-trip estimado **en el momento del sweep** (spread de ticks reales en esos instantes, no promedio), el Candidato A se archiva sin construir el resto. La señal que no existe desnuda no se rescata con filtros: los filtros concentran edge, no lo crean.

### 2.3. Candidato B — Momentum intradía / Opening Range Breakout en índices ★ prioridad

**Hipótesis**: el impulso direccional de la apertura de contado persiste intradía (continuación del rango de apertura). Evidencia: Zarattini & Aziz 2023 (ORB QQQ, alfa ~33% anualizado neto, 2016–2023); Zarattini, Barbon & Aziz 2024 (Sharpe 2.81 en universo amplio; replicado independientemente por QuantConnect con Sharpe 2.4 y robustez paramétrica); mecanismo emparentado con revisión por pares en Gao, Han, Li & Zhou 2018 (momentum intradía de mercado, *JFE*). Las cifras publicadas se descuentan 30–60% por decay post-publicación: el descuento no cambia la prioridad, los gates emiten el veredicto.

**Definición normativa (a fijar en Issue A):**

| Elemento | Regla |
|---|---|
| Universo | CFDs de índices: US500, NAS100, US30, GER40 (apertura de contado de cada uno) |
| Rango de apertura | Primeros N minutos de la sesión de contado (N ∈ {5, 15, 30}, parámetro del WFA) |
| Entrada | Ruptura del extremo del rango en la dirección de la primera vela de la sesión |
| Stop | Extremo opuesto del rango (o fracción ATR, parámetro) |
| Sizing | Vol-targeting: riesgo fijo en % de cuenta por trade ⇒ lotes = riesgo / distancia de stop |
| Salida | Cierre forzado al fin de la sesión de contado (sin overnight, sin swap, sin weekend) |
| Noticias | Sin entrada en ventanas restringidas por la ficha de la firma (calendario, capa 1) |

**Propiedades estructurales**: ~700–1.000 apuestas/año en 4 índices (amplitud → G1 rápido, Sharpe por diversificación), riesgo definido desde la entrada (compatible con presupuesto diario), no usa volumen (inmune a la fragilidad del `tick_volume`), P6 trivial por construcción.

### 2.4. Candidato C — TSMOM H4/D1 multi-activo (diferido)

Momentum de serie temporal con vol-targeting sobre FX+metales+índices. La evidencia más longeva del quant sistemático (Moskowitz/Ooi/Pedersen 2012; un siglo+ en estudios posteriores). Encaje prop medio: overnight/weekend (elegible solo en firmas que lo permitan), DD largos en tensión con consistency rules, acumulación lenta de trades. **Rol**: sleeve diversificador post-veredicto de A/B; su correlación estructuralmente baja con estrategias intradía es su valor.

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
| `mt5_export.py` | CLI sobre el paquete oficial `MetaTrader5`: (a) M1 OHLCV + `tick_volume`; (b) **ticks** (`copy_ticks_range`) donde el terminal los provea — insumo del modelo de spread, de los fills intrabar y del diagnóstico §2.2.1; (c) ficha del símbolo extendida: `tick_value`, `volume_step`, `stops_level`, `freeze_level`, `digits`, `swap_long`, `swap_short`, `swap_rollover_day`. Parquet crudo + metadata. |
| `calendar.py` | Calendario económico (noticias de alto impacto por divisa/índice) → ventanas por símbolo. Insumo de cumplimiento (P6) y de stress de costos. |
| `sessions.py` | **Horarios de sesión de contado por índice** (apertura/cierre, con DST del mercado subyacente) — insumo del rango de apertura del Candidato B y del filtro de sesión del A. |
| `quality.py` | Contrato de calidad: gaps anómalos, duplicados, velas corruptas, cobertura, **suficiencia de historia** (un símbolo sin historia para G1 se excluye; nunca se relajan gates). Falla ruidosamente. |
| `store.py` | Lectura normalizada tz-servidor → UTC (`zoneinfo`), iterador de barras/ticks con marcas de corte de día según `daily_reset_time` de la firma y marcas de sesión según `sessions.py`. |

### 4.1. Política de extracción de datos (invariante de cuenta)

La pregunta "¿llamará la atención extraer ticks?" se vuelve irrelevante por diseño: **la cuenta de challenge/fondeada jamás ejecuta el exportador**. Separación estricta de roles:

- **Cuenta de datos**: una cuenta demo/trial de The5ers sobre el mismo servidor MT5 (mismo feed de precios, mismos símbolos, mismas fichas) o, en su defecto, un login de solo lectura (investor password) en un terminal dedicado. Es la única cuenta que toca `mt5_export.py`.
- **Cuenta de capital**: solo la tocará el puente de ejecución post-GO. Nunca corre scripts de datos, nunca abre históricos masivos, nunca comparte terminal con el pipeline.
- **Guard en código (`AccountScopeError`)**: `mt5_export.py` verifica al conectar que `account_info().trade_mode == DEMO` o que el terminal no tiene permiso de trading; en caso contrario aborta. El invariante no es disciplina del operador: es una excepción.

Cortesía de cliente (aunque las descargas de histórico son operación estándar del terminal MT5 — todo gráfico abierto y todo run del strategy tester las hace — el exportador se comporta como un buen ciudadano):

- Descarga **secuencial y troceada**: M1 por meses, ticks por días; pausa configurable entre peticiones (0.5–2 s) y backoff exponencial ante errores del servidor.
- Un símbolo a la vez; ejecución preferente en fin de semana u horas de baja actividad.
- **Cache-first**: el terminal cachea el histórico localmente y cada chunk se persiste a Parquet con hash al recibirse; los re-runs leen del almacén y jamás re-descargan (extensión del principio de runs reanudables).
- **Realidad de profundidad de ticks**: los servidores MT5 suelen servir ticks solo para una ventana limitada (semanas–meses, dependiente del broker), mientras que el M1 llega más atrás. Plan: M1 profundo + ticks hasta donde existan; la ventana disponible queda registrada en la metadata y el modelo de spread por hora se construye sobre esa ventana. Si la historia M1 de The5ers no satisface el contrato de suficiencia (G1), se adelanta el issue de reconciliación con datos de terceros en lugar de relajar gates.

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

---

## 7. Umbrales go/no-go

Valores iniciales; el Issue A los fija. Riesgo por trade de referencia: 0.25–0.5%, calibrable por fase contra los gates P.

### 7.1. Gates G — robustez por símbolo y candidato (sobre OOS)

| # | Criterio | Umbral inicial |
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

| # | Criterio | Umbral inicial |
|---|---|---|
| C1 | Símbolos del universo del candidato que pasan G1–G9 | ≥ 60% |
| C2 | PF OOS mínimo de los que no pasan | ≥ 0.8 |

### 7.3. Gates P — economía prop a nivel de cuenta (por candidato y firma)

| # | Criterio | Umbral inicial |
|---|---|---|
| P1 | P(pasar challenge completo) | ≥ 50% |
| P2 | E[intentos hasta fondeo] | ≤ 2 |
| P3 | P(breach del límite diario en un mes fondeado, equity flotante) | < 2% |
| P4 | Supervivencia mediana fondeada | ≥ 6 meses |
| P5 | Payout neto a 12 m, percentil 25 de la distribución MC | > 0 |
| P6 | Violaciones de reglas de firma en simulación OOS | = 0 |

### 7.4. Gates T — torneo

| # | Criterio | Umbral inicial |
|---|---|---|
| T1 | DSR del candidato ganador, deflactado por el nº de candidatos del torneo | ≥ 0.95 |
| T2 | Ensemble: correlación OOS de retornos diarios entre candidatos que pasan | < 0.3 para validar ensemble; en caso contrario, solo el de mejor economía P |

### 7.5. Veredicto

- **GO (candidato X, firma Y)**: pasa C+P+T → incubación (§10) con ese candidato/universo/firma.
- **GO-ENSEMBLE**: ≥2 candidatos pasan con T2 → incubación del ensemble.
- **GO-PARCIAL**: pasa en subconjunto de símbolos → incubación restringida.
- **NO-GO**: ningún candidato pasa → revisar hipótesis, no parámetros. Se permite **una** iteración de política de riesgo/firma sin tocar parámetros de señal (registrada como trial para T1).

---

## 8. Manejo de errores

- **Fail-fast con contexto**: dataset sin calidad, config inválida, ficha incompleta → aborto explícito. Nunca degradación silenciosa.
- **`LookaheadError`**: reloj interno del simulador; leer barra/tick/swing con `confirmed_time > now` lanza excepción.
- **`DayBoundaryError`**: inconsistencia entre cortes de día del store y `daily_reset_time` de la firma aborta el run.
- **`SessionBoundaryError`**: posición del Candidato B viva tras el cierre de sesión de contado aborta el run (el cierre forzado es invariante, no best-effort).
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

## 10. Post-GO: incubación y puente de ejecución (fuera del alcance v1)

El GO autoriza **incubación**, no un challenge: N semanas de forward test en demo con el candidato ganador (o ensemble), comparando ledger vivo vs expectativa del backtest (distribución de rechazos, slippage real, spreads en los momentos críticos de cada candidato: sweeps para A, aperturas para B). El gate de salida (bandas de consistencia definidas en Issue A) habilita el diseño del **puente de ejecución hacia la plataforma de la firma** (MT5/cTrader), proyecto con cadena de issues propia.

---

## 11. Gobernanza SDD — descomposición en issues

| Issue | Alcance | Depende de |
|---|---|---|
| **A — `docs(spec)`** | Spec definitivo: contrato plugin, sección normativa del Candidato B (rango, sizing, sesiones), umbrales G/C/P/T finales, universos por candidato, fichas de firmas candidatas, presupuesto y métrica de selección del grid, bandas de incubación. **Bloquea al resto.** | — |
| **B — `feat(data)`** | Export MT5 (M1 + ticks + fichas extendidas) + calendario + sesiones + quality + store. | A |
| **C — `feat(strategy)`** | Contrato plugin + Inspector compartido + componentes comunes (`vwap_engine` portado, `zones`). | B |
| **D — `feat(strategy)`** | `smc_engine` + **diagnóstico de señal desnuda** (§2.2.1). Entregable: informe de distribución condicional por símbolo/sesión + decisión archivar/continuar el Candidato A. | C |
| **E — `feat(strategy)`** | Candidato B completo (rango, gatillo, sizing, cierre forzado). **Paralelo a D.** | C |
| **F — `feat(strategy)`** | Candidato A completo (riesgo + gatillo CT). **Condicional al resultado de D.** | D (pasa diagnóstico) |
| **G — `feat(backtest)`** | Simulador (equity intradía, fills por ticks, cierre por sesión, breaches) + costos + ledger + métricas. **Paralelo a D/E/F** (depende solo del contrato de C). | C |
| **H — `feat(validation)`** | WFA + Monte Carlo (símbolo y portafolio). | G |
| **I — `feat(validation)`** | Purged K-Fold + DSR + PBO + sensibilidad. | H |
| **J — `feat(validation)`** | `prop_sim` + `verdict` con gates T + tearsheet + manifest. | I |
| **K — `feat(strategy)`** | Candidato C (TSMOM) + validación de ensemble. **Post-veredicto de A/B.** | J |

Camino crítico: A → B → C → {E, G} → H → I → J. El Candidato B puede llegar a veredicto aunque A se archive en D.

### 11.1. Dependencias de runtime (vía `uv`)

`MetaTrader5`, `pandas`, `pyarrow`, `numpy`, `scipy`, `statsmodels`, `matplotlib`, `quantstats`. Dev: `hypothesis`, `pytest`. Versiones en Issue B.
