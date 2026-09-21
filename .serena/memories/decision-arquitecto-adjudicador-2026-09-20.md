*(2026-09-20 — decisiones de rumbo del dueño del proyecto + roadmap trazado y revisado en cruz.)*

# El arquitecto de estrategias: adjudicador feed-forward, no buscador

Roadmap completo en `docs/ROADMAP_ARQUITECTO.md`. Esta memoria guarda **las decisiones y su
porqué**, no el contenido del documento.

## Las tres decisiones

**D-A. El arquitecto adjudica, no busca.** Transcribe estrategias declaradas por terceros —traders
publicados, con nombre— a genomas. No genera hipótesis propias ni explora un espacio de parámetros.
El objetivo declarado: validar o descartar las ideas de traders de renombre.

**D-B. El arquitecto es feed-forward.** Ningún resultado del evaluador regresa al proponente. No es
política: son dos almacenes separados físicamente.

**D-C. Ningún ensayo sobre datos de CFD.** Las estrategias se prueban sobre futuros CME. MT5 no se
usa ni como paso previo. Razón del usuario: entorno manipulado y con muchísima fricción.

## Por qué D-B es la decisión que más vale

El modo de falla de un arquitecto automatizado es el **lazo**: proponer → medir → ajustar → proponer.
Verificado en el referente del sector: `microsoft/RD-Agent`
(`rdagent/scenarios/qlib/developer/feedback.py`) le inyecta al LLM que propone la siguiente hipótesis
el retorno anualizado con costos y el max drawdown del backtest, y le pide decidir
`"Replace Best Result"`. Búsqueda sobre el conjunto de prueba, en bucle, sin DSR ni denominador en
ningún lado del framework. **El invariante «señal de retorno sin OOS» de genesis es la corrección de
ese defecto, tomada antes de construir nada.**

Un arquitecto que transcribe claims externos no tiene ese lazo que amputar.

## Lo que la revisión cruzada agregó y el documento original no decía

Revisión con `gemini-3.8-flash-high` vía `agy-delegate` (ver `mem:delegacion-agy-configurada`).
Nueve hallazgos: seis aceptados, uno con corrección, dos rechazados parcialmente.

**D-B no cierra todos los lazos** — el hallazgo central, y es correcto:

1. **El operador es un canal de realimentación.** El muro está entre el arquitecto y los resultados,
   no entre el *operador* y los resultados. Elegir qué trader transcribir después mirando cómo le
   fue al anterior es selección bajo D1, ejecutada por un humano. Remedio: pre-registrar **el orden
   de las fuentes** (#88), no sólo cada hipótesis.
2. **Sesgo de supervivencia de la fuente.** Un trader publica lo que funcionó en el régimen
   reciente, no una muestra aleatoria. Genesis hereda ensayos invisibles que nunca entran al
   denominador. Remedio: el holdout, y tratar un «sobrevive» externo con más escepticismo que uno
   pre-registrado. **Descartado** el remedio que propuso el modelo (inventar un `n_trials_prior`):
   ese número no se puede conocer y ponerlo es exactamente la cifra sin fundamento que el proyecto
   rechaza.

**Dos errores propios que la revisión encontró:**

- **El empalme de continuos SÍ afecta a estrategias intradía.** El roadmap repetía —tomándolo de
  `mem:pivote-a-prop-de-futuros-cme-2026-09`— que como nunca se cruza un roll con posición abierta,
  la convención de empalme no altera resultados. **Falso, con contraejemplo en el repo**:
  `candidate_b1_orb.yaml` usa Chandelier con ATR de 22 barras y RVOL con `lookback_days: 10`. Los dos
  cruzan el roll. Un empalme sin ajustar distorsiona la volatilidad que dimensiona cada posición.
  Y los futuros CME cotizan ~23 h: un «rango de apertura» no significa nada sin declarar RTH o ETH.
- **Faltaba el carril de primitivas de ejecución.** #110 entrega el *mecanismo* de despacho, no las
  estrategias — su propio DoD lo dice. Una tabla de despacho con una sola rama implementada sigue
  siendo una sola estrategia. Sin primitivas (reversión, VWAP, barrido de liquidez), el adaptador
  alimentaría claims que la gramática sabe nombrar y nada sabe correr. El corpus decide cuáles
  construir, así que va después de él.

**Un hallazgo que mejoró un diseño:** la prueba de «predicción falsable» de Gate 0 no era mecánica
—un campo de texto no vacío es cosmética; un LLM juez es no determinista— y se resolvió con una
**taxonomía cerrada de mecanismos económicos**: el corpus mantiene un catálogo finito y enumerado,
el genoma referencia un ID, y Gate 0 verifica que resuelva y que sea compatible con el `kind`. El
juicio humano ocurre una vez, al dar de alta el mecanismo.

## Dos hallazgos de orden que valen por sí solos

**El #86 se reactivó solo.** Su condición de reanudación número 3 dice textualmente *«Se decide
construir el arquitecto — la respuesta A2 lo dejó condicionado a que el ledger de ensayos funcione,
y esa condición es una cláusula de política todavía no escrita»*. Esa decisión se tomó hoy. No hace
falta la entrevista completa: hace falta esa cláusula, que además es la D4 del RFC #57.

**El pivote a futuros abarató el holdout (#81), pero sólo en parte.** Todo el análisis de costo del
#81 está calculado contra el dataset US500 de CFD, que murió con D-C. Sus decisiones 2 y 3 (qué pasa
al mirar, cuántas veces) son gratis hoy. La decisión 1 (tamaño) **no**: depende del catálogo real del
proveedor, y el MNQ cotiza desde mayo de 2019 (~6,4 años). Matiz: MFFU permite 3 minis o 30 micros,
así que se puede usar la historia larga del NQ y operar MNQ. La ventana de irreversibilidad se cierra
cuando se mire la primera barra de CME.

## Dato que confirma D-C mecánicamente

`ledger_extra_trials` (`src/genesis/validation/verdict.py`) es un entero que se suma al DSR efectivo
de G4 y a T1 **sin filtrar por símbolo, bróker ni clase de activo** (punto 4 del #114). Correr 40
estrategias en CFD y después en futuros son 80 en el denominador, no 40.

Pero **no es una razón para D-C, es una consecuencia a resolver**: si D1 declara el venue como
exigencia, el remedio correcto es particionar el ledger, no abandonar un universo. Usarlo como
argumento era circular. Queda como requisito en el roadmap.

## Estado del corpus (el «cerebro» tipo Obsidian)

Idea del usuario, validada con reservas. Es un **traductor entre taxonomía retail y mecanismo
académico** (`order block` → desbalance de liquidez → fuente), no un generador de estrategias. La
unidad es **el claim**, no el autor ni el concepto, porque las contradicciones existen entre claims.
Se minan **desacuerdos y condiciones de falla, no consensos**: doce autores hablando de order blocks
no son doce evidencias, son una idea copiada doce veces. Prohibido cualquier score por conteo de
nodos. La mayoría del vocabulario retail no va a mapear a ningún mecanismo, y **ese es el resultado
esperado**.

La ranura ya existe sin usar: `candidates/specs/candidate_c1_gold_lob.yaml:7-15` declara
`sources.academic`, `sources.institutional` y `failure_mode`.

Relacionadas: `mem:pivote-a-prop-de-futuros-cme-2026-09` (contiene el error del empalme, corregido
acá), `mem:auditoria-alineacion-issues-2026-09-14`, `mem:change-103-arquitecto-y-compilador-genomas`,
`mem:d1-que-cuenta-como-ensayo`, `mem:d3-holdout-oos-intocable`,
`mem:revision-cruzada-atrapa-inferencias-que-ningun-test-atrapa`,
`mem:proposito-real-y-alcance-de-genesis`.
