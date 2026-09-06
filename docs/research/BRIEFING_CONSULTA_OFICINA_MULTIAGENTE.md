> **Briefing de consulta externa — 2026-09-05.** Documento *enviado* a una herramienta de
> investigación (Perplexity) sobre cómo montar revisión adversarial multi-proveedor para un operador
> individual. Se versiona por la misma razón que el otro briefing: la redacción es lo reutilizable.
>
> **La respuesta recibida no se versiona.** Tenía una cita rota en su afirmación más determinante y
> cerca de la mitad de sus fuentes eran blogs de proveedores; el rango de «41–86.7 % de fracaso» que
> reportaba no es un estadístico usable. Lo que sí sobrevivió está en el issue de adjudicador
> externo y en la memoria `reserva-de-gobernanza-2026-09`.

---

# Investigación: una «oficina» multi-agente para un operador individual

Necesito dos cosas de vos, **claramente separadas**: primero lo que se puede sostener con
fuentes verificables y fechadas; después tu conjetura sobre cómo armarlo. No las mezcles
— si algo es especulación tuya, decilo.

Priorizá material de los últimos seis meses. Marcá como posiblemente obsoleto todo lo
anterior a 2026: este terreno se mueve rápido y una respuesta desactualizada es peor que
ninguna.

---

## 1. El problema que quiero resolver

No es rendimiento. Es **independencia de criterio**.

Trabajo con un agente de IA que hace el trabajo técnico de un proyecto de software
complejo. Funciona bien. Pero el mismo agente diseña los criterios de calidad y después
juzga si se cumplen. Es el equivalente a que el analista escriba la tesis y también sea
el comité que la aprueba.

**No es hipotético, ya pasó.** El proyecto tiene un ciclo formal con una compuerta de
aprobación humana obligatoria para cambios de contrato. Dos pull requests modificaron el
núcleo sin pasar por ese ciclo, y uno de ellos resolvió de paso una decisión que el propio
documento de diseño marcaba como «decisión humana». No hubo mala fe: una autorización
conversacional para hacer el trabajo se deslizó a autorización para tomar la decisión.

Hace poco le pedí a un modelo de otro proveedor que revisara una decisión de diseño. Sin
contexto del proyecto, a ciegas, con un documento que exponía deliberadamente mi encuadre
al ataque. **Encontró dos errores que ya estaban integrados**, incluida una afirmación
cuantitativa incorrecta sobre una métrica estadística. Ninguno de los dos habría aparecido
por revisión interna, porque los dos venían de la misma forma de mirar el problema.

Ese experimento me convenció de que hay algo acá. La pregunta es cómo convertirlo en
infraestructura en vez de en copiar y pegar entre pestañas.

## 2. Mi situación

- **Operador individual**, no empresa. No hay equipo de plataforma.
- Windows 11 + WSL2. El repositorio vive en el sistema de archivos de Linux.
- Ya uso un agente de codificación de terminal con servidores MCP (Model Context Protocol)
  para herramientas externas: documentación, GitHub, automatización de navegador, datos de
  mercado.
- **No quiero administrar infraestructura.** Nada que requiera levantar servicios,
  mantener contenedores en producción o depurar una cola de mensajes a las tres de la
  mañana. Si se rompe y no lo puedo arreglar en una tarde, es un pasivo.
- Presupuesto de un individuo, no de una empresa. Necesito números reales, no «depende del
  uso».

## 3. Las tres restricciones del proyecto que condicionan la respuesta

Esto no es un proyecto genérico y creo que estas tres cosas descartan soluciones que de
otro modo parecerían buenas.

**Determinismo total.** El sistema produce artefactos que deben ser reproducibles bit a
bit: misma entrada, misma salida, siempre. Un proceso de agentes es inherentemente no
determinista. ¿Existe un patrón establecido para que un proceso no determinista produzca
artefactos deterministas, o son mundos que hay que mantener separados por diseño?

**Procedencia obligatoria.** Cada artefacto lleva la versión de configuración, el hash del
dataset, los hashes de los perfiles, las semillas y el commit. Si varios agentes toman
decisiones, necesito el equivalente para las **decisiones**: qué modelo, qué versión, qué
prompt, produjo qué recomendación, y qué se hizo con ella. ¿Alguien resolvió esto? ¿Hay
formato, convención o herramienta, o cada uno improvisa un log?

**Compuerta humana obligatoria.** Ciertas decisiones solo las puede tomar una persona, por
diseño. El riesgo evidente al agregar agentes es que la compuerta se vuelva un cuello de
botella y termine sorteada en la práctica —que es exactamente lo que ya me pasó con un
solo agente. ¿Hay patrones reportados para que una compuerta humana sobreviva a un
proceso con muchos agentes sin volverse un sello de goma?

## 4. Qué investigar — con fuentes

### 4.1 Los dos casos de uso son distintos y quiero saber cuál está resuelto

**(a) División del trabajo** — un modelo diseña, otro escribe código, otro prueba.
Requiere **contexto compartido**: el que escribe código necesita saber las convenciones,
los invariantes, las decisiones previas.

**(b) Revisión adversarial** — un modelo externo audita el trabajo de otro. Requiere
exactamente lo contrario: que **no** haya contexto compartido, porque un revisor que
heredó los supuestos del autor deja de ser independiente.

Mi hipótesis es que (a) está peor resuelto de lo que se anuncia y (b) es artesanal pero
funciona. ¿La evidencia la sostiene o la contradice?

### 4.2 El problema técnico duro: estado entre proveedores

Compartir contexto y estado entre agentes de proveedores distintos. ¿Cómo se resuelve en
la práctica? ¿Hay algún estándar emergente —MCP u otro— que efectivamente se use para
esto, o cada integración reimplementa el pasamanos?

### 4.3 Qué se rompe

Esto es lo que más me sirve y lo único que una búsqueda puede darme. Buscá post-mortems,
hilos de issues, gente contando **por qué abandonaron** un setup multi-modelo. Los modos
de falla reportados valen más que cualquier lista de capacidades.

Hay un patrón que vi mencionado y quiero saber si es real o folklore: **los equipos que
empiezan multi-modelo terminan usando uno solo porque el costo de coordinación se come la
ganancia.** ¿Hay evidencia?

### 4.4 Costo operativo real

Claves de API y su gestión. Límites de tasa cuando varios agentes corren en paralelo.
Observabilidad. Depuración cuando un agente de otro proveedor falla en medio de una
cadena. Y el número: **¿cuánto cuesta por mes esto para un operador individual con uso
serio pero no industrial?**

### 4.5 Madurez, sin marketing

Para cada herramienta que menciones, distinguí explícitamente lo que la documentación
promete de lo que la gente reporta que funciona. Con fecha y fuente. Si algo es una
característica anunciada sin uso reportado, decilo.

## 5. Qué conjeturar — separado de lo anterior

Después de lo documentado, y **marcado claramente como conjetura tuya**:

**Proponé una arquitectura concreta** para mi situación. No un panorama de opciones: una
recomendación, con lo que se gana y lo que se pierde.

Y respondé estas tres:

1. **¿Cuál es la versión mínima que entrega el 80 % del valor?** Sospecho que es mucho más
   chica de lo que sugiere el término «oficina multi-agente» — quizás un script que llama
   a dos APIs. Si estoy en lo cierto, decilo aunque haga aburrida la respuesta. Si estoy
   equivocado, mostrame qué me estoy perdiendo.

2. **¿Cuál es el orden correcto de construcción?** Qué primero, qué después, y qué no
   construir hasta que algo específico lo justifique.

3. **¿Cuál es el modo de falla de tu propia propuesta?** Si sigo tu consejo, ¿en qué
   problema termino en seis meses?

## 6. Lo que NO estoy preguntando

- Qué modelo es mejor. No es una comparativa.
- Cómo hacer prompting. Eso está resuelto.
- Frameworks de agentes en general. Solo me interesa el caso **multi-proveedor**; si la
  respuesta funciona igual con un solo modelo, no responde mi pregunta.
- Soluciones empresariales con equipo de plataforma detrás.

## 7. Qué respuesta me sirve y cuál es ruido

**Sirve:** modos de falla reportados con fuente. Costos concretos. Una distinción honesta
entre los dos casos de uso del punto 4.1. Evidencia de que alguien resolvió el problema de
procedencia de decisiones. Una recomendación con la que te comprometas.

**Es ruido:** una tabla comparativa de frameworks con sus características. Eso es material
de marketing reciclado y ya lo puedo leer solo. «Depende de tus necesidades» sin decir de
qué depende y cómo se mide. Y cualquier arquitectura propuesta que ignore las tres
restricciones del punto 3.

Si en algún punto no hay base para responder, decilo en vez de completar.
