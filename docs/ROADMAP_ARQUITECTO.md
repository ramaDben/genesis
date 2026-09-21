# Roadmap — El Arquitecto de Estrategias

*Trazado el 2026-09-20. Estado del árbol al escribirlo: `main` en `1389d91`, engine de pulse en
`explore`, sin change activo.*

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
| **B. Datos CME** | falsación previa, fuente, fichas, exportador, sesiones | **el primer ensayo real** |
| **C. Decisiones** | política, holdout, semántica de ensayos, pre-registro | **la interpretación de cualquier resultado**, y A.6 |

A y B avanzan en paralelo sin tocarse. C no bloquea construir —salvo A.6, que necesita D1— pero sí
bloquea que lo construido signifique algo.

---

## 4. Casilla cero: lo que va antes que todo

### ☐ 0.1 — Leer el estudio de falsación de señales OHLCV en MNQ

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

### ☐ 0.2 — Demostrar que el ledger registra

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

---

## 5. Carril C — Las decisiones con ventana que se cierra

### ☐ C.1a — Declarar el régimen del holdout ([#81](https://github.com/ramaDben/genesis/issues/81), decisiones 2 y 3)

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

### ☐ C.1b — Dimensionar el holdout *(después de B.1, estrictamente antes de B.3)*

**[rev] Esto no se puede decidir hoy.** El tamaño depende de cuánta historia exista, y eso sale del
catálogo del proveedor. El MNQ cotiza desde **mayo de 2019** — unos 6,4 años, no quince. Fijar a
ciegas un holdout de dos años sobre un historial de seis consume un tercio de la muestra y puede
romper G1, que exige ≥300 trades OOS.

Matiz que cambia el cálculo: MFFU permite **3 minis o 30 micros**, así que se puede usar la historia
larga del **NQ** (desde 1996) y operar **MNQ**. Eso hay que confirmarlo contra el catálogo real del
proveedor en B.1.

Todo el análisis de costo que el #81 trae escrito —perder una ventana, dejar G1 con 8% de margen
sobre 405 trades— está calculado contra el dataset US500 de CFD, que **murió con D-C**. No sirve
como referencia; hay que rehacerlo contra el dataset de futuros.

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

Cuatro de sus siete decisiones abiertas dejan de ser teóricas:

| Decisión | Qué cambia con el arquitecto |
|---|---|
| **D1** — qué cuenta como ensayo | Pregunta nueva y **bloqueante de A.6**: ¿cada interpretación de un claim subespecificado es un ensayo propio, o la familia cuenta como uno? Y: ¿el venue entra como **exigencia** o como **selección**? De eso depende si el ledger debe particionar (ver §1, D-C) |
| **D2** — destino del `CANDIDATE_REGISTRY` | Sigue resuelta **por elusión**: `strategy/contract.py:63` sigue indexado por letra y los genomas compilados nunca entran ahí. Conviene declararla al formalizar la gramática, no seguir eludiéndola |
| **D4** — techo de presupuesto de ensayos | Con un arquitecto pasa de teórico a operativo. Es la cláusula que C.2 tiene que escribir |
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

### ☐ B.1 — Fuente de datos y comisiones *(decisión abierta, no resoluble leyendo el repo)*

No hay MT5 para futuros. Las opciones reales son Databento, CME DataMine directo, el feed de
Rithmic/Tradovate, IQFeed o Norgate — con precios, licencias y granularidades muy distintas. El
requisito de reproducibilidad institucional exige que la fuente sea **estable y re-descargable**,
porque el hash de dataset tiene que poder recomputarse dentro de dos años.

Y las comisiones por contrato de MFFU **no están publicadas** en su help center; dependen de la
plataforma. Hacen falta para `costs.py`.

**[rev] Entrega además el insumo de C.1b**: el catálogo real de fechas y la profundidad histórica
efectiva por contrato, que es lo que permite dimensionar el holdout. Sin eso, C.1b se decide a
ciegas.

### ☐ B.2 — Fichas de contrato por venue

`value_per_point = tick_value / tick_size` (`src/genesis/data/symbols.py:36`) da el multiplicador del
contrato de forma natural, así que la abstracción del #55 aguanta futuros **sin cambio de esquema**.
Lo que falta es una fuente de fichas por venue, no un fallback calculado: la heurística
`tick_size = 10^-digits` **falla 25× en ES/NQ** (tick real 0,25 con 2 dígitos). Ver el #114.

### ☐ B.3 — Exportador, empalme de continuos y sesiones CME

El más caro, y el primero que mira una barra real — o sea, **el punto de no retorno de C.1b**.

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

## 9. Orden propuesto

```
0.1  Leer la falsación de MNQ ──────────────┐ insumo que puede reordenar (no veto)
0.2  Demostrar que el ledger registra       │
                                            │
C.1a Holdout: régimen (decisiones 2 y 3) ───┤ gratis hoy, no depende del dataset
C.2  POLITICA.md (cláusula del arquitecto)  │ reactivado por la decisión de hoy
C.3  RFC #57: D1, D2, D4, D7 ───────────────┤ D1 bloquea a A.6
                                            │
A.1  Gramática con despacho ────────────────┤ requisito de viabilidad
A.2  Gate 0 + taxonomía de mecanismos       │
A.3  Corpus ────────────────────────────────┤ decide qué primitivas hacen falta
A.4  Primitivas de ejecución                │  carril A
A.5  Enmascaramiento y cassette             │  (sin datos de mercado,
A.6  Registro de subespecificación ←── C.3  │   sin gastar ensayos)
A.7  Dedup semántico                        │
A.8  Adaptador de fuente ───────────────────┘

B.1  Fuente de datos + comisiones ──────────┐ carril B, en paralelo
C.1b Holdout: tamaño ←── B.1                │ bloquea el primer ensayo,
B.2  Fichas de contrato por venue           │ no la construcción
B.3  Exportador, empalme, sesiones ─────────┘ ← punto de no retorno de C.1b

C.4  Pre-registro #88 (hipótesis + orden de fuentes) ← antes del primer ensayo
```

**Dependencias que no se pueden invertir:** C.3 antes de A.6; A.3 antes de A.4; B.1 antes de C.1b;
C.1b antes de B.3; todo el carril A antes de A.8.

---

## 10. Lo que este roadmap no resuelve

- **De dónde salen los datos de CME** (B.1). Decisión de compra, con costo real.
- **Las tres decisiones del #81**: régimen (C.1a) y tamaño (C.1b).
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
  veredicto incómodo, no después.
