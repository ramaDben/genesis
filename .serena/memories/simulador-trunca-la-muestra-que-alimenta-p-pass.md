# El simulador trunca la muestra que alimenta `p_pass` — y unificar no lo arregla

Medido el 2026-09-14 en la fase `propose` del Change #109, contra `fe5e683`. Reemplaza a
`mll-duplicado-acopla-simulador-y-p-pass`, cuya conclusión (unificar las dos
implementaciones) fue refutada por una revisión adversarial el mismo día.

## La cadena causal (verificada línea por línea)

1. `backtest/simulator.py:497-516` — `_evaluate_total_breach` computa el breach contra
   `floating_equity` y fija `account_exhausted = True`.
2. `backtest/simulator.py:374` — con la cuenta agotada, **deja de procesar entradas nuevas**
   por el resto de la corrida (R30).
3. `validation/prop_sim.py:245-261` — `_build_daily_basket` construye la canasta diaria del
   Monte Carlo de `p_pass` **a partir de esos mismos ledgers OOS**.

El simulador **sí** altera el `p_pass`, por truncamiento del insumo. Esto refuta el argumento
del `idea.md` del #109 («el `p_pass` no lo produce el simulador»).

## Lo que la primera conclusión erró

La primera lectura fue: «hay dos implementaciones del MLL, unificarlas arregla el
truncamiento». **Falso.** Un simulador unificado que aplique $2.000 con el criterio correcto
cruza el umbral igual, fija `account_exhausted` igual y corta las entradas igual. El ledger se
sigue truncando. Unificar la regla no toca el problema.

## El defecto de fondo: conflicto de roles, no duplicación

El simulador de capa 3 cumple **dos roles incompatibles con el mismo artefacto**:

| Rol | Qué exige del ledger |
|---|---|
| Simular una cuenta prop concreta | que se agote y **pare** al cruzar el umbral (R30) — fiel a una cuenta real |
| Producir la muestra que capa 4 remuestrea | que sea **completa**, porque el Monte Carlo estima `p_pass` remuestreando esos días |

Un camino truncado es la respuesta correcta a la primera pregunta y una muestra sesgada para
la segunda. Con el umbral de $5.000 el conflicto está latente; con los $2.000 reales de MFFU
pasa a ser dominante. El efecto es perverso: `p_pass` puede **subir** al aumentar la fidelidad
del umbral, porque las colas malas desaparecen del ledger antes de llegar al Monte Carlo.

**Principio fijado en el #109:** la muestra que alimenta la validación no se trunca por
agotamiento de cuenta. El breach se registra como evento (`BreachEvent` ya existe) y el corte
por agotamiento es competencia de `prop_sim`. La forma concreta es trabajo de `design`, porque
toca R30.

## Capa 4 no puede evaluar intradía, y su proxy es optimista

`_simulate_single_path` recibe `daily_pnl: Sequence[float]` (`prop_sim.py:376-383`). Su
docstring lo declara con ADR: *«**nunca** la base de equity flotante intradía: ADR-J4,
R34/R35 — el proxy cierre-a-cierre es una cota inferior conservadora de la probabilidad real
de breach diario»* (`prop_sim.py:387-390`).

Conviene nombrar bien ese sesgo: es conservador **como elección de modelado** (no inventa
breaches que los datos diarios no prueban), pero su efecto sobre el juicio es **optimista** —
menos breach estimado significa **más `p_pass`**. Para un proyecto cuyo único producto es
`p_pass`, la distinción no es semántica. Por eso «una sola implementación» del MLL es un
criterio irrealizable, y lo que se exige en su lugar es **una sola fuente de la regla** (la
ficha) con **el sesgo de cada evaluador declarado**.

## Método

La cadena causal la encontró una delegación a agy (tier `pro`, solo lectura) y la verificó
Claude contra el código. La refutación del remedio la encontró una **segunda** delegación
adversarial sobre el proposal ya escrito. Moraleja aplicable: una revisión adversarial del
documento, por separado de la auditoría del código, atrapó un error de razonamiento que la
auditoría de código no podía ver — porque el error no estaba en los hechos sino en la
inferencia.

Relacionado: `mem:genoma-gobierna-parametros-la-prop-gobierna-la-cuenta`,
`mem:pivote-a-prop-de-futuros-cme-2026-09`, `mem:mffu-rapid-eod-50k-reglas-confirmadas`,
`mem:change-51-scope-decision`
