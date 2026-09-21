# Dimensionamiento del holdout

> **Estado: RATIFICADA el 2026-09-21** por el dueño del proyecto.
> Ratificada **en bloque** con [POLITICA_HOLDOUT.md](POLITICA_HOLDOUT.md), como exigen los dos
> documentos, y **antes** de que exista un solo dato de futuros CME en el disco.
> Cierra la casilla **C.1b** del [`ROADMAP_ARQUITECTO.md`](ROADMAP_ARQUITECTO.md) — la decisión de
> tamaño del [#81](https://github.com/ramaDben/genesis/issues/81), más el umbral de aprobación que
> [`POLITICA_HOLDOUT.md`](POLITICA_HOLDOUT.md) dejó abierto.
>
> Escrito el **2026-09-21**, antes de que exista una sola barra de futuros CME en el disco. Esa
> fecha es parte del contenido: dimensionar un holdout después de mirar los datos no vale nada.
>
> **No se puede ratificar por separado de `POLITICA_HOLDOUT.md`.** Las dos son la misma decisión
> partida en dos documentos, y las dos vencen en B.3.
>
> **La sección 4 se reescribió el 2026-09-21**, después de verificar el reglamento de la firma en
> fuente primaria. La versión anterior preguntaba si la cuenta *sobrevivía*; la correcta pregunta si
> *llega a ser fondeada*. También se corrigió una afirmación falsa: el criterio **no** estaba ya
> construido. Ver §4.2 y §4.6.

---

## 0. Las tres preguntas que este documento responde

1. **¿Dónde se corta?** Qué fecha separa lo que se puede mirar de lo que no.
2. **¿Cuánto se aparta?** Cuántos meses quedan del lado prohibido.
3. **¿Con qué criterio se aprueba?** Qué tiene que pasar en el holdout para que un candidato pase,
   declarado **antes** de ver un solo resultado.

La tercera es la más importante y la que estuvo abierta más tiempo. Un umbral elegido después de
ver el número no es un umbral: es una racionalización con formato de umbral.

---

## 1. Las dos restricciones duras que fijan el rango posible

No se elige el tamaño del holdout en el aire. Hay dos topes en el código que lo acotan por los dos
lados, y el tamaño sale de ahí.

### Tope de arriba: el holdout le come ventanas al walk-forward

El walk-forward corta la historia en ventanas de **252 días hábiles de entrenamiento + 126 de
prueba, avanzando de a 126** (`validation/window_config.py`). Cada mes que se aparta para el
holdout es un mes que el walk-forward no tiene, y en algún punto se pierde una ventana entera.

**El mínimo es 4 ventanas**, y no es negociable: el método que estima la probabilidad de
sobreajuste (CSCV) necesita al menos cuatro para tener resolución, y con menos el pipeline **aborta
con error**, no degrada silenciosamente (`validation/dsr_pbo.py:_MIN_CSCV_SPLITS = 4`).

### Tope de abajo: G1 exige 300 operaciones, y eso fija una velocidad mínima

El gate **G1** exige **300 operaciones fuera de muestra** (`validation/verdict.py:_G1_MIN_TRADES_OOS`).
Se suman sobre **todas** las ventanas, no sobre una.

Eso convierte el tamaño del holdout en una restricción sobre **qué tan lenta puede ser la
estrategia**: menos ventanas es menos días fuera de muestra, y menos días fuera de muestra exige
más operaciones por día para llegar a 300. Es el punto que roza directamente el objetivo declarado
del proyecto —una estrategia lenta, ejecutable a mano—, y por eso es la variable que de verdad
decide.

---

## 2. La medición

Instrumento: **MNQ** (Micro E-mini Nasdaq-100). Primera sesión **2019-05-05**, último dato
disponible **2026-09-18**. Se eligió el micro sobre el mini porque con un límite de pérdida de
2.000 USD la granularidad importa: el micro vale 2 USD por punto, el mini 20.

Números obtenidos **corriendo el generador de ventanas real** del proyecto
(`wfa._iter_window_bounds`), no estimando. Los días hábiles excluyen fines de semana y descuentan
9 feriados por año.

| Corte | Holdout | Días de entren.+valid. | Ventanas | Margen sobre el mínimo de 4 | Días fuera de muestra | **Velocidad mínima que exige G1** | Días de holdout | **Operaciones en el holdout, a esa velocidad mínima** |
|---|---|---|---|---|---|---|---|---|
| 2026-03-01 | 7 meses | 1719 | 11 | +7 | 1386 | 1 cada 4,6 días | 139 | 30 |
| 2025-10-01 | 12 meses | 1614 | 10 | +6 | 1260 | 1 cada 4,2 días | 243 | 58 |
| 2025-05-01 | 17 meses | 1509 | 9 | +5 | 1134 | 1 cada 3,8 días | 349 | 92 |
| **2025-01-01** | **21 meses** | **1426** | **9** | **+5** | **1134** | **1 cada 3,8 días** | **432** | **114** |
| 2024-10-01 | 24 meses | 1362 | 8 | +4 | 1008 | 1 cada 3,4 días | 495 | 147 |

### Cómo se lee esta tabla

Las dos columnas que importan tiran para lados opuestos:

- **«Velocidad mínima que exige G1»**: cuanto más grande el holdout, más rápida tiene que ser la
  estrategia para calificar. Un holdout grande **achica el universo de estrategias admisibles**.
- **«Operaciones en el holdout»**: cuanto más grande el holdout, con más evidencia se toma la
  decisión final. Un holdout grande **hace más confiable la única prueba sin reintento**.

La última columna está calculada para la estrategia **más lenta que todavía califica**. Es el caso
peor, y es el que hay que mirar: si el sistema funciona ahí, funciona en todo el rango.

---

## 3. Decisión 1 — Corte el **2025-01-01**, holdout de **21 meses**

### El razonamiento

Contra el holdout de 12 meses: **58 operaciones no alcanzan** para decidir, una sola vez y sin
reintento, si una estrategia sirve o no. Con 58 operaciones, la suerte pesa más que la ventaja.

Contra el holdout de 24 meses: baja a 8 ventanas y sube la velocidad mínima a 1 operación cada 3,4
días. Es un costo real sobre el objetivo de «estrategia lenta», y se paga para ganar 33 operaciones
más que el corte de 21 meses.

**21 meses es donde las dos curvas se cruzan mejor:**

- **9 ventanas**, margen +5 sobre el mínimo. Sobrado.
- La velocidad mínima sube de 1 cada 4,2 días a **1 cada 3,8 días**. Prácticamente no cambia qué
  estrategias son admisibles.
- **114 operaciones** en el holdout contra 58. **Casi el doble de evidencia** por un costo casi
  nulo del otro lado.

### Por qué esta fecha y no otra cercana

**No está al filo de un cambio de conteo de ventanas.** Para mantener 9 ventanas hacen falta ≥1386
días hábiles de entrenamiento; para saltar a 10 hacen falta ≥1512. Con 1426 días, al corte le
sobran **40 días hábiles** antes de caer a 8 y le faltan **86** para llegar a 10. Está cómodamente
en el medio, así que una diferencia de feriados o un par de sesiones faltantes en el dataset real
no cambia la decisión.

El corte de 2025-05-01 da los mismos 9 ventanas con menos holdout, así que es estrictamente peor.
Y está más cerca del borde de los 10.

**Es una frontera de calendario limpia.** El 1 de enero no se puede confundir con una fecha elegida
para que los números salgan bien.

### Lo que esta decisión NO significa

No significa que el entrenamiento termine en enero de 2025 y no vuelva a ver datos. Por
[`POLITICA_HOLDOUT.md`](POLITICA_HOLDOUT.md) §2.1, lo que se congela es el **procedimiento**, que
se reajusta hacia adelante dentro del holdout según su propio calendario. Lo que nunca ve es su
propio resultado.

### El corte es fecha fija, y eso tiene una consecuencia buena

Por §3 de la política, el corte se declara por **fecha calendaria**, no por proporción. Eso quiere
decir que **el holdout crece solo** con el paso del tiempo, sin volver a decidir nada: en 2027 el
mismo corte del 2025-01-01 dejará 33 meses del lado prohibido en vez de 21.

Y lo inverso también: el tramo de entrenamiento **no crece**. Está congelado en 1426 días hábiles
por definición. Las 9 ventanas son 9 para siempre.

---

## 4. Decisión 2 — El candidato aprueba si **llega a ser fondeado**

> **[reescrito el 2026-09-21]** La primera versión de esta sección preguntaba «¿sobrevivió o se
> quemó?». Estaba mal planteada, y se corrigió después de verificar el reglamento en fuente
> primaria. El detalle está más abajo, en §4.2.

### 4.1 El reglamento real, verificado en fuente primaria

Todo el criterio se apoya en el reglamento del plan exacto que se va a operar. Verificado el
**2026-09-21** en el centro de ayuda de la firma
([Rapid EOD 50k — A Comprehensive Look](https://help.myfundedfutures.com/en/articles/16158363-rapid-eod-50k-a-comprehensive-look)),
que confirma lo que ya estaba anotado en `mem:mffu-rapid-eod-50k-reglas-confirmadas` desde el
2026-09-11:

| Regla | Valor | Qué hace |
|---|---|---|
| Balance de evaluación | 50.000 USD | Punto de partida |
| Objetivo de ganancia | 3.000 USD | Condición de ascenso |
| Pérdida máxima | 2.000 USD, arrastrando al **cierre** de cada día | **La única condición que mata la cuenta** |
| Congelamiento del arrastre | Se bloquea en 52.100 USD | Deja de subir a partir de ahí |
| Días mínimos operados | 4 | Condición de ascenso |
| Consistencia | 30% del total acumulado en el mejor día | **No mata la cuenta**: obliga a seguir operando |
| Consistencia para cobrar | **Ninguna** | Desaparece al pasar a fondeado |

Las dos frases textuales que cambian el diseño del criterio:

> *«30% consistency rule **in the evaluation phase** of the Rapid EOD Plan»*
>
> *«Consistency Requirement: **None** (you do not need to meet a consistency rule to get paid).»*

### 4.2 Por qué «sobrevivir» era la pregunta equivocada

La versión anterior trataba el holdout como una prueba de resistencia: 21 meses operando contra un
límite de 2.000 USD, y la pregunta era si la cuenta aguantaba hasta el final.

Eso mide algo que **nadie le va a pedir nunca a esta estrategia**. El desafío real termina en
cuanto se llega al objetivo — normalmente en semanas, y el mínimo son 4 días. Pedirle 21 meses
continuos es una prueba mucho más dura *y distinta*, y la habrían reprobado candidatos perfectamente
buenos por una razón que no tiene nada que ver con su calidad.

Y hay un segundo error, más de fondo: **la regla de consistencia no puede matarte**. Excederla no
rompe nada, solo obliga a seguir operando hasta diluir el día grande. Un criterio binario de
supervivencia no tiene dónde poner esa regla: no es una forma de morir, es una forma de tardar más.

La pregunta correcta, la que además es la del dueño del proyecto, es:

> **En los 21 meses del holdout, ¿la estrategia consigue ser fondeada? ¿En cuánto tiempo, y a costa
> de cuántos intentos?**

Cada intento fallido se paga con dinero real. Eso no es un detalle estadístico: es el costo.

### 4.3 El procedimiento, declarado antes de mirar

Sobre el holdout, el procedimiento congelado produce operaciones en su **orden real**. Con esa
secuencia se corre el reglamento así:

1. El **primer intento arranca el primer día** del holdout, con 50.000 USD.
2. Se recorren los días **en su orden real**. Nunca se barajan (ver §4.6).
3. Si el arrastre al cierre toca los 2.000 USD → **intento quemado**. El siguiente intento arranca
   el día hábil siguiente, con el balance reiniciado.
4. Si se alcanzan los 3.000 USD **y** el mejor día pesa 30% o menos **y** ya van 4 días operados →
   **fondeado**. Se anota en qué día del holdout y con cuántos intentos.
5. Se sigue hasta que el holdout se termina.
6. Un intento que quede **sin resolver** cuando el holdout se acaba **se descarta**: no cuenta ni
   como fondeo ni como quiebre.

Las reglas 3 y 6 son convenciones elegidas por nosotros. Se declaran acá, **antes** de ver un solo
resultado, que es la única propiedad que importa.

### 4.4 El criterio de aprobación

**Dos condiciones, las dos sin números inventados por nosotros:**

| # | Condición | Por qué no es un parámetro libre |
|---|---|---|
| **1** | **Al menos un fondeo** dentro del holdout | El horizonte no lo elegimos: es el holdout, que quedó fijado en §3 por razones ajenas a esto |
| **2** | **Los fondeos son al menos tantos como los quiebres** | La mitad es el único punto distinguido de la escala que no depende de una preferencia: es donde un intento pasa a tener más chances de salir bien que mal |

La condición 1 sola sería casi imposible de reprobar: con 21 meses y reintentos, casi cualquier cosa
se fondea alguna vez. La condición 2 es la que discrimina de verdad, porque un límite de 2.000 USD
con arrastre castiga muy rápido a una estrategia cuyo borde se evaporó fuera de muestra.

Sobre por qué la mitad y no otra cosa: cualquier otro corte necesita saber **cuánto cuesta un
intento y cuánto paga una cuenta fondeada**, y el precio del Rapid EOD 50K **no está publicado**.
Un umbral que depende de un número que no tenemos sería un parámetro libre disfrazado.

### 4.5 Lo que se reporta pero **no** decide

Estos números no aprueban ni reprueban a nadie. Se publican porque son la información económica que
el dueño del proyecto necesita para decidir si vale la pena intentarlo:

- **Días hasta el primer fondeo**, y la mediana de todos los fondeos.
- **Intentos consumidos.** Multiplicado por el precio del desafío, es el costo real de entrada.
- **`p_pass`**, la probabilidad que calcula el simulador por remuestreo — con la salvedad de §4.7.

### 4.6 Lo que falta construir, y que no estaba en la versión anterior

La versión anterior de este documento afirmaba que *«ya está construido»*. **Eso era falso**, y se
corrige acá.

`validation/prop_sim.py:run_prop_sim` **no reproduce el camino real**: genera los días con un
*moving-block bootstrap* —los mete en una bolsa y los vuelve a sacar en otro orden, miles de veces—
y devuelve una probabilidad. Para un límite de pérdida **con arrastre**, el orden de los días es
justamente lo único que decide si se quiebra o no. Barajarlos destruye la señal que hay que medir.

Lo que **sí** existe y sirve tal cual:

| Pieza | Estado |
|---|---|
| Recorrido día a día del reglamento, con reinicio de intento al quebrar | Existe |
| Presupuesto de intentos y costo por intento (`max_attempts`, `n_attempts_used`) | Existe |
| Ancla del arrastre sobre balances de cierre | Existe en `prop_sim` |
| **Regla de consistencia que bloquea el ascenso sin descalificar** | **Existe, y modelada igual que el reglamento** |

Falta una sola cosa: **una entrada que consuma la secuencia real de días en orden**, en lugar de la
remuestreada. Es poco trabajo, pero hay que hacerlo **antes** de la primera corrida sobre el
holdout, y hay que hacerlo sin bootstrap.

Segundo detalle de implementación: el horizonte por defecto son 12 meses y el holdout son 21. El
horizonte tiene que ser **el holdout**, no el valor por defecto.

### 4.7 La salvedad sobre `p_pass`, que sigue en pie

El propio código declara que esa probabilidad está **sesgada al alza**:

> `prop_sim.py` evalúa siempre sobre el proxy cierre-a-cierre de ADR-J4 (nunca equity flotante
> intradía real), lo que **subestima** la probabilidad de breach y por lo tanto sesga `p_pass` al
> alza. […] **no es un margen de seguridad.**
>
> — `PropSimResult`, `validation/prop_sim.py`

En castellano: mira el resultado al cierre de cada día, no el vaivén del capital durante la rueda.
Como el límite se puede tocar en medio del día, hay quiebres que no ve. **Es optimista, y el código
avisa que no hay que tratarlo como conservador.**

Por eso `p_pass` se reporta y no vincula. Medir el tamaño del sesgo exige comparar el proxy contra
equity intradía, y eso necesita datos de CME: sería **después** de B.3, o sea que no puede influir
en este criterio de todos modos.

**Crédito:** la idea de anclar el criterio al reglamento de la firma en vez de a una métrica
estadística salió de la revisión externa de agy (Gemini, tier pro) del 2026-09-21.

---

## 5. Resumen ejecutable

| Qué | Valor |
|---|---|
| Instrumento | **MNQ** (Micro E-mini Nasdaq-100) — decidido el 2026-09-21, ver §6 |
| Primera sesión utilizable | 2019-05-05 |
| **Corte del holdout** | **2025-01-01** |
| Tamaño del holdout | 21 meses (~432 días hábiles al 2026-09-18, y creciendo) |
| Tramo de entrenamiento+validación | 2019-05-05 → 2024-12-31, ~1426 días hábiles |
| Ventanas walk-forward resultantes | 9 (mínimo duro: 4) |
| Velocidad mínima que impone G1 | ~0,265 operaciones/día = 1 cada 3,8 días |
| **Criterio de aprobación** | **Al menos un fondeo, y fondeos ≥ quiebres**, sobre el camino real |
| Réplica del reglamento | 50.000 USD · objetivo 3.000 · pérdida máxima 2.000 con arrastre al cierre · 4 días mínimos · consistencia 30% que no descalifica |
| Se reporta sin vincular | Días hasta el fondeo, intentos consumidos, `p_pass` |
| Implementación | `validation/prop_sim.py`, **más una entrada de camino real que falta escribir** (§4.6) |
| Qué se congela antes de mirar | El procedimiento, no los parámetros — `POLITICA_HOLDOUT.md` §2.1 |
| Cuántas miradas | Una, sin reintento — `POLITICA_HOLDOUT.md` §2 |

---

## 6. Qué queda abierto, y qué se cerró

### Cerrado el 2026-09-21

| Era | Quedó |
|---|---|
| Si la consistencia del 30% aplica a la evaluación o al retiro | **Solo a la evaluación**, y **no descalifica**. Verificado en fuente primaria (§4.1). Confirma lo anotado el 2026-09-11 |
| Si se usa la historia larga de **NQ** en vez de MNQ | **MNQ.** Con 2.000 USD de pérdida máxima, el contrato grande mueve 20 USD por punto: 100 puntos en la apertura liquidan la cuenta en una sola operación. El micro mueve 2. La granularidad pesa más que los años de historia, y la tabla de §2 ya está calculada sobre MNQ |

### Sigue abierto

| Pendiente | Cuándo se resuelve |
|---|---|
| **Escribir la entrada de camino real** en `prop_sim` (§4.6) | Antes de la primera corrida sobre el holdout. Es la única pieza de código que este criterio necesita |
| Confirmar contra el dataset real que el corte del 2025-01-01 sigue dando 9 ventanas | B.2, al construir las fichas de contrato. Hay 40 días hábiles de margen, así que es improbable que cambie |
| Recalibrar los costos a futuros CME | `backtest/costs_config.json` todavía tiene spread 1,5 · comisión 7 · deslizamiento 0,2, que son de la época de CFDs. Antes de cualquier corrida sobre MNQ |
| Precio del desafío Rapid EOD 50K | No publicado. No bloquea el criterio (§4.4), sí hace falta para leer el costo de los intentos |
| Magnitud del sesgo al alza de `p_pass` | No medible antes de B.3, y por diseño no influye en el criterio elegido |

---

## 7. Ventana de irreversibilidad

Igual que [`POLITICA_HOLDOUT.md`](POLITICA_HOLDOUT.md): **esto tiene que estar ratificado antes de
B.3**, la casilla que mira la primera barra real de CME.

Estado al **2026-09-21**: **cerrada del lado correcto.** La decisión quedó
ratificada sin que hubiera un solo dato de CME en el disco, que es la única forma en que vale.
