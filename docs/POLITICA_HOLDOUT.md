# Política del holdout

> **Estado: propuesta, pendiente de ratificación humana.**
> Cierra la casilla **C.1a** del [`ROADMAP_ARQUITECTO.md`](ROADMAP_ARQUITECTO.md) — las decisiones 2
> y 3 del [#81](https://github.com/ramaDben/genesis/issues/81). El **tamaño** del holdout y su
> **umbral de aprobación** no están aquí: son C.1b, en
> [`DIMENSIONAMIENTO_HOLDOUT.md`](DIMENSIONAMIENTO_HOLDOUT.md). Las dos tienen que ratificarse
> juntas y antes de B.3.
>
> **Corregido el 2026-09-21**: ver §2.1. Lo que se congela antes de mirar el holdout es el
> *procedimiento*, no los parámetros ajustados. La primera versión decía lo contrario y
> contradecía el diseño del walk-forward.
>
> Escrito el **2026-09-20**, antes de que exista un solo dato de futuros CME en el disco.
> Esa fecha es parte del contenido: una política de holdout escrita después de mirar los datos no
> vale nada, y esta se escribió antes. Verificado al escribirla: **no existe ningún holdout** —
> cero menciones de `holdout` en `src/` y `scripts/`.

---

## 0. Qué es un holdout y por qué existe este documento

Un **holdout** es un pedazo de la historia de precios que se aparta al principio, no se mira nunca,
y se usa una sola vez al final para responder una única pregunta: *lo que construimos, ¿funciona
sobre datos que nadie usó para construirlo?*

Todo lo demás que hace genesis —walk-forward, Monte Carlo, purged K-fold, DSR, PBO— mide el
sobreajuste **que nosotros producimos**. Ninguno mide el sobreajuste que viene **heredado de la
fuente**: el trader de YouTube que publica su estrategia ya la ajustó a esta misma historia, y los
intentos que descartó antes de publicarla no están en ningún registro que podamos contar. Es el
invariante **I7** del roadmap: un «sobrevive» externo vale menos, y no sabemos cuánto menos.

**El holdout es el único instrumento que mide eso.** Si se contamina, esa medición no existe y no
hay forma de reconstruirla. No es una salvaguarda más entre varias: es la única de su clase.

---

## 1. Decisión 2 — Qué pasa cuando se mira el holdout

### Propuesta: **es un gate, no un informativo.**

Un candidato que falla en el holdout **no pasa**, cualesquiera sean sus números en el resto del
pipeline. No se reporta como «advertencia», no se pondera contra los demás gates, no se compensa
con un DSR alto.

### Por qué

**Un número que no obliga a nada se racionaliza.** Esto no es una hipótesis sobre la naturaleza
humana: es el modo de falla que este proyecto ya documentó en su propio CLAUDE.md sobre el gate
humano del ciclo SDD —«en la práctica se aprobó sin leer»— y el que el ledger vacío de agosto
demostró por otro camino. Un control que puede ignorarse sin consecuencia mecánica termina
ignorándose.

Y hay una asimetría que lo decide: **si el holdout es informativo, el costo de mirarlo es cero, así
que se mira temprano y seguido.** Cada mirada lo degrada. Un holdout informativo se autodestruye
por uso; uno vinculante se protege solo, porque mirarlo tiene consecuencias.

### Lo que esto cuesta, dicho de frente

Un gate binario sobre pocos datos **rechaza candidatos buenos por mala suerte**. Con 300
operaciones OOS y un holdout más chico todavía, la varianza es real. Esa es la contrapartida
aceptada: **el proyecto prefiere rechazar un candidato bueno antes que aprobar uno malo**, porque
el costo de los dos errores no es simétrico. Un rechazo equivocado cuesta una oportunidad; una
aprobación equivocada cuesta el capital de una cuenta de fondeo y, peor, destruye la credibilidad
de todos los veredictos anteriores del sistema.

### Cómo se implementa

El umbral del holdout **se declara por adelantado, junto con la política**, no después de ver el
resultado. Un umbral elegido al ver el número es selección sobre el holdout, que es exactamente lo
que la decisión 3 prohíbe.

---

## 2. Decisión 3 — Cuántas veces se puede mirar

### Propuesta: **una vez por candidato, y el resultado es definitivo.**

Reglas concretas:

1. **Una mirada por candidato.** Se mira el holdout una sola vez por cada candidato, al final, con
   el candidato ya congelado. **Lo que se congela es el *procedimiento*, no los números ajustados**
   — ver §2.1, que es la corrección más importante de este documento.
2. **Mirar cuenta como ensayo.** Cada mirada al holdout se registra en `ledger/trials.jsonl` como
   cualquier otro ensayo y **deflaciona el DSR de todos los candidatos posteriores**. Esto es D1
   aplicada al holdout: el holdout es una dimensión sobre la que se selecciona, luego se paga.
3. **No hay reintento.** Un candidato que falló el holdout **no se ajusta y se vuelve a correr**.
   Ni con otros parámetros, ni con otro filtro, ni «arreglando un bug». Mirar, fallar, ajustar y
   volver a mirar es el mecanismo de sobreajuste en su forma más pura, y es peor que no tener
   holdout, porque produce un número que *parece* una validación fuera de muestra y no lo es.
4. **Una variante ajustada de un candidato que falló es un candidato nuevo**, con su propio ensayo,
   su propia entrada en el ledger, y con la exigencia de estar pre-registrada bajo C.4 **antes** de
   que se conociera el resultado del original. Si no se pre-registró antes, no se corre.
5. **No hay reset del holdout.** No existe un procedimiento sancionado para «refrescarlo». Si se
   contamina, se contaminó: se declara contaminado por escrito, con fecha y causa, y el proyecto
   pierde ese instrumento hasta que exista historia nueva que nunca se haya mirado.

### Por qué la regla 3 es la que realmente importa

Las reglas 1 y 2 son contabilidad. La 3 es la que hace trabajo, porque describe el atajo que
efectivamente se va a querer tomar: el candidato falló por poco, la causa parece obvia y el arreglo
parece legítimo. **Siempre parece legítimo.** Esa es la razón por la que la regla tiene que estar
escrita antes de que la situación ocurra, y no ser un juicio del momento.

---

## 2.1. Qué significa exactamente «congelado»

> **[corrección del 2026-09-21]** La primera versión de este documento decía que se congelaban
> «genoma, parámetros, umbrales y perfil de firma». Eso estaba mal y lo detectó una revisión
> externa (agy/Gemini, tier pro) mientras se dimensionaba el holdout en C.1b. Se corrige acá.

### El error

Congelar los **parámetros ajustados** contradice el diseño del propio walk-forward.

El walk-forward de este proyecto usa `step = 126` días hábiles
(`validation/window_config.py:STEP_TRADING_DAYS`). Eso no es un detalle de implementación: es una
afirmación sobre la estrategia. Dice que **el ajuste se rehace cada seis meses**, porque el
proyecto no cree que un conjunto de parámetros siga siendo válido indefinidamente.

Si después congelamos esos parámetros durante uno o dos años de holdout, estamos obligando al
candidato a hacer exactamente lo que el diseño declara que es un error. Y peor: lo que medimos ya
no es la estrategia, es «la estrategia con los parámetros de tal fecha», que es algo que nadie va a
operar nunca.

### La corrección

**Se congela el procedimiento completo, y dentro del procedimiento va el calendario de reajuste.**

Concretamente, lo que queda fijado y hasheado antes de mirar el holdout:

| Se congela | No se congela |
|---|---|
| El genoma: qué mecanismo, qué señales, qué reglas de entrada y salida | Los valores numéricos que el ajuste produzca en cada ventana |
| La grilla de búsqueda: qué valores se prueban y cuáles no | Cuál de esos valores gana en cada ventana |
| El criterio de selección dentro de la grilla | — |
| **La cadencia de reajuste** (los mismos 252/126/126 del walk-forward) | — |
| El perfil de firma, el perfil de costos y la política de ejecución | — |
| El umbral de aprobación del holdout (§4 y C.1b) | — |

Dentro del holdout, el procedimiento congelado **se reajusta según su propio calendario, siempre
hacia adelante**: cada reajuste usa únicamente datos anteriores a la ventana que va a operar. Nunca
mira el futuro. Esa es la misma disciplina forward-only que el resto del pipeline ya impone por
construcción (`LookaheadError`).

### Por qué esto sigue siendo una sola mirada

Porque **nadie mira el resultado hasta el final**. El procedimiento corre solo de punta a punta
sobre el holdout y devuelve un único veredicto. Que internamente se haya reajustado cuatro veces no
es «mirar cuatro veces»: es el procedimiento haciendo lo que se declaró que iba a hacer, sin que
ningún humano vea un número intermedio y decida algo con él.

La regla 3 —no hay reintento— no se debilita en nada. Sigue prohibido ver el resultado y tocar
cualquier casilla de la columna izquierda de la tabla.

### Efecto lateral que conviene anotar

Esta corrección **desactiva una objeción contra los holdouts grandes**: se decía que un holdout de
dos años dejaba al entrenamiento «ciego» a los dos años más recientes. Con el procedimiento
congelado en vez de los parámetros, eso deja de ser cierto — el procedimiento sí se reajusta con
los datos recientes a medida que avanza por el holdout. Lo que nunca ve es su propio resultado.

---

## 3. El borde del holdout es parte de la identidad del artefacto

La fecha de corte del holdout **se declara en el manifiesto de cada corrida**, junto al hash de
dataset, los hashes de perfiles, las semillas y el commit.

Razón: sin eso, dos corridas con cortes distintos son indistinguibles en los artefactos, y correr
la misma estrategia con varios cortes hasta que uno dé bien es **selección sobre el borde del
holdout** — una dimensión de selección invisible que el ledger no vería. Declarar el borde en el
manifiesto hace que esa manipulación deje rastro.

Requisito derivado, para B.3: **el corte del holdout se define por fecha calendaria**, no por
proporción de la muestra. Una proporción se mueve sola cada vez que el dataset crece, y entonces el
borde deja de ser un compromiso y pasa a ser una consecuencia.

---

## 4. Qué NO decide este documento

| Pendiente | Dónde se decide |
|---|---|
| **Tamaño y fecha de corte del holdout** | C.1b — escrito en [`DIMENSIONAMIENTO_HOLDOUT.md`](DIMENSIONAMIENTO_HOLDOUT.md) |
| **Valor del umbral del holdout** | C.1b — escrito en [`DIMENSIONAMIENTO_HOLDOUT.md`](DIMENSIONAMIENTO_HOLDOUT.md) §3 |
| **Si se usa la historia larga de NQ (desde 1996) para operar MNQ** | B.1 / C.1b |
| **Techo de presupuesto de ensayos (D4)** | C.2 / RFC [#57](https://github.com/ramaDben/genesis/issues/57) |
| **Cuánto descontar por el sesgo de supervivencia de la fuente (I7)** | Abierto, y probablemente no estimable honestamente. El holdout lo mide indirectamente; ese es todo el punto |

---

## 5. Ventana de irreversibilidad

Esta política **tiene que estar ratificada antes de B.3**, la casilla que mira la primera barra real
de CME. Después de eso no se puede declarar un holdout honesto sobre los datos que ya se miraron,
y ninguna cantidad de disciplina posterior lo repara.

Estado de la ventana al **2026-09-20**: **abierta**. No hay datos de CME en el disco.
