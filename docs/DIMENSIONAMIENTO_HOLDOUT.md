# Dimensionamiento del holdout

> **Estado: propuesta, pendiente de ratificación humana.**
> Cierra la casilla **C.1b** del [`ROADMAP_ARQUITECTO.md`](ROADMAP_ARQUITECTO.md) — la decisión de
> tamaño del [#81](https://github.com/ramaDben/genesis/issues/81), más el umbral de aprobación que
> [`POLITICA_HOLDOUT.md`](POLITICA_HOLDOUT.md) dejó abierto.
>
> Escrito el **2026-09-21**, antes de que exista una sola barra de futuros CME en el disco. Esa
> fecha es parte del contenido: dimensionar un holdout después de mirar los datos no vale nada.
>
> **No se puede ratificar por separado de `POLITICA_HOLDOUT.md`.** Las dos son la misma decisión
> partida en dos documentos, y las dos vencen en B.3.

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

## 4. Decisión 2 — El candidato aprueba si **sobrevive el reglamento de MFFU**

### La propuesta

Se toman las operaciones que el procedimiento congelado generó sobre el holdout y se las hace
pasar por una réplica del desafío real de MyFundedFutures: cuenta de **50.000 USD**, límite de
pérdida de **2.000 USD que arrastra al cierre de cada día**, y la **regla de consistencia del 30%**.

Se pregunta una sola cosa: **¿la cuenta sobrevivió, o se quemó?**

### Por qué este criterio y no una métrica

Porque **ningún umbral lo inventamos nosotros**. Los tres números —50.000, 2.000, 30%— salen del
reglamento de la prop firm. No hay nada que elegir, y por lo tanto no hay nada que ajustar después
de ver el resultado. Es la propiedad que la decisión 3 de la política exige y que casi ningún
criterio estadístico tiene: un Sharpe mínimo, un profit factor mínimo o un drawdown máximo son
todos números que alguien tiene que elegir, y elegirlos después de ver el resultado es trampa.

Y porque **responde literalmente la pregunta del proyecto**. El objetivo no es «tener buen Sharpe»:
es pasar una prueba de fondeo concreta con reglas concretas. Cualquier métrica intermedia es un
sustituto de eso; esto es eso.

Los gates normales no sirven tal cual para el holdout: **G1 exige 300 operaciones y el holdout solo
no las alcanza** (114 en el caso peor). Reciclarlos obligaría a bajarles el umbral, que es
exactamente elegir un parámetro libre.

**Crédito:** la propuesta salió de la revisión externa de agy (Gemini, tier pro) del 2026-09-21.

### Ya está construido

`validation/prop_sim.py:run_prop_sim` hace exactamente esto: toma los ledgers de operaciones fuera
de muestra, la ficha de la firma y el contrato de casa, y simula caminos del desafío. No hay que
escribir el simulador, hay que conectarlo al holdout.

### La salvedad que hay que resolver antes de ratificar

`run_prop_sim` devuelve una **probabilidad** de aprobar (`p_pass`) sobre muchos caminos simulados.
Y el propio código declara que esa probabilidad está **sesgada al alza**:

> `prop_sim.py` evalúa siempre sobre el proxy cierre-a-cierre de ADR-J4 (nunca equity flotante
> intradía real), lo que **subestima** la probabilidad de breach y por lo tanto sesga `p_pass` al
> alza. […] **no es un margen de seguridad.**
>
> — `PropSimResult`, `validation/prop_sim.py`

En castellano: el simulador mira el resultado al cierre de cada día, no el vaivén del capital
durante el día. Como el límite de pérdida se puede tocar en medio de la rueda, hay quiebres que el
simulador no ve. **Es optimista, y el código dice que no hay que tratarlo como conservador.**

Eso deja dos formas de usarlo, y hay que elegir una antes de la primera corrida:

| Forma | Qué se exige | A favor | En contra |
|---|---|---|---|
| **(a) Camino realizado** | La secuencia real de operaciones del holdout, en su orden real, sobrevive el reglamento | Cero parámetros libres. Es el camino que efectivamente habría ocurrido | Un solo camino: mucha varianza. Un candidato bueno puede morir por el orden de las operaciones |
| **(b) Probabilidad con margen** | `p_pass` ≥ un umbral alto, declarado hoy | Usa toda la distribución, menos ruidoso | El umbral es un parámetro libre, y además hay que inflarlo para compensar el sesgo — sin saber cuánto vale el sesgo |

**Recomendación: (a), el camino realizado, con (b) como dato reportado pero no vinculante.**

La razón es la asimetría que ya está escrita en §1 de la política: el proyecto prefiere rechazar un
candidato bueno antes que aprobar uno malo. La opción (a) es más ruidosa y por lo tanto rechaza más
candidatos buenos por mala suerte — eso es el error barato. La opción (b) exige elegir un número
para compensar un sesgo cuya magnitud no conocemos, y equivocarse por optimismo es el error caro.

Además (a) no tiene manija: no hay ninguna casilla que alguien pueda mover al ver el resultado.

**Dependencia:** medir el tamaño real del sesgo requiere comparar el proxy cierre-a-cierre contra
equity intradía, y eso necesita datos de CME que todavía no existen. Si esa medición se hace algún
día, será **después** de B.3 y por lo tanto no puede influir en este umbral. Otra razón para elegir
el criterio sin parámetros.

---

## 5. Resumen ejecutable

| Qué | Valor |
|---|---|
| Instrumento | MNQ (Micro E-mini Nasdaq-100) |
| Primera sesión utilizable | 2019-05-05 |
| **Corte del holdout** | **2025-01-01** |
| Tamaño del holdout | 21 meses (~432 días hábiles al 2026-09-18, y creciendo) |
| Tramo de entrenamiento+validación | 2019-05-05 → 2024-12-31, ~1426 días hábiles |
| Ventanas walk-forward resultantes | 9 (mínimo duro: 4) |
| Velocidad mínima que impone G1 | ~0,265 operaciones/día = 1 cada 3,8 días |
| Criterio de aprobación | Supervivencia del reglamento MFFU sobre el camino realizado |
| Réplica del reglamento | 50.000 USD · 2.000 USD de pérdida máxima con arrastre al cierre · consistencia 30% |
| Implementación | `validation/prop_sim.py:run_prop_sim`, ya existente |
| Qué se congela antes de mirar | El procedimiento, no los parámetros — `POLITICA_HOLDOUT.md` §2.1 |
| Cuántas miradas | Una, sin reintento — `POLITICA_HOLDOUT.md` §2 |

---

## 6. Qué queda abierto

| Pendiente | Cuándo se resuelve |
|---|---|
| Confirmar contra el dataset real que el corte del 2025-01-01 sigue dando 9 ventanas | B.2, al construir las fichas de contrato. Hay 40 días hábiles de margen, así que es improbable que cambie |
| Si se usa la historia larga de **NQ** (desde 2008 en FirstRate) en vez de MNQ | Sigue abierto. Cambiaría toda esta tabla y **tendría que decidirse antes de B.3**, no después |
| Confirmar con MFFU si la regla de consistencia del 30% aplica a la evaluación o sólo al retiro | Pregunta pendiente al soporte de la firma. Afecta a la réplica del reglamento |
| Magnitud del sesgo al alza de `p_pass` | No medible antes de B.3, y por diseño no influye en el criterio elegido |

---

## 7. Ventana de irreversibilidad

Igual que [`POLITICA_HOLDOUT.md`](POLITICA_HOLDOUT.md): **esto tiene que estar ratificado antes de
B.3**, la casilla que mira la primera barra real de CME.

Estado al **2026-09-21**: **abierta**. No hay datos de CME en el disco.
