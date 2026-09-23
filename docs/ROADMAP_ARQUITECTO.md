# Roadmap — El Arquitecto de Estrategias

*Trazado el 2026-09-20. Estado del árbol al escribirlo: `main` en `1389d91`, engine de pulse en
`explore`, sin change activo.*

*Revisado de nuevo el 2026-09-21: **B.1 ejecutada**, con la cotización real por API y la licencia
leída en el contrato ([#126](https://github.com/ramaDben/genesis/issues/126)). Segunda revisión
cruzada con `gemini-3.8-flash-high` sobre el plan de compra — cinco hallazgos, dos falsos, uno
material (§7.1b). Los cambios llevan **[rev 2026-09-21]**.*

*Revisado el 2026-09-20 contra `gemini-3.8-flash-high` (revisión cruzada adversarial). Nueve
hallazgos; seis aceptados en sustancia, uno con corrección de precisión, dos rechazados
parcialmente. Los cambios que produjo están marcados con **[rev]** donde alteran una conclusión.*

**Este documento no es normativo.** No reemplaza al SSoT
(`docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md`) ni autoriza implementación. Es el orden
acordado y el porqué de cada posición. Toda afirmación sobre el código está verificada contra el
árbol citado, con `archivo:línea`.

---

## 1. El objetivo, y lo que decidió esta sesión

**Construir el arquitecto de estrategias.** El torneo sobre MFFU vuelve a ser el primer caso de uso,
no la meta.

Tres decisiones tomadas el 2026-09-20 que restringen todo lo que sigue:

**D-A. El arquitecto adjudica, no busca.** Su trabajo es transcribir estrategias declaradas por
terceros —traders publicados, autores con nombre— a genomas, y dejar que el evaluador las juzgue.
No genera hipótesis propias ni explora un espacio de parámetros.

**D-B. El arquitecto es feed-forward.** Lee, traduce, y no vuelve a ver nada. Ningún resultado del
evaluador regresa al proponente. Esta es la propiedad que hace que la máquina sea segura, y no es
una política: es una separación física entre dos almacenes.

**D-C. Ningún ensayo se corre sobre datos de CFD.** Las estrategias se prueban sobre futuros CME.
Los datos de MT5 no se usan ni como paso previo.

**D-D [2026-09-22]. El universo se compra por clase de activo, no por índice.** Un líder por clase
—MNQ, MGC, M6E, MBT, MCL— de los que MFFU fondea, $84,85. Cierra la disyuntiva de §7.1e a favor de
(b): el proyecto dejó de ser un torneo de índices y pasó a ser un **validador multi-mercado**, y una
estrategia que sobrevive en cinco regímenes distintos demuestra algo que cuatro índices
correlacionados al 0,947 no pueden. **Es cambio de spec y se asume.** Su consecuencia —que comprar y
declarar son actos distintos, y que el Candidato B se queda sin universo declarable hasta que B.7
verifique una segunda ancla— está en §7.1e y en la casilla B.7.

**D-E [2026-09-22]. La unidad es el par (estrategia, activo), y genesis juzga, no elige.** Ni la
estrategia ni el activo van primero: lo único que se mide es **si esta estrategia gana o pierde en
este activo**. Es una grilla —estrategias en un eje, activos en el otro— y genesis es la máquina que
llena celdas. Propuesta del arquitecto, contrastada con Gemini 3.8 Flash (High) contra el árbol
(§9.7), aprobada por el dueño. Cinco puntos:

1. **Un veredicto por estrategia, sin ganador.** Se elimina `_select_winning_candidate`
   (`validation/verdict.py:433`); si pasan dos, pasan dos. Casilla **B.8**.
2. **El castigo por pruebas múltiples se mantiene y deja de depender del lote.** Hoy T1 suma
   `n_candidatos_torneo - 1` (`verdict.py:505`): la misma estrategia con los mismos datos sale
   distinta según cuántas corrieron al lado. Todas las estrategias de una corrida se registran en el
   ledger **antes** de juzgar ninguna, y el término de torneo desaparece. **T1 se queda**: mide la
   canasta diaria de la estrategia entera, que G4 no mide. Casilla **B.8**.
3. **Cuatro niveles de pregunta.** *Celda* —¿gana en este activo? (G1–G9)—; *fila* —¿gana en su
   universo? (C1, C2)—; *canasta* —¿aguanta operando todo a la vez? (C3)—; *cuenta* —¿sobrevive una
   cuenta fondeada? (P1–P6, T1). Combinar **varias** estrategias en una cuenta (T2) se difiere hasta
   que pasen dos.
4. **«No aplica» es estado de ejecución, no descuento.** Evita simular lo que no está definido (un ORB
   sobre Bitcoin), pero **nunca achica el denominador de C1**: el activo se excluye **no
   declarándolo**, antes de ver datos. La grilla sugiere qué declarar; lo declarado se congela en el
   pre-registro (C.4). §2.x del spec queda intacto. Casilla **B.6**.
5. **Las carpetas `strategy/candidate_a/` y `strategy/candidate_b/` desaparecen; la palabra
   «candidate» adentro del código se queda.** En validación, «candidato» es el término técnico de lo
   que está bajo prueba; el problema nunca fue la palabra sino el ganador. La clave
   `candidate_config` del hash de ensayos (`trial_ledger.py:133`) **no se renombra**: cambiaría todos
   los `trial_id` y el ledger contaría dos veces lo ya contado. Casilla **A.1**.

### Por qué D-B importa, y hasta dónde llega

El modo de falla de un arquitecto automatizado no es proponer mal: es **proponer, medir y volver a
proponer**. Ese lazo es el mecanismo de sobreajuste, y es lo que hace que un buscador con memoria
sea indistinguible de una casa de apuestas con contabilidad.

El referente del sector lo tiene abierto. En `microsoft/RD-Agent`
(`rdagent/scenarios/qlib/developer/feedback.py`), las métricas que se le inyectan al LLM que propone
la siguiente hipótesis son:

```python
IMPORTANT_METRICS = [
    "IC",
    "1day.excess_return_with_cost.annualized_return",
    "1day.excess_return_with_cost.max_drawdown",
]
```

…y la decisión que devuelve se llama `"Replace Best Result"`. Es búsqueda sobre el conjunto de
prueba, en bucle, sin descuento por número de intentos. No hay DSR ni denominador en ninguna parte
del framework.

Un arquitecto que transcribe claims externos **no tiene ese lazo que amputar**. Por eso esta forma
es preferible a la autónoma.

**[rev] Pero D-B no cierra todos los lazos, y el documento original decía que sí.** Quedan dos
abiertos, los dos fuera del código:

1. **El operador es un canal de realimentación.** El muro está entre el *arquitecto* y los
   resultados. No hay muro entre el *operador* y los resultados. Cuando el primer lote de
   estrategias fracase, el operador elegirá qué transcribir después mirando cómo le fue al anterior
   — y eso **es selección bajo D1**, ejecutada por un humano en vez de por un bucle.
2. **El sesgo de supervivencia de la fuente.** Un trader publicado no publica una muestra aleatoria
   de sus ideas: publica la que funcionó en el régimen reciente. Genesis hereda el sobreajuste de
   una cantidad desconocida de ensayos invisibles que jamás entrarán al denominador.

Ninguno de los dos invalida el diseño feed-forward —que sigue siendo estrictamente mejor que el de
lazo cerrado— pero los dos exigen mecanismos propios. Están en I6 e I7 (§2).

### Por qué D-C importa, mecánicamente

No es sólo que los CFD tengan fricción y una contraparte con conflicto de interés. Hay dos razones
verificadas:

1. **Un ensayo sobre CFD cuesta lo mismo y compra menos.** Bajo D1 un ensayo es un ensayo. Correr 40
   estrategias sobre CFD y después las mismas 40 sobre futuros son **80 en el denominador**, no 40.
   Probar primero en MT5 duplica el costo estadístico de cada candidato.
2. **RVOL mide otra variable.** `candidate_b1_orb.yaml` filtra por volumen relativo. En MT5 el
   «volumen» es conteo de ticks del feed del bróker; en CME son contratos negociados. No es la misma
   variable con más ruido: es otra variable. Un filtro RVOL validado sobre CFD no está validado para
   futuros ni parcialmente.

**[rev] Lo que NO es una razón de D-C, aunque lo parezca.** El documento original argumentaba además
que `ledger_extra_trials` (`src/genesis/validation/verdict.py`) no filtra por símbolo, bróker ni
clase de activo, así que un `TrialRecord` de CFD penaliza para siempre el DSR de los candidatos de
futuros (punto 4 del [#114](https://github.com/ramaDben/genesis/issues/114)).

Eso es cierto pero es **circular**: si D1 resuelve que el venue es una *exigencia* y no una
dimensión de selección, el remedio correcto es particionar el ledger por venue, no abandonar un
universo. La limitación del ledger no es una razón para D-C — es **una consecuencia a resolver**, y
queda como requisito concreto en C.3.

---

## 2. Los invariantes del arquitecto

No son casillas. Son las condiciones que cualquier casilla debe respetar, y cuya violación invalida
el resultado aunque el código funcione.

| # | Invariante | Mecanismo que lo sostiene |
|---|---|---|
| **I1** | El proponente nunca ve resultados OOS | Separación física de almacenes, no permiso |
| **I2** | El corpus registra lo que dice el mundo, jamás lo que dijo el evaluador | Dos rutas distintas, auditables por separado |
| **I3** | Toda dimensión sobre la que se **selecciona** cuenta como ensayo; ninguna sobre la que se **exige** | D1 del RFC [#57](https://github.com/ramaDben/genesis/issues/57), ratificada en #76 |
| **I4** | Un genoma que declara una regla debe ejecutar esa regla | Gramática con despacho (A.1) + Gate 0 (A.2) |
| **I5** | Verificar el mecanismo no es correr un ensayo | Barras sintéticas deterministas para lo primero; futuros para lo segundo |
| **I6** **[rev]** | El **orden de las fuentes** se declara antes de ver un solo resultado | Pre-registro (C.4). Elegir el siguiente trader mirando cómo le fue al anterior es selección |
| **I7** **[rev]** | Un «sobrevive» de fuente externa vale **menos** que uno de hipótesis pre-registrada | El holdout (C.1) es lo único que mide el sobreajuste heredado. Refuerza que sea gate, no informativo |

### Sobre I5, que es lo que mantiene todo construible hoy

Hay dos actividades que se parecen y no son la misma:

- **Verificar el mecanismo** — comprobar que un genoma con `kind: mean_reversion` ejecuta reversión
  y no ruptura de apertura. No produce veredicto, no produce `p_pass`, **no entra al denominador**.
  El patrón ya existe: `tests/strategy/genome/test_b1_equivalence.py:101`
  (`test_b_vs_b1_synthetic_5000_bars_equivalence`) lo hace con 5.000 barras sintéticas deterministas.
- **Correr un ensayo** — el pipeline completo hasta veredicto. Eso cuesta, y ese es el que no toca
  CFD.

**Consecuencia práctica: todo el carril A se construye y se verifica sin tocar un solo dato de
mercado real y sin gastar un ensayo.**

### Sobre I7, y qué se espera de verdad

Corolario que conviene tener escrito antes del primer resultado, no después: **se espera que la
enorme mayoría de los claims externos no sobreviva.** Eso no es el fracaso del proyecto — es su
producto. Un «no sobrevive» de una estrategia famosa es un resultado informativo, publicable y
barato. Un «sobrevive» es el caso que exige más escepticismo, no menos, porque esa estrategia ya
pasó por un filtro de selección invisible antes de llegar acá.

---

## 3. Los tres carriles

| Carril | Contenido | Qué bloquea |
|---|---|---|
| **A. Arquitecto** | gramática, Gate 0, corpus, primitivas, enmascaramiento, subespecificación, dedup, adaptador | nada del resto |
| **B. Datos CME y motor honesto** | falsación previa, fuente, fichas, exportador, sesiones, costos por instrumento, F-retardo, guarda de universo | **el primer ensayo real**, y que su resultado signifique algo |
| **C. Decisiones** | política, holdout, semántica de ensayos, pre-registro | **la interpretación de cualquier resultado**, y A.6 |

**[rev 2026-09-20] B va primero, no en paralelo.** La versión original decía que A y B avanzaban en
paralelo sin tocarse. Es cierto que no se tocan, y eso ocultó lo que importa: **B es el único carril
en el camino crítico hacia el primer veredicto.** El carril A construye la máquina de proponer; sin
B no hay nada que responda. Ver §9.1 para el razonamiento completo y §9.4 para el orden vigente.

**[rev 2026-09-22] Y B creció, porque «tener los datos» no alcanza.** Se le sumaron tres casillas que
no son de datos sino del motor que los consume: **B.4** (los costos son globales y cuatro veces
mayores que los reales), **B.5** (F-retardo estaba declarado y sin dueño) y **B.6** (el denominador
de C1 es «lo que le pases»). Las tres comparten el mismo defecto: el motor **responde igual** tenga
razón o no, sin avisar. Un carril que entrega datos a un motor que miente no desbloquea el primer
veredicto — lo vuelve peligroso.

C no bloquea construir —salvo A.6, que necesita D1— pero sí bloquea que lo construido signifique
algo. Dos de sus casillas (C.1a y C.1b) se volvieron **urgentes** al adelantarse B: el holdout hay
que declararlo antes de mirar la primera vela, y B.3 es el punto de no retorno. **[rev 2026-09-21]
Las dos ya están escritas** (PR #124) y **ratificadas el 2026-09-21**.

---

## 4. Casilla cero: lo que va antes que todo

### ☑ 0.1 — Leer el estudio de falsación de señales OHLCV en MNQ *(cerrada 2026-09-20, PR #122)*

**Qué es.** El [#107](https://github.com/ramaDben/genesis/issues/107) deja anotada una pista sin
leer: un trabajo en arXiv titulado *«Structural Limits of OHLCV-Based Intraday Signals in MNQ
Futures: A Systematic Falsification Study»*.

**Por qué va primero.** Es el instrumento exacto del destino (MNQ), la familia de señales exacta que
hoy es lo único que genesis puede expresar (intradía sobre OHLCV) y la conclusión exacta que más
importa (falsación sistemática). Cuesta una lectura. Es el ítem con mejor relación información/costo
de todo el documento.

**[rev] Es un insumo, no una compuerta.** El documento original le daba poder de veto sobre el
roadmap entero. Un preprint sin revisión de pares no lo tiene: puede traer ventanas no
representativas, fricciones irreales o una definición estrecha de señal. Su calidad se evalúa como
la de cualquier otra fuente del corpus, con la misma prueba de predicción falsable que A.2 le exige
a todas. Si el trabajo aguanta esa prueba, entonces sí reordena; si no, queda archivado como
literatura relacionada.

**Hecho cuando.** Está leído, entrado al corpus con su procedencia y su predicción falsable, y la
conclusión —sirva o no— está escrita con su porqué.

**Resultado.** Leído en la fuente primaria: arXiv:2605.04004 v3 (Mesfin 2026), PDF de 17 páginas.
**No reordena el roadmap** —preprint de autor único, sin revisión de pares, denominador de ensayos
autodeclarado como desconocido, controles positivos que son sobrevivientes de su propia búsqueda,
pliegue OOS contaminado admitido, sin ajuste de roll: bajo los gates de genesis no pasaría G4— pero
**sí mueve el prior**, y fuerte sobre la familia ORB, que es el candidato prioritario del torneo:
T = 0,88 sobre 447 operaciones OOS. Corpus sembrado en `docs/corpus/` con seis claims y la
evaluación de la fuente *como fuente*. Ver `docs/corpus/0.1-conclusion.md`.

### ☑ 0.2 — Demostrar que el ledger registra *(cerrada 2026-09-20, PR #123)*

**Qué es.** Correr el pipeline de punta a punta sobre datos sintéticos y verificar que
`ledger/trials.jsonl` queda con un registro.

**Por qué va antes que el arquitecto.** Hoy tiene **cero líneas**, después de tres backtests reales
corridos en agosto — los runners ad-hoc de esa sesión nunca llamaron a `record_trial_completions`.
El cableado existe y está activo por defecto (`scripts/run_pipeline.py:233`, hay que pedir
`--no-ledger` para apagarlo), pero nunca se demostró de punta a punta.

La política A2 del proyecto dice que lo único que separa al arquitecto de una casa de apuestas es la
contabilidad honesta de ensayos. **Un arquitecto sobre un contador que nunca contó es exactamente lo
que A2 prohíbe.**

**Hecho cuando.** Una corrida sintética deja un `TrialRecord` verificable, y una segunda corrida
idéntica **no** duplica el registro (idempotencia del `trial_id`). El `dataset_hash` sintético lo
deja distinguible de cualquier ensayo real.

**Vía.** Rápida — es un script y una medición, no toca `src/`.

**Resultado: PASA.** `scripts/prove_ledger.py`, dos corridas idénticas sobre datos sintéticos
deterministas: 1 registro tras la primera, **1 tras la segunda**, 0 duplicados,
`trial_id=dba20c3d…`. Tres hallazgos de paso:

1. Escribe en un ledger **temporal**, no en el del repo: `verdict.py` suma `ledger_extra_trials` sin
   filtrar por símbolo ni clase de activo, así que un registro sintético inflaría el `n_trials` de
   toda corrida real futura. Defecto del punto 4 del #114, ahora confirmado en la práctica.
2. `--candidate B` está **roto** desde el #109 (`BacktestConfigError: Sin ExitGeometry`): la fábrica
   por letra no implementa `ExitGeometryProvider`. Hay que pasar `--genome`. **D2 se está
   resolviendo por atrición**, no por decisión — ver C.3.
3. En la segunda corrida el pipeline imprime `ledger: +1 registrado(s)` **aunque no escribió nada**:
   cuenta los `trial_id` que devuelve `record_trial_completions`, no las filas que `append_trial`
   agregó. El archivo queda correcto; la salida miente al operador.

Verificado además: `ledger/trials.jsonl` está en 0 bytes y `ledger/archive/trials_pre_109.jsonl` en
0 líneas. El contador arranca genuinamente en cero y nunca se archivó nada.

---

## 5. Carril C — Las decisiones con ventana que se cierra

### ☑ C.1a — Declarar el régimen del holdout ([#81](https://github.com/ramaDben/genesis/issues/81), decisiones 2 y 3)

> **Escrita** en [`POLITICA_HOLDOUT.md`](POLITICA_HOLDOUT.md) ([PR #124](https://github.com/ramaDben/genesis/pull/124)).
> Estado: **RATIFICADA el 2026-09-21.** Resultado: el holdout es **gate, no
> informativo**; **una mirada por candidato**, sin reintento y sin reset; mirar cuenta como ensayo;
> el borde entra al manifiesto y se define por **fecha calendaria**, no por proporción.
>
> **Corrección posterior (§2.1 de ese documento), detectada por una revisión externa de agy:** lo
> que se congela antes de mirar el holdout es el **procedimiento** —genoma, grilla, criterio de
> selección y **cadencia de reajuste**—, **no los parámetros ajustados**. Congelar los parámetros
> contradecía el `step = 126` del propio walk-forward, que afirma que el ajuste se rehace cada seis
> meses. Efecto lateral: desactiva la objeción de que un holdout grande deja el entrenamiento ciego
> a los años recientes.

**[rev] El #81 se parte en dos.** El documento original lo trataba como una sola casilla «gratis
ahora», y eso es falso para una de sus tres decisiones.

Estas dos **no dependen del dataset** y son gratis hoy:

- **Decisión 2 — qué pasa cuando se mira.** ¿Informativo o gate? I7 empuja fuerte hacia gate: si el
  holdout es lo único que mide el sobreajuste heredado de la fuente, un número que no obliga a nada
  es un número que se racionaliza.
- **Decisión 3 — cuántas veces se puede mirar.** Es D1 aplicada al holdout. Mirar, fallar, ajustar y
  volver a mirar es selección sobre el holdout.

**Hecho cuando.** Las dos están escritas con su porqué, y el borde del holdout está declarado como
clave de identidad del artefacto junto a los hashes de dataset y perfiles.

### ☑ C.1b — Dimensionar el holdout *(estrictamente antes de B.3)*

> **Escrita** en [`DIMENSIONAMIENTO_HOLDOUT.md`](DIMENSIONAMIENTO_HOLDOUT.md)
> ([PR #124](https://github.com/ramaDben/genesis/pull/124), el mismo que C.1a — **no se pueden
> ratificar por separado**). Estado: **RATIFICADA el 2026-09-21.**

**Resultado: corte el 2025-01-01, holdout de 21 meses.** Medido corriendo el generador de ventanas
real (`wfa._iter_window_bounds`), no estimado, sobre MNQ desde 2019-05-05:

| Corte | Holdout | Ventanas | Velocidad mínima que exige G1 | Operaciones en el holdout* |
|---|---|---|---|---|
| 2025-10-01 | 12 meses | 10 | 1 cada 4,2 días | 58 |
| **2025-01-01** | **21 meses** | **9** | **1 cada 3,8 días** | **114** |
| 2024-10-01 | 24 meses | 8 | 1 cada 3,4 días | 147 |

<sub>\* Para la estrategia más lenta que todavía califica — el caso peor, que es el que decide.</sub>

Las dos últimas columnas tiran para lados opuestos: un holdout grande **achica el universo de
estrategias admisibles** (G1 pide 300 trades OOS sumados sobre menos ventanas) pero **hace más
confiable la única prueba sin reintento**. 21 meses es el cruce: casi el doble de evidencia que 12
por un costo casi nulo en velocidad mínima, y con 40 días hábiles de margen antes de caer a 8
ventanas.

**Criterio de aprobación, que estaba abierto: llegar a ser fondeado.** Se recorre el holdout día
por día, **en su orden real**, con el reglamento del Rapid EOD 50K —objetivo $3.000, $2.000 de
pérdida máxima con arrastre al cierre, 4 días mínimos, consistencia 30%—, y al quebrar se reinicia
el intento al día hábil siguiente. **Aprueba si hay al menos un fondeo y los fondeos son al menos
tantos como los quiebres.** Ningún umbral lo elegimos nosotros. Días hasta el fondeo e intentos
consumidos se reportan, pero no vinculan. La idea de anclar el criterio al reglamento en vez de a
una métrica estadística la propuso agy.

> **[corregido el 2026-09-21]** La primera redacción preguntaba si la cuenta **sobrevivía** los 21
> meses. Eso mide algo que el desafío real nunca pide: termina en cuanto se llega al objetivo,
> normalmente en semanas. Y la consistencia del 30% **no descalifica** —verificado en fuente
> primaria, sólo obliga a operar más días—, así que no cabe en un criterio binario de supervivencia.
> La misma redacción afirmaba que `validation/prop_sim.py:run_prop_sim` **ya lo implementaba**:
> **es falso.** Genera los días con un *moving-block bootstrap* y devuelve una probabilidad; con un
> límite que arrastra, barajar el orden borra justo lo que decide el quiebre. Falta escribir una
> entrada que consuma la secuencia real, y es la única pieza de código que el criterio necesita.

**Salvedad que sigue en pie:** `p_pass` está declarado en el propio código como **sesgado al alza**
(evalúa cierre-a-cierre, nunca equity flotante intradía) y explícitamente **no** como margen de
seguridad. Por eso se reporta y no vincula.

**Cerrado el 2026-09-21 — MNQ, no NQ.** Con $2.000 de pérdida máxima, el contrato grande mueve $20
por punto: 100 puntos en la apertura liquidan la cuenta en una sola operación, contra $2 por punto
del micro. La granularidad pesa más que los años de historia, y la tabla de arriba ya estaba
calculada sobre MNQ. Deja de ser una dependencia de B.3.

Todo el análisis de costo que el #81 trae escrito —perder una ventana, dejar G1 con 8% de margen
sobre 405 trades— estaba calculado contra el dataset US500 de CFD, que **murió con D-C**. Queda
reemplazado por la tabla de arriba.

**La ventana de irreversibilidad sigue abierta y se cierra en B.3**, en el instante en que se mire
la primera barra de CME. Un holdout no se puede declarar sobre datos que ya se miraron.

Verificado: **no existe ningún holdout.** Cero menciones de `holdout` en `src/`, `scripts/` y
`tests/`.

**Nota de gobernanza.** El #81 está reservado (`state:diferido`). El roadmap **propone** con el
argumento; moverlo es decisión del dueño del proyecto, no del agente.

### ☐ C.2 — Retomar `POLITICA.md` ([#86](https://github.com/ramaDben/genesis/issues/86), hoy `state:diferido`)

**Esto no es una propuesta: el issue se reactivó solo.** Su condición de reanudación número 3 dice
textualmente:

> *«Se decide construir el arquitecto — la respuesta A2 lo dejó condicionado a que el ledger de
> ensayos funcione, y esa condición es una cláusula de política todavía no escrita.»*

Esa decisión se tomó el 2026-09-20. El issue se dispara por sus propios términos, no porque yo lo
sugiera.

**Alcance mínimo para no bloquear.** No hace falta la entrevista completa (faltan B2–B4 y los bloques
C a G). Hace falta la cláusula que A2 dejó pendiente: **bajo qué condiciones se autoriza al
arquitecto a generar ensayos, y cuál es el techo.** Eso es D4 del RFC #57 («¿hay un techo declarado
de presupuesto de ensayos?»), que con un arquitecto pasa de teórico a operativo.

**Hecho cuando.** Existe `POLITICA.md` versionado y con hash, con al menos: la cláusula del
arquitecto, el techo de presupuesto de ensayos, y los invariantes I1–I7 de este documento elevados a
política citable.

### ☐ C.3 — RFC [#57](https://github.com/ramaDben/genesis/issues/57): cerrar lo que el arquitecto vuelve urgente

**[rev] Esta casilla se movió de lugar: bloquea a A.6.** El documento original la ponía al final y
al mismo tiempo declaraba en A.6 que A.6 la necesitaba. Contradicción interna, corregida.

Cinco de sus siete decisiones abiertas dejan de ser teóricas:

| Decisión | Qué cambia con el arquitecto |
|---|---|
| **D1** — qué cuenta como ensayo | Pregunta nueva y **bloqueante de A.6**: ¿cada interpretación de un claim subespecificado es un ensayo propio, o la familia cuenta como uno? Y: ¿el venue entra como **exigencia** o como **selección**? De eso depende si el ledger debe particionar (ver §1, D-C) |
| **D2** — destino del `CANDIDATE_REGISTRY` | Sigue resuelta **por elusión**: `strategy/contract.py:63` sigue indexado por letra y los genomas compilados nunca entran ahí. Conviene declararla al formalizar la gramática, no seguir eludiéndola |
| **D4** — techo de presupuesto de ensayos | Con un arquitecto pasa de teórico a operativo. Es la cláusula que C.2 tiene que escribir |
| **D5** — límites de complejidad del genoma | **[rev] Omisión del documento original, corregida.** A.1 propone una gramática cerrada y A.2 un catálogo cerrado de mecanismos: las dos son respuestas *de facto* a D5, tomadas por construcción y sin declararlas. Es el mismo modo de falla que D2. Un límite de complejidad además no es estético: cada grado de libertad extra del genoma es una dimensión sobre la que el arquitecto puede seleccionar, y por D1 eso son ensayos. **La gramática de A.1 no se cierra hasta que D5 esté escrita** |
| **D7** — concurrencia del ledger | `append_trial` **no es atómico entre procesos**. Quedó fuera de alcance del #53 explícitamente. Cualquier arquitecto que paralelice corridas lo choca de frente |

**D6** («qué autores y en qué orden») se reformula: con D-A pasa a ser *qué traders y en qué orden*,
y por I6 esa respuesta es **pre-registro**, no una decisión que se revisa entre lotes.

### ☐ C.4 — Pre-registro ([#88](https://github.com/ramaDben/genesis/issues/88))

**Sube de posición.** Era «gratis, en cualquier momento»; ahora es **la frontera entre el corpus y
el ledger**: el mecanismo que hace que un claim transcrito sea un ensayo limpio y no una idea que ya
se vio correr.

**[rev] Y ahora carga un segundo trabajo: implementa I6.** No alcanza con pre-registrar cada
hipótesis — hay que pre-registrar **el orden en que se van a transcribir las fuentes**, antes de ver
el primer veredicto. Sin eso, el operador se convierte en el lazo de realimentación que D-B creía
haber eliminado.

Su argumento original sigue en pie: las hipótesis del operador nacieron mirando estos mismos
gráficos, y las de los traders publicados también. Es sobreajuste humano, inevitable, y es
exactamente lo que el holdout de C.1 atrapa.

---

## 6. Carril A — El arquitecto

### ☐ A.1 — Gramática con ramificación ([#110](https://github.com/ramaDben/genesis/issues/110))

**Qué es.** Convertir los `kind` del genoma en enums cerrados con despacho explícito y fallo
ruidoso.

**Por qué es la primera casilla de construcción.** Dejó de ser «el issue más estructural» y pasó a
ser **requisito de viabilidad del objetivo**. Verificado hoy, tras el merge del #109:

- `src/genesis/strategy/genome/schema.py:64-68` — `GenomeAlpha` sigue declarando
  `regime_filter: Mapping[str, Any] | None` y `entry_trigger: Mapping[str, Any]`. Diccionarios
  opacos. La clave `kind` del alfa **no es un campo del esquema**.
- `src/genesis/strategy/genome/schema.py:75` — el único `kind` tipado es el de `GenomeRiskExit`, y
  es `str` libre.
- `src/genesis/strategy/genome/candidate.py:270` — `is_chandelier = ... == "chandelier_trailing"`.
  Un booleano, no un despacho.

Consecuencia para el objetivo: hoy un trader de reversión a la media, de order blocks o de VWAP
compila sin una queja y se ejecuta como ruptura de rango de apertura. Un arquitecto que transcribe
traders sobre esta gramática **no rinde poco: produce falsedades con formato válido.**

**Lo que esta casilla NO entrega.** El mecanismo de despacho, no las estrategias. El propio DoD del
#110 lo dice: *«registrando un `kind` de prueba se ejecuta una rama distinta de la de ORB. No admite
una estrategia real al repo, prueba el mecanismo»*. Las primitivas van en A.4.

Las referencias de línea del cuerpo del #110 quedaron viejas con el #109 (decía 52-53 y 274); la
sustancia se verificó intacta.

**Hecho cuando.** Los criterios del DoD del propio issue, con énfasis en el 4 y el 5: un test que
demuestra que el despacho **es** un despacho, y otro que fija que `entry_trigger.kind:
"mean_reversion"` **no compila** en vez de ejecutarse como ORB. Y el 6: la equivalencia bit a bit de
B.1 sigue verde — este change no puede cambiar ningún resultado de backtest.

**Vía.** Ciclo SDD completo. Toca contrato público de capa 2.

**[rev 2026-09-22, D-E punto 5] Lo que esta casilla habilita después: retirar las carpetas por
candidato.** Hoy el ORB está implementado **dos veces**: `strategy/candidate_b/candidate.py` (a
mano, lo que `factories.py` corre como `"B"`) y `strategy/genome/candidate.py` (compilado del YAML).
La equivalencia ya está probada (`tests/strategy/genome/test_b1_equivalence.py`, 5.000 barras
sintéticas), así que cuando la gramática ramifique se borra la versión a mano y la estrategia pasa a
ser **sólo un dato**. `strategy/candidate_a/smc/` no es una estrategia sino un motor de estructura de
mercado (ADR-D8): sale de `candidate_a/` y pasa a **librería de primitivas** junto a `common/`, con
cuyos `atr.py` y `timeframe.py` hoy se duplica. `strategy/` queda con tres cosas: contrato,
compilador y primitivas. Dos restos a limpiar en el mismo movimiento: el genoma declara
`symbol: "US500"` —ticker CFD, prohibido por D-C— en un campo que **ningún código de producción lee**,
y `_candidate_family` (`trial_ledger.py:150`) toma el primer carácter del id, así que todo genoma
`CANDIDATE-…` cae en la familia «C» del TSMOM. Sólo afecta reportes; se reemplaza por un campo
explícito de familia en el genoma.

### ☐ A.2 — Gate 0 mecánico, reformulado ([#105](https://github.com/ramaDben/genesis/issues/105) + [#107](https://github.com/ramaDben/genesis/issues/107), fundidos)

**Qué es.** Que `parse_genome` valide la procedencia, hoy que la ignora por completo.

**Lo que cambia respecto de cómo están escritos los issues.** Ambos asumen que toda fuente es
académica. Con D-A la fuente típica pasa a ser un trader publicado, y el Gate 0 deja de preguntar
«¿tiene paper?» para preguntar **«¿la procedencia está completa y el genoma coincide con lo que la
fuente dice?»**. Tres consecuencias:

1. **`paper_ref` obligatorio deja de tener sentido como está.** Hoy `schema.py:123-127` exige el
   campo no vacío con el mensaje *«academic provenance D1»*. Un video no tiene paper, y meter la URL
   ahí corrompe el significado del campo en silencio. Hace falta un bloque de procedencia que admita
   fuente no canónica: canal, URL, marca de tiempo, **cita textual del claim**.
2. **`fidelity: interpreted` ya está soportado.** Verificado: `schema.py:129-138` acepta los cuatro
   valores del enum y sólo rechaza los que no existen. *(Corrige a la memoria
   `change-103-arquitecto-y-compilador-genomas`, que afirma que el parser rechaza lo no canónico —
   es falso.)*
3. **La prueba de la predicción falsable**, que es el antídoto contra el defecto del #107 producido
   a escala. Toda entrada con mapeo a mecanismo debe poder escribir:

   > *«La fuente predice que X ocurre; la regla apuesta a X.»*

   Gao et al. la pasa: predice momentum intradía tras el rango de apertura, y el ORB lo
   operacionaliza. `candidate_c1_gold_lob.yaml:4` no la pasa: cita a Lou, Polk & Skouras sobre
   retornos nocturnos vs intradía de **acciones de EE.UU.** para justificar un ORB de 60 minutos en
   **oro** sobre la apertura de Londres. Nadie mintió: el paper es real y el tema es afín. El
   mecanismo no tiene nada que ver.

   Eso es lo que el arquitecto produciría en masa sin bloqueo mecánico. Un LLM al que se le pide
   mapear «order block» a literatura devuelve Kyle (1985), O'Hara, Easley — con tono seguro,
   bibliografía real y ninguna relación mecánica con un rectángulo dibujado en un gráfico.

#### [rev] Cómo se hace mecánica esa prueba

El documento original enunciaba la prueba sin decir cómo se hace cumplir, y eso la dejaba en uno de
dos lugares malos: un campo de texto que sólo se verifica no vacío (cosmética que cualquiera burla
escribiendo prosa verosímil) o un LLM juez (no determinista, y viola el invariante de determinismo
del proyecto).

**Taxonomía cerrada de mecanismos.** Mismo patrón que A.1 aplica a los `kind`, aplicado acá a la
procedencia:

- El corpus mantiene un catálogo **finito y enumerado** de mecanismos económicos —desbalance de
  inventario, momentum intradía, estacionalidad de apertura/cierre, barrido de liquidez en zonas de
  stops, prima de riesgo por provisión de liquidez— cada uno con su fuente y su **predicción
  declarada**.
- El genoma no escribe prosa: **referencia un ID de mecanismo**.
- Gate 0 verifica mecánicamente dos cosas: que la referencia resuelva contra el catálogo, y que la
  predicción declarada de ese mecanismo sea compatible con el `kind` del `entry_trigger`.

El juicio humano ocurre **una vez**, cuando un mecanismo entra al catálogo, y queda auditable. No se
repite ni se delega a un modelo en cada compilación. Un claim cuyo mecanismo no está en el catálogo
no compila: hay que darlo de alta primero, con su fuente.

**Hecho cuando.** Un genoma sin bloque de procedencia completo no compila; uno que referencia un
mecanismo inexistente no compila; uno cuyo mecanismo es incompatible con su `kind` no compila; y los
dos genomas existentes están migrados con su `fidelity` honesto — lo que **cambia el `trial_id` de
B1, y eso es correcto y debe quedar registrado, no evitado** (DoD 3 del #107).

**Vía.** Ciclo SDD completo.

### ☐ A.3 — El corpus

**Qué es.** El registro por tópicos con procedencia. Markdown enlazado, versionado en el repo —
`docs/corpus/`, no un vault personal, porque si sustenta una admisión tiene que ser auditable.

**[rev] Subió de posición.** Estaba después del registro de subespecificación; va antes por dos
razones: alimenta la taxonomía de mecanismos de A.2, y **decide qué primitivas construir en A.4**,
porque es lo que dice qué describen realmente los traders.

**La unidad es el claim**, no el autor ni el concepto. Un archivo = una afirmación testeable, con
cita textual, fuente, marca de tiempo, autor, concepto al que pertenece, y qué predice. Autores y
tópicos son índices sobre claims.

Importa por una razón: **las contradicciones existen entre claims, no entre autores.** «Fulano
contra Mengano» es una pelea de opiniones; «el claim 47 contradice al 112 sobre si el filtro de
volumen mejora o degrada el ORB» es una proposición adjudicable que se compila a dos genomas que
difieren en una sola cosa.

**Las dos funciones que sí agregan valor:**

1. **Traducir folclore a mecanismo.** `order block` → *desequilibrio de liquidez* → fuente → entrada
   en la taxonomía de A.2. Y el concepto que **no logra mapearse** queda marcado como tal, que es
   información valiosísima y barata: es Gate 0 diciendo que no hay por qué antes de gastar un
   ensayo. **La mayoría del vocabulario retail no va a mapear, y ese es el resultado esperado, no
   una falla del corpus.**
2. **Minar contradicciones y condiciones de falla, no consensos.** El consenso no dice nada: doce
   autores hablando de order blocks no son doce evidencias, son una idea copiada doce veces por
   gente que se lee entre sí. El desacuerdo especificado sí dice dónde mirar, y es informativo caiga
   como caiga.

**La ranura ya existe.** `candidates/specs/candidate_c1_gold_lob.yaml:7-15` declara un bloque
`sources:` con `academic`, `institutional` y `failure_mode`. Está sin trackear en git y nada lo
valida, pero es la forma que el corpus llenaría.

**Prohibición explícita (I2).** Ninguna métrica derivada de contar nodos puede alimentar una
decisión de admisión. Nada de «score de confianza» por volumen de menciones — un grafo hace que la
copia se vea como corroboración, y esa falla va en dirección permisiva.

**Hecho cuando.** Existen los primeros N claims con procedencia completa, al menos un concepto
marcado como *sin mecanismo publicado*, al menos una contradicción identificada entre dos claims, y
la primera versión de la taxonomía de mecanismos que A.2 consume.

**Vía.** Rápida — `docs/`, no ejecuta.

### ☐ A.4 — Primitivas de ejecución **[rev — casilla nueva]**

**Qué es.** La matemática y el manejo de estado forward-only de cada familia operativa que el
despacho de A.1 va a poder nombrar: reversión a la media, VWAP, barrido de liquidez, lo que el
corpus muestre que hace falta.

**Por qué faltaba.** Es el hueco que encontró la revisión cruzada, y es serio. A.1 entrega el
mecanismo de despacho; una tabla de despacho con una sola rama implementada **sigue siendo una sola
estrategia**. Sin esta casilla, el adaptador de fuente alimentaría claims que la gramática sabe
nombrar y nada sabe ejecutar, y el proyecto quedaría con un compilador sofisticado sin qué correr.

**Por qué acá y no antes.** Porque el corpus (A.3) dice **cuáles** construir. Construirlas antes es
adivinar qué describen los traders, que es exactamente el tipo de suposición que este proyecto
existe para no hacer.

**Restricción heredada.** Estado incremental **forward-only**: cada primitiva se escribe como
estimador online, no como cálculo vectorizado sobre dataframe. Es el invariante anti-anticipación de
la capa 3 y no admite excepción.

**Hecho cuando.** Cada primitiva admitida tiene su test de propiedad (ningún output de `on_bar(t)`
cambia si se mutan barras posteriores a `t`) y su verificación de mecanismo sobre barras sintéticas
deterministas, al estilo de `test_b1_equivalence.py`. Ninguna consume un ensayo (I5).

**Vía.** Ciclo SDD completo, una por una. Cada primitiva es un contrato de capa 2 nuevo.

### ☐ A.5 — Enmascaramiento y trazabilidad de la llamada al arquitecto **[rev — casilla nueva]**

**Qué es.** La costura donde se invoca al LLM, tratada como parte del artefacto de reproducibilidad.

**El problema que resuelve, que no estaba en el documento.** `LookaheadError` protege a la
*estrategia* de ver barras futuras. **No protege al arquitecto de haberse memorizado el mercado.** Un
modelo entrenado hasta 2026 que transcribe una regla sobre datos 2019-2026 ya sabe qué pasó, y ese
conocimiento entra justo por el hueco del relleno de parámetros subespecificados (A.6): cuando el
arquitecto elige un valor, su sesgo de preentrenamiento sobre qué funcionó es indistinguible de un
criterio.

El ledger **no puede detectarlo**: contaría el ensayo como honesto siendo tramposo.

**El diseño de referencia existe.** `HephaestLab/TraderHarness` lo resuelve mecánicamente con
enmascaramiento doble: máscara temporal por construcción en cada salida de datos, calendario
relativo (`D-1`, `D+0` en vez de fechas absolutas), entidad neutra determinista **preservando las
reglas del instrumento**, saneo de la misma máscara sobre respuestas y trazas, y auditoría de fuga
antes de exportar. Dicen explícitamente que la auditoría automatizada no implica riesgo cero de
re-identificación semántica, y esa honestidad conviene heredarla.

Equivalente acá: el arquitecto no ve «ES, marzo de 2024»; ve «instrumento con este `tick_size`, este
multiplicador y este horario de sesión, ventana 7».

**La segunda mitad: la llamada es parte del artefacto.** La reproducibilidad institucional del
proyecto (config_version + hash de dataset + ficha de firma + semillas + commit) no contempla que una
decisión la haya tomado un modelo no determinista. Si un LLM entra al bucle, hay que persistir la
lista completa de mensajes, el schema de herramientas, la respuesta y el razonamiento, con replay
verificable por huella y sin API key — el patrón *cassette*.

**Hecho cuando.** El arquitecto no puede resolver qué instrumento ni qué fechas está mirando a
partir de lo que se le entrega; existe una auditoría de fuga que corre antes de persistir; y toda
llamada queda con replay determinista referenciado desde el artefacto del ensayo.

**Vía.** Ciclo SDD completo si toca el formato del artefacto; vía rápida para la parte de tooling.

### ☐ A.6 — Registro de subespecificación *(bloqueado por C.3/D1)*

**Qué es.** El objeto contable que hoy no existe en ninguna parte, ni acá ni en ninguno de los
proyectos del ecosistema que se revisaron.

Un trader casi nunca especifica su regla al nivel que un simulador necesita. Dice «entro en el
retest con confluencia». Cada hueco que el arquitecto rellena es **un grado de libertad que el autor
nunca declaró**.

**[rev] El dilema, y cómo se resuelve.** Si una estrategia tiene 5 parámetros sin especificar:

- Probar 3 valores de cada uno son **243 ensayos por un solo video**, y ninguna estrategia va a
  superar G4 con ese denominador.
- Que el arquitecto elija «el razonable» sin declarar nada es dejar que el LLM invente la estrategia
  con sus sesgos de preentrenamiento — el problema que A.5 ataca.

La salida sale del lenguaje del propio D1: **el relleno se declara como exigencia, no como
selección.** Un único valor canónico, fijado y publicado antes de correr, sin grilla. Cuesta **un**
ensayo. La honestidad no viene de probar muchas variantes: viene de que el registro revele que ese
valor lo puso el arquitecto y no el autor, de modo que el veredicto diga «probamos *esta lectura* de
lo que Fulano dijo» y no «probamos la estrategia de Fulano».

Un claim tan subespecificado que ni siquiera admite un relleno canónico defendible se rechaza en
Gate 0 por falta de especificación. Eso es un resultado legítimo del corpus.

**Por qué está bloqueado por C.3.** La pregunta «¿cada interpretación es un ensayo propio o la
familia cuenta como uno?» es D1 y no tiene respuesta hoy. Implementar el registro antes de
responderla es codificar una semántica de conteo que nadie decidió. *(El documento original declaraba
esta dependencia y ordenaba en contra; corregido.)*

**Hecho cuando.** Todo genoma con `fidelity != canonical` declara qué dijo el autor textualmente,
qué no dijo, y qué eligió el arquitecto para llenar cada hueco. Y ese conteo alimenta el ledger, no
un documento.

**Vía.** Ciclo SDD completo. Toca el esquema del genoma.

### ☐ A.7 — Dedup semántico

**Qué es.** Detectar que dos genomas distintos producen la misma estrategia operativa.

**Por qué después de A.1 y A.4.** Mientras la gramática sea «parámetros sobre una plantilla fija»,
*toda* familia de genomas es la misma plantilla y el problema es máximo pero indistinguible del bug.
Con despacho y varias primitivas, la equivalencia semántica pasa a ser una pregunta legítima.

**El patrón de referencia.** `microsoft/RD-Agent` no compara especificaciones: compara
comportamiento. Antes de aceptar un factor nuevo lo correla contra toda la librería existente y veta
el redundante. Genesis ya tiene la maquinaria escrita —`test_b1_equivalence.py` compara señal por
señal sobre 5.000 barras— sólo que como test del compilador, no como gate del torneo.

**Restricción.** Se corre sobre ventana IS, nunca OOS. Se puede detectar el duplicado sin abrir
información que no debe guiar la búsqueda (I1).

**Hecho cuando.** Dos genomas que emiten señales idénticas sobre la ventana testigo se agrupan, y el
ledger reporta un «número efectivo de intentos» además del literal.

**Vía.** Ciclo SDD completo.

### ☐ A.8 — Adaptador de fuente

**Qué es.** La tubería: video/PDF/post → texto normalizado → claim en el corpus → genoma.

**Por qué va último.** Es lo único de este carril que **multiplica** el flujo, y no debe existir
hasta que todo lo que lo contiene esté puesto: la gramática que puede expresar lo que se transcribe
(A.1), las primitivas que pueden ejecutarlo (A.4), el Gate 0 que rechaza la procedencia incompleta
(A.2), el enmascaramiento que impide que el transcriptor use lo que sabe del futuro (A.5), el
registro que cuenta los grados de libertad inventados (A.6) y la dedup que evita pagar dos veces por
la misma idea (A.7).

Construirlo antes es exactamente lo que hace el patrón RBI de Moon Dev, que genera variantes con
filtros distintos y **no cuenta ninguna**.

---

## 7. Carril B — Datos CME

### ☑ B.1 — Fuente de datos y comisiones *(DoD cerrado 2026-09-21, [#126](https://github.com/ramaDben/genesis/issues/126))*

> **[rev 2026-09-21] Los seis puntos del DoD están respondidos.** Quedan dos decisiones humanas,
> no trabajo: aprobar la lista de compra y resolver §7.1c, que toca un invariante. El detalle
> completo con las cifras y las citas del contrato está en el [#126]; acá va lo que cambia el
> resto del roadmap. Todo verificado en fuente primaria, ninguna cifra inferida.

No hay MT5 para futuros. Las opciones reales son Databento, CME DataMine directo, el feed de
Rithmic/Tradovate, IQFeed o Norgate — con precios, licencias y granularidades muy distintas. El
requisito de reproducibilidad institucional exige que la fuente sea **estable y re-descargable**,
porque el hash de dataset tiene que poder recomputarse dentro de dos años. **[rev 2026-09-21] Esa
exigencia no la concede ningún proveedor del rubro** — el contrato de Databento dice lo contrario,
explícitamente. Ver §7.1c; es la única decisión humana que B.1 deja abierta.

~~Y las comisiones por contrato de MFFU **no están publicadas** en su help center; dependen de la
plataforma.~~ **[rev 2026-09-20] Esto era falso.** Sí están publicadas, en la *Futures Instrument
List* del help center. Ver la tabla más abajo.

**[rev] Entrega además el insumo de C.1b**: el catálogo real de fechas y la profundidad histórica
efectiva por contrato, que es lo que permite dimensionar el holdout.

**[rev 2026-09-21] Esta dependencia se resolvió por adelantado.** El dato que C.1b necesitaba era
la primera sesión utilizable del MNQ, y está verificado en fuente primaria contra los dos
proveedores: **2019-05-05** en FirstRate, y Databento declara el MNQ desde 2019. Con eso alcanzó
para dimensionar, así que **C.1b ya está escrita** y no bloquea. Lo que B.1 todavía tiene que
confirmar es el catálogo de contratos con sus fechas efectivas, que es insumo de B.2 y de la
elección de contrato, ya cerrada a favor de MNQ el 2026-09-21.

#### [rev 2026-09-20] Precio verificado en la fuente primaria

Consultado en `databento.com/pricing` y `databento.com/venues/cme-globex`:

| Hecho | Valor |
|---|---|
| Modelo de cobro | **Uso, por GB de datos binarios sin comprimir descargados** — no por dataset |
| Crédito inicial para cuentas nuevas | **$125, expira 6 meses después del alta** |
| Planes | Standard $199/mes · Plus $1.750/mes (anual) · Unlimited $4.500/mes (anual) |
| Cobertura | CME Globex MDP 3.0 |
| Esquemas incluidos **en todos los planes** | L0: `ohlcv-1s`, `ohlcv-1m`, `ohlcv-1h`, `ohlcv-1d` |
| Profundidad de MNQ | desde **2019** |

**Consecuencia.** El costo de entrada para barras OHLCV es plausiblemente **cero**: el crédito
inicial de $125 debería cubrir varios años de barras de 1m de un instrumento, porque el peso está
en el tick, no en la barra. El `~$42/trimestre` que cita el CLAIM del corpus es para **tick**, que
es órdenes de magnitud más pesado. Databento no publica una cifra por dataset para el histórico de
CME, así que **el número exacto sólo se conoce cotizando en la consola con el rango cargado** — eso
es parte del DoD de esta casilla.

#### [rev 2026-09-21] Alternativas relevadas, y por qué la data gratis no sirve para un veredicto

La pregunta se hizo explícitamente: *¿hay forma de obtener la data gratis, de datasets que otros
hayan subido a Reddit o GitHub?* Se relevó. **Sí hay data gratis; ninguna sirve para emitir un
veredicto.** Y en GitHub/Reddit **no existe un dataset comunitario serio** de futuros CME
intradía: lo que hay son recortes de pocos meses o scripts que descargan de las fuentes de abajo.

| Fuente gratis | Qué da | Por qué no alcanza |
|---|---|---|
| Kaggle (NQ 1 min) | 2022-12 a 2025-12, ~1,05 M de barras | 3 años; procedencia y empalme desconocidos |
| Yahoo Finance / Stooq | ES, NQ, CL, GC continuos | **sólo diario**; método de roll no documentado |
| TurtleTrader | contratos mayores desde los 70 | **sólo diario**, nada intradía |
| Sitios de CME / ICE | descarga directa | historia superficial, inviable en bulto |

**El problema no es el precio, es el empalme.** Un futuro es una sucesión de contratos
trimestrales; pegarlos produce un salto artificial en cada unión, y **cómo se corrige ese salto
cambia todos los resultados**. Es exactamente el defecto que invalida al estudio arXiv:2605.04004
(concatenación sin ajuste de roll, con ATR de 20 barras encima). Un CSV de procedencia desconocida
reproduce ese error **sin que podamos detectarlo**: un `no-go` no distinguiría entre estrategia
mala y dato malo, y un `go` sería peor.

A eso se suma la profundidad. Tres años de historia, contra G1 = 300 operaciones OOS más el
holdout, no alcanza.

> **Decisión de uso.** La data gratis **sí** se admite como **dataset de desarrollo**: ejercitar la
> tubería, cazar bugs y verificar mecanismos, igual que los datos sintéticos de la casilla 0.2. Es
> mejor que lo sintético porque trae los defectos reales (huecos, medios días, feriados). Bajo I5,
> verificar el mecanismo no es correr un ensayo. **Condición dura: nunca produce un veredicto y
> nunca escribe en el ledger.**

##### FirstRate Data — alternativa real a Databento

| | Databento | FirstRate Data |
|---|---|---|
| Cobertura MNQ | desde 2019 | **2019-05-05 → 2026-09-18** (verificado) |
| Granularidades | ohlcv 1s/1m/1h/1d | 1m, 5m, 30m, 1h, 1d |
| Continuos | resuelve el contrato, **precios crudos sin ajustar** | crudo **+ ajustado por diferencia + ajustado por proporción**, y archivos por contrato |
| Costo de compra | por GB; **$125 de crédito de alta** | **no publicado en el sitio** — sólo visible en el checkout |
| Actualizaciones | incluidas en el modelo por uso | 1 mes gratis; después **$99,95/año** por ticker de futuros, o **$59,95/mes** por el bundle de 130 |
| Muestra gratis | — | sí, descargable |
| Licencia | leer en B.1 | **prohíbe redistribuir el dato crudo**; permite obra derivada y extractos (~2 semanas) **con atribución** |

**Corrección:** una versión previa de esta conversación citó «$99,95» como el precio de compra de
FirstRate. Es incorrecto: **$99,95 es la suscripción anual de actualizaciones**. El precio de
compra del histórico no está publicado en las páginas públicas y hay que verlo en el checkout.
Conocerlo es parte del DoD.

**Cómo se dirime, y por qué el orden importa:**

1. **Cotizar Databento primero** (`scripts/quote_databento.py`). No cuesta nada y no consume
   crédito. Si MNQ en `ohlcv-1m` entra en los $125, la discusión termina ahí: gana Databento por
   procedencia —~~histórico inmutable, re-pedible idéntico dentro de dos años, que es justo lo que
   exige la reproducibilidad institucional~~.
   **[rev 2026-09-21] Cotizado: $14,48, entra sobrando — y el script ya existe, no era una
   aspiración. Pero la segunda mitad de la frase era un supuesto, y es falso.** El contrato no
   promete ni inmutabilidad ni re-descarga; §9.3 corta incluso el derecho de uso sobre la copia
   ya bajada al terminar la cuenta. Databento gana igual, porque ningún proveedor del rubro
   promete otra cosa — pero gana por precio y por procedencia documentada, no por una garantía
   que no está escrita. Ver §7.1c.
2. Si no entra, FirstRate es una alternativa legítima. **En ese caso se toma la serie SIN AJUSTAR**
   y el empalme se hace igual en B.3. Su ajuste es una caja negra en medio del dato, y meter una
   transformación opaca es precisamente lo que este proyecto no hace. **O sea que FirstRate no
   ahorra trabajo de B.3** — la ventaja de sus series ajustadas es poder contrastar nuestro
   empalme contra el suyo, que es control de calidad, no atajo.
3. La cláusula de licencia de FirstRate es **compatible** con publicar veredictos: lo que se
   publicaría son resultados y extractos, no las barras crudas. Conviene confirmarlo por escrito
   antes del primer veredicto público, no después.

#### [rev 2026-09-20] Comisiones de MFFU — punto 4 del DoD, **cerrado**

Publicadas en el help center de MFFU (*Futures Instrument List*), contra lo que este documento
afirmaba antes:

| Instrumento | Costo total ida y vuelta | Tick | Valor del tick | Punto | Fricción en puntos |
|---|---|---|---|---|---|
| **MNQ** | **$1,90** | 0,25 | $0,50 | $2,00 | **0,95 pts** |
| **NQ** | **$4,68** | 0,25 | $5,00 | $20,00 | **0,234 pts** |

Tres consecuencias:

1. **El número del CLAIM-001 no se contradice, se descompone.** El estudio de MNQ usa 2,0 pts =
   $4,00 de fricción, aritmética consistente con $2,00 por punto. La comisión de MFFU es $1,90, o
   sea **la mitad** de esa cifra. El resto es spread y slippage. **No es motivo para bajar el piso
   de fricción**: para ejecución manual el slippage es peor que el supuesto de un backtest, no
   mejor. Lo que se gana es que ahora el término de comisión es un dato medido y no un supuesto.
2. **En puntos, NQ tiene 4× menos fricción que MNQ.** MFFU permite 3 minis o 30 micros, así que la
   elección mini/micro no es sólo de tamaño: cambia el piso de rentabilidad por operación.
   **[rev 2026-09-21] Cerrado a favor de MNQ**, por granularidad: con $2.000 de pérdida máxima un
   solo NQ arriesga $20 por punto y no deja dimensionar la posición. **La contrapartida es real y
   hay que medirla:** a igual riesgo asumido, el micro paga del orden de **10× más comisión** que el
   mini, porque hacen falta ~10 micros para igualar un mini y la comisión es por contrato. Ese es el
   precio de la granularidad, y se cuantifica al recalibrar los costos a CME.
3. `costs.py` puede parametrizarse con cifras reales para MNQ y NQ.

> Pendiente: confirmar si $1,90 es uniforme entre plataformas (Tradovate, Rithmic, NinjaTrader) o
> si varía. La tabla de MFFU no lo desagrega.

#### DoD — estado final

| Punto | Estado 2026-09-21 |
|---|---|
| 1. Cuenta, crédito y fecha de expiración | **cerrado** — $125, vence **2027-03-21**, aplica a `Historical`; tope mensual fijado en $125 |
| 2. Cotización real del rango objetivo | **cerrado** — ver §7.1a |
| 3. Catálogo de contratos con fechas efectivas | **cerrado** — es el esquema `definition`, **$0,05** |
| 4. Comisión por contrato de MFFU | cerrado el 2026-09-20, ver arriba |
| 5. Licencia (redistribución y retención) | **cerrado — con resultado negativo**, ver §7.1c |
| 6. Precio de FirstRate en el checkout | **sin objeto**: Databento entra sobrando en el crédito |

**Por qué `ohlcv-1m` y no tick.** La ventana de frecuencia de §9.3 (1–4 operaciones diarias) no
necesita tick, y el filtro F-retardo sólo exige poder desplazar la entrada una barra o quince
minutos. Comprar tick ahora sería pagar por precisión que ninguna estrategia admisible usa.
**[rev 2026-09-21] Ahora eso tiene un número detrás:** el tick (`tbbo`) de MNQ sale **$2.548** y
las barras de un segundo **$437**, contra **$14,48** del minuto. El argumento ya no descansa sólo
en el principio.

#### §7.1a [rev 2026-09-21] La cotización, y por qué deja de haber decisión de compra

Obtenida por API con `scripts/quote_databento.py` (endpoints de metadata, gratuitos, no descargan
ningún byte) — no por la consola web, que no deja registro de qué se pidió. Dataset `GLBX.MDP3`,
2019-05-05 → 2026-09-21 salvo donde se indique:

| Símbolo | Esquema | GB | USD |
|---|---|---|---|
| `MNQ.v.0` (continuo) | `ohlcv-1m` | 0,1356 | 9,50 |
| **`MNQ.FUT` (todos los contratos)** | **`ohlcv-1m`** | **0,2069** | **14,48** |
| `MNQ.FUT` | `definition` | 0,0298 | 0,05 |
| `MNQ.FUT` | `bbo-1m` | 0,6370 | 11,47 |
| `MNQ.FUT` | `ohlcv-1s` | 6,2399 | 436,80 |
| `MNQ.FUT` | `tbbo` | 90,9874 | 2.547,65 |
| `NQ.FUT`, **desde 2010-06-06** | `ohlcv-1m` | 0,3816 | 26,71 |

**La serie completa que el proyecto necesita cuesta el 12% del crédito de alta.** El documento
trataba B.1 como una decisión de compra con proveedores en competencia; a este precio no hay tal
decisión. FirstRate deja de ser alternativa a evaluar, y §10 pierde su primer pendiente.

**Hallazgo lateral: `GLBX.MDP3` tiene `ohlcv-1m` desde 2010-06-06.** El MNQ no existe antes de
2019 —es un contrato micro, lanzado ese año— pero el NQ sí. Dieciséis años de historia del mismo
subyacente salen $26,71. **Comprarla no es admitirla**: los datos anteriores a 2019 se marcan
no-veredicto, igual que el sintético de la casilla 0.2, y no escriben en el ledger. Su admisión a
los gates es una decisión separada; ver §7.1b.

#### §7.1b [rev 2026-09-21] El spread, que es el término que la tesis del proyecto pone a prueba

Levantado por la revisión cruzada con Gemini (`agy-delegate --tier pro`, método de
`mem:revision-cruzada-atrapa-inferencias-que-ningun-test-atrapa`). De cinco hallazgos, **dos eran
falsos** —la equivalencia entre el NQ de 2012 y los CFDs de D-C, y la idea de que más historia
in-sample obliga a ampliar el holdout, que contradice `DIMENSIONAMIENTO_HOLDOUT.md:137`— y uno ya
estaba resuelto en el código (`simulator.py:152`, la rama de fill sin ticks es pesimista por
diseño). Éste sobrevivió:

`costs.py:33` (`spread_for`) toma la mediana de `ask - bid` de la ventana de ticks **si hay
cobertura**, y cae a `config.default_spread_points` —una constante de configuración— si no la hay.
Comprando sólo `ohlcv-1m`, el simulador quedaría en esa constante para siempre. Un proyecto cuya
tesis es «¿sobrevive a costos reales?» no puede apoyar el término de spread en un supuesto fijo.

**Mitigación cotizada: el esquema `bbo-1m`, $11,47** por todos los contratos de MNQ — bid y ask por
minuto, spread medido. Las resoluciones mayores (`bbo-1s` $351, `tbbo` $2.548) no entran en el
crédito.

**Consecuencia de alcance:** `spread_for` espera hoy una ventana de ticks, no una foto por minuto.
Adaptarlo es trabajo en capa 3 y **pasa por el ciclo SDD completo**. No bloquea la compra, pero es
una casilla que antes no estaba en el mapa.

#### §7.1c [rev 2026-09-21] La licencia dice que no, y eso toca un invariante **[DECISIÓN HUMANA]**

El [Databento User Agreement](https://databento.com/legal/databento-user-agreement) (efectivo
2024-01-31) **no contiene ninguna cláusula de retención, inmutabilidad ni disponibilidad** del
archivo histórico. Al contrario:

> §1.1 — «...license, to access and use... **for so long as Customer has a Customer Account... in
> good standing with Databento**.»
>
> §9.3 — «Upon termination for any reason: ...**Customer may no longer download, access, or use any
> Third-Party Data**.»

La segunda no dice «no podés bajar más»: cesa el derecho de uso sobre **lo ya descargado**.

Este documento escribía el requisito como «la fuente tiene que ser estable y **re-descargable**,
porque el hash de dataset tiene que poder recomputarse dentro de dos años». Eso pide una garantía
que Databento no concede — y que, por cómo se licencia la data de bolsa, no concede ningún
proveedor del rubro. **El invariante está apoyado en una promesa que no existe.**

**Propuesta, no decisión tomada.** Mover el punto de apoyo a lo que el proyecto controla:

- El hash se calcula sobre la **copia local cruda**, y esa copia **es** la evidencia del artefacto.
- Se exige **respaldo** de los bytes crudos, no capacidad de re-pedirlos.
- La re-descarga pasa a ser verificación deseable contra corrupción local, **no** la garantía.

No relaja ningún gate: cambia dónde se apoya la misma exigencia. Pero toca un invariante de diseño
y por eso queda marcado como decisión del dueño del proyecto, no como hecho consumado.

**Y una consecuencia para §10.** La redistribución está definida en §1.5(e) del contrato como
entregar a terceros los datos «**or other information derived from the same**». Un veredicto
publicado es información derivada. §1.6 exige atribución («Data Provided by Databento») y, de
paso, autoriza a Databento a usar el nombre y logo del cliente en su marketing. No bloquea nada
hoy; hay que resolverlo por escrito antes del primer veredicto público. Lo que **sí** quedó
descartado como problema: las condiciones de «no profesional» de CME aplican a tiempo real con
plan Standard, y la Exchange Data Policy §1.2 dice que pasadas 8 horas el dato «is considered
historical and **no longer subject to these restrictions**».

#### §7.1d [rev 2026-09-21] La lista de compra propuesta ***(superada — ver §7.1e)***

| Qué | Para qué | USD |
|---|---|---|
| `MNQ.FUT` `ohlcv-1m` 2019→hoy | la serie de precios | 14,48 |
| `MNQ.FUT` `definition` | catálogo de contratos, insumo de B.2 | 0,05 |
| `MNQ.FUT` `bbo-1m` | spread medido en vez de supuesto (§7.1b) | 11,47 |
| `NQ.FUT` `ohlcv-1m` **2010**→hoy | historia larga, marcada no-veredicto (§7.1a) | 26,71 |
| `NQ.FUT` `definition` | catálogo | 0,06 |
| | **Total** | **52,77** |

De $125, y dentro del tope mensual. **No** se compra el `bbo-1m` del NQ ($23,27): si la historia
larga llega a usarse sería como precios, no para ejecutar, y el costo de ejecución sale de MNQ y
del contrato de MFFU. El spread del NQ de 2012 no se paga nunca.

**Ojo con el calendario de facturación.** El tope de gasto es mensual y se reinicia; el crédito es
único y no. Una descarga partida en dos meses calendario deja el segundo tramo sin cobertura.

#### §7.1e [rev 2026-09-22] El tamaño del universo, que es lo que la lista anterior ignoraba

La lista de §7.1d compra **un solo instrumento**. El spec lo prohíbe, y no en el changelog sino en el
cuerpo normativo (§2.x, líneas 600-602):

> Ninguna campaña sobre un universo de **un solo instrumento** puede emitir veredicto GO, GO-PARCIAL
> ni GO-ACOTADO. **C1 sólo tiene contenido con `|U| ≥ 2`**, y ese es el mínimo normativo. No es una
> constante elegida: es el punto exacto en que C1 deja de ser vacío.

Con MNQ solo, C1 da **1 de 1 = 100%** y pasa sin decir nada: el gate no falla, **se vacía**. B.1 se
escribió como una decisión de proveedor, y nadie cruzó la lista contra el tamaño mínimo de universo.
Es un agujero de la casilla, no un error de precio.

##### Y para el Candidato B tal como está declarado hoy, es peor

El universo declarado de B son **cuatro** instrumentos: MES, MNQ, MYM, MGC (§510). Ese es el
denominador de C1 **siempre**, y no se contrae. Con la lista vieja quedaría **un evaluable y tres no
evaluables**, que cuentan como **no superados**: techo de **1/4 = 25% < 60%**. C1 no se vacía —
**reprueba de entrada**, y ningún veredicto favorable es alcanzable.

Y si se compraran los cuatro, MGC sigue sin ancla (§2.3), así que arranca fallado: haría falta
**3 de 4**, o sea **acertar en los tres índices restantes, al 100%**.

> **De acá salía la decisión que había que tomar ANTES de descargar.** Se planteó como dos caminos
> excluyentes:
>
> | | Qué implica | Costo |
> |---|---|---|
> | **(a)** Comprar también MES y MYM y evaluar a B sobre su universo declarado | +$31,98 → $116,83 de $125 | Mantiene cuatro índices con correlación de retornos de **0,947** entre MES y MNQ (§1128): C1 mide casi lo mismo cuatro veces |
> | **(b)** Redeclarar el universo de B a líderes por clase | $84,85 | Es **cambio de spec**, y debe quedar escrito antes de que llegue el primer dato |
>
> **DECIDIDO el 2026-09-22 (humano): (b).** El proyecto dejó de ser un torneo de índices y pasó a ser
> un validador multi-mercado; la compra es la de arriba, **$84,85**, y se asume el cambio de spec.

##### Pero (a) y (b) no eran excluyentes, y eso obliga a separar dos actos

**Corrección de esta misma sección.** La tabla presentó *comprar* y *declarar* como si fueran la
misma decisión. No lo son, y es justamente lo que §«Comprar no es declarar» dice más abajo. Al
escribir (b) aparece la consecuencia que la tabla escondía:

> El Candidato B ancla su rango de apertura en la **apertura de contado del subyacente**. El spec es
> normativo y explícito (§2.3, nota obligatoria): los tres micro-índices la tienen, **MGC no**, y el
> ancla de MGC queda **pendiente** contra página oficial de CME (PA-106-A).

`M6E`, `MBT` y `MCL` **no aparecen ni una vez en el spec**: entraron al proyecto como lista de compra,
nunca como universo de un candidato. Ninguno tiene ancla verificada, y **MBT no puede tenerla** —
Bitcoin no abre, cotiza continuo.

Así que declarar los cinco líderes como universo de B daría **un evaluable de cinco = 20%**, peor que
el 25% que (b) venía a arreglar. **La compra (b) es correcta; la declaración literal de (b) sería
peor que el problema.**

##### Lo que sí se declara, y de qué depende

**La compra y la declaración se resuelven por separado:**

| Acto | Qué se decide | Estado |
|---|---|---|
| **Compra** (el disco) | Cinco líderes, un por clase, $84,85 | **DECIDIDO** — no gasta ensayos (D1) |
| **Universo declarado de B** (el denominador de C1) | Sólo instrumentos con **ancla verificada** | **BLOQUEADO** por las anclas |

Un ORB sobre un instrumento sin apertura de contado no es «un dato que falta»: es una estrategia que
**no está definida** ahí. No lo arregla comprar datos.

Entre los cinco comprados, **B tiene hoy un solo instrumento declarable: MNQ** — y `|U| = 1` está
prohibido. Para que B pueda emitir cualquier veredicto necesita **una segunda ancla verificada**.

> **PA-106-A se generaliza.** Deja de ser «el ancla del oro» y pasa a ser **el ancla por clase**:
> para cada líder comprado, resolver contra **página de producto oficial de CME** si existe una
> apertura de contado que sirva de ancla, y cuál es. Es **investigación en fuente primaria, no
> dinero**, y no gasta ensayos. «No tiene apertura» es un resultado legítimo: ese instrumento queda
> en el disco, sirve al Candidato C y a la búsqueda futura, y **no se declara para B**.

**(a) no muere: queda en reserva y condicionada.** Si ninguna ancla adicional cierra, la única forma
de que B emita veredicto es comprar MES y MYM (+$31,98) y volver a un universo de índices. Esa compra
**se difiere hasta que las anclas respondan**, porque hoy no se sabe si hace falta. Lo que se ganó es
convertir una decisión de gasto en una pregunta verificable que cuesta cero.

**El orden se mantiene intacto:** las anclas se resuelven **antes** de declarar el universo de B, y el
universo se declara **antes** de mirar un solo dato. Declararlo después sería elegir el denominador de
C1 mirando resultados, que es el mecanismo exacto que C.4 existe para impedir.

##### El mínimo no es el óptimo, y el umbral no es monótono

El spec lo declara para `|U| ≤ 4` (§2.x, líneas 604-606); extendido a 5 queda:

| Tamaño | C1 ≥ 60% exige | Exigencia real |
|---|---|---|
| 1 | 1 de 1 | **vacío** — prohibido |
| 2 | 2 de 2 | 100% |
| 3 | 2 de 3 | 67% |
| 4 | 3 de 4 | 75% |
| 5 | 3 de 5 | **60%** |

**Comprar exactamente dos instrumentos es la configuración más dura que existe** después de la
prohibida. Un universo chico no es un universo indulgente.

> **Trampa de gobernanza, que conviene dejar escrita antes de que aparezca.** Esa tabla invita a
> elegir el tamaño del universo por lo que afloja C1. Hacerlo sería **selección sobre el gate** — el
> mismo mecanismo que §9.5 rechaza cuando alguien propone bajar G1 de 300 a 100 después de ver que
> 300 es difícil. El tamaño y la composición del universo de cada candidato se declaran en **C.4
> (pre-registro), antes de medir nada**. La tabla está para entender el costo de esa declaración, no
> para optimizarla.

##### Comprar no es declarar

Bajo D1, el universo sobre el que se **selecciona** cuenta como ensayo, sube el denominador del DSR y
endurece G4. Pero **tener el dato en el disco no gasta ningún ensayo**: lo que cuesta es declararlo
en el universo de un candidato. De ahí la regla de compra — **ancho en el disco, angosto en la
declaración.**

##### La trampa de MGC

MGC está en el universo del torneo (§510) pero **no es evaluable hoy**: le falta el ancla del rango
de apertura (§2.3). Y el spec es explícito (§2.x, líneas 586-588):

> [el universo efectivo] **no altera el denominador de C1**: un instrumento no evaluable cuenta como
> **no superado**.

O sea que **declarar MGC hoy mete un fracaso automático dentro del denominador**. Comprar el dato
conviene —es insumo de B.3, y el ancla es trabajo, no dinero—; declararlo antes de resolver el ancla
empeora C1 en vez de ayudarlo.

##### La historia larga de NQ se difiere

§7.1a la justificaba como «no-veredicto, por si acaso», por $26,71 — la mitad de la lista vieja. Se
difiere por tres razones acumuladas, ninguna de las cuales es que el dato sea malo:

1. **No alimenta ningún gate.** Está marcada no-veredicto por decisión propia (§7.1a, línea 911), así
   que no entra en C1 ni en G1.
2. **NQ no es MNQ.** El criterio de admisión al universo exige **contrato micro** para poder
   dimensionar contra el umbral de la firma (§2.x). El NQ de tamaño completo no califica, así que
   esta serie no puede ser dato de universo aunque se quisiera.
3. **Lo específico que desbloquearía, el motor no lo puede correr.** Su uso más valioso sería validar
   estrategias más lentas —que es lo que baja la velocidad mínima de G1 y lo que vuelve una
   estrategia portable (B.5)—. Pero el simulador **aplana toda posición al cierre de cada sesión, sin
   condición** (`backtest/simulator.py:563-568`), y si alguna sobrevive levanta `SessionBoundaryError`.
   Sin tenencia overnight, la historia profunda no compra la capacidad que la justificaría.

> **Corrección registrada (revisión cruzada, 2026-09-22).** Una versión anterior de este párrafo
> decía que el cierre forzado de sesión «bloquea» la historia profunda. Es una exageración: el
> Candidato B es un ORB intradía que va flat al cierre **por diseño**, así que para él el cierre
> forzado no estorba, y 2010–2019 sí aportaría regímenes de volatilidad que 2019–2026 no tiene. Lo
> correcto es lo de arriba: la historia profunda no está vetada, está **en la cola**, detrás de cosas
> que sí alimentan gates. Los $26,71 se reasignan al universo.

##### La lista que reemplaza a §7.1d

Precios medidos por API el **2026-09-22** (endpoints de metadata, gratuitos; ningún byte
descargado), rango 2019-05-05 → borde del dataset. Precios y catálogo en **todos los contratos**;
spread en **continuo por volumen**, por §7.1b: el spread que importa es el del contrato que
efectivamente se opera, y el ajuste de roll es sobre precios, no sobre spreads.

| Instrumento | Clase | `ohlcv-1m` | `definition` | `bbo-1m` cont. | Subtotal |
|---|---|---:|---:|---:|---:|
| MNQ | índices | 14,48 | 0,05 | 3,52 | **18,05** |
| MGC | metales | 20,51 | 0,27 | 3,46 | **24,24** |
| M6E | divisas | 9,83 | 0,01 | 3,52 | **13,36** |
| MBT | cripto | 6,84 | 0,15 | 2,60 | **9,59** |
| MCL | energía | 16,83 | 0,32 | 2,46 | **19,61** |
| | | 68,49 | 0,80 | 15,56 | **84,85** |

**$84,85 de $125**, con **$40,15** de margen. Los cinco los **fondea MFFU**, verificado en fuente
primaria el 2026-09-21 (`help.myfundedfutures.com/en/articles/9735811`), que es el límite duro de lo
monetizable: un validador se mide por lo que puede recibir del mundo, pero sólo cobra por lo que la
firma fondea.

**Un líder por clase de activo** — la diversificación que importa acá no es de cartera sino de
**régimen de mercado**: una estrategia que sobrevive en índices, metales, divisas, cripto y energía
es robusta en un sentido que cuatro índices correlacionados al 0,947 (§1128) no pueden demostrar.

**Ojo con el calendario de facturación.** El tope de gasto es mensual y se reinicia; el crédito es
único y no. Una descarga partida en dos meses calendario deja el segundo tramo sin cobertura: la
compra se ejecuta **en un solo mes calendario**.

**Lo que esta lista NO compra:** `bbo-1m` en «todos los contratos» ($83,46 en los cinco, contra
$15,56 del continuo), las resoluciones finas (`bbo-1s`, `tbbo`), y la historia de NQ anterior a 2019.

### ☐ B.2 — Fichas de contrato por venue

`value_per_point = tick_value / tick_size` (`src/genesis/data/symbols.py:36`) da el multiplicador del
contrato de forma natural, así que la abstracción del #55 aguanta futuros **sin cambio de esquema**.
Lo que falta es una fuente de fichas por venue, no un fallback calculado: la heurística
`tick_size = 10^-digits` **falla 25× en ES/NQ** (tick real 0,25 con 2 dígitos). Ver el #114.

~~**[rev 2026-09-21] El dataset de desarrollo es una sub-tarea de esta casilla, y se puede hacer
ya.** Bajar la muestra gratis de FirstRate (o el CSV de Kaggle) y dejarla en el store como dataset
de desarrollo permite ejercitar la tubería con barras reales de MNQ **sin esperar la decisión de
compra y sin tocar el ledger**.~~ **[rev 2026-09-21, más tarde el mismo día] Caduco.** La muestra
gratis existía para no depender de una compra que se creía cara; la compra resultó costar $14,48 y
el catálogo de contratos que esta casilla necesita es el esquema `definition`, **$0,05**. Bajar un
CSV de procedencia desconocida para ejercitar la tubería dejó de tener sentido cuando el dato bueno
cuesta menos que el rodeo. Se mantiene el requisito general: todo dataset que no vaya a producir
veredicto lleva su `dataset_hash` marcado como no-veredicto, igual que el sintético de la casilla
0.2 — y eso ahora aplica a la historia de NQ anterior a 2019 (§7.1a).

### ☐ B.3 — Exportador, empalme de continuos y sesiones CME

El más caro, y el primero que mira una barra real — o sea, **el punto de no retorno de C.1b**.

**[rev 2026-09-21] El empalme no se puede tercerizar: confirmado en las dos fuentes.** Databento
resuelve *qué* contrato corresponde en cada fecha según la regla de roll elegida (`.v.0` por
volumen, `.n.0` por interés abierto, `.c.0` por calendario) pero **entrega precios crudos, sin
ajustar**, con una posición declarada: los ajustes son opacos, pueden introducir errores del
proveedor y desvirtúan el cálculo de ciertas señales. FirstRate sí ofrece series ajustadas, pero
su método es una caja negra, así que de esa fuente también se tomaría la serie cruda. **En los dos
caminos el ajuste de roll queda de nuestro lado, y el alcance de B.3 no se achica.**

**[rev] Corrección de un error del documento original.** Decía que con estrategia intradía nunca se
sostiene una posición a través de un roll, así que la convención de empalme no altera resultados.
**Es falso**, y el contraejemplo está en el repo: `candidate_b1_orb.yaml` usa Chandelier con ATR de
22 barras y un filtro RVOL con `lookback_days: 10`. **Los dos cruzan el roll.** Un empalme sin
ajustar mete saltos artificiales en la estimación de volatilidad que dimensiona cada posición y fija
cada stop. Lo mismo vale para máximos/mínimos de sesión previa y cualquier media que abarque días.

El algoritmo de ajuste (proporcional o back-adjusted) es un requisito matemático, no un detalle de
infraestructura, y su elección **viaja en el hash de dataset** como cualquier otra clave de
identidad.

**Y la sesión.** Los futuros CME cotizan casi 23 horas. Un «rango de apertura» no significa nada sin
declarar si se mide sobre RTH o ETH, y el volumen tampoco. `src/genesis/data/sessions.py` existe
pero está poblado para índices CFD. La tabla de sesiones CME es parte de esta casilla, no un
apéndice.

### ☐ B.4 — Costos por instrumento **[rev 2026-09-22 — casilla nueva; absorbe la mención de §7.1b]**

§7.1b la anotó como «adaptar `spread_for` a `bbo-1m`». Con un universo multi-clase eso se queda
corto, y lo que falta es **más grave que el spread**.

**El modelo de costos es global, no por instrumento.** `backtest/costs.py:29` define
`commission_per_lot` como campo de una configuración **única**, y `costs.py:59` la aplica sin mirar
el símbolo: `sizing_hint * config.commission_per_lot * stress`. El archivo que la puebla
(`backtest/costs_config.json`) trae tres números heredados del régimen CFD:

```json
{ "default_spread_points": 1.5, "commission_per_lot": 7.0, "slippage_points": 0.2 }
```

**Contra la realidad medida:** MFFU cobra **$1,90** ida y vuelta en MNQ. El motor cobra $7,00 por
lote más 1,5 puntos de spread —que en el micro, a $2 por punto, son $3,00—, o sea **≈$10 por
operación contra ≈$2,40 reales: cuatro veces de más.**

**Por qué importa más de lo que parece.** Un costo inflado no produce un error simétrico: produce
**falsos negativos**. Génesis rechazaría estrategias viables, y cada rechazo **quema un ensayo en el
ledger de forma permanente** — el contador de D1/G4 no distingue un rechazo legítimo de uno causado
por una constante mal puesta. Se paga el ensayo y no se compra información.

**Y la ficha de símbolo está al revés para futuros.** `SymbolFigure` (`data/symbols.py:23-32`) lleva
`tick_value`, `tick_size`, `swap_long`, `swap_short`, `swap_rollover_day` — **swap, que es
financiamiento de CFD, y ningún campo de comisión.** Los futuros no tienen swap: tienen comisión por
contrato. La ficha conserva el vocabulario del régimen del que el proyecto ya salió por D-C.

**Se parte en dos, y la mitad no espera a la compra:**

| | Qué | ¿Espera datos? |
|---|---|---|
| **B.4a** | Comisión y spread por instrumento en la ficha; `commission_for` y `spread_for` reciben el símbolo y **lo usan** | **No** — arranca ya |
| **B.4b** | `spread_for` lee la foto por minuto del `bbo-1m` en vez de una ventana de ticks | Sí — depende de B.1b |

Las dos son **capa 3** y **pasan por el ciclo SDD completo**, con gate humano.

**B.4a cierra PA-106-C.** El spec ya tenía anotado que las comisiones por contrato no estaban
publicadas y que eso **bloquea G3, G9 y todos los gates P** — «no es sólo economía: sin comisiones
verificadas los gates de robustez tampoco corren». B.1 consiguió las comisiones en fuente primaria de
MFFU; B.4a es el tramo que falta para que entren al motor y esos gates dejen de correr sobre un
número inventado.

**B.4b es más grande de lo que §7.1b sugería.** No alcanza con cambiar `spread_for`: el motor no
tiene **loader ni esquema de almacenamiento** para cotizaciones BBO muestreadas por minuto —
`simulator.py` admite ventanas de ticks (`TickRow`) u OHLCV M1, y nada más. El alcance real incluye
el formato en el store y el modelo de fill contra una foto por minuto, no sólo la función de costo.

**DoD de B.4a.** (1) La ficha de cada instrumento del universo lleva su comisión ida y vuelta citada
en fuente primaria de MFFU. (2) `commission_for` **falla con contexto** si el símbolo no tiene ficha,
en vez de caer a una constante — la degradación silenciosa es el modo de falla que ya se pagó en
`spread_for` (§7.1b). (3) Un golden test fija el costo de una operación de MNQ en $1,90 y una de MGC
en $2,20. (4) `commission_per_lot` desaparece de `costs_config.json` como valor global.

### ☐ B.5 — F-retardo: está declarado, no planificado **[rev 2026-09-22 — casilla nueva]**

§9.2 lo define y §9.4 lo usa en el hito del primer veredicto, pero **no tiene casilla, ni DoD, ni
implementación**: «retardo» aparece ocho veces en este roadmap y **cero veces en el código**. Un
filtro que no es de nadie no se construye.

**Y hace dos trabajos, no uno.** El primero ya estaba: rechazar lo que un humano no puede ejecutar.
El segundo lo trajo el dueño el 2026-09-22 y el documento no lo había derivado:

> **Portabilidad.** Tres de las seis firmas relevadas prohíben automatizar — Apex, Take Profit
> Trader y The5ers (`mem:pivote-a-prop-de-futuros-cme-2026-09`). MFFU se eligió justamente por eso.
> Una estrategia que **sobrevive** a F-retardo es ejecutable a mano y, por lo tanto, **deja de estar
> atada a MFFU**: puede llevarse a las seis firmas y a una cuenta propia.

§9.2 dice que F-retardo «sólo puede rechazar, nunca admitir». Eso sigue siendo correcto **como
evidencia estadística**: sobrevivir al retardo no es evidencia de que la estrategia funcione. Pero es
un **hecho de negocio** sobre dónde se la puede operar, y esa lectura no estaba escrita. Al cuidarse
de lo primero, el documento no vio lo segundo.

**El límite, que también conviene dejar escrito: son dos ejes, no uno.** F-retardo desbloquea el eje
de la **automatización**, no el del **hedging**. Apex cierra la cuenta por estar largo en ES y corto
en YM; The5ers prohíbe varias posiciones simultáneas; MFFU es la única permisiva en los dos ejes a la
vez. **Una estrategia de un solo instrumento que aguante el retardo es portable; una que opere cinco
a la vez sigue siendo MFFU o nada, por lenta que sea.**

> **Consecuencia para el candidato B, que conviene decir ahora y no después.** B es un ORB: un
> quiebre del rango de apertura es crítico en el tiempo por definición. Es exactamente la forma de
> estrategia que F-retardo está diseñado para matar. Si B sobrevive a los gates pero no al retardo,
> el resultado no es «malo»: es **válido y no portable**, y queda atado a MFFU.

**DoD.** (1) El runner corre cada candidato en tres variantes —entrada al cierre de barra, bar+1 y
~15 minutos— con la misma semilla y el mismo `dataset_hash`. (2) El artefacto registra las tres y el
veredicto cita **la peor**. (3) Queda asentado que no cuenta como ensayo bajo D1, por ser exigencia y
no selección. (4) El veredicto lleva un campo de **portabilidad**, derivado de si la variante
retardada sobrevive — es la salida que decide a qué firmas se puede ir.

### ☐ B.6 — C1 no tiene guarda mecánica **[rev 2026-09-22 — casilla nueva; va primera]**

Hallazgo de la revisión cruzada del 2026-09-22, verificado contra el árbol. **Es el único de toda
esta tanda que puede producir un GO falso, y por eso va antes que el resto.**

El spec declara dos reglas normativas sobre el universo: el denominador de C1 **nunca se contrae**
(§2.x, líneas 586-588) y **ninguna campaña con `|U| = 1` puede emitir veredicto favorable** (§2.x,
líneas 600-602). **El código no implementa ninguna de las dos.** En `validation/verdict.py:388-391`:

```python
n_symbols = len(symbol_gate_outcomes)
n_passing = sum(1 for outcome in symbol_gate_outcomes.values() if outcome.all_pass)
c1_fraction_passing = n_passing / n_symbols if n_symbols > 0 else 0.0
c1_pass = c1_fraction_passing >= _C1_MIN_FRACTION
```

`n_symbols` es **la cantidad de símbolos que trae el bundle**, no el universo declarado. O sea que el
denominador **es exactamente lo que se le pase**. Un bundle con un solo símbolo da `1/1 = 100%`, C1
pasa, y si los demás gates pasan el veredicto sale **GO**. No hay en todo el módulo ninguna
comprobación de tamaño mínimo ni de correspondencia con el universo declarado: `_C1_MIN_FRACTION`
(línea 71) es la única constante relacionada, y su otro uso (línea 809) sólo clasifica GO-ACOTADO.

**La asimetría es lo que lo pone primero.** B.4 (costos inflados) produce **falsos negativos**:
rechaza estrategias buenas y quema ensayos, que es caro. Esto produce **falsos positivos**: deja
pasar una estrategia que nunca se validó de forma cruzada, y el siguiente paso después de un GO es
poner dinero real en un challenge. Un gate que no protege es peor que no tener gate, porque se
confía en él.

**Y no es hipotético: es exactamente el camino que la lista vieja de §7.1d habilitaba.** Comprar sólo
MNQ y correr el veredicto habría dado C1 = 100% en verde.

**DoD.** (1) El bundle de veredicto transporta el **universo declarado** del candidato, no sólo los
símbolos evaluados. (2) El denominador de C1 es ese universo declarado; los símbolos ausentes o no
evaluables cuentan como **no superados**, según §2.x. (3) Un universo declarado de tamaño 1 **aborta
con excepción de dominio y contexto**, sin emitir veredicto — no devuelve NO-GO, que sería indistinguible
de una evaluación legítima. (4) Tests: un bundle de un símbolo levanta la excepción; un bundle de
2 sobre un universo declarado de 4 da C1 = 50% y reprueba, no 100%. (5) **[rev 2026-09-22, D-E
punto 4]** El resultado por celda admite un tercer estado, **no aplica**, para no simular una
estrategia donde no está definida; `SymbolGateOutcome.all_pass` es hoy `bool` (`verdict.py:150`) y no
puede expresarlo. **No aplica cuenta como no superado** si el activo está declarado: la única forma de
excluirlo es no declararlo, antes del primer dato.

Capa 4, **ciclo SDD completo** con gate humano.

### ☐ B.8 — El veredicto juzga, no elige **[rev 2026-09-22 — casilla nueva; D-E puntos 1-2]**

Hoy `run_verdict` emite **un solo** `VerdictKind` para todo el lote (`verdict.py:954-976`), elige un
ganador por `payout_p25_12m` (`_select_winning_candidate`, `:433`) y deflacta sólo al ganador con
`n_trials_signal_total_ganador + (n_candidatos_torneo - 1) + ledger_extra_trials` (`_compute_t1`,
`:505-517`). Es lógica de torneo funcionando, no vocabulario.

**El agujero que la revisión cruzada encontró en la primera versión de esta casilla.** Proponía sacar
el término de torneo y dejar que las compañeras de lote entraran por el ledger. Pero `run_verdict`
**lee** una foto del ledger y la escritura es una función aparte (`record_trial_completions`, `:840`):
cuando se juzga una estrategia, sus compañeras todavía no están anotadas y habrían pagado **cero**.
Sacar el término sin pre-registrar **relajaba** T1. Por eso el pre-registro es parte del DoD, no un
detalle.

**DoD.** (1) Un veredicto por estrategia; desaparece el campo de ganador. (2) Todos los `trial_id`
del lote se registran en el ledger **antes** de computar cualquier veredicto. (3) T1 se conserva como
DSR de la canasta diaria de **cada** estrategia, sin `n_candidatos_torneo`. (4) Test de invariancia:
la misma estrategia con los mismos datos da el mismo veredicto corrida sola, en lote de tres, o en
cualquier orden. (5) Test de dureza: ningún `n_trials` resulta menor que el del código actual para el
mismo conjunto de ensayos. (6) El manifest sube de versión (`genesis-validation-j/3`): veredictos
por estrategia, sin claves de ganador ni `n_candidatos_torneo`.

**Rompe a sabiendas** unos 13 tests de `tests/validation/test_verdict.py` y `test_verdict_ledger.py`
que asumen ganador único; el inventario está en §9.7.

**Va antes del primer veredicto**, no después: el primer veredicto corre dos o tres estrategias
juntas (§9.4), que es exactamente el caso donde el torneo cambia el resultado.

Capa 4, **ciclo SDD completo** con gate humano. Comparte archivo con B.6; se pueden fundir en un
solo change si el diseño lo admite, pero B.6 no espera a B.8.

### ☐ B.7 — Ancla del rango de apertura por clase **[rev 2026-09-22 — casilla nueva]**

La decisión de universo de §7.1e (comprar un líder por clase) la destapó: **de los cinco
instrumentos que se compran, sólo MNQ tiene ancla de rango de apertura verificada.** Y `|U| = 1`
está prohibido, así que hoy el Candidato B **no tiene universo declarable**.

No es un problema de datos. El spec lo dice como norma (§2.3, nota obligatoria): B define su rango
sobre la **apertura de contado del subyacente**. Donde no hay apertura de contado, **la estrategia no
está definida** — comprar el dato no la define.

**Estado por instrumento, sin rellenar con memoria del modelo:**

| Instrumento | Ancla | Estado |
|---|---|---|
| MNQ | 14:30 UTC, apertura de contado del Nasdaq 100 | **verificada** (§2.3) |
| MGC | — | **pendiente**, PA-106-A |
| MCL | — | no evaluado nunca: no figura en el spec |
| M6E | — | ídem |
| MBT | — | ídem, y **no puede tener**: Bitcoin cotiza continuo, no abre |

**DoD.** (1) Para cada líder comprado, resolver contra **página de producto oficial de CME** si existe
una apertura de contado utilizable como ancla, y cuál es, en UTC y con su regla de DST. (2) «No tiene
apertura» es un **resultado válido y se registra como tal** — no se inventa un sustituto ni se usa la
apertura de Globex, que no es apertura de contado. (3) La tabla de anclaje de §2.3 del spec se
actualiza con lo verificado. (4) El resultado determina qué instrumentos puede **declarar** el
Candidato B; los demás quedan en el disco, disponibles para el Candidato C y la búsqueda futura.

**No espera la compra** — es fuente primaria, no dato de mercado — y **no gasta ensayos**: bajo D1 lo
que cuenta es declarar, no averiguar. Va en paralelo a B.6 y B.4a.

> **Es la casilla más barata del carril y la que más decide.** Si devuelve una segunda ancla, B tiene
> universo y no hay que gastar un peso más. Si no devuelve ninguna, se reactiva la compra de MES y MYM
> (+$31,98, §7.1e), que quedó **diferida y no descartada**. En los dos casos la pregunta se responde
> antes de ver un dato, que es la única forma de que la respuesta valga.

Vía rápida (investigación y `docs/`) hasta que toque `sessions.py`; esa parte, ciclo SDD.

---

## 8. Fuera de alcance de esta fase

Con razón escrita, para que no parezca olvido.

| Issue | Por qué sale |
|---|---|
| [#96](https://github.com/ramaDben/genesis/issues/96) concurrencia y riesgo por clima | **Premisa vencida**: mide contra un límite diario de 4-5% que MFFU Rapid EOD **no tiene**, sobre un universo CFD pre-pivote. Además el presupuesto de contratos es una restricción de ejecución multi-símbolo que el arquitecto no necesita. Se reescribe antes de decidirse, y entra por C.2 como política |
| [#112](https://github.com/ramaDben/genesis/issues/112) `funded_starting_balance` | Rama MFFU/`prop_sim`. Sale de la ruta crítica sin cerrarse |
| [#111](https://github.com/ramaDben/genesis/issues/111) semántica OOS de P6 | Ídem, pero es barato e independiente del objetivo — puede ir en cualquier hueco |
| [#87](https://github.com/ramaDben/genesis/issues/87) adjudicador externo | Sigue reservado: depende de que exista `POLITICA.md` primero. Construir el juez antes de la ley |

**[#114](https://github.com/ramaDben/genesis/issues/114) se queda abierto tal como está.** Es un
registro de decisión, no un pedido de trabajo — está abierto a propósito para que sea *findable* el
día que alguien choque con el error. Lo único que cambia es que su punto 4 (el ledger no filtra por
símbolo ni clase de activo) se promueve a insumo de D1 en C.3.

---

## 9. Orden de ejecución **[rev 2026-09-20 — reordenado]**

### 9.1 Por qué se reordenó

El orden anterior ponía A y B «en paralelo» y en los hechos arrancaba por A: ocho casillas de
arquitecto antes de que existiera un solo dato de futuros en el disco. Una revisión adversarial
externa lo atacó y el ataque es correcto: **sin datos de CME no hay veredicto posible, por más
arquitecto que haya.** El carril A construye la máquina de proponer; el carril B construye la
única cosa capaz de responder. Construir la primera antes que la segunda es optimizar la parte
que no está en el camino crítico.

Tres hechos medidos en esta sesión cierran la discusión:

1. **G1 exige 300 operaciones OOS** (`src/genesis/validation/verdict.py:60`). Es la restricción que
   gobierna qué frecuencia de estrategia es siquiera admisible, y no se puede razonar sobre ella sin
   saber cuánta historia hay.
2. **MNQ tiene datos desde 2019** (~6,4 años). Reservar holdout sobre eso es un presupuesto ajustado,
   no holgado.
3. **Databento da $125 de crédito inicial** y cobra por GB descargado; las barras OHLCV de 1m/1h/1d
   de CME Globex están incluidas en todos los planes. El costo de entrada de B.1 es plausiblemente
   **cero**, contra las semanas que cuesta el carril A. La relación costo/desbloqueo no admite duda.

### 9.2 La relajación «ejecutable por un humano», bien leída

El dueño relajó el alcance: la estrategia no tiene que ser automatizada si es lo bastante lenta para
ejecutarla a mano. **Esa relajación no es sobre frecuencia, es sobre tolerancia al retardo.**

Un humano puede tomar dos o tres entradas por día sin problema. Lo que no puede es ejecutar en el
segundo exacto del cierre de una barra. Y el CLAIM-006 del corpus mide justamente eso: **un retardo
de una barra invierte el signo de T** (+4,30 → −2,78) en la señal más fuerte del estudio de MNQ. No
se degrada: cambia de signo. Toda la ventaja vivía dentro de una sola barra.

De ahí sale un filtro barato que se agrega al roadmap:

> **F-retardo.** Todo candidato se corre además con la entrada retardada (bar+1 y ~15 min). Si la
> ventaja muere o invierte con el retardo, el candidato es **inejecutable por un humano** y queda
> descartado sin discusión.

Es un filtro de **una sola dirección**: sólo puede rechazar, nunca admitir. Sobrevivir al retardo no
es evidencia a favor, así que no es una dimensión de selección y **no cuenta como ensayo bajo D1**
(es una exigencia, no una selección). Eso lo hace gratis en términos de DSR.

**[rev 2026-09-22] Y además decide a qué firmas se puede ir.** Sobrevivir al retardo no es evidencia
estadística a favor —eso sigue firme—, pero sí es un hecho de negocio: una estrategia ejecutable a
mano deja de estar atada a MFFU, que se eligió precisamente porque tres de las seis firmas relevadas
prohíben automatizar. El desarrollo, el DoD y el límite de esa lectura —son dos ejes, automatización
y hedging, y esto desbloquea sólo el primero— están en **B.5**, que es además donde el filtro deja de
ser una declaración sin dueño.

### 9.3 La ventana de frecuencia admisible

Las dos restricciones aprietan desde lados opuestos y dejan una ventana estrecha:

| Presión | Empuja hacia | Origen |
|---|---|---|
| G1 = 300 operaciones OOS, ~6,4 años de MNQ, menos el holdout | **más frecuencia** | `verdict.py:60` |
| Fricción MNQ 2,0 pts = $4,00 ida y vuelta; 11 de 14 familias del estudio tenían ventaja bruta de 0,07–1,50 pts | **menos frecuencia** (objetivos más grandes) | CLAIM-001 |
| Ejecución humana sin retardo fino | **menos frecuencia** | F-retardo |
| Drawdown TRAILING_EOD de $2.000 y regla de consistencia del 30% | **más operaciones, más chicas** | perfil MFFU |

**Ventana resultante: aproximadamente 1 a 4 operaciones por día.** Alcanza para juntar 300
operaciones OOS en ~1–1,5 años de historia, es lento para ejecutarlo a mano, y admite objetivos lo
bastante grandes como para que $4 de fricción no sean el término dominante.

> **Pendiente de verificación con la fuente:** si la regla de consistencia del 30% de MFFU aplica a
> la fase de evaluación o sólo al retiro. El perfil la codifica con `semantics: terminate`
> (`data/house_rule.py:136`), pero eso es la implementación, no el reglamento. Afecta directamente
> cuán vinculante es la fila 4 de la tabla.

### 9.4 El orden

```
── HECHO ──────────────────────────────────────────────────────────────
0.1  Falsación de MNQ leída, corpus sembrado           PR #122
0.2  Ledger demostrado: registra y es idempotente      PR #123

── RATIFICADO el 2026-09-21 ───────────────────────────────────────────
C.1a Holdout: régimen               ┐ Las cinco decisiones, en bloque.
C.1b Holdout: corte 2025-01-01,     │ Firmadas sin un solo dato de CME
     21 meses, criterio MFFU        ┘ en el disco.                PR #124

── DoD CERRADO el 2026-09-21 ──────────────────────────────────────────
B.1  Databento: alta, crédito, cotización y licencia          #126
     Falta: aprobar la compra y decidir §7.1c.
     [rev 2026-09-22] La lista de §7.1d compraba UN instrumento. El spec
     prohíbe emitir veredicto con |U| = 1; y sobre el universo declarado
     de B (4 símbolos) el techo sería 1/4 = 25% < 60%. En los dos casos:
     ningún veredicto favorable es alcanzable. La reemplaza §7.1e — un
     líder por clase, de los que MFFU fondea:
     MNQ MGC M6E MBT MCL = $84,85 de $125.

── AHORA: desbloquear ─────────────────────────────────────────────────
B.6  Guarda de universo en C1  ← PRIMERO. Es el único que puede emitir
                                 un GO falso: hoy el denominador de C1
                                 es "lo que le pases". Capa 4, ciclo SDD.
B.4a Costos por instrumento    ← NO espera la compra. En paralelo a B.6.
                                 El motor cobra 4× de más, y cada falso
                                 negativo quema un ensayo del ledger.
                                 Cierra PA-106-C.

     ↓ DECIDIDO el 2026-09-22 (humano), §7.1e
     Se compra la lista de cinco líderes, $84,85. NO se compran MES ni
     MYM. Es cambio de spec y se asume.
     Lo que la decisión destapó: comprar y declarar son actos distintos.
     De los cinco, sólo MNQ tiene ancla de rango de apertura verificada,
     y |U| = 1 está prohibido.

B.7  Ancla del rango de apertura por clase  ← NUEVO. No espera la compra:
                                 es fuente primaria (CME), no dato de
                                 mercado. En paralelo a B.6 y B.4a.
                                 Generaliza PA-106-A. Su resultado es lo
                                 único que define qué puede declarar B.

     ↓ declaración del universo de B, ANTES de mirar un dato
     Se declara con lo que B.7 devuelva. Si ninguna ancla adicional
     cierra, se reactiva la compra de MES + MYM (+$31,98) — diferida,
     no descartada.

B.1b Descargar la lista de §7.1e  ← acción humana (aprobación)
B.2  Fichas de contrato CME       ← el `definition` de B.1b es su insumo
B.3  Exportador, empalme de continuos, sesiones  ← punto de no retorno
                                    C.1a y C.1b ratificadas: vía libre
B.4b `spread_for` lee `bbo-1m`    ← capa 3, ciclo SDD completo. Alcance
                                    mayor que el spread: hoy no hay
                                    loader ni esquema para BBO por minuto
B.5  F-retardo: implementarlo     ← capa 3/4, ciclo SDD completo.
                                    Decide ejecutabilidad Y portabilidad

── DESPUÉS: hacer honesto lo que ya existe ────────────────────────────
B.8  El veredicto juzga, no elige   ← D-E. Un veredicto por estrategia,
                                      pre-registro del lote en el ledger,
                                      T1 sin término de torneo. Capa 4.
C.3  RFC #57: D1, D2, D4, D5, D7    ← D5 cierra la gramática, D1 bloquea A.6
A.1  Gramática con ramificación ←── D5
     └─ luego: retirar candidate_b/ a mano (equivalencia ya probada)
        y mover smc/ a librería de primitivas
A.4  Primitivas de ejecución (una o dos, las que pida el corpus)
C.4  Pre-registro: hipótesis + ORDEN DE FUENTES  ← antes del primer ensayo

── PRIMER VEREDICTO ───────────────────────────────────────────────────
Dos o tres estrategias escritas A MANO, dentro de la ventana de 9.3,
corridas con F-retardo. Sin arquitecto automático de por medio.

── SÓLO SI EL MOTOR DEMOSTRÓ QUE SIRVE ────────────────────────────────
A.2  Gate 0 + taxonomía de mecanismos      ┐
A.3  Corpus formalizado                    │ CONGELADAS.
A.5  Enmascaramiento y cassette            │ Resuelven problemas que sólo
A.6  Registro de subespecificación ←── C.3 │ aparecen con volumen de
A.7  Dedup semántico                       │ estrategias, y todavía no hay
A.8  Adaptador de fuente                   ┘ ninguna.
C.2  POLITICA.md                             ← antes de capital real
```

**Dependencias que no se pueden invertir:** C.1a y C.1b **antes** de B.3; D5 antes de cerrar A.1;
C.3/D1 antes de A.6; C.4 antes del primer ensayo real.

**[rev 2026-09-22] Tres dependencias nuevas, todas del mismo tipo — cosas que si se hacen después
dejan de servir:**

- **La decisión de universo (§7.1e) antes de B.1b.** Redeclarar el universo con datos en el disco es
  elegir el denominador de C1 mirando resultados. **[rev 2026-09-22] Decidida: (b).** Lo que queda
  vivo es su consecuencia — **B.7 antes de declarar el universo de B**, y la declaración antes de
  mirar un dato. Un ORB sin apertura de contado no está definido sobre ese instrumento, y eso no lo
  arregla ninguna compra.
- **B.6 antes de cualquier veredicto.** Sin la guarda, un veredicto favorable no prueba lo que dice
  probar, y el paso siguiente a un GO es dinero real en un challenge.
- **B.4a antes de G3, G9 y los gates P.** El spec ya lo había anotado como **PA-106-C**: sin
  comisiones verificadas esos gates no corren de forma significativa. B.1 consiguió las comisiones en
  fuente primaria; B.4a es lo que falta para que entren al motor.

**[rev 2026-09-21] Cayó una dependencia:** «B.1 antes de C.1b» ya no aplica. El único dato que
C.1b necesitaba de B.1 era la primera sesión utilizable del MNQ, verificada en fuente primaria
(2019-05-05), así que C.1b se pudo escribir sin esperar la compra.

### 9.5 Lo que se rechazó de la revisión externa

- **«Bajar G1 de 300 a 100 operaciones y aflojar los criterios.»** Rechazado. Bajar la vara después
  de ver que la vara es difícil es selección sobre resultados, que es el mecanismo exacto que este
  proyecto existe para no ejecutar. Y se contradice con la evidencia que la propia revisión cita:
  el estudio de MNQ muestra que las familias de alta frecuencia tienen ventaja bruta **por debajo**
  del costo de operarlas.
- **«El ledger te salva del lazo de realimentación humano.»** Falso, y peligroso. El ledger cuenta
  los ensayos que se **corrieron**; nunca cuenta las alternativas que el operador consideró y
  descartó antes de correr nada. Ese lazo se cierra en la cabeza del operador, aguas arriba de
  cualquier registro. El único remedio sigue siendo I6: **pre-registrar el orden de las fuentes**
  (C.4).
- **«El carril A es un desperdicio»** dicho en el mismo texto que exige ampliar la gramática. Ampliar
  la gramática **es** A.1. Lo que se congela son A.2 y A.5–A.8, no el carril entero.

### 9.6 Revisión cruzada del 2026-09-22 (Gemini 3.8 Flash High, `agy-delegate --tier flash`)

Método de `mem:revision-cruzada-atrapa-inferencias-que-ningun-test-atrapa`: cinco afirmaciones
propias sometidas a verificación adversarial contra el árbol, con exigencia de cita `archivo:línea` y
de decir «no verificado» antes que inferir.

| Afirmación sometida | Veredicto | Qué pasó |
|---|---|---|
| El spec exige `\|U\| ≥ 2` y la lista de §7.1d no puede emitir veredicto | **verificada** | La línea 37 era changelog, pero la regla es normativa en el cuerpo (§2.x:598-602). Agregó el techo de **1/4 = 25%** para el universo declarado de B |
| La historia larga de NQ la bloquea el motor, no el dato | **parcial** | Corregida en §7.1e. B va flat al cierre por diseño, así que el cierre forzado no lo estorba: la historia profunda está **en la cola**, no vetada |
| Los costos son globales y no por instrumento | **verificada** | `costs.py:48` — `del symbol, timestamp, figure`. Ni `SymbolFigure` ni los perfiles de firma tienen comisión |
| F-retardo está declarado pero no planificado | **verificada** | Cero implementación; las únicas ocurrencias de «delay» en el código son reintentos HTTP |
| Comprar no gasta ensayos, declarar sí; y MGC declarado hoy empeora C1 | **verificada** | Con MGC fallando de entrada, C1 pasa a exigir **100% en los tres índices restantes** |

**El hallazgo que no estaba en el dossier y se volvió la casilla B.6:** el denominador de C1 en
`verdict.py:388-391` es `len(bundle)`, no el universo declarado. Las dos reglas normativas sobre
universo son texto sin ejecutor. Es el único defecto de esta tanda capaz de emitir un **GO falso**.

**Lo que se rechazó:** «la serie 2019–2024 de MNQ queda al borde de no alcanzar los 300 trades de
G1», apoyado en la estimación de ~250 oportunidades/año de **§7.6 del spec**. Esa sección está
**superada por `docs/DIMENSIONAMIENTO_HOLDOUT.md`**, que midió el problema corriendo el generador de
ventanas real en vez de estimarlo: con el corte ratificado 2025-01-01 hay 9 ventanas y 1.134 días
fuera de muestra, y G1 se traduce en **1 operación cada 3,8 días** — holgado dentro de la ventana de
1 a 4 por día de §9.3. El propio §7.6 se autodeclara «estimaciones heredadas del régimen CFD, a
confirmar contra datos CME reales». Que una revisión externa haya vuelto a caer en §7.6 es evidencia
de que la contradicción **hay que resolverla en el SSoT**, y queda anotada en §10.

### 9.7 Revisión cruzada de D-E, 2026-09-22 (dos rondas, Gemini 3.8 Flash High)

**Primera ronda — ¿el modelo de grilla es un cambio de esquema o una refundación?** La revisión dijo
**refundación**; el arquitecto había dicho **cambio de esquema**. Ninguno tenía razón entera:

| Afirmación | Veredicto | Qué quedó |
|---|---|---|
| El genoma ata una estrategia a un símbolo, obligatorio | VERIFICADA | `schema.py`, `GenomeUniverse.symbol` |
| El campo `session` ya es un requisito | PARCIAL | Es un string que nadie lee; `"US_EQUITY_OPEN"` **no existe** en `SESSIONS` |
| El desajuste está localizado en la capa 2 | **FALSA** | P1–P6 evalúan una canasta conjunta (`prop_sim.py:258`): la cuenta es compartida y **debe** seguir siéndolo |
| El catálogo de activos no tiene sesiones | VERIFICADA | `SymbolFigure` y `SESSIONS` viven separados; `SESSIONS` es 100 % era CFD |
| El resultado por celda no tiene tercer estado | VERIFICADA | `all_pass: bool` |

La reconciliación es D-E punto 3: **la grilla no reemplaza a la cartera, convive con ella** — celda,
fila, canasta y cuenta son preguntas distintas. **Error del arquitecto corregido en esta ronda:** había
afirmado que el ledger de ensayos «ya está armado por par». Falso: `compute_trial_id` no incluye el
símbolo, y un test normativo fija que la misma configuración sobre dos símbolos es **un** ensayo. La
revisión lo leyó como «sub-conteo masivo»; **es D1 funcionando bien** —el universo entra por
`dataset_hash_by_symbol`, así que la identidad del ensayo es `(config, universo)`—.

**Segunda ronda — la propuesta de cinco puntos.** Tres correcciones incorporadas:

- **T1 no es redundante con G4.** El arquitecto proponía eliminarlo. G4 mide operaciones de un activo
  con los ensayos de ese activo; T1 mide la canasta diaria con la suma de los ensayos del universo.
  Eliminarlo relajaba la exigencia de cartera. (El arquitecto lo detectó en paralelo leyendo
  `_compute_t1`.)
- **El ledger se escribe después del veredicto.** Sin pre-registrar el lote, las compañeras pagaban
  cero: ejemplo de la revisión, un lote de tres con ledger vacío baja de `108 + 2 = 110` a `108`.
  Origen del DoD (2) de B.8.
- **«No aplica» fuera del denominador de C1 era una relajación**, prohibida por §2.x. Pasa a ser estado
  de ejecución; la exclusión sólo por no declarar, antes de los datos.

Y una omisión: la primera versión tenía tres niveles y **se olvidaba de C3**. Quedaron cuatro.

**Lo que se rechazó:** que evaluar P1–P5 celda por celda reprobaría masivamente. Es cierto y no aplica:
nadie propuso evaluar los gates P por celda. **Lo que queda abierto de la revisión, sin casilla:** C2
exige PF ≥ 0,8 en el peor activo que falla, así que un universo sugerido por la grilla puede incluir un
activo aplicable pero ruidoso que hunda la fila entera. El filtro de calidad de activo (liquidez,
costo contra tick) ya está en el criterio de admisión de §2.x; falta que el catálogo lo lleve como
dato, que es parte de B.7.

---

## 10. Lo que este roadmap no resuelve

- ~~**De dónde salen los datos de CME** (B.1). Decisión de compra.~~ **[rev 2026-09-21] Resuelto,
  y dejó de ser una decisión de compra:** la cotización real dio **$14,48** para la serie completa
  de MNQ contra un crédito de $125 ([#126](https://github.com/ramaDben/genesis/issues/126)). A ese
  precio no hay proveedores que comparar. Lo que la lectura de la licencia **sí** dejó abierto es
  otra cosa, y más grave: la garantía de re-descarga no existe (§7.1c).
- ~~**Si la regla de consistencia del 30% de MFFU aplica a la evaluación o sólo al retiro.**~~
  **[rev 2026-09-21] Resuelto en fuente primaria: sólo a la evaluación, y no descalifica** — sólo
  obliga a operar más días hasta diluir el día grande. El perfil ya la codifica con esa semántica.
- ~~**Las tres decisiones del #81**: régimen (C.1a) y tamaño (C.1b).~~ **[rev 2026-09-21] Escritas**
  en POLITICA_HOLDOUT.md y DIMENSIONAMIENTO_HOLDOUT.md (PR #124) y **ratificadas el 2026-09-21**,
  las cinco decisiones en bloque. Ya no queda nada pendiente de decisión humana en esta casilla.
- **El techo de presupuesto de ensayos** (D4). Es un número que sale de política, no de código.
- **Si el venue es exigencia o selección** bajo D1. Decide si el ledger debe filtrar o agrupar.
- **Cuánto descontar por el sesgo de supervivencia de la fuente.** I7 dice que un «sobrevive»
  externo vale menos; **no dice cuánto menos**, y no hay forma honesta de estimar los ensayos
  invisibles que hay detrás de un video. El holdout es el único instrumento que mide eso
  indirectamente. Inventar un `n_trials` previo sería exactamente la clase de cifra sin fundamento
  que el proyecto rechaza.
- **Qué se publica y con qué nombre.** Un veredicto que dice «la estrategia de Fulano no sobrevive a
  costos» nombra a una persona real y a su negocio. Con el objetivo del RPSF de la CMF de fondo, esa
  es una clase de riesgo distinta a la de un backtest interno, y conviene decidirla antes del primer
  veredicto incómodo, no después. **[rev 2026-09-21] Y ahora tiene además una dimensión
  contractual**, que no es la misma pregunta: el contrato de Databento define la redistribución
  como entregar a terceros los datos «or other information derived from the same» (§1.5e), y un
  veredicto publicado es información derivada. Exige atribución y autoriza a Databento a usar
  nuestro nombre en su marketing (§1.6). Ver §7.1c.

**[rev 2026-09-22] Deuda declarada en el SSoT, que este roadmap no puede saldar solo.** Son
contradicciones entre el spec y lo que el proyecto ya decidió; tocarlas es tocar el documento que
gobierna los gates, y va por su propio camino:

- **§7.6 contradice a `DIMENSIONAMIENTO_HOLDOUT.md` sobre G1.** §7.6 concluye que G1 «no es
  holgadamente alcanzable» a partir de estimaciones que él mismo declara heredadas del régimen CFD;
  el dimensionamiento lo **midió** con el generador de ventanas real y da 1 operación cada 3,8 días.
  Mientras las dos versiones convivan, cualquier lector —humano o revisor externo, como pasó en
  §9.6— puede citar la equivocada. El documento medido gana; el spec tiene que decirlo.
- **El vocabulario de «torneo» quedó vestigial.** D-A (2026-09-20) ya decidió que el arquitecto
  adjudica estrategias de terceros en vez de competir tres candidatos propios, y el dueño lo ratificó
  el 2026-09-21. A/B/C no son «el torneo»: son las primeras estrategias que llegaron. El SSoT sigue
  titulado y redactado como torneo, y el nombre aparece en identificadores del veredicto.
  ~~**Es renombre, no cambio de comportamiento**~~ **[rev 2026-09-22] Falso:** el veredicto elige
  ganador y ajusta el castigo por cantidad de competidores. El comportamiento lo resuelve **B.8**
  (D-E); lo que queda acá es sólo la redacción del SSoT, que va por su propio change.
- **El universo del Candidato B, decidido el 2026-09-22, todavía no está en el spec.** §2.3 línea 510
  sigue declarando `MES, MNQ, MYM, MGC`, y §7.6 apoya su estimación en «3 micro-índices sobre una
  sola sesión RTH». La decisión (b) de §7.1e los contradice. **Hasta que el spec cambie, el
  denominador normativo de C1 para B son cuatro índices** — el roadmap no puede redeclararlo por su
  cuenta, porque el SSoT es el que gobierna los gates. El cambio no se escribe todavía: espera el
  resultado de **B.7**, porque escribir un universo sin ancla verificada sería repetir el error que
  §7.1e acaba de corregir.
- **PA-106-A quedó chica.** Está redactada como «el ancla del oro»; el problema es **el ancla por
  clase** (B.7). Al reescribirla hay que conservar lo que ya dice bien —fuente primaria, no se
  rellena con memoria del modelo— y agregar que «no tiene apertura de contado» es un resultado
  válido que se registra, no un pendiente perpetuo.
- **El alcance de asesoría regulada (RPSF/CMF) fue retirado por el dueño el 2026-09-21.** El objetivo
  declarado es operar con prop firms. La viñeta de arriba sobre qué se publica **sigue vigente por la
  vía contractual de Databento**, pero su premisa regulatoria ya no aplica, y la memoria que la
  sostenía hay que corregirla.
