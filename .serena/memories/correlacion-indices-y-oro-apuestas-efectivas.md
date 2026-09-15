*(2026-09-11 — medición sobre el store del proyecto. **Corregida el mismo día**: la primera versión de esta memoria concluía lo contrario porque medía la magnitud equivocada. Ver §"La corrección".)*

# Cuántas apuestas independientes dan realmente los índices y el oro

## Por qué se midió

El usuario planteó un **portafolio de estrategias** sobre oro, Nasdaq, Russell, S&P y Dow, citando a
la academia. La premisa es correcta: la **Ley Fundamental de la Gestión Activa** (Grinold & Kahn)
dice `IR = IC × √BR`, donde *breadth* es el número de decisiones **independientes**. Clarke, de Silva
& Thorley la extendieron al caso de activos correlacionados. Si las apuestas están correlacionadas,
el `√BR` se derrumba.

## LA CORRECCIÓN — el hallazgo central

**La correlación de retornos del activo NO es la correlación de las apuestas.** Para elegir un
universo hay que medir la correlación del **resultado de la estrategia**, no la del subyacente.

| Par (equivalente CME) | Corr. **retornos diarios** | Corr. **resultado ORB** |
|---|---|---|
| MES–MNQ | 0,947 | **0,281** |
| MES–MYM | 0,847 | **0,445** |
| MNQ–MYM | 0,684 | **0,099** |
| MES–MGC | 0,435 | **0,131** |
| MNQ–MGC | 0,407 | **0,162** |
| MYM–MGC | 0,429 | **0,033** |

**N efectivo de las cuatro: 1,39 sobre retornos → 2,54 sobre el resultado del ORB.**
Ganancia de IR: 1,18× → **1,59×**.

**Por qué.** El P&L de un ORB depende de la relación entre el **ancho del rango de apertura** y el
**recorrido posterior** — una cantidad adimensional y propia de cada instrumento. Dos índices pueden
moverse juntos en dirección y tener seguimiento relativo al rango completamente distinto. Ahí está
la amplitud que la correlación de retornos no ve.

El error de la primera versión fue confundir "estos activos se mueven juntos" con "estas apuestas
son la misma apuesta". Lo detectó el usuario preguntando por qué se excluían MYM y M2K.

## Condiciones de la medición

- **Fuente**: `data/raw/<símbolo>/m1/**/*.parquet` del store del proyecto. Proxies CFD de los
  futuros: US500→MES, US100→MNQ, US30→MYM, XAUUSD→MGC.
- **Ventana**: 2025-10-30 → 2026-06-30 (~8 meses).
- **Retornos**: 130 retornos diarios log; Pearson.
- **Resultado ORB**: 170 días. Rango de apertura = high/low de 09:30–10:00 ET (`America/New_York`,
  maneja el cambio de horario). Señal = primer cierre fuera del rango entre 10:00 y 15:55.
  Resultado = `dirección × (cierre_sesión − precio_ruptura) / ancho_rango`, o sea R en unidades de
  rango. Sin stops, sin costos, sin filtro de régimen.
- **N efectivo**: `n/(1+(n−1)·ρ̄)`.
- **Script**: `/tmp/neff.py` y `/tmp/orb_overlap.py` — **no versionados**, reproducibles en minutos.

## Resultados complementarios

**Frecuencia de disparo**: con rango de 30 min, los cuatro rompen el rango el **100 %** de los días
(el proxy no tiene filtro; el Candidato B real tiene filtro RVOL, que baja esto y cambia la
estructura de solapamiento).

**Acuerdo direccional de la señal**: MES–MNQ 88 % mismo sentido; MES–MYM 79 %; MNQ–MYM 76 %;
cualquiera contra oro **60–63 %**.

**N efectivo por canasta (sobre resultado ORB)**:

| Canasta | N_ef | IR × |
|---|---|---|
| MES + MNQ + MYM + MGC | **2,54** | 1,59 |
| MNQ + MYM + MGC | 2,51 | 1,58 |
| MES + MNQ + MGC | 2,17 | 1,47 |
| MYM + MGC | 1,94 | 1,39 |
| MES + MGC | 1,77 | 1,33 |
| MES + MNQ | 1,56 | 1,25 |

MES aporta poco sobre MNQ+MYM+MGC (2,51 → 2,54), pero **no cuesta nada**: el techo de contratos es
compartido, así que sumar instrumentos reparte el mismo presupuesto en vez de ampliarlo. Y MES es el
contrato más líquido del mundo — argumento de ejecución, no de estadística.

## El otro error de la primera versión: el DSR

La primera versión afirmaba que "cada instrumento extra suma ensayos al denominador del DSR". **Es
falso bajo el régimen de exigencia.** Por D1 (`mem:d1-que-cuenta-como-ensayo`, ratificada el
2026-08-29): *cuenta como ensayo toda dimensión sobre la que SELECCIONAS; no cuenta ninguna sobre la
que EXIGES*. Declarar el universo por adelantado y pedir que el candidato pase en **todos** los
instrumentos es conjunción: **cuesta cero ensayos** y es más difícil de pasar, no más fácil.

Solo bajo GO-PARCIAL —correr en todos y quedarse con el que funcionó— cada instrumento suma.

*(Matiz de implementación: el runner actual sobre-cuenta el caso conjuntivo, un `trial_id` por
símbolo por invocación. Es deliberado y conservador; la memoria de D1 lo explica y advierte que no
es un bug.)*

## Russell (M2K): no medido, no excluido

**No hay datos de Russell en el store.** La primera versión lo excluyó apoyándose en la correlación
de retornos — que resultó ser el criterio equivocado. Por construcción (small cap, doméstico,
sensible a tasas, menos concentrado en mega-cap tech) es plausiblemente **el más diferenciado** de
los índices US. Queda **pendiente de medir**, no descartado.

## Conclusión operativa

Universo del Candidato B: **MES, MNQ, MYM, MGC**, declarados por adelantado bajo régimen de
**exigencia**, más **M2K en cuanto haya datos de CME**. El criterio normativo de admisión de un
instrumento es su correlación con los ya admitidos **sobre el resultado de la estrategia**.

## Salvedades honestas

- El proxy ORB es crudo: sin stops, sin costos, sin filtro RVOL, sin la salida Chandelier del
  Candidato B real. La correlación del P&L real puede diferir — **hay que rehacer esta medición
  sobre el candidato real cuando exista**.
- 170 días, un régimen. El 0,43 de oro contra acciones en retornos es alto para lo habitual.
- Medido sobre **CFDs de índice en MT5**, no sobre los futuros CME que se van a operar.
- El 100 % de frecuencia de disparo delata que el proxy no filtra nada.

Relacionadas: `mem:pivote-a-prop-de-futuros-cme-2026-09`,
`mem:mffu-rapid-eod-50k-reglas-confirmadas`, `mem:d1-que-cuenta-como-ensayo`.
