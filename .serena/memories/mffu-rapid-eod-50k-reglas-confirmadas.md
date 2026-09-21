*(2026-09-11 — leído de `help.myfundedfutures.com`, fuente primaria. Las prop firms cambian reglas:
reverificar antes de construir el `FirmProfile`.)*

# MyFundedFutures — Rapid EOD 50K: reglas confirmadas y qué exigen de genesis

Contexto de por qué MFFU: `mem:pivote-a-prop-de-futuros-cme-2026-09`.

## Evaluación, planes de 50K

| | **Rapid EOD** | Rapid (estándar) | Builder Default | Builder Add-On |
|---|---|---|---|---|
| Objetivo | $3.000 | $3.000 | $3.000 | $3.000 |
| Max Loss (MLL) | **$2.000 EOD** | $2.000 EOD | $2.000 EOD | $1.500 EOD |
| Daily Loss Limit | **Ninguno** | Ninguno | $1.000 *soft pause* | $1.000 *soft pause* |
| Contratos | 3 mini / 30 micro | 5 mini / 50 micro | 4 mini / 40 micro | 4 / 40 |
| Consistencia | 30% | 50% | Ninguna | Ninguna |
| Días mínimos | 4 | 2 | 1 | 1 |
| Noticias T1 | Permitido | Permitido | Permitido | Permitido |
| Precio | *no verificado* | *no verificado* | $153 (→$107 c/30%) | $125 (→$87) |

Sin fees de activación en ningún plan.

## Etapa Sim Funded — acá está la trampa

| | **Rapid EOD** | Rapid (estándar) | Builder |
|---|---|---|---|
| Balance inicial | $0 | $0 | $0 |
| **Tipo de drawdown** | **EOD trailing** | ⚠️ **Intraday trailing (HWM de equity)** | EOD trailing |
| MLL | $2.000 | $2.000 | $2.000 / $1.500 |
| Contratos | 3 / 30 | 5 / 50 | 4 / 40 |
| Noticias T1 | **Prohibido** | **Prohibido** | Permitido |
| Cuentas fondeadas | **3** | — | 1 |
| Split | **90/10** | 90/10 | 80/20 |
| Buffer 1er payout | $2.100 | $2.100 | $2.100 / $1.600 |
| Payouts | **Diarios, sin tope** | Diarios (24 h), sin tope | 48 h, tope $2.000/ciclo, **máx 5** |
| Consistencia payout | **Ninguna** | Ninguna | 50% |

**⚠️ El Rapid estándar cambia de EOD a intraday al pasar a fondeada.** Pasás la evaluación bajo una
regla y operás bajo otra, más dura. Eso invalidaría la validación justo cuando empieza a importar.
**Por eso Rapid EOD, no Rapid.**

## Mecánica fina

- **Congelamiento**: el trailing se bloquea en **$100** (o balance inicial + $100 en evaluación: 50K
  bloquea en $52.100, alcanzado cuando el balance cierra sobre $52.000). **Una sola política de
  lock** — a diferencia de Apex, que tiene tres según plataforma y etapa.
- **Doble tiempo del umbral EOD**: se **calcula** al cierre pero se **aplica contra equity flotante**
  intradía. Textual: *"open equity losses are taken into consideration when calculating whether or
  not the account failed on this rule"*.
- **Consistencia 30% NO rompe la cuenta**: exceder el umbral solo obliga a operar más días hasta que
  el ratio baje. Es una condición de **terminación** de la evaluación, no un gate de fallo.
- **En Sim Funded el balance arranca en $0 y puede ir negativo** hasta que el MLL suba a breakeven.
  Documentado como "expected and normal".
- **Días mínimos 4** (Rapid EOD). El Builder pasa en 1.

## Hedging y presupuesto de contratos

**Hedging** (artículo del 2025-11-10): prohibido solo sobre el **mismo subyacente** (NQ vs MNQ).
Textual: *"It is important to note that hedging through different unrelated assets is permitted."*
→ **largo ES + corto GC está permitido.** Advertencia discrecional, sin umbral: *"when traders rely
solely on hedging strategies — even across different assets — it becomes challenging to accurately
evaluate their trading abilities."* Remiten a la regla 534 de CME.

**Cross Instrument Policy**: el techo de contratos es **total y compartido entre instrumentos**, en
tiempo real. *"Orders that combine different instruments (e.g., 2 minis and 20 micros) may
technically execute even if they exceed the overall limit, but this is not permitted!"* Eludirlo a
propósito es breach.

## Noticias — genesis ya tiene las piezas

- **Ninguna posición ni orden en el book 2 minutos antes y después de *cualquier* dato.** Todas las cuentas.
- **T1** = FOMC, actas FOMC, informe de empleo, CPI (+ EIA para energía, informes agrícolas para agro).
  Flat 2 min antes, reapertura 2 min después.
- T1 **prohibido** en Rapid Sim Funded y Pro Sim Funded; permitido en todas las evaluaciones y en Builder.

Mapea directo a `news_bracket_before_minutes=2` / `news_bracket_after_minutes=2` de `FirmProfile`
(ya existen) apoyado en `genesis/data/calendar.py` (ya existe). Es la única pieza del pivote que no
cuesta nada.

## Qué exige de genesis (verificado contra el código el 2026-09-11)

1. **`MaxLossLimitKind.TRAILING_EOD` no existe.** Hoy solo hay `STATIC` y `TRAILING` (este último
   sigue `_all_time_peak_equity` de equity flotante = la variante *intraday*). Falta la que sigue el
   máximo balance **de cierre** y se aplica continuo.
2. **Denominación en dólares.** `_evaluate_total_breach` calcula
   `threshold = reference * (max_loss_limit_pct/100)`, o sea un % del pico móvil. En MFFU (y en Apex)
   son $2.000 fijos. El modelo actual da más aire a medida que el pico sube → **sobreestima `p_pass`**.
3. **Congelamiento del umbral** (`threshold_lock_at`): no existe en ninguna forma.
4. **DLL opcional y con semántica de pausa.** Rapid EOD no tiene DLL; `FirmProfile.daily_loss_limit_pct`
   hoy es obligatorio. Y en Builder el DLL **pausa el día**, no rompe — pero `_evaluate_daily_breach`
   solo hace `ledger.append(BreachEvent(...))`: **no detiene la operación ni marca la cuenta**, así
   que el simulador sigue operando después del DLL (error en dirección permisiva). Además usa una
   base doble (`max(pérdida vs cierre previo, pérdida vs pico intradía)`) más estricta que un DLL
   contra el balance de apertura; cuál usa MFFU **no está documentado**.
5. **Balance inicial $0 con saldo negativo permitido** rompe supuestos de `starting_balance` en el
   simulador y en `prop_sim` (hoy el runner pasa `--starting-balance 100000`).
6. **Buffer de payout** ($2.100 antes del primero, $500 de beneficio neto entre payouts): concepto
   nuevo, no está en `PropEconomicsProfile`.
7. **Consistencia como condición de terminación, no de fallo.** `consistency_rule_pct` ya existe en
   `PropEconomicsProfile`; falta revisar cómo lo aplica `prop_sim` (¿bloqueo de payout o gate de pase?).
8. **Presupuesto de contratos compartido entre símbolos, en tiempo real.** `max_lots`/`max_positions`
   son escalares. genesis simula **por símbolo** (`run_wfa(candidate, symbol, ...)`) y agrega cartera
   recién en capa 4 — una restricción de exposición conjunta intradía **no se puede expresar así**.
   Es el hallazgo arquitectónico más serio del pivote; engancha con el issue **#96**.

## Lo que NO está verificado

- **Política de VPS**: búsqueda de "VPS" y "virtual private server" en su help center devuelve
  **cero resultados**. Ni permitida ni prohibida explícitamente (Topstep sí la veta por escrito).
  Ausencia de regla no es permiso — **preguntar a soporte antes de diseñar la operación**.
- **Comisiones por contrato**: no publicadas en el help center; dependen de la plataforma
  (Tradovate / Rithmic / NinjaTrader). Necesarias para `costs.py`.
- **Precio del Rapid EOD 50K.**

## Sobre `SymbolFigure` y futuros (buena noticia)

`value_per_point = tick_value / tick_size` **da el multiplicador del contrato** de forma natural
(ES: 12,50/0,25 = 50). La abstracción de Change #55 aguanta futuros **sin cambio de esquema**,
siempre que se alimenten las cifras crudas del venue. Lo que falta es una **fuente de fichas por
venue**, no un fallback calculado — la heurística `tick_size = 10^-digits` **falla 25× en ES/NQ**
(tick real 0,25 con 2 dígitos) y 5× en 6E. Ver el parche revertido en `src/genesis/data/metadata.py`.

---

## Verificación contra el código (2026-09-14, base `fe5e683`)

Los huecos de arriba se contrastaron con el código. Tres precisiones que cambian el diagnóstico:

**El MLL vive duplicado, con dos semánticas distintas.**

| Dónde | Referencia del trailing |
|---|---|
| `backtest/simulator.py:490` `_evaluate_total_breach` | `_all_time_peak_equity` — pico de equity **flotante intradía** (ADR-G2) |
| `validation/prop_sim.py:424-436` `_simulate_single_path` | `attempt_peak_balance = max(..., balance)` sobre balances **diarios** |

O sea: **el ancla EOD que MFFU exige ya existe de facto en `prop_sim`**, y no en el simulador. El hueco real en ambos no es el ancla sino el **umbral en moneda** (siempre se computa como `referencia × pct`) y el **congelamiento**. `p_pass` sale de `prop_sim`, no del simulador.

**El desvío más grande es un número configurado, no una capacidad ausente.** `backtest/risk_profile.json` declara `max_loss_limit_pct: 10.0` con `kind: "static"` → sobre 50.000, umbral **estático de $5.000** contra los **$2.000 EOD trailing** reales. 2,5 veces más colchón.

**Corrección al hueco 4.** «`_evaluate_daily_breach` no detiene la operación» vale para `simulator.py:468` (registra el `BreachEvent` y sigue). En `prop_sim` NO es así: en la fase de challenge, `prop_sim.py:439` `if breach_daily or breach_total:` reinicia el intento; en la rama fondeada el breach diario es continuable **por diseño declarado** (R27/R28/R29) y sólo el total termina. No es un error permisivo de `prop_sim`.

**Confirmado sin cambios:** `MaxLossLimitKind` sólo tiene `STATIC` y `TRAILING`; no hay congelamiento de umbral; `consistency_rule_pct` existe como campo (`prop_sim.py:80`), se carga y se serializa pero **ninguna rama de decisión lo lee**; no hay buffer de payout (`prop_sim.py:507-512`); `rg` sobre `src/` no encuentra `mffu`/`rapid`/`eod` ni literal monetario alguno; la composición de cartera es post-hoc (`_build_daily_basket`, `prop_sim.py:245`) sobre un motor estrictamente mono-símbolo.

**Dato que corre al revés:** `profiles/the5ers.json` impone `daily_loss_limit_pct: 5.0` y MFFU **no tiene límite diario**. Ese desvío aprieta el juicio; los otros cuatro lo aflojan.

Todo esto abrió el issue **#109** y el change `109-el-modelo-de-la-firma-no-es-mffu-...`, en fase explore. Ver `mem:arquitecto-estrategias-y-ledger-ensayos`.

---

## Reverificación del 2026-09-21 — consistencia 30%, y dos correcciones al diagnóstico

Fuente primaria releída: [Rapid EOD 50k — A Comprehensive Look](https://help.myfundedfutures.com/en/articles/16158363-rapid-eod-50k-a-comprehensive-look).
Diez días después de la primera lectura, **sin cambios en el reglamento**. Contrastado en paralelo
contra una búsqueda web delegada a agy, que coincidió punto por punto (pero no aportó URLs
utilizables: todas apuntaban al dominio raíz).

**Lo confirmado, textual:**

> *«30% consistency rule **in the evaluation phase** of the Rapid EOD Plan»*
>
> *«Consistency Requirement: **None** (you do not need to meet a consistency rule to get paid).»*

O sea, sin ambigüedad: la consistencia del 30% **aplica sólo a la evaluación**, **desaparece** en la
etapa fondeada, y **no descalifica** — obliga a operar más días hasta diluir el día grande. La
fórmula es `mejor día ≤ 0,30 × ganancia neta acumulada`, así que un día de $1.500 mueve la meta
efectiva de $3.000 a $5.000.

Esto ya estaba en este mismo archivo desde el 2026-09-11, pero se había vuelto a listar como
pendiente en `DIMENSIONAMIENTO_HOLDOUT.md`. **Ya no lo es.**

### Corrección 1 — `consistency_rule_pct` SÍ se lee

El apartado «Verificación contra el código (2026-09-14)» afirma que el campo *«existe, se carga y se
serializa pero ninguna rama de decisión lo lee»*. **Eso ya no es cierto** (verificado el 2026-09-21):

```
validation/prop_sim.py:515-522
    consistency_ok = consistency_rule is None or (
        max(attempt_daily_profits, default=0.0)
        <= consistency_rule.pct / 100.0 * profit_since_phase_start
    )
    ... and consistency_ok
```

Gatea la **promoción de fase**, no la descalificación — que es exactamente la semántica del
reglamento. La rama con semántica `FAIL` está explícitamente no modelada y levanta
`PropSimConfigError`.

### Corrección 2 — `run_prop_sim` no reproduce el camino real

Dato que faltaba en esta memoria y que condiciona cualquier criterio de aprobación: `run_prop_sim`
**no recorre la secuencia real de días**. Genera los caminos con un *moving-block bootstrap*
(`_bootstrap`, `PropSimConfig.block_size`) sobre la canasta diaria, y devuelve una distribución.

Para un MLL **con arrastre**, el orden de los días es lo único que decide el quiebre, así que
remuestrear destruye la señal que se quiere medir. Evaluar el camino realizado exige una entrada
nueva que consuma los días en orden; el motor por debajo (`_simulate_one_path`) ya sirve tal cual.

Otros parámetros que importan al conectarlo: `max_attempts=10`, `horizon_months=12` (el holdout son
21 → hay que subirlo), `path_horizon_trading_days=750`.

### Consecuencia

El criterio de aprobación del holdout se reescribió sobre esta base: **no** «¿sobrevivió?», sino
«¿llegó a ser fondeado, en cuánto tiempo y a cuántos intentos?». Ver
`docs/DIMENSIONAMIENTO_HOLDOUT.md` §4 (PR #124).

**Sigue sin verificar:** el precio del Rapid EOD 50K (no publicado), las comisiones por contrato y
la política de VPS.
