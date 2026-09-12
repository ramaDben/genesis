# Spec Génesis v1.5 — Sistema de Trading Sistemático para Prop Firms (Torneo de Candidatos)

**Fecha**: 2026-09-11
**Estado**: definitivo (SSoT vigente). Reemplaza íntegramente al v1.4.
**Destino operativo**: **futuros de CME operados en una prop firm de futuros** (ficha activa: MyFundedFutures, plan Rapid EOD, cuenta de 50K — §1.3.0). El régimen anterior —índices CFD sobre MT5 en firmas tipo The5ers/FTMO— queda como **histórico** y se conserva documentado, no vigente.
**Objetivo de negocio**: construir un pipeline de validación institucional que adjudique, mediante gates mecánicos, cuál de varios candidatos de estrategia (si alguno) rentabiliza bajo las reglas reales de una prop firm — y autorizar capital solo sobre esa evidencia.

### Changelog v1.4 → v1.5

**Esto no es un backfill: es una reorientación del destino operativo.** El precedente #20 (v1.3 → v1.4)
cerró placeholders de una ficha sin cambiar el rumbo. Esta versión cambia el **vehículo** (CFDs de
índices sobre MT5 → **futuros de CME**), la **firma** (The5ers/FTMO → **MyFundedFutures Rapid EOD 50K**)
y la **denominación del riesgo** (porcentajes sobre un ancla móvil → **montos absolutos** contra un
colchón que trailea y se congela). Doc-only: sin cambios en `src/genesis/` ni en `tests/`.

Secciones tocadas, en orden del documento:

1. **§1.0 (nueva) — Criterio normativo de admisión de firmas.** La ejecución automatizada permitida
   pasa a ser **condición de admisión**: sin ella un GO no es ejecutable. Con el relevamiento de seis
   firmas de futuros sobre páginas oficiales (2026-09-11) y su conclusión: **tres de seis lo prohíben**.
2. **§1.1 — Ficha de firma extendida.** `max_loss_limit` pasa a **monto absoluto** + tipo
   (`static` | `trailing_intraday` | `trailing_eod`); campos nuevos `threshold_lock_at`,
   `payout_buffer`, `min_net_profit_between_payouts`, `funded_starting_balance`, `contract_budget`,
   `automation_allowed`; `daily_loss_limit` pasa a **opcional** con semántica declarada
   (`breach` | `pause`). Tres notas normativas nuevas: doble tiempo de `trailing_eod`, por qué el
   porcentaje sobreestima `p_pass`, y el bloqueo de la simulación multi-activo concurrente hasta #96.
3. **§1.3 — Fichas de firma.** Encabezado reescrito (activa vs. históricas). **§1.3.0 (nueva)**: ficha
   MFFU Rapid EOD 50K, dos etapas, cada fila con su cita de procedencia; notas de plan, hedging y
   riesgo de plataforma. **§1.3.1 y §1.3.2 se conservan sin editar**, envueltas en nota de régimen
   histórico.
4. **§2.3 — Candidato B.** Universo → futuros CME; `Sizing` marca la grilla de `risk_pct` como anulada;
   tabla de sesiones → **tabla de anclaje del rango de apertura**, con **MGC = `PENDIENTE — no
   verificado`** y la nota de que el denominador de C1 **no se contrae**; frecuencia operativa marcada
   como estimación heredada.
5. **§2.x — Universos.** Criterio de admisión **intrínseco al activo** (la correlación no admite ni
   excluye); definición canónica única de **universo del torneo vs. universo efectivo**; **tamaño
   mínimo `|U| ≥ 2`** para emitir veredicto; universo B = MES/MNQ/MYM/MGC; M2K fuera por datos.
   Universos de A y C envueltos como históricos, sin editar.
6. **§2.x.1 (nueva) — Régimen de búsqueda (D1).** El universo múltiple es **selección**: cada
   instrumento suma al denominador del DSR, y el **ledger (#53) pasa a prerrequisito**.
7. **§4 y §4.1 — Capa 1 sin MT5.** `mt5_export.py` marcado como régimen histórico y nombrado su
   reemplazo; §4.1 reescrita en cinco bloques: invariante de cuenta trivialmente satisfecho, front
   month sin ajustar, **decisión tomada sobre la barra de empalme** (se marca y se excluye; el lookback
   no se reinicia), cambio de semántica de `tick_volume` con marcador `volume_kind`, y cortesía de
   cliente.
8. **§6.1 y §6.2 — Flujo y presupuesto de grid.** El flujo refleja que **C3 fija la canasta antes de
   `prop_sim`**; §6.2 advierte que el conteo de 27 presupone tres valores de `risk_pct` y queda sujeto
   a la re-derivación.
9. **§7.2 — Gates C.** C1 y C2 **intactos**, con el denominador explicitado y el fundamento económico
   del 60%. **C3 añadida** como **restricción de dimensionamiento, no gate de muerte**: fija `k_max` y
   su incumplimiento **reduce la canasta**. Más: controles anti-minería de la reducción, anulación de la
   grilla de `risk_pct` con sus dos cotas, requisito de reporte sin umbral (correlación y `n_eff`), y
   la constancia de que **no existe ningún gate de Pearson entre instrumentos**.
10. **§7.3 — Gates P.** P3 cambia de **definición** (colchón hasta el umbral vinculante de la ficha) y
    **conserva su umbral** `< 2%`. Nota de **delimitación de ámbito** frente a G7 — por símbolo vs. a
    nivel de cuenta — que establece que **P3 vincula**.
11. **§7.5 — Veredicto.** Regla de composición (todos los supervivientes hasta `k_max`,
    equiponderados); **precedencia explícita de C1** en GO-PARCIAL; **orden de evaluación normativo**;
    **GO-ACOTADO** como forma nueva de veredicto, con su tabla de distinción; forma canónica extendida
    a `GO (candidato X, firma Y, canasta {…})`; no-transferibilidad extendida al cambio de régimen.
12. **§7.6 — Sanity-checks.** G1 **re-derivado** sobre el universo CME, con conclusión **distinta** de
    la de v1.4. G4/T1 **declarado invalidado** hasta que exista el ledger.
13. **§11.1 — Preguntas abiertas.** Once pendientes nuevos (PA-106-A..K) con qué falta y qué bloquea;
    PA-1 y PA-2 marcadas caducas, PA-3 a PA-5 vigentes.

**Qué NO cambia.** Los umbrales de **G1–G9, C1, C2, P1, P2, P4, P5, P6, T1 y T2** son idénticos a los
de v1.4. Tampoco cambian §0 (principio rector), §1.2 (economía del embudo), §2.1 (contrato plugin),
§2.2 (Candidato A), §2.4 (Candidato C), §2.5 (higiene del torneo), §3 (arquitectura), §5 (capas 2–3),
§7.1 (gates G), §7.4 (gates T), §8 (errores), §9 (testing), §10 (incubación) ni §11/§11.2. La
numeración de v1.4 se conserva íntegra: las secciones nuevas entran como `§1.0`, `§1.3.0` y `§2.x.1`
precisamente para no desplazar ninguna referencia existente.

**Fuera de alcance de esta versión** (cada uno va en su propio change): la implementación de
`trailing_eod` y del umbral en dólares en capa 3; el exportador CME, el empalme de continuos y las
sesiones CME en capa 1; el árbitro de exposición del `contract_budget` compartido (#96); el cálculo de
C3 en capa 4; la reversión del parche de `metadata.py`; la medición y admisión de M2K; y la fidelidad
declarada de `candidate_b1_orb.yaml` (#107).

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

### 1.0. Criterio normativo de admisión de firmas

> Una firma solo es admisible como firma objetivo de Génesis si **permite ejecución automatizada**.
> Sin esa condición un veredicto GO no es ejecutable y el pipeline entero produce un número que nadie
> puede usar. El criterio es previo a la ficha: una firma que prohíbe automatizar **no se modela**.

El campo `automation_allowed` de §1.1 materializa este criterio, con cita de la fuente. Es `false` ⇒
la firma no entra al pipeline.

**Relevamiento de firmas de futuros (páginas oficiales, leídas el 2026-09-11):**

| Firma | Automatización | Cita oficial |
|---|---|---|
| Apex Trader Funding | ❌ | *"No Automation or Algorithm Usage allowed"* |
| Take Profit Trader | ❌ | UTP #1 *"No Trading Bots or Algos"*; PRO: *"All trades must be manually executed"* |
| The5ers Futures | ❌ | *"No. These practices are strictly forbidden."* |
| MyFundedFutures | ✅ | *"Traders may make use of automated trading strategies tailored to their own specific settings…"* (sin HFT) |
| Topstep | ✅ | API oficial de pago; **prohíbe VPS/VPN/servidores remotos** |
| Tradeify | ✅ | Con verificación (propiedad demostrable del código, video en vivo activándolo) |

> **Tres de seis firmas relevadas lo prohíben.** No es una anécdota de una firma: es una
> característica del sector, y significa que la premisa de Génesis —validar sistemas mecánicos— es
> compatible con una **minoría** de la industria. El criterio de §1.0 es la consecuencia normativa.

**Nota de procedencia (normativa).** El relevamiento se hizo sobre las **páginas oficiales** de cada
firma, no sobre agregadores. Los agregadores que encabezan la búsqueda afirmaban lo contrario para
Apex y para Take Profit Trader: ese dominio está sistemáticamente desactualizado o es de afiliados.
Toda evaluación futura de admisión se hace contra fuente primaria, con fecha de lectura registrada.

**El criterio se evalúa por producto, no por marca.** Una misma firma puede permitir automatización en
su producto de CFDs y prohibirla en el de futuros — ver la nota de §1.3.1 sobre The5ers.

### 1.1. Ficha de la firma (`prop_profile.json`)

Contrato de datos versionado, análogo a la ficha del símbolo. Campos mínimos:

| Campo | Descripción |
|---|---|
| `automation_allowed` | **Booleano, con cita de la fuente y fecha de lectura.** `false` ⇒ la firma **no es admisible** (§1.0) |
| `phases` | Fases del challenge: target de profit, días mínimos, plazo (o ilimitado) por fase |
| `daily_loss_limit` | **Opcional.** Límite de pérdida diaria en **monto absoluto**, con base de cálculo y **semántica declarada** (`breach` = rompe la cuenta \| `pause` = suspende el día). Una ficha **sin** DLL declarado es válida; ver §7.3 (P3) |
| `max_loss_limit` | DD máximo — **monto absoluto en la divisa de la cuenta** y tipo: `static` \| `trailing_intraday` \| `trailing_eod`; ancla del trailing |
| `threshold_lock_at` | **Nuevo.** Nivel de balance/equity a partir del cual el umbral trailing **deja de moverse** (se congela). Sin este campo, un umbral trailing es indistinguible de uno que persigue al pico para siempre |
| `daily_reset_time` | Hora y zona horaria del corte diario |
| `equity_basis` | Base de evaluación del DD: `equity` (equity flotante) o `balance` (cierre). Ver la nota de doble tiempo abajo |
| `consistency_rule` | Si existe: % máximo del profit total atribuible a un solo día, y **si incumplirla es fallo o solo condición de terminación** |
| `news_restrictions` | Ventanas prohibidas alrededor de noticias de alto impacto, con **lista T1 explícita** y **variación entre etapa de evaluación y etapa fondeada** |
| `weekend_holding` | Permitido o no — **determina la elegibilidad del Candidato C** |
| `profit_split`, `payout_cycle` | Reparto y cadencia de retiros |
| `payout_buffer` | **Nuevo.** Beneficio realizado exigido **antes del primer retiro** |
| `min_net_profit_between_payouts` | **Nuevo.** Beneficio neto mínimo entre retiros consecutivos |
| `funded_starting_balance` | **Nuevo.** Balance con el que arranca la etapa fondeada. Puede ser **0**, con saldo negativo permitido |
| `challenge_cost` | Coste de cada intento |
| `contract_budget` | Techo de exposición **total y compartido entre instrumentos, en tiempo real**, con equivalencia declarada entre tamaños (10 micros = 1 mini). Reemplaza a `max_lots`/`max_positions`, que eran escalares por símbolo |
| `min_profitable_days` | Días con profit mínimo exigidos por fase |

**Nota normativa — semántica de doble tiempo de `trailing_eod`.** El umbral se **calcula** al cierre
de la sesión, sobre el **balance de cierre**, y se **aplica contra el equity flotante** intradía. No es
un detalle de implementación: decide si un trade que sube y devuelve rompe la cuenta. Un modelo que
recalcule el umbral intradía (`trailing_intraday`) es **más duro**, y uno que lo aplique solo contra
balance es **más blando**: los tres tipos son contratos distintos y la ficha debe declarar cuál rige.

**Nota normativa — la denominación en porcentaje sobreestima `p_pass`.** Un `max_loss_limit` expresado
como `%` de un ancla móvil **da más aire a medida que el pico sube**, mientras que el umbral real de
una prop de futuros es una **cantidad fija en dólares** que trailea y luego se congela. Modelar en
porcentaje infla la probabilidad de pasar — el único número que este proyecto existe para producir.
Por eso v1.5 fija el campo en monto absoluto.

**Nota normativa — `funded_starting_balance = 0` y el denominador del sizing.** Cuando la etapa
fondeada arranca en 0 y admite saldo negativo, **cualquier sizing expresado como porcentaje del
balance queda indefinido**. El denominador normativo del sizing bajo fichas de futuros prop es el
`max_loss_limit` — el colchón —, que es el presupuesto real de la cuenta. Ver §7.2 y §11.1 (PA-106-5).

**Bloqueo explícito de la simulación multi-activo concurrente (normativo).** `contract_budget` se
**declara** en la ficha, pero este spec **prohíbe** simular varios instrumentos concurrentemente
contra un presupuesto compartido hasta que exista el árbitro de exposición (issue #96). Sin él la
capa 3 daría por ejecutadas operaciones que la cuenta real habría rechazado, y **sobreestimaría
`p_pass`**. Este bloqueo **no** alcanza al cómputo de C3, que se hace por superposición y es una cota
superior conservadora (§7.2).

Nota heredada (aplicable a las **fichas históricas** de §1.3.1 y §1.3.2, no a la ficha activa): el
campo `equity_basis` quedó resuelto como `equity` para The5ers v1. La evaluación del gate P3 de
`prop_sim` usaba equity flotante intradía como base primaria; adicionalmente, el límite se consideraba
violado si la pérdida medida contra el balance al cierre del día anterior también lo cruzaba (cota más
estricta de las dos). Ver §1.3.1 y §7.3.

### 1.2. Economía del embudo

```
E[negocio] = −coste_challenges × E[intentos]
             + P(fondeo) × E[payouts | fondeado, supervivencia]
```

La probabilidad de pasar es función del **Sharpe** de la trayectoria de equity, no de la expectancy por trade; sin límite de tiempo, reducir la volatilidad a Sharpe constante aumenta P(pasar) monótonamente. Corolarios de diseño que rigen todo el spec: (a) el Sharpe se fabrica con amplitud — muchas apuestas pequeñas poco correlacionadas; (b) el riesgo por trade se calibra contra los gates P, con política distinta por fase (challenge vs fondeado); (c) la diversificación entre candidatos no correlacionados (ensemble) es la vía más barata de subir el Sharpe del portafolio.

### 1.3. Fichas de firma

El pipeline admite **más de una firma candidata** a la vez. Cada firma se especifica con el patrón de
campos de §1.1 (`prop_profile.json`) más su propia tabla de instrumentos. La firma activa de una
corrida se selecciona explícitamente (`--firm`/`--profile`, ver §4.1 y §7.5).

- **Ficha activa (§1.3.0)**: **MyFundedFutures, plan Rapid EOD, cuenta de 50K**. Es la única firma
  admisible bajo §1.0 entre las relevadas que además conserva el mismo tipo de drawdown en las dos
  etapas.
- **Fichas históricas (§1.3.1, §1.3.2)**: The5ers y FTMO, del **régimen CFD/MT5**. Se conservan sin
  editar porque los artefactos y veredictos ya producidos están condicionados a ellas por
  `firm_profile_hash` (§7.5, no-transferibilidad). **No son vigentes.**

#### 1.3.0. MyFundedFutures — Rapid EOD 50K (**ficha activa**)

Todos los valores provienen de `help.myfundedfutures.com`, **fuente primaria leída el 2026-09-11**.
Cada fila cita su origen; lo no confirmado se declara, no se rellena.

**Etapa de evaluación (Rapid EOD, 50K):**

| Campo | Valor |
|---|---|
| `automation_allowed` | **true** — *"Traders may make use of automated trading strategies tailored to their own specific settings…"*, sin HFT *(help.myfundedfutures.com, leído 2026-09-11)* |
| Objetivo de profit | **$3.000** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `max_loss_limit` | **$2.000**, tipo **`trailing_eod`** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `threshold_lock_at` | **balance inicial + $100** (50K ⇒ $52.100; alcanzado al cerrar sobre $52.000). Política única de la firma *(help.myfundedfutures.com, leído 2026-09-11)* |
| `daily_loss_limit` | **ninguno** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `contract_budget` | **3 mini / 30 micro**, total y **compartido entre instrumentos, en tiempo real** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `consistency_rule` | **30%** — condición de **terminación**, no de fallo: excederla obliga a operar más días, no descalifica *(help.myfundedfutures.com, leído 2026-09-11)* |
| `min_profitable_days` | **4 días mínimos** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `news_restrictions` | Instrumentos **T1 permitidos** en evaluación; obligación de estar flat **2 min antes / 2 min después** de cualquier dato de alto impacto *(help.myfundedfutures.com, leído 2026-09-11)* |
| `challenge_cost` | **no verificado** — ver §11.1 |

**Etapa sim funded (Rapid EOD):**

| Campo | Valor |
|---|---|
| `funded_starting_balance` | **$0**, con saldo negativo permitido hasta que el MLL suba a breakeven — la firma lo describe como *"expected and normal"* *(help.myfundedfutures.com, leído 2026-09-11)* |
| `max_loss_limit` | **$2.000**, **`trailing_eod`** — **no cambia de tipo al fondearse** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `contract_budget` | **3 mini / 30 micro** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `news_restrictions` | Instrumentos **T1 prohibidos** en fondeada *(help.myfundedfutures.com, leído 2026-09-11)* |
| Cuentas fondeadas simultáneas | **3** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `profit_split` | **90/10** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `payout_buffer` | **$2.100** de beneficio realizado antes del primer retiro *(help.myfundedfutures.com, leído 2026-09-11)* |
| `min_net_profit_between_payouts` | **$500** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `payout_cycle` | **diario, sin tope** *(help.myfundedfutures.com, leído 2026-09-11)* |
| Consistencia de payout | **ninguna** *(help.myfundedfutures.com, leído 2026-09-11)* |
| `challenge_cost` (precio del plan) | **no verificado** — ver §11.1 |
| Política de VPS | **no verificado** — la búsqueda de "VPS" / "virtual private server" en su help center devuelve **cero resultados**; ausencia de regla **no es permiso**. Ver §11.1 |
| Comisiones por contrato | **no verificado** — dependen de la plataforma. Ver §11.1 |

**Nota normativa — por qué Rapid EOD y no Rapid estándar:**

> El plan Rapid **estándar** cambia el drawdown de EOD a **intraday trailing (HWM de equity)** al pasar
> a fondeada. Se pasaría la evaluación bajo una regla y se operaría bajo otra, más dura. Eso invalida
> la validación justo cuando empieza a importar: el `p_pass` medido no describiría la cuenta que se
> opera. Rapid **EOD** conserva el mismo tipo de drawdown en las dos etapas, y esa es la razón de la
> elección — no el precio ni la comodidad.

**Nota normativa — hedging, con su ambigüedad declarada:**

> MFFU prohíbe el hedging solo sobre el **mismo subyacente** (su ejemplo: NQ contra MNQ), y su texto
> dice *"hedging through different unrelated assets is permitted"*. **MES, MNQ y MYM son *related*
> aunque no compartan subyacente**, y MFFU remite además a la **regla 534 de CME** sobre wash trades.
> La ambigüedad entre "mismo subyacente" y "no relacionados" **no se resuelve leyendo**: queda en
> §11.1 como pendiente a confirmar con soporte **antes** de operar direcciones opuestas dentro del
> clúster de índices. Mientras no se confirme, este spec **no autoriza** posiciones simultáneas de
> signo opuesto entre MES, MNQ y MYM.

**Nota de riesgo de plataforma (normativa, aplicable a cualquier firma):**

> Si la firma reescribe su rulebook, la validación **caduca**: el `trial_id`, el `firm_profile_hash` y
> el `p_pass` quedan describiendo un contrato que ya no existe. Apex demostró en 2026 que las firmas lo
> hacen — todo su producto anterior quedó etiquetado *"Legacy"*. Por lo tanto: la ficha de firma
> registra la **fecha de lectura de cada parámetro**, y **una ficha con más de 6 meses debe
> reverificarse contra fuente primaria antes de emitir un veredicto.**

---

> **Nota de régimen histórico (§1.3.1 y §1.3.2).** Las dos fichas que siguen —The5ers y FTMO—
> describen el **régimen CFD sobre MT5** y **no son vigentes**: ninguna de las dos es admisible como
> firma objetivo bajo §1.0 en su producto de futuros. Se conservan **sin editar** porque sus valores
> siguen siendo ciertos sobre el mundo que describen y porque los veredictos ya producidos están
> condicionados a ellas por `firm_profile_hash` (§7.5). Editarlas reescribiría la historia de
> artefactos que ya existen.
>
> **Matiz sobre The5ers, que importa y es fácil de leer al revés:** su página general de prácticas
> prohibidas **sí** permite EAs con código fuente propio — pero eso aplica a su producto **CFD**. Su
> producto de **futuros** los prohíbe explícitamente (*"strictly forbidden"*, §1.0). Dos regímenes
> distintos dentro de la misma marca: por eso §1.0 se evalúa **por producto**.

#### 1.3.1. The5ers — ficha *(histórica, régimen CFD/MT5)*

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

#### 1.3.2. FTMO — ficha *(histórica, régimen CFD/MT5)*

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
| Universo | Futuros CME, front month **sin ajustar**: MES, MNQ, MYM, MGC — ver §2.x. El **universo efectivo** de una corrida excluye los instrumentos cuyo ancla de rango de apertura no esté verificada (hoy: MGC); el **denominador de C1 no se contrae** |
| Rango de apertura | Primeros N minutos de la sesión de contado, con **N ∈ {5, 15, 30}** como espacio de búsqueda IS (parámetro del WFA) |
| Entrada | Ruptura **confirmada** con cierre de vela M1 fuera del extremo del rango (no ruptura intrabar), en la dirección de la primera vela de la sesión |
| Stop | Extremo opuesto del rango (regla primaria); parámetro alternativo `atr_stop_frac ∈ {0.5, 1.0, 1.5}` en el espacio de búsqueda IS |
| Sizing | Vol-targeting: riesgo fijo `risk_pct` **como fracción del `max_loss_limit`** (§1.1) → contratos = riesgo / distancia de stop. **La grilla `{0.25%, 0.375%, 0.5%}` de v1.4 queda anulada** bajo fichas de futuros prop; los valores están pendientes de re-derivación entre el piso de operabilidad y el techo de canasta que fija §7.2 |
| Salida | Cierre forzado al **último tick de precio disponible antes del cierre de sesión de contado**; `SessionBoundaryError` si la posición sobrevive al corte |
| Noticias | Sin entrada en ventanas restringidas por la ficha de la firma según el calendario económico (`calendar.py`, capa 1) |

#### Tabla de anclaje del rango de apertura por instrumento (UTC, horario estándar)

| Instrumento | Ancla del rango de apertura | Cierre de la ventana operativa | Nota DST / estado |
|---|---|---|---|
| MES | Apertura de contado del S&P 500 — **14:30 UTC** | 21:00 UTC | DST US (NY): en EDT las horas UTC se desplazan −1 h (13:30–20:00 UTC) |
| MNQ | Apertura de contado del Nasdaq 100 — **14:30 UTC** | 21:00 UTC | Ídem MES |
| MYM | Apertura de contado del Dow 30 — **14:30 UTC** | 21:00 UTC | Ídem MES |
| MGC | **PENDIENTE — no verificado** | **PENDIENTE — no verificado** | Ver la nota obligatoria de abajo |

Los horarios exactos, incluyendo el desplazamiento DST, se materializan en `sessions.py` usando
`zoneinfo`. La tabla anterior es la referencia normativa en horario estándar (UTC sin DST).

**Nota normativa obligatoria — el oro no tiene apertura de contado:**

> El Candidato B define su rango de apertura sobre la **apertura de contado** del subyacente. Los tres
> micro-índices la tienen (la apertura del mercado de acciones). **MGC no.** El oro de COMEX cotiza en
> Globex casi 23 horas y no existe una "apertura de contado" análoga. El ancla del rango de apertura de
> MGC **queda declarada como pendiente**, a resolver contra la **página de producto oficial de CME**
> (fuente primaria) en el change de capa 1, junto con la tabla de sesiones. **No se rellena con memoria
> del modelo.**
>
> **Consecuencia de alcance:** mientras el ancla de MGC no esté verificada, el Candidato B **no puede
> correrse sobre MGC**. Eso **no** excluye a MGC del universo del torneo —su admisión es por
> propiedades intrínsecas del activo (§2.x), no por la estrategia—; lo excluye del **universo efectivo**
> del Candidato B hasta que el ancla se cierre. El universo efectivo de cada corrida se registra en la
> metadata del artefacto.
>
> **El denominador de C1 NO se contrae** (normativo). Un instrumento que no se puede evaluar cuenta
> como **no superado**, no como ausente: con el universo de §2.x, C1 ≥ 60% sigue exigiendo **3 de 4**
> aunque MGC no sea evaluable, lo que obliga al Candidato B a pasar en **los tres micro-índices**.
> Ver §2.x, *Universo del torneo y universo efectivo*.

**Propiedades estructurales**: riesgo definido desde la entrada (compatible con el presupuesto de la
firma), no usa volumen para la señal (inmune a la fragilidad del `tick_volume` — ver §4.1, donde esa
columna además cambia de semántica), P6 trivial por construcción.

> **Frecuencia operativa — estimación heredada, a re-medir.** La cifra de ~700–1.000 apuestas/año de
> v1.4 se derivó de **cuatro índices CFD sobre dos sesiones distintas** (tres estadounidenses y uno
> europeo). El universo de v1.5
> son **3 micro-índices sobre una sola sesión RTH**, más MGC con ancla pendiente. La estimación se
> conserva **solo** como orden de magnitud para los tres micro-índices y queda marcada como
> **estimación heredada del régimen CFD, a re-medir sobre datos CME reales** en el change de capa 1.
> Ver el sanity-check de G1 en §7.6.

### 2.4. Candidato C — TSMOM H4/D1 multi-activo (diferido)

Momentum de serie temporal con vol-targeting sobre FX+metales+índices. La evidencia más longeva del quant sistemático (Moskowitz/Ooi/Pedersen 2012; un siglo+ en estudios posteriores). Encaje prop medio: overnight/weekend (elegible solo en firmas que lo permitan), DD largos en tensión con consistency rules, acumulación lenta de trades. **Rol**: sleeve diversificador post-veredicto de A/B; su correlación estructuralmente baja con estrategias intradía es su valor.

### 2.x. Universos por candidato

#### Criterio de admisión al universo (normativo)

> Un instrumento entra al universo del torneo por sus **propiedades intrínsecas**: liquidez y
> profundidad de libro suficientes, costo de transacción aceptable respecto del tick, existencia de
> contrato **micro** que permita dimensionar contra el umbral de la firma, y ficha de contrato
> **pública y auditable**.
>
> **La correlación no es criterio de admisión.** Ponerla acá acoplaría el SSoT —agnóstico a la
> estrategia por diseño— a un candidato concreto, porque la estructura de correlación de un ORB no es
> la de un CT sweep-fade ni la de un TSMOM. La correlación y la dependencia de cola se gobiernan en
> **capa 4**, con C3 (§7.2), **por candidato**.

#### Universo del torneo y universo efectivo (definición canónica)

> **Universo del torneo**: los instrumentos admitidos por las propiedades intrínsecas de arriba. Es el
> **denominador de C1, siempre**.
>
> **Universo efectivo de una corrida**: el subconjunto sobre el que el candidato puede realmente
> evaluarse, excluyendo aquellos cuyos parámetros normativos no estén verificados (hoy: MGC, por el
> ancla del rango de apertura — §2.3). Se registra en la metadata del artefacto y **no altera el
> denominador de C1**: un instrumento no evaluable cuenta como **no superado**.

Contraer el denominador a los evaluables convertiría un pendiente de datos en una **rebaja del gate**
—2 de 3 = 67% pasaría, cuando 2 de 4 = 50% no—, y permitiría que un sistema mono-factorial de renta
variable estadounidense superara C1 sin validación cruzada real. **Un pendiente no es una excepción.**
§2.3 y §7.2 referencian esta definición; no la repiten.

#### Tamaño mínimo del universo para emitir veredicto (normativo)

C1 es un **porcentaje** del universo del candidato. Con un universo de un solo símbolo, pasar en ese
símbolo da **100% ≥ 60%**: la única evaluación se valida a sí misma y el gate que sostiene toda la
validación cruzada entre instrumentos deja de decir nada.

> Ninguna campaña sobre un universo de **un solo instrumento** puede emitir veredicto GO, GO-PARCIAL
> ni GO-ACOTADO. **C1 solo tiene contenido con `|U| ≥ 2`**, y ese es el mínimo normativo. No es una
> constante elegida: es el punto exacto en que C1 deja de ser vacío.

Observación que conviene declarar, porque el umbral **no** endurece de forma monótona con el tamaño:
`|U| = 2` exige **2 de 2** (100%), más estricto que `|U| = 3` (2 de 3) y que `|U| = 4` (3 de 4). Un
universo chico **no** es un universo indulgente — salvo en el caso degenerado de 1.

Dos defensas que ya existen en otras partes del spec y que conviene leer juntas acá:

1. **El universo vive en el SSoT.** Achicar el universo de un candidato es un cambio de esta sección,
   o sea un change del ciclo SDD con gate humano. **No es un parámetro de corrida.**
2. **Achicarlo después de medir es selección.** Por D1 (§2.x.1), restringir el universo habiendo visto
   resultados cuenta como ensayo y suma al denominador del DSR. Elegir el símbolo que anduvo bien y
   declararlo "el universo" es el caso de manual que el ledger (#53) existe para atrapar.

**Lo que sí está permitido con un solo símbolo:** corridas **exploratorias o de diagnóstico** que
**no emiten veredicto** — el precedente es el diagnóstico de señal desnuda de §2.2.1. Quedan
registradas en el ledger como ensayos, con la misma consecuencia sobre el DSR que cualquier búsqueda.

#### Universo del Candidato B (futuros CME)

| Instrumento | Subyacente | Contrato |
|---|---|---|
| MES | S&P 500 | Micro E-mini |
| MNQ | Nasdaq 100 | Micro E-mini |
| MYM | Dow Jones 30 | Micro E-mini |
| MGC | Oro COMEX | Micro |

Todos **front month, sin ajustar** (§4.1). El **multiplicador de cada contrato se deriva de la ficha
del símbolo** (`value_per_point = tick_value / tick_size`, `src/genesis/data/symbols.py`), **no se
transcribe a mano** en este documento: una ficha auditable es criterio de admisión, y duplicar sus
números acá solo crea una segunda fuente que puede divergir.

**M2K (micro Russell 2000)** queda **fuera del universo de v1.5 por falta de datos, no por criterio**.
Entra en v1.6 por una vía declarada **de antemano**: a priori por los criterios intrínsecos de arriba,
o condicionado a medición **contando cada evaluación como ensayo de selección** (§2.x.1).

> **Nota de régimen histórico (universos de los Candidatos A y C).** Las dos tablas que siguen son
> **heredadas del régimen CFD/MT5 y no son vigentes bajo la firma activa** (§1.3.0). Se conservan sin
> editar valores; se re-derivan cuando cada candidato entre en alcance.

#### Universo del Candidato A (CT sweep-fade) *(histórico, régimen CFD/MT5)*

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

#### Universo del Candidato C (TSMOM — implementación diferida a Issue K) *(histórico, régimen CFD/MT5)*

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

#### 2.x.1. Régimen de búsqueda sobre el universo (D1)

> El propósito del universo múltiple es **buscar en qué instrumentos funciona un candidato**, no exigir
> que funcione en todos. Bajo la regla **D1** —*cuenta como ensayo toda dimensión sobre la que
> SELECCIONAS; no cuenta ninguna sobre la que EXIGES*— eso es **selección**: **cada instrumento del
> universo cuenta como un ensayo** y suma al denominador del DSR.

Y la consecuencia operativa, que es lo que de verdad obliga:

> **El ledger de ensayos persistente (issue #53) pasa de deseable a prerrequisito.** La selección entre
> instrumentos ocurre **entre corridas**; hoy `n_trials` solo cuenta la grilla interna de una. Sin
> ledger se buscaría en cuatro instrumentos y el DSR se enteraría de uno, y **G4 dejaría de proteger en
> silencio**. **Ninguna campaña sobre el universo de §2.x puede emitir veredicto antes de que el ledger
> exista.**

Sustento (verificado contra fuente, con volumen y páginas):

- Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*, SSRN 2460551.
- White (2000), *Econometrica* 68:1097–1126; Sullivan, Timmermann & White (1999), *J. Finance*
  54:1647–1692.
- Bailey, Borwein, López de Prado & Zhu (2014), *Notices of the AMS* 61(5):458–471
  (*Minimum Backtest Length*).
- Harvey, Liu & Zhu (2016), *RFS* 29(1):5–68.

**No-colapsabilidad de contadores (normativo).** Los ensayos del régimen **CFD/MT5 no son comparables**
con los del régimen **CME** y no se acumulan en el mismo denominador. El cambio de ficha de firma y de
universo cambia `candidate_config` y por lo tanto el `trial_id`; eso es correcto y deseado. No se crea
ninguna lista blanca de equivalencias entre regímenes.

**Toda ampliación futura del universo se declara antes de medir** (issue #88). Una hipótesis
pre-registrada **interpreta** un resultado; nunca **relaja** un gate — ver §7.5.

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
| `mt5_export.py` *(régimen histórico)* | CLI sobre el paquete oficial `MetaTrader5`: (a) M1 OHLCV + `tick_volume`; (b) **ticks** (`copy_ticks_range`) donde el terminal los provea — insumo del modelo de spread, de los fills intrabar y del diagnóstico §2.2.1; (c) ficha del símbolo extendida: `tick_value`, `tick_size`, `volume_step`, `stops_level`, `freeze_level`, `digits`, `swap_long`, `swap_short`, `swap_rollover_day`. Parquet crudo + metadata. **Componente del régimen CFD/MT5; no se elimina, deja de ser la vía activa.** |
| *exportador CME* (nombre y forma: change de capa 1) | Reemplazo activo de `mt5_export.py` bajo el régimen de futuros: M1 + ticks del **front month sin ajustar**, ficha de contrato por venue, marcador `volume_kind` en la metadata. El proveedor de datos es una **decisión abierta declarada** — ver §11.1. |
| `calendar.py` | Calendario económico (noticias de alto impacto por divisa/índice) → ventanas por símbolo. Insumo de cumplimiento (P6) y de stress de costos. |
| `sessions.py` | **Horarios de sesión de contado por índice** (apertura/cierre, con DST del mercado subyacente) — insumo del rango de apertura del Candidato B y del filtro de sesión del A. |
| `quality.py` | Contrato de calidad: gaps anómalos, duplicados, velas corruptas, cobertura, **suficiencia de historia** (un símbolo sin historia para G1 se excluye; nunca se relajan gates). Falla ruidosamente. |
| `store.py` | Lectura normalizada tz-servidor → UTC (`zoneinfo`), iterador de barras/ticks con marcas de corte de día según `daily_reset_time` de la firma y marcas de sesión según `sessions.py`. |

### 4.1. Política de extracción de datos

#### (a) Invariante de cuenta — trivialmente satisfecho bajo CME

Con futuros de CME el **proveedor de datos es independiente del broker**: los datos no salen de la
cuenta de la prop firm. El invariante "cuenta de datos ≠ cuenta de capital" y el guard
`AccountScopeError` quedan por lo tanto **trivialmente satisfechos**, y se documenta la simplificación
en vez de arrastrar una defensa que ya no defiende nada. **El guard no se elimina**: sigue protegiendo
al régimen histórico y no cuesta nada.

#### (b) Empalme de continuos: front month sin ajustar

Se opera y se mide sobre el **front month sin ajustar**. El corte al contrato siguiente lo decide el
volumen, pero **se aplica únicamente en la frontera de cierre de sesión, nunca intradía**.

Tres razones, y ninguna es de conveniencia: si el cruce de volumen cae dentro de RTH, cortar ahí
**corrompe el rango de apertura de ese mismo día**; un ORB intradía **nunca sostiene a través del
roll**, así que no hay posición que empalmar; y el **ajuste hacia atrás corrompe los niveles de precio**
de los que depende el rango de apertura. Las firmas además exigen operar el front month.

#### (c) El salto de nivel en el roll se declara y se trata (normativo)

Sin ajuste, la serie tiene un **gap artificial de base/carry en cada vencimiento** — cuatro veces al
año, en marzo, junio, septiembre y diciembre. No declararlo inyecta volatilidad falsa en todo
indicador con memoria multi-día (ATR de dimensionamiento, filtros de volatilidad, rangos previos).

> **Decisión normativa:** la **barra de empalme se marca en la metadata y se excluye** del cómputo de
> todo indicador con memoria multi-día. El **lookback no se reinicia**: se saltea la barra contaminada.

Esta decisión se toma acá y no se delega, porque su consecuencia es cuantitativa y directa: el **ATR
dimensiona la posición en dólares**, así que un gap de base/carry contaminando el lookback deforma el
sizing de decenas de sesiones posteriores, y las dos alternativas dan ATR distintos. Reiniciar el
lookback, además, destruye historia útil cuatro veces al año sin necesidad.

El change de capa 1 puede **anular** esta elección **únicamente con evidencia medida sobre datos CME
reales, registrada como delta a este spec** — no por conveniencia de implementación.

#### (d) `tick_volume` cambia de semántica

De **conteo de ticks** (MT5) a **volumen negociado real** (CME). Misma columna, significado distinto, y
`strategy/common/vwap_engine.py` ya la consume como si fuera volumen.

> El export **debe** escribir un marcador explícito `volume_kind` en la metadata del dataset. Dos
> datasets donde la misma columna significa cosas distintas **no pueden convivir sin marca**.

#### (e) Cortesía de cliente y profundidad de historia

La pregunta "¿llamará la atención extraer datos?" se vuelve irrelevante por diseño: **la cuenta de
challenge/fondeada jamás ejecuta el exportador**. Separación estricta de roles:

- **Cuenta de datos** *(régimen histórico, MT5)*: una cuenta demo/trial de la firma de datos activa sobre el mismo servidor MT5 (mismo feed de precios, mismos símbolos, mismas fichas) o, en su defecto, un login de solo lectura (investor password) en un terminal dedicado. Es la única cuenta que toca `mt5_export.py`. Bajo CME la separación es estructural: el proveedor de datos no es el broker.
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
                              │              │               │      C1, C2 ──► C3
                              │              │               │             ▼
                              │              │               │    k_max + canasta operada
                              │              │               │             ▼
                              │              │               │    prop_sim (SOBRE esa canasta)
                              └──────────────┴───────────────┴─────────────┘
                                             ▼
                       verdict ──► T1 (deflación de torneo) ── T2 (ensemble)
                                             ▼
              VEREDICTO por firma + canasta + tearsheet + manifest
```

Reglas sin excepción: solo trades OOS alimentan la validación; trials contados mecánicamente por candidato; gates P a nivel de cuenta, nunca por símbolo; manifest reproducible con un comando.

**Orden normativo (§7.5).** Los gates C se evalúan **antes** que los P, y C3 fija `k_max` y la
composición de la canasta **antes** de que `prop_sim` corra. `prop_sim` y P1–P6 se evalúan **sobre la
canasta que se va a operar**, nunca sobre el conjunto completo de supervivientes: si la canasta cambia,
cambian la frecuencia de trades, el tiempo hasta el objetivo y el ratio de consistencia, y el veredicto
describiría otra cuenta. Si la canasta de `k_max` falla los gates P, el veredicto es **NO-GO**; está
prohibido reintentar con canastas más chicas.

### 6.2. Presupuesto de grid IS y métrica de selección (definitivos)

#### Presupuesto de trials IS por candidato por ventana WFA

**`N_trials_IS = 27`** (grid completo 3×3×3) por candidato por ventana WFA.

Derivación para el Candidato B (3 parámetros libres):

| Parámetro | Espacio de búsqueda IS | Niveles |
|---|---|---|
| `N` (minutos del rango) | {5, 15, 30} | 3 |
| `atr_stop_frac` (fracción ATR del stop) | {0.5, 1.0, 1.5} | 3 |
| `risk_pct` (riesgo por trade, **fracción del `max_loss_limit`**) | **PENDIENTE de re-derivación** — la grilla de v1.4 queda anulada (§7.2) | 3 *(supuesto de v1.4, sujeto a cambio)* |

Grid completo: 3 × 3 × 3 = **27 combinaciones**. Este es el presupuesto máximo de trials IS por candidato por ventana WFA. El diseño concreto del muestreo IS (grid lineal, log-lineal, Sobol) se decide en Issue H dentro de este presupuesto.

> **Advertencia normativa (v1.5).** El conteo de 27 **presupone tres valores operables de `risk_pct`**.
> Bajo fichas de futuros prop esa grilla está anulada y sus valores pendientes (§7.2): si la
> re-derivación deja menos de tres, el presupuesto deja de ser 3×3×3 y el sanity-check de G4 debe
> rehacerse (§7.6). El techo de 27 se conserva como **cota superior**, no como conteo vigente.

Nota: `risk_pct` es un parámetro de sizing que no altera la señal ni el conteo de trades; las configuraciones de señal distintas son 3 × 3 = 9. Para el conteo de trials del DSR (que penaliza la búsqueda sobre la **forma** de la señal) lo relevante son las 9 configuraciones de señal. Esta distinción se documenta aquí como restricción de diseño; el cálculo exacto del DSR se implementa en Issue I.

El techo de **N_trials_IS = 27** es una restricción de diseño del WFA que Issue H debe honrar. No se puede superar el presupuesto añadiendo parámetros o niveles sin actualizar este spec.

#### Métrica de selección IS: DSR-IS

La métrica de selección IS del WFA es **DSR-IS** (Deflated Sharpe Ratio calculado sobre los trials IS del candidato). Esta elección coincide con la que ya señalaba §6 del v1.1 y se confirma aquí como definitiva.

Justificación: DSR-IS penaliza la multiplicidad de comparaciones IS directamente en la métrica de selección, reduciendo el sesgo de overfitting IS antes de que llegue al OOS. Es coherente con el gate G4 (DSR OOS ≥ 0.95) al usar la misma familia de correcciones.

#### Coherencia presupuesto de trials con DSR ≥ 0.95

Con N_trials_IS = 27, la deflación del Sharpe por el término de corrección del DSR es modesta: `ln(27) ≈ 3.30`, muy por debajo de los cientos o miles de trials que erosionan el DSR por debajo de 0.95. El gate G4/T1 (DSR ≥ 0.95) es alcanzable con este presupuesto. Ver §7.2 para el sanity-check completo.

---

## 7. Umbrales go/no-go (definitivos)

Los umbrales de esta sección son **definitivos**. La referencia de riesgo por trade de v1.4
(0.25–0.5% del balance) **queda anulada** bajo fichas de futuros prop: el denominador pasa a ser el
`max_loss_limit` y los valores están pendientes de re-derivación entre las dos cotas que fija §7.2.

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
| C1 | Símbolos del **universo del torneo** (§2.x) del candidato que pasan G1–G9 | ≥ 60% |
| C2 | PF OOS mínimo de los que no pasan | ≥ 0.8 |

El denominador de C1 es el **universo normativo**, no el efectivo: un instrumento que no se puede
evaluar cuenta como **no superado** (§2.x). Con `|U| = 4`, C1 ≥ 60% exige **3 de 4**. El mínimo de
universo para emitir veredicto es `|U| ≥ 2` (§2.x).

**Fundamento económico del 60%.** Que un candidato aparezca en **exactamente uno** de varios
instrumentos emparentados es **evidencia en contra** del candidato, no un éxito parcial: un edge
estructural se apoya en un mecanismo, y los mecanismos no respetan fronteras de ticker (Asness,
Moskowitz & Pedersen, *Value and Momentum Everywhere*, *J. Finance* 68(3):929–985). Para cualquier
universo de `n ≥ 2`, aprobar en uno da `1/n ≤ 50% < 60%`, y con el universo de §2.x aprobar en dos da
50%: **ambos son NO-GO mecánico por C1**, sin necesidad de ninguna regla adicional.

#### C3 — restricción de dimensionamiento de canasta (**no** es un gate de pase/fallo)

C1 y C3 responden preguntas **ortogonales**, y colapsarlas en un mismo veredicto es un error de
diagnóstico:

| Pregunta | La responde | Qué significa fallar |
|---|---|---|
| ¿El edge **generaliza** entre instrumentos? | **C1** | No hay ventaja robusta ⇒ **NO-GO** |
| ¿La canasta **entra** en el presupuesto de la cuenta? | **C3** | No alcanza el capital ⇒ **se opera una canasta más chica** |

Un candidato puede tener edge en 3 de 4 instrumentos (C1 ✓) y aun así solo poder llevar 1 a la vez.
Matarlo por lo segundo sería emitir *"no hay ventaja"* cuando lo que ocurre es *"no alcanza el
colchón"*.

| # | Criterio | Umbral definitivo | Efecto al incumplirse |
|---|---|---|---|
| C3 | Drawdown conjunto intradía p95 en **días de señal simultánea**, sobre la canasta operada | ≤ 50% del `max_loss_limit` | **Se reduce la canasta**, no se emite NO-GO |

**Cómo se determina la canasta (normativo, sin búsqueda):**

> Para cada tamaño `k ∈ [1, |supervivientes|]`, la composición de la canasta la fija una **regla
> declarada antes de la campaña** (§2.x.1, #88) — **una sola canasta por tamaño**, nunca un conjunto de
> alternativas. Se evalúa C3 sobre **todas** esas canastas y se define
>
> `k_max = max { k : C3(k) ≤ 50% del max_loss_limit }`
>
> **No se desciende parando en el primer tamaño que cumple.** Esa formulación presupone **monotonía**
> —que si `k` no cumple, `k+1` tampoco— y la monotonía **no se sostiene**: el p95 no es subaditivo, y
> sobre todo el conjunto de condicionamiento *cambia con `k`*, porque "días de señal simultánea" es un
> conjunto distinto para cada canasta. Además, podar al miembro **menos** correlacionado (MGC frente a
> los tres índices) puede **empeorar** la cola conjunta en lugar de mejorarla. Evaluar todos los `k`
> cuesta cuatro corridas y elimina el supuesto.
>
> **Con `k = 1` no hay cola conjunta y C3 queda vacío**, porque no existe simultaneidad con nadie. C3
> **no** se transforma en otro gate ahí: simplemente no aplica, y la protección la dan dos gates que ya
> existen y que sí corren sobre un instrumento único — **P3** (§7.3: probabilidad de que la pérdida
> intradía de un solo día consuma el colchón, **a nivel de cuenta**; con `k = 1` la cuenta *es* ese
> instrumento) y **G6** (MC MaxDD multi-día p95 ≤ 50% del `max_loss_limit`).
>
> **C3 no emite NO-GO en ningún caso.**

**El presupuesto que ata es el colchón, no el techo de contratos:**

> El `contract_budget` de Rapid EOD (30 micros) **no restringe**: cuatro micro-índices están lejísimos
> del techo. Lo que restringe es el **colchón de $2.000**, vía el riesgo por trade. Por lo tanto
> `k_max` **no es un dato de la firma: es el resultado de una calibración que el proyecto controla**, y
> el artefacto debe reportar la pareja (`risk_pct`, `k_max`) **con fecha de pre-registro**, no solo
> `k_max`.

**Controles anti-minería de la reducción (normativos).** Reducir la canasta es **elegir**, y elegir
mirando el resultado es data mining. Las tres reglas que lo impiden sin matar al candidato:

1. **La reducción es por tamaño, no por búsqueda.** Está **prohibido** evaluar subconjuntos
   alternativos del mismo tamaño hasta dar con uno que pase. Por eso la regla de composición fija
   **una** canasta por cada `k`.
2. **La composición la fija una regla declarada antes de la campaña** (#88), y el tipo de regla
   determina qué hace falta para que sea admisible:
   - **Regla intrínseca** (mayor liquidez, menor costo relativo al tick, mayor número de trades): no
     mira desempeño, **no agrega ensayos**, admisible siempre.
   - **Regla de desempeño** ("el mejor por Sharpe / PF / P&L"): es **selección**. Admisible
     **únicamente si el ledger de ensayos (#53) está operativo y alimenta el `n_trials` de G4** con los
     instrumentos evaluados. Hoy G4 se calcula por símbolo sobre su propia grilla y no ve a los otros
     tres, y T1 deflacta por número de **candidatos**, no de instrumentos: sin ledger, una regla de
     desempeño no está pagada, está **sin contabilizar**. §2.x.1 ya prohíbe emitir veredicto sin
     ledger, así que el caso no debería presentarse.
3. **La reducción se declara en el veredicto**: produce **GO-ACOTADO** con la canasta explícita
   (§7.5), no un GO a secas.

**Recomendación explícita, no obligación:** elegir "el mejor por métrica" es la opción más ruidosa que
hay — el ganador de la muestra es en parte suerte (DeMiguel/Garlappi/Uppal; Bates & Granger). Cuando el
capital obliga a quedarse con uno, una regla **intrínseca** es preferible a una de desempeño, porque no
agrega ensayos y no hereda el sesgo del ganador. La elección de la regla queda al pre-registro.

#### La grilla de `risk_pct` de v1.4 queda anulada para futuros prop

Hay **dos** denominadores posibles para el sizing y **los dos rompen** con la grilla heredada:

| Denominador | Qué da con `{0.25%, 0.375%, 0.5%}` | Veredicto |
|---|---|---|
| **% del balance** (v1.4) | En sim funded el balance **arranca en $0** y puede ir negativo | **Indefinido** |
| **% del nominal** ($50.000) | $125 / $187,50 / $250 por trade — o sea **6,25% a 12,5% del colchón real de $2.000 en un solo trade**; cuatro stops simultáneos = $500 a $1.000, hasta el 50% de la cuenta en una mañana | **Operable pero temerario** |
| **% del `max_loss_limit`** ($2.000) | $5 / $7,50 / $10 por trade. Un stop ordinario de 50 puntos en MNQ cuesta **$100 por micro**; 4 ticks de MES ya son $5 | **Físicamente inoperable** |

> **Denominador normativo del sizing en fichas de futuros prop: el `max_loss_limit`** (el colchón), que
> es el presupuesto real de la cuenta y no depende de un balance que puede ser cero o negativo.
>
> Los **valores** de la grilla de `risk_pct` **no se heredan de v1.4**: quedan pendientes de
> re-derivación contra las distancias de stop reales en datos CME, sujetos a dos cotas que este spec sí
> fija:
>
> - **Piso de operabilidad**: `risk_per_trade ≥` el costo de un stop típico del candidato en **un**
>   contrato micro. Por debajo de eso el sizing no puede expresarse en contratos enteros.
> - **Techo de canasta**: `k_max × risk_per_trade ≤ 50% del max_loss_limit` — que es C3 escrito como
>   restricción de sizing en vez de como medición.
>
> La grilla debe caber entre las dos cotas. Si no cabe ninguna configuración, la conclusión es que **la
> cuenta es demasiado chica para el candidato** — y eso se reporta, no se fuerza.

**Consecuencia sobre §6.2:** el presupuesto `N_trials_IS = 27` (3×3×3) supone **tres** valores de
`risk_pct`. Si la re-derivación deja menos de tres valores operables, el conteo de trials cambia y el
sanity-check de G4 debe rehacerse. Ver §7.6 y §11.1 (PA-106-5).

#### Requisito de reporte sin umbral (no es un gate)

> La **matriz de correlación OOS** del P&L diario entre los instrumentos de la canasta y su **número
> efectivo de apuestas** `n_eff = n / (1 + (n−1)·ρ̄)` se **reportan obligatoriamente** en el artefacto
> del veredicto. El veredicto declara la amplitud efectiva de la canasta; **no se le aplica umbral.**

#### Por qué C3 mira la cola y no Pearson

**Un solo gate, anclado a G6.** El umbral de C3 —**≤ 50% del `max_loss_limit`**— es la **forma exacta
de G6**, aplicada a la canasta conjunta restringida a días de señal simultánea en vez de a un símbolo
aislado: el mismo número, la misma magnitud (drawdown contra el presupuesto de la firma) y la misma
dirección de consecuencia.

**No existe ninguna fila de gate con umbral de correlación de Pearson entre instrumentos**, y la
ausencia es deliberada. Un gate del tipo `ρ < 0.3` "porque T2 usa 0.3" no se sostiene por tres razones:

1. **Poblaciones distintas.** T2 mide correlación entre **candidatos estratégicos** diseñados para no
   parecerse. Un gate entre **activos** operados por la **misma** estrategia mediría otra cosa: dos
   índices de gran capitalización estadounidense con el mismo gatillo a la misma hora comparten una
   beta de mercado estructural, y su línea base no es la de dos estrategias distintas.
2. **Consecuencia asimétrica.** Fallar T2 **no descalifica** a nadie: se descarta el ensemble y se
   opera el mejor individual. Tomar prestado el número invirtiéndole la consecuencia no es un anclaje.
3. **Redundancia con los gates P.** `prop_sim` simula la **cuenta conjunta**; la correlación ya está
   incorporada en P1–P5 por construcción.

Lo que sí faltaba, y es lo que C3 aporta, es una cota **explícita y legible sobre la cola conjunta**,
que ni Pearson ni el promedio de `prop_sim` exhiben:

> **Correlación lineal baja del P&L no es independencia.** En la medición que motivó esta restricción,
> las señales del ORB coinciden en dirección el **88% de los días** entre MES y MNQ; un shock macro a
> los pocos minutos de la apertura golpea los stops de los tres índices a la vez, y ahí la
> **dependencia de cola tiende a 1**. Sobre un umbral trailing de $2.000 ese es el escenario de ruina,
> y ninguna correlación de Pearson lo captura.

**Evidencia de por qué existe la restricción** (no es la justificación del universo, que es intrínseca
— §2.x). Dos mediciones sobre `data/raw/*/m1/`, ventana 2025-10-30 → 2026-06-30:

| Par | Corr. de **retornos** (130 d) | Corr. del **resultado ORB** (170 d) |
|---|---|---|
| MES–MNQ | 0,947 | 0,281 |
| MES–MYM | 0,847 | 0,445 |
| MES–MGC | 0,435 | 0,131 |
| MNQ–MYM | 0,684 | 0,099 |
| MNQ–MGC | 0,407 | 0,162 |
| MYM–MGC | 0,429 | 0,033 |

**Límites de la medición, declarados:** N = 170 ⇒ error estándar ≈ 0,077, o sea los valores bajo ~0,15
**no se distinguen de cero ni de 0,25**; la ventana es de 8 meses y un solo régimen; el proxy de ORB no
tiene stops, costos, filtro RVOL ni salida Chandelier. **La medición no fija ningún umbral** — el
umbral de C3 viene del anclaje a G6. La medición justifica por qué la restricción existe y por qué mira
la cola. Los mismos números entran, sin umbral, en el requisito de reporte de amplitud efectiva.

#### C3 es computable sin el árbitro de exposición (#96)

> C3 se calcula por **superposición de las curvas de equity intradía por símbolo**, restringida a los
> días de señal simultánea. Esa superposición **ignora el `contract_budget` compartido**, y por eso es
> una **cota superior conservadora**: la cuenta real no habría podido sostener **más** posiciones de las
> que el presupuesto permite, nunca menos. C3 por lo tanto **no depende de #96** y no cae bajo el
> bloqueo de simulación concurrente de §1.1. Lo que sí depende de #96 es **operar** la canasta y emitir
> cualquier gate P sobre ella — ver §11.1.

### 7.3. Gates P — economía prop a nivel de cuenta (por candidato y firma)

| # | Criterio | Umbral definitivo |
|---|---|---|
| P1 | P(pasar challenge completo) | ≥ 50% |
| P2 | E[intentos hasta fondeo] | ≤ 2 |
| P3 | P(en un mes fondeado, la pérdida intradía de **un solo día** consuma el **colchón disponible hasta el umbral vinculante** al inicio de ese día) | **< 2%** |
| P4 | Supervivencia mediana fondeada | ≥ 6 meses |
| P5 | Payout neto a 12 m, percentil 25 de la distribución MC | > 0 |
| P6 | Violaciones de reglas de firma en simulación OOS | = 0 |

**Definición normativa del umbral vinculante de P3:**

> El **umbral vinculante** es el `daily_loss_limit` de la ficha **si está declarado**, y el
> `max_loss_limit` trailing **si no lo está**. En MFFU Rapid EOD 50K el denominador arranca en
> **$2.000** y es una cantidad que el simulador ya sigue: la distancia entre el equity y el umbral
> trailing, que varía a lo largo del camino y **se congela** cuando el umbral se bloquea
> (`threshold_lock_at`, §1.1).

**Las dos salidas descartadas, y por qué:**

> Marcar P3 como **N/A** porque Rapid EOD no tiene límite diario sería un **bypass**: una estrategia que
> pierde $1.800 en una mañana y recupera $1.700 a la tarde no viola ninguna regla de MFFU, pero está a
> $200 de liquidar la cuenta — y sacaría GO. **Inventar** un límite diario propio metería una constante
> de política de riesgo dentro del SSoT, que debe ser mecánico y derivado del contrato. P3 se ancla al
> control **vinculante que la ficha declare**: sin constantes nuevas y con el mismo umbral del 2%.

**Delimitación frente a P4:**

> **P3 es de un día** — la cola izquierda de la distribución diaria; atrapa a la estrategia de buen
> camino promedio con un día catastrófico cada tanto. **P4 es del camino** — la acumulación a lo largo
> de meses; atrapa a la que sangra de a poco.

**Nota normativa obligatoria — delimitación de ámbito frente a G7:**

> P3 y G7 **no miden lo mismo y ninguno domina al otro**, porque operan en ámbitos distintos que este
> mismo documento separa en los títulos de sus secciones: **G7 es un gate G — "robustez por símbolo y
> candidato"** (§7.1), evaluado por Monte Carlo **sobre un símbolo aislado**; **P3 es un gate P —
> "economía prop a nivel de cuenta"** (§7.3), evaluado por `prop_sim` **sobre la cuenta conjunta**.
>
> La diferencia es material bajo el universo de §2.x. Con señales que coinciden en dirección el 88% de
> los días entre MES y MNQ, caídas intradía moderadas **por símbolo** pasan G7 holgadamente y, sumadas
> en la cuenta, consumen el colchón de $2.000 en una sola mañana. **G7 no puede ver ese evento**: no
> existe en ninguna de sus corridas por símbolo.
>
> Segunda diferencia, propia de la etapa fondeada: **los retiros vacían el excedente** sobre el colchón.
> Tras un payout, la distancia al umbral trailing al inicio del día puede ser de unos pocos cientos de
> dólares, y un día adverso ordinario la consume. La MC de G7 corre sobre una curva continua **sin
> retiros de capital**, así que tampoco ve ese evento.
>
> Por lo tanto **P3 vincula**, y es la única salvaguarda de la cuenta fondeada contra el shock intradía
> de cartera. El umbral se mantiene en **< 2%**.

Los gates **G6 y G7 no cambian de redacción**: referencian `max_loss_limit` simbólicamente y la
denominación en monto absoluto se hereda de §1.1 sin tocarlos.

### 7.4. Gates T — torneo

| # | Criterio | Umbral definitivo |
|---|---|---|
| T1 | DSR del candidato ganador, deflactado por el nº de candidatos del torneo | ≥ 0.95 |
| T2 | Ensemble: correlación OOS de retornos diarios entre candidatos que pasan | < 0.3 para validar ensemble; en caso contrario, solo el de mejor economía P |

### 7.5. Veredicto

- **GO (candidato X, firma Y, canasta {…})**: pasa C+P+T → incubación (§10) con ese candidato/canasta/firma.
- **GO-ENSEMBLE**: ≥2 candidatos pasan con T2 → incubación del ensemble.
- **GO-PARCIAL**: el candidato pasa **C+P+T** —lo que incluye **C1 ≥ 60% del universo**— pero no en la
  totalidad de sus instrumentos. La incubación se restringe a los supervivientes, **equiponderados**.
  **GO-PARCIAL nunca es una vía para eludir C1**: un candidato que falla C1 es NO-GO. Con el universo de
  cuatro instrumentos de §2.x, C1 ≥ 60% exige **3 de 4**.
- **GO-ACOTADO (candidato X, firma Y, canasta {…})**: pasa C+P+T sobre una canasta de tamaño `k_max`
  **menor** que el número de instrumentos en los que superó los gates, porque el presupuesto de riesgo
  de la cuenta no permite llevarlos todos a la vez. **Es un GO** — ver abajo.
- **NO-GO**: ningún candidato pasa → revisar hipótesis, no parámetros. Se permite **una** iteración de política de riesgo/firma sin tocar parámetros de señal (registrada como trial para T1).

#### Regla de composición: se conservan TODOS los supervivientes, no el mejor

> Un candidato que supera los gates en varios instrumentos se opera en **todos los que el presupuesto
> de riesgo de la cuenta permita llevar a la vez** (`k_max`, §7.2), **equiponderados**. Mientras `k_max`
> alcance para todos los supervivientes, **no se selecciona el de mejor métrica**: el ganador de la
> muestra es en parte suerte, y preferirlo empeora el resultado esperado fuera de muestra.
>
> Cuando `k_max` es **menor** que el número de supervivientes, la canasta se recorta **por capital**,
> con la regla de composición declarada de antemano (§7.2). Eso **no** convierte al veredicto en NO-GO
> ni en GO-PARCIAL: es un **GO-ACOTADO**.

Sustento (verificado contra fuente):

- DeMiguel, Garlappi & Uppal (2009), *RFS* 22(5):1915–1953 — sobre 14 modelos y 7 datasets, ninguno
  bate consistentemente a 1/N fuera de muestra.
- Bates & Granger (1969), *JORS* 20:451–468; Timmermann, *Forecast Combinations* (Handbook of Economic
  Forecasting, cap. 4) — las combinaciones baten a la elección del mejor modelo individual ex ante, y
  las simples suelen dominar a las refinadas.
- Asness, Moskowitz & Pedersen (2013), *J. Finance* 68(3):929–985 — primas consistentes en ocho
  mercados y clases de activo; promediar entre mercados mitiga el ruido que no es común a la señal.

#### Orden de evaluación (normativo)

Si `prop_sim` corriera sobre la canasta completa de supervivientes y **después** C3 la recortara, el
veredicto certificaría métricas de cuenta —P1 probabilidad de pasar, P4 supervivencia, P5 payout— de un
portafolio **que no es el que se va a operar**. Con una canasta de 1 en vez de 3 cambian la frecuencia
de trades, el tiempo hasta el objetivo de profit y el ratio de la regla de consistencia del 30%.

```
WFA + G1–G9 (por símbolo)
   └─► C1, C2 (¿el edge generaliza?)
        └─► C3 → k_max y composición de la canasta operada
             └─► prop_sim + P1–P6 SOBRE ESA CANASTA, no sobre el conjunto de supervivientes
                  └─► T1, T2
                       └─► Veredicto
```

> **Si la canasta de tamaño `k_max` no supera los gates P, el veredicto es NO-GO.** Está **prohibido**
> reintentar con canastas más chicas hasta que alguna pase: eso sería exactamente la búsqueda sobre
> subconjuntos que la regla de composición pre-registrada existe para impedir, y entraría por la puerta
> de atrás.

#### GO-ACOTADO — un GO acotado por capital

> **GO-ACOTADO (candidato X, firma Y, canasta {…})**: el candidato pasa C+P+T sobre una canasta de
> tamaño `k_max` menor que el número de instrumentos en los que superó los gates. **Es un GO**, no un
> NO-GO degradado ni un GO-PARCIAL: la ventaja existe y generaliza (C1 lo certificó); lo que falta es
> **capital**.
>
> El artefacto registra obligatoriamente: los instrumentos que superaron los gates, `k_max`, la
> calibración `risk_pct` que lo produjo, la regla de composición aplicada y su **fecha de
> pre-registro**. Un GO-ACOTADO cuyo `k_max` se explique por una calibración de riesgo elegida
> **después** de ver los resultados **no es un GO**: es minería.

| Veredicto | Qué falló | Lectura |
|---|---|---|
| **NO-GO** | C1, o los gates G/P/T | No hay ventaja robusta, o no rentabiliza bajo las reglas |
| **GO-PARCIAL** | Nada; pasó C1 pero no en el 100% del universo | La ventaja existe pero no es universal |
| **GO-ACOTADO** | Nada; el capital no alcanza para la canasta completa | La ventaja existe y generaliza; **falta cuenta, no edge** |

**No existe un piso de `k_max ≥ 2`.** Exigirlo aplicaría un principio de **construcción de cartera**
(1/N) a una restricción de **factibilidad**: 1/N dice qué hacer *cuando podés sostener N*; si el capital
solo permite 1, no hay elección entre concentrar y diversificar. Además, C1 sigue exigiendo 3 de 4, así
que un GO-ACOTADO con `k = 1` solo es alcanzable por un candidato que demostró ventaja en **al menos
tres** instrumentos — la validación cruzada ocurrió, lo que se acota es la ejecución. Y la cola en
`k = 1` no queda descubierta: la cubren **G6**, **G7** y **P3**.

Lo que sí se exige: operar uno **renuncia** al beneficio de diversificación, y el artefacto debe
decirlo — el `n_eff` reportado será 1 (§7.2). Un GO-ACOTADO no pretende ser tan bueno como un GO
completo; pretende **no confundirse con un NO-GO**.

#### Sobre la hipótesis pre-registrada: lo que NO rescata

> No se admite ninguna excepción por **hipótesis pre-registrada** que rescate a un candidato que falla
> C1. Una hipótesis pre-registrada (issue #88) **interpreta** un resultado; **no relaja** un gate, y los
> gates no se relajan. Su rol es otro: toda ampliación futura del universo debe declararse **antes de
> medir**, y toda selección entre instrumentos debe contarse como ensayo (§2.x.1).

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
- **Forma canónica obligatoria**: la forma canónica del veredicto es
  **`GO (candidato X, firma Y, canasta {…})`** — nunca `GO (candidato X)` a secas. La firma es parte
  inseparable de la identidad del veredicto, y **la canasta también**, por la misma razón: dos canastas
  distintas sobre el mismo candidato y la misma firma son dos cuentas distintas (§7.5, orden de
  evaluación).
- **Cambio de régimen**: la no-transferibilidad cubre también el paso **CFD → CME**. Un veredicto del
  mundo CFD **no es válido** en el mundo CME bajo ninguna circunstancia — cambian el vehículo, la
  estructura de costos, el horario y el contrato de la firma.

*Trabajo futuro (no normado en esta versión)*: una eventual excepción `FirmMismatchError` que aborte al
intentar componer/comparar artefactos con `firm_profile_hash` distintos queda como nota de trabajo
futuro; no se crea en código ni se le asigna issue en este change (doc-only).

### 7.6. Sanity-checks de alcanzabilidad (G1 y G4/T1)

#### Sanity-check G1 ≥ 300 (alcanzabilidad de trades OOS totales)

El gate G1 exige ≥ 300 trades OOS en la curva OOS cosida sobre todas las ventanas WFA.

**Re-derivación para el Candidato B bajo el universo CME (v1.5):**

El cálculo de v1.4 partía de ~700–1.000 apuestas/año repartidas en **cuatro índices CFD sobre dos
sesiones distintas** (tres estadounidenses y uno europeo). El universo de v1.5 son **3 micro-índices
sobre una sola sesión RTH**, más MGC con ancla pendiente (§2.3). La aritmética cambia:

- G1 se evalúa **por símbolo** (§7.1), así que lo que importa es la frecuencia **de cada instrumento**,
  no la suma de la canasta. Perder un instrumento no reduce los trades de otro; reduce la cobertura del
  universo.
- Una sesión RTH por instrumento, un ORB por sesión ⇒ **~250 oportunidades/año por instrumento** como
  cota superior, antes de cualquier filtro (RVOL, ventana de noticias, falta de ruptura confirmada).
- Con una ventana OOS cosida de 6–12 meses, eso da **~125–250 trades OOS por instrumento** como cota
  superior — **por debajo de G1 ≥ 300**.

> **Conclusión, distinta de la de v1.4:** G1 ≥ 300 **no es holgadamente alcanzable** por instrumento con
> una sola ventana OOS anual. Exige **acumular varias ventanas WFA** sobre la curva OOS cosida, y por lo
> tanto **historia profunda** — que es exactamente lo que el change de capa 1 debe garantizar al elegir
> proveedor (§11.1).
>
> Las cifras de arriba son **estimaciones heredadas del régimen CFD, a confirmar contra datos CME
> reales**. No se usan para ajustar nada: se usan para saber que la profundidad de historia es un
> requisito duro y no un detalle de implementación.

Si un instrumento no alcanzara 300 trades OOS en la ventana disponible, la salida es **extender la
ventana temporal** (documentado en `quality.py` como restricción de suficiencia de historia) o
**excluir ese instrumento del universo del candidato** — con la consecuencia de §2.x: excluirlo
**después de medir** es selección, y el universo vive en el SSoT. **Los gates no se relajan.**

#### Sanity-check G4/T1 DSR ≥ 0.95 (coherencia con presupuesto de grid)

El gate G4 (y T1, que deflacta por el número de candidatos) exige DSR ≥ 0.95 tras el WFA.

**Análisis con N_trials_IS = 27:**

La corrección del DSR (Deflated Sharpe Ratio de Bailey & López de Prado) penaliza la búsqueda IS mediante el término `Φ⁻¹(1 − 1/T_trials)` donde `T_trials` es el número de trials evaluados. Con 27 trials:

- `ln(27) ≈ 3.30` (como referencia del crecimiento del término de corrección)
- La deflación esperada del Sharpe IS → OOS con 27 trials es modesta comparada con búsquedas de cientos o miles de trials.

**Conclusión de v1.4**: con N_trials_IS = 27 (grid 3×3×3), el presupuesto de grid es suficientemente pequeño para que la deflación del DSR no haga el gate G4 ≥ 0.95 inalcanzable bajo condiciones normales de edge. El techo de 27 trials queda documentado como restricción de diseño del WFA (Issue H).

> **Este sanity-check queda INVALIDADO como está, bajo v1.5** (normativo). Dos razones independientes, y
> cada una basta:
>
> 1. **El régimen de §2.x.1 es de selección.** El número efectivo de ensayos incluye **también los
>    instrumentos sobre los que se selecciona**, no solo la grilla interna de una corrida. `N = 27` ya no
>    describe el denominador real del DSR.
> 2. **La grilla de `risk_pct` está anulada** (§7.2). Si la re-derivación deja menos de tres valores
>    operables, el grid deja de ser 3×3×3 y el conteo cambia por aritmética.
>
> El sanity-check **se recalcula cuando exista el ledger (#53)**, y hasta entonces **no se emite
> veredicto sobre el universo múltiple** (§2.x.1). Declarar alcanzabilidad sobre un contador que ya no
> aplica sería afirmar algo que el spec no puede sostener.

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

**Estado de PA-1 a PA-5 bajo el cambio de régimen (v1.5):** PA-1 y PA-2 (nombres de símbolo y
profundidad de ticks en The5ers) quedan **caducas** — describen un venue que ya no es el destino.
PA-3, PA-4 y PA-5 siguen **vigentes**: son agnósticas al venue.

#### Pendientes abiertos por el cambio a futuros CME (v1.5)

Ninguno se rellena con supuestos. Cada uno declara **qué falta** y **qué bloquea**.

| Pendiente | Qué falta | Por qué bloquea |
|---|---|---|
| **PA-106-A — Ancla del rango de apertura de MGC** | Página de producto oficial de CME (fuente primaria) | Sin ella el Candidato B **no corre sobre MGC** (§2.3). No contrae el denominador de C1 |
| **PA-106-B — Política de VPS de MFFU** | Búsqueda de "VPS" / "virtual private server" en su help center: **cero resultados**. Ausencia de regla **no es permiso** | Decide la arquitectura de operación post-GO |
| **PA-106-C — Comisiones por contrato** | No publicadas; dependen de la plataforma (Tradovate / Rithmic / NinjaTrader) | Insumo obligatorio de `costs.py`, que bloquea **G3** (PF con costos completos), **G9** (PF con stress ×1.5) **y todos los gates P**. No es solo economía: sin comisiones verificadas los gates de robustez tampoco corren |
| **PA-106-D — Árbitro de exposición (#96)** | No existe | Bloquea **operar** la canasta contra el `contract_budget` compartido y emitir gates P sobre ella. **No** bloquea C3, que se computa por superposición (§7.2) |
| **PA-106-E — Denominador y valores de `risk_pct`** | v1.5 **fija el denominador** (`max_loss_limit`, §7.2); los **valores** quedan pendientes de re-derivación entre el piso de operabilidad y el techo de canasta | Sin valores, `k_max` no se calcula y C3 no se evalúa. Además cambia el conteo de trials de §6.2 y el sanity-check de §7.6 |
| **PA-106-F — Una cuenta multi-activo vs. varias mono-activo** | MFFU admite **3 cuentas fondeadas** en Rapid EOD. Tres colchones de $2.000 **independientes** eliminan el riesgo de cola conjunta que C3 acota; el costo son 3 suscripciones y 3 evaluaciones, y el **precio del plan no está verificado** | Decide la arquitectura de la operación y puede volver a C3 irrelevante. Abierta desde antes del cambio de régimen; v1.5 la declara con sus términos y **no la resuelve** |
| **PA-106-G — Precio del plan Rapid EOD 50K** | No verificado | Entra en `challenge_cost` y en la economía del embudo (§1.2) |
| **PA-106-H — Hedging entre instrumentos *related*** | Ambigüedad entre "mismo subyacente" y "activos no relacionados"; confirmar con soporte | Decide si la canasta MES/MNQ/MYM puede tomar signos opuestos (§1.3.0) |
| **PA-106-I — Datos de M2K** | No existen en el store | Sin ellos su admisión al universo no se evalúa (§2.x) |
| **PA-106-J — Proveedor de datos CME** | Databento / Rithmic / Tradovate / CME DataMine — decisión abierta | Change de capa 1 (§4.1). Condiciona la profundidad de historia, que §7.6 marca como requisito duro |
| **PA-106-K — Ledger de ensayos (#53)** | No existe | **Prerrequisito**: ninguna campaña sobre el universo múltiple emite veredicto sin él (§2.x.1), y el sanity-check de G4 queda invalidado hasta entonces (§7.6) |

### 11.2. Dependencias de runtime (vía `uv`)

`MetaTrader5`, `pandas`, `pyarrow`, `numpy`, `scipy`, `statsmodels`, `matplotlib`, `quantstats`. Dev: `hypothesis`, `pytest`. Versiones en Issue B.
