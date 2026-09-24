# Fuente — Mesfin (2026), *Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures: A Systematic Falsification Study*

## Procedencia

| Campo | Valor |
|---|---|
| Autor | Mathias Mesfin, *Independent Researcher* |
| Identificador | arXiv:2605.04004 |
| Categoría | q-fin.TR (Trading and Market Microstructure) |
| Versiones | v1 5 may 2026 · v2 13 jul 2026 · **v3 15 sep 2026 (leída)** |
| Revisión de pares | **No.** Preprint |
| Extensión | 17 páginas, 4 figuras, apéndice de replicación |
| URL | https://arxiv.org/abs/2605.04004 |
| Leído el | 2026-09-20, versión v3 completa (PDF) |

Origen en genesis: pista anotada sin leer en el
[#107](https://github.com/ramaDben/genesis/issues/107), promovida a casilla 0.1 del roadmap.

## Qué hace

Somete **catorce familias de señales** intradía a un protocolo de falsación sobre **MNQ**
(Micro E-Mini Nasdaq 100), barras de 5 minutos, **sólo RTH** (09:30–16:00 ET), diciembre 2021 –
agosto 2025: 72.604 barras, 947 días completos.

**Cinco criterios simultáneos**, todos sobre retornos **netos** OOS:

1. T ≥ 2,0
2. ≥ 30 operaciones por pliegue OOS
3. Retorno neto positivo después de fricción
4. Dirección consistente en 2023, 2024 y 2025
5. Test de permutación

**Ninguna de las catorce pasó las cinco.**

Validación *walk-forward* de ventana expansiva: entrena 2022 → prueba 2023; entrena 2022-23 → prueba
2024; entrena 2022-24 → prueba 2025 (parcial). 2022 se excluye de toda afirmación de estabilidad
anual por ser año de entrenamiento en los tres pliegues.

## Supuestos de ejecución (directamente reutilizables)

| Parámetro | Valor |
|---|---|
| Fricción MNQ, ida y vuelta | **2,0 puntos = $4,00 por contacto micro** — spread, tasas de intercambio de NinjaTrader y deslizamiento conservador |
| Fricción MGC, ida y vuelta | 0,50 puntos = 5 ticks a $1,00 |
| Convención de ejecución | Señal al cierre de barra, entrada a la apertura de la barra siguiente |

La convención de ejecución es la correcta y vale la pena registrarla: *«elimina el error de precio de
llenado que aqueja a la mayoría de los backtests retail, donde la estrategia ejecuta a un precio que
sólo era visible en retrospectiva.»*

## La tesis central

> *«En barras OHLCV de cinco minutos en un contrato tan líquido como MNQ, ese costo se sitúa
> alrededor de uno a dos puntos por operación.»*

El edge bruto de cualquier patrón OHLCV públicamente observable converge al costo de explotarlo. No
lo deriva de la HME: lo presenta como observación empírica que la HME vuelve poco sorprendente.

## Evaluación crítica de la fuente

### Lo que la hace valiosa

**1. Declara su propio sesgo de origen, y es el declarante más honesto que este proyecto ha
registrado.** Primer párrafo de la introducción:

> *«Este proyecto empezó como una búsqueda de estrategias, no como un estudio de falsación. Varios
> meses probando señales individuales —cada una fallando bajo evaluación fuera de muestra y costos de
> transacción— dejaron el patrón lo bastante claro como para que documentar los fracasos
> sistemáticamente pareciera más productivo que seguir buscando excepciones. Ese replanteo es el
> origen real de este paper, y importa porque un paper que empezó como búsqueda tiene una epistémica
> distinta de uno diseñado ab initio como estudio de resultado nulo.»*

Eso es exactamente **D1**, escrito por alguien que no usa esa palabra. El denominador real de
ensayos es desconocido y muy superior a catorce.

**2. Declara la exposición de búsqueda de su control positivo principal.** *«53 o más combinaciones
de parámetros a través de siete parámetros fueron evaluadas antes de fijar la especificación
final»*, y añade que esa exposición *«no puede corregirse post hoc»*, citando a Bailey & López de
Prado (2014, DSR) y Bailey et al. (2017, PBO) para decir que aplicar cualquiera de los dos
**reduciría** la confianza en su T = 3,11.

**3. Es una falsación, no una promoción.** Su resultado es mayoritariamente negativo y está escrito
sin intentar rescatar nada. Es la clase de fuente que el sesgo de supervivencia de la publicación
hace rara.

### Lo que obliga a descontar

**1. Cita el DSR y el PBO pero no los aplica.** Ninguna corrección por multiplicidad se ejecuta en
ninguna parte. Con un número de ensayos declaradamente desconocido, un T = 3,11 y un T = 4,30 no son
lo que parecen. **Bajo los gates de genesis, este paper no pasaría G4.**

**2. Los controles positivos no son independientes.** Salen de *«un programa de investigación
compañero»* del mismo autor sobre los mismos datos. No son una validación externa del método: son
los sobrevivientes de la misma búsqueda. Es I7 en estado puro.

**3. Contaminaciones declaradas en el control positivo RTH:**
   - El GMM se ajustó sobre **todo 2022** y el pliegue W1 prueba sobre **2022 H2** — el modelo vio el
     período de prueba.
   - La línea base de ATR (10,34) se computó sobre todo 2022-2024 y se fijó globalmente, lo que
     introduce *«un leve look-ahead relativo a la estructura walk-forward»*.
   - No se computaron las referencias incondicionales por pliegue para los períodos OOS.

**4. El contrato continuo se construye por concatenación trimestral simple, sin ajuste de roll y sin
calendario de feriados.** El propio autor cita a López de Prado (2018) sobre discontinuidades de
fecha de roll y admite que sus señales dependen de movimientos relativos y z-scores de volumen, lo
que *«mitiga parcialmente pero no elimina esta preocupación»*.

Esto **corrobora por el lado del error** lo que la casilla B.3 del roadmap exige: el empalme no es
detalle de infraestructura. Aquí hay ATR de 20 barras y z-scores de volumen de 50 barras cruzando
rolls sin ajustar.

**5. La fuente de datos es un feed retail.** NinjaTrader, barras de 5 minutos agregadas desde barras
de 1 minuto. No es tick, no es DataMine, no es re-descargable con hash estable. El propio paper
señala que los datos tick son la extensión de mayor prioridad y que **Databento ofrece tick de MNQ a
~$42 por trimestre** — dato de compra directamente útil para la casilla B.1.

**6. Dos inconsistencias internas verificadas:**
   - El **umbral del test de permutación** aparece como `p < 0,05` en el resumen del PDF v3 (p. 1) y
     como `p < 0,001` en la Tabla 3 y en el texto de la §3. También `p < 0,001` en el resumen de
     arXiv. No es el mismo umbral en dos lugares del mismo documento.
   - La **Tabla 13 marca «ORB Long H=15» como *year-unstable***, pero la Tabla 4 muestra sus tres
     años OOS **positivos y crecientes** (+2,43 / +7,04 / +15,05), que es precisamente lo que el
     criterio 4 define como estable. Por sus propios criterios esa familia falla **sólo** por
     T = 0,88, no por estabilidad anual. El resumen repite el error.

**7. Ventana corta y parcial.** 947 días, y 2025 es parcial (enero–agosto). Con tres pliegues OOS de
los cuales uno está contaminado y otro incompleto, la estructura walk-forward es más frágil de lo que
el conteo de barras sugiere.

## Veredicto como fuente

**Útil, con reservas grandes, y admisible al corpus.** Pasa la prueba de predicción falsable de A.2:
enuncia una predicción concreta y contrastable (el techo de edge bruto en ~1–2 puntos), no una
narrativa.

**No es una compuerta sobre el roadmap.** Es un preprint de autor único, sin revisión de pares, con
un denominador de ensayos que él mismo declara desconocido, controles positivos que son
sobrevivientes de su propia búsqueda, y contaminaciones admitidas. Tratarlo como evidencia
concluyente sería cometer contra él el error que el proyecto existe para no cometer.

Lo que sí hace es **mover el prior**, y lo mueve mucho en un punto que toca al candidato prioritario
del torneo. Ver `CLAIM-002`.
