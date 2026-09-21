# Política del holdout

> **Estado: propuesta, pendiente de ratificación humana.**
> Cierra la casilla **C.1a** del [`ROADMAP_ARQUITECTO.md`](ROADMAP_ARQUITECTO.md) — las decisiones 2
> y 3 del [#81](https://github.com/ramaDben/genesis/issues/81). El **tamaño** del holdout no está
> aquí: es C.1b y depende del catálogo real del proveedor (B.1).
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
   el candidato ya congelado: genoma, parámetros, umbrales y perfil de firma fijados y hasheados
   **antes** de la corrida sobre el holdout.
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
| **Tamaño y fecha de corte del holdout** | C.1b, después de B.1 (catálogo real del proveedor) |
| **Valor del umbral del holdout** | C.1b, junto con el tamaño; debe quedar escrito antes de la primera corrida |
| **Si se usa la historia larga de NQ (desde 1996) para operar MNQ** | B.1 / C.1b |
| **Techo de presupuesto de ensayos (D4)** | C.2 / RFC [#57](https://github.com/ramaDben/genesis/issues/57) |
| **Cuánto descontar por el sesgo de supervivencia de la fuente (I7)** | Abierto, y probablemente no estimable honestamente. El holdout lo mide indirectamente; ese es todo el punto |

---

## 5. Ventana de irreversibilidad

Esta política **tiene que estar ratificada antes de B.3**, la casilla que mira la primera barra real
de CME. Después de eso no se puede declarar un holdout honesto sobre los datos que ya se miraron,
y ninguna cantidad de disciplina posterior lo repara.

Estado de la ventana al **2026-09-20**: **abierta**. No hay datos de CME en el disco.
