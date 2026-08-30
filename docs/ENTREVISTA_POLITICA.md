# Entrevista de política de decisión

**Estado: pendiente de responder.** Este documento es el insumo de `POLITICA.md`, que todavía
no existe.

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

**A2.** ¿Qué NO es este proyecto? Nombrá al menos una cosa que alguien podría proponer con buen
argumento y que igual querés rechazar.

*Gobierna:* el criterio para rechazar propuestas bien argumentadas — el caso más difícil.

**A3.** ¿Qué te haría abandonarlo? Un resultado, una fecha, una cifra, un cansancio.

*Gobierna:* cuándo el adjudicador debe avisarte que estás cerca de esa condición, en vez de seguir.

---

## B. Dinero

**B1.** ¿Hay capital comprometido hoy, o esto es todavía un proyecto de conocimiento?

*Gobierna:* si las decisiones de despliegue son hipotéticas o reales.

**B2.** Si mañana un candidato diera GO, ¿cuánto capital entraría? ¿Es plata que podés perder
entera sin que cambie tu vida, o no?

*Gobierna:* cuánto rigor es proporcionado. La respuesta cambia D3 y varias más.

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
