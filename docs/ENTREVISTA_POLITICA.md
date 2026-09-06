# Entrevista de política de decisión

**Estado: bloque A y pregunta B1 respondidos el 2026-09-05. B2–G pendientes.** Este documento es
el insumo de `POLITICA.md`, que todavía no existe.

**Reservado.** El trabajo de gobernanza queda en pausa deliberada hasta una fase más madura del
proyecto — ver el hito *Gobernanza y política de decisión* en GitHub. Las respuestas ya dadas
quedan escritas acá para que la entrevista se reanude donde quedó y no desde cero.

## Para qué es esto

El ciclo SDD tiene una compuerta humana obligatoria (`approve_design`). En la práctica se aprobó
sin leer, porque las decisiones llegan en un vocabulario técnico que no es el del dueño del
proyecto. Una compuerta que se aprueba sin leer no es una compuerta.

La salida es **separar la política de la adjudicación**: los límites se fijan una vez, por
adelantado, en términos que el humano sí domina —dinero, tiempo, riesgo, alcance—; después un
adjudicador externo aplica esa política caso por caso, y solo lo que no encaja escala.

Tres reglas de diseño que no se negocian:

1. **El adjudicador no puede ser el mismo agente que propone el cambio.** Si el que quiere que se
   apruebe también decide si la política lo autoriza, no hay control. Va a un modelo de otro
   proveedor.
2. **Sesgo hacia escalar.** Ante duda razonable sobre si algo está cubierto, **no está cubierto**.
   Cada escalamiento es evidencia de un hueco en la política, no un fastidio.
3. **Cambiar la política nunca se pre-autoriza.** Aflojar un gate, ampliar el alcance o subir un
   límite vuelve siempre al humano, sin excepción y sin importar cuán bueno sea el argumento.

## Cómo responder

Con frases, no con precisión. «No sé» es una respuesta válida y útil: marca dónde la política va a
tener un hueco conocido en vez de uno invisible.

**Sobre las cifras de dinero (bloque B):** este repositorio es privado pero está en git. Las
magnitudes absolutas conviene dejarlas fuera —el mismo criterio que ya se aplica a las
credenciales—. Respondé en términos relativos (porcentajes, proporciones, «tanto como X») o decí
«va aparte» y el `POLITICA.md` lo tratará como un parámetro externo, igual que hace el proyecto con
la ficha de firma.

---

## A. El propósito

**A1.** ¿Para qué es genesis? En una o dos frases, sin vocabulario técnico. Si dentro de dos años
funcionara perfectamente, ¿qué estarías haciendo con él?

*Gobierna:* qué cambios son «alcance» y cuáles son deriva.

> **Respuesta (2026-09-05).** El alcance se movió tres veces en veinte minutos durante la
> entrevista, así que quedó escrito separando lo fijo de lo móvil:
>
> - **Propósito (fijo):** producir y validar modelos de trading con evidencia suficiente para
>   sustentar decisiones de terceros.
> - **Destino (declarado):** evaluador agnóstico al mandato y al universo — CFDs, futuros, cripto.
> - **Fase actual:** prop firms, intradía, CFDs e índices. Lo demás es destino, no requisito.
>
> **Y el marco real, que apareció recién acá:** el objetivo declarado es entrar al **RPSF de la
> CMF** y ofrecer asesoría de inversión basada en un modelo probado; si sale algo robusto, buscar
> inversionistas y no solo prop firms. Genesis deja de ser un proyecto de trading y pasa a ser
> **la base de evidencia de un negocio regulado**. Los gates dejan de ser gestión de riesgo
> personal y pasan a sustentar afirmaciones hechas a clientes y a un regulador; la procedencia deja
> de ser elegancia de ingeniería y pasa a ser rastro de auditoría.

**A2.** ¿Qué NO es este proyecto? Nombrá al menos una cosa que alguien podría proponer con buen
argumento y que igual querés rechazar.

*Gobierna:* el criterio para rechazar propuestas bien argumentadas — el caso más difícil.

> **Respuesta (2026-09-05).** «No es una máquina de hacer perder dinero, no crea estrategias por
> suerte ni estrategias que hagan perder dinero. No es una casa de apuestas.»
>
> Cláusula concreta que acepta rechazar aunque venga bien argumentada: **desplegar capital real sin
> haber pasado los gates.** Traducción operativa para `POLITICA.md`:
>
> 1. No se despliega nada que no haya pasado los gates.
> 2. No se afloja un gate para que un candidato pase.
> 3. El conteo de ensayos no se relaja — es la versión mecánica de «no por suerte», y coincide
>    con la decisión D1 ya ratificada.
> 4. No se afirma más de lo que el artefacto sustenta.
>
> **Derivación que restringe algo grande:** el arquitecto (búsqueda automatizada de candidatos) es
> literalmente una máquina de probar muchas cosas; lo único que lo separa de una casa de apuestas
> es la contabilidad honesta de ensayos. Con A2 escrita, **el arquitecto queda condicionado a que
> el ledger de ensayos funcione.**

**A3.** ¿Qué te haría abandonarlo? Un resultado, una fecha, una cifra, un cansancio.

*Gobierna:* cuándo el adjudicador debe avisarte que estás cerca de esa condición, en vez de seguir.

> **Respuesta (2026-09-05).** Tres meses, con la pregunta reformulada y aceptada: a los tres meses
> el control **no** es «¿encontramos edge?» sino **«¿aprendimos si acá hay edge que encontrar?»**.
>
> Razón: la IA acelera implementar y probar, pero no acelera cuántos datos existen ni si hay edge
> en ellos — y **sí acelera el agotamiento del presupuesto estadístico**. Cincuenta candidatos en
> una semana llevan el denominador del DSR a cincuenta en una semana.
>
> Regla que sale de ahí: **ambición en construir es gratis; ambición en buscar es cara y no
> reembolsable.**

---

## B. Dinero

**B1.** ¿Hay capital comprometido hoy, o esto es todavía un proyecto de conocimiento?

*Gobierna:* si las decisiones de despliegue son hipotéticas o reales.

> **Respuesta (2026-09-05).** No hay capital comprometido. Lo invertido es tiempo y muchas sesiones
> de trabajo. Y el objetivo declarado va más allá de la pregunta: **verificar si lo estudiado
> mirando velas japonesas, estructura de precio y ahora regímenes se puede validar o invalidar.**
>
> Eso reencuadra el proyecto por tercera vez, y conviene que quede escrito: **el primer trabajo de
> genesis no es buscar edge genéricamente, es arbitrar las hipótesis discrecionales ya acumuladas
> por el operador.** Tres consecuencias:
>
> 1. **Es el caso más barato que existe.** Bajo D1, una hipótesis formada antes de tocar los datos
>    y especificada por adelantado es **un ensayo con cero grados de libertad** — la misma categoría
>    que una regla canónica con parámetros publicados. El objetivo real resulta ser lo
>    estadísticamente más barato, no lo más caro.
> 2. **Corrige el hito de tres meses.** El RFC recomienda arrancar por lo canónico; para este
>    operador eso es menos informativo. Que Bollinger muera con costos reales no dice nada sobre si
>    su lectura de estructura es válida. La ruta correcta es probar **sus** hipótesis, que cuestan
>    lo mismo en ensayos y responden la pregunta que de verdad tiene.
> 3. **La trampa, y es seria.** Las hipótesis se formaron mirando estos mismos gráficos. Testearlas
>    sobre el mismo período no es fuera de muestra: es testear sobre los datos que las generaron.
>    Es la versión humana del problema de anticipación que la capa 3 previene por construcción.
>    **Esto refuerza la posición sobre D3** por una razón que la discusión no tenía: no existe
>    ningún holdout recortable de esta serie que sea virgen respecto de la hipótesis, porque la
>    serie completa ya fue mirada por una persona durante años. El holdout que vale es futuro.
>
> Acción que se deriva y **no cuesta nada**: pre-registrar las hipótesis por escrito —condición,
> instrumento, entrada, salida, qué se espera— **antes** de correr nada. Escritas después de la
> primera corrida ya no son un ensayo limpio, son una racionalización, y eso no se puede demostrar
> lo contrario ni ante un cliente ni ante la CMF. La regla ya existe: RFC §9, regla 2.
>
> **Sobre los regímenes, un aviso concreto:** cada definición de régimen que se pruebe y descarte
> es un ensayo bajo D1. Tres formas de definir régimen son tres ensayos, no uno.
>
> **Y una corrección a A3:** «no es opción retroceder sin antes probar las estrategias» es querer
> una respuesta antes de irse, que es legítimo — pero el tiempo invertido no es evidencia de que
> algo funcione. Se escribe así: **la condición de salida es epistémica, no temporal.** Se para
> cuando hay respuesta, no cuando se acaba la paciencia. Los tres meses son la expectativa, no el
> criterio.

**B2.** Si mañana un candidato diera GO, ¿cuánto capital entraría? ¿Es plata que podés perder
entera sin que cambie tu vida, o no?

*Gobierna:* cuánto rigor es proporcionado. La respuesta cambia D3 y varias más.

> **Pendiente — y es la pregunta que sostiene el bloque.** Con el RPSF sobre la mesa hay ahora tres
> tipos de plata posibles: la propia, la de la prop firm y la de un inversionista o cliente de
> asesoría. Si el estándar es más exigente cuando la plata es ajena, **el rigor pasa a ser un
> parámetro del mandato** y no una constante del pipeline — un cambio de arquitectura, no de
> política. Conviene fijarla ahora, mientras no hay presión.

**B3.** ¿Cuál es la pérdida máxima que tolerás antes de detener todo? No la que esperás — la que
te haría parar.

*Gobierna:* el mandato de riesgo, y eventualmente un parámetro real del simulador.

**B4.** ¿Cuánto estás dispuesto a gastar por mes en infraestructura —APIs, datos, suscripciones—
para que esto funcione mejor?

*Gobierna:* si la revisión adversarial corre en cada decisión o solo en las grandes.

---

## C. Tiempo

**C1.** ¿Hay una fecha? Si la hay, ¿qué pasa si no se llega?

*Gobierna:* si el adjudicador puede aprobar atajos bajo presión de tiempo, o nunca.

**C2.** ¿Qué te cuesta que esto tarde seis meses más de lo previsto? ¿Dinero, oportunidad,
paciencia, nada?

*Gobierna:* el precio real de las decisiones conservadoras, que hasta ahora vengo asumiendo barato.

---

## D. Rigor contra velocidad

*Este bloque es el que más decisiones futuras resuelve de una sola vez.*

**D1.** Dos errores posibles: descartar una estrategia que sí funcionaba, o desplegar una que no
funcionaba. ¿Cuál te duele más, y por cuánto?

*Gobierna:* la orientación de todos los umbrales, y qué hacer cuando un candidato queda al borde.

**D2.** Si un candidato falla un gate por poco —digamos, profit factor 1.28 contra un umbral de
1.30— ¿qué querés que pase?

*Gobierna:* el caso concreto donde más presión hay para aflojar. Sospecho que tu respuesta es «se
rechaza», pero tiene que estar escrito antes de que pase, no después.

**D3.** ¿Preferís un resultado más débil que entendés, o uno más fuerte que no?

*Gobierna:* cuánta complejidad puede acumular el sistema antes de que deje de ser auditable por vos.

**D4.** Ya viste que traer un modelo externo encontró dos errores míos que estaban integrados.
¿Querés eso en cada decisión de diseño, solo en las grandes, o solo cuando lo pidas?

*Gobierna:* la frecuencia de la revisión adversarial, y su costo.

---

## E. Lo irreversible

**E1.** Nombrá las acciones que querés ver **siempre**, sin importar quién las proponga ni con qué
argumento.

*Sugerencias para reaccionar, no para copiar:* mover dinero real; abrir una cuenta; publicar algo
con tu nombre; mandar algo a un tercero; borrar datos; firmar términos.

*Gobierna:* la lista dura del adjudicador — lo que nunca puede aprobar solo.

**E2.** ¿Hay algo que preferís que se haga sin consultarte aunque sea irreversible, porque
consultarte lo arruinaría?

*Gobierna:* que la lista de arriba no crezca hasta volver a hacer de la compuerta un trámite.

**E3.** Si yo estuviera por hacer algo que no está en ninguna lista y no sé si te molestaría,
¿preferís que pregunte o que decida y te avise?

*Gobierna:* el default en territorio no mapeado. Es la pregunta que más veces se va a aplicar.

---

## F. Lo no negociable

**F1.** ¿Qué invariantes del proyecto no querés que se transen, ni siquiera con un buen argumento?

*Candidatos que veo, para que confirmes o descartes:* los gates no se relajan; el determinismo se
mantiene; nada se ejecuta en vivo desde genesis; los artefactos siempre llevan procedencia.

*Gobierna:* qué propuestas se rechazan sin evaluar el argumento.

**F2.** Si dentro de un año la evidencia dice que uno de esos invariantes está de más, ¿querés
poder cambiarlo, o querés que sea permanente aunque te arrepientas?

*Gobierna:* si la política tiene cláusulas revisables y cláusulas fijas. Las dos opciones son
defendibles.

---

## G. Escalamiento y revisión

**G1.** Cuando algo escale a vos, ¿qué necesitás para decidir bien? ¿Dos posiciones enfrentadas?
¿Una recomendación con su costo? ¿Un número?

*Gobierna:* el formato de todo lo que te llegue de acá en adelante.

**G2.** ¿Cuántas decisiones por semana estás dispuesto a atender antes de que se vuelva trámite
otra vez? Sé honesto — el número real, no el que suena responsable.

*Gobierna:* cuán angosta tiene que ser la compuerta para seguir siendo real.

**G3.** ¿Cada cuánto querés revisar esta política? ¿Y qué debería obligar a revisarla antes de
tiempo?

*Gobierna:* que el documento no envejezca en silencio, que es como mueren estas cosas.

---

## Después de responder

1. Se redacta `POLITICA.md`, versionado y con hash, para que cada decisión pueda citar qué cláusula
   la autorizó.
2. El borrador va a un modelo externo con una única consigna: **«¿qué NO cubre esta política?»**.
   La va a redactar el mismo agente cuyos puntos ciegos busca cubrir; que la ataque alguien que no
   los comparte.
3. Recién entonces se construyen las piezas que la aplican: la consulta adversarial, el ledger de
   decisiones y el chequeo mecánico que falla si no hay revisión registrada.

Ver la memoria `politica-de-decision-y-compuerta-humana`.

---

## Estado al reservar — 2026-09-05

Lo respondido: **A1, A2, A3, B1**. Lo pendiente: **B2, B3, B4** y los bloques **C a G**.

El trabajo queda en pausa por decisión explícita, no por bloqueo. Lo que reanuda la entrevista es
cualquiera de estas tres cosas:

1. **Aparece capital real**, propio o ajeno — B2 y B3 dejan de ser hipotéticas.
2. **Un candidato se acerca a un GO** — ahí la compuerta humana tiene por primera vez algo que
   proteger, y aprobar sin leer pasa a tener consecuencia.
3. **Se decide construir el arquitecto** — A2 lo dejó condicionado al ledger de ensayos, y esa
   condición es una cláusula de política que todavía no está escrita.

Mientras tanto rige la regla vieja: **solo un humano llama `approve_design`**, con la debilidad ya
diagnosticada de que en la práctica se aprobaba sin leer. Reservar esto significa aceptar esa
debilidad a sabiendas mientras no haya capital ni candidatos en juego.
