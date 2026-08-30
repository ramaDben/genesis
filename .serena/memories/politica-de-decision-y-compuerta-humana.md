*(2026-08-29 — diagnóstico del usuario + diseño acordado; la entrevista está SIN RESPONDER)*

# La compuerta humana nunca funcionó, y qué se acordó hacer

## El hecho que lo origina

**El usuario declaró que aprobó todos los `approve_design` sin leer nada**, porque las decisiones
llegan en un vocabulario técnico que no domina. No es negligencia: es un defecto de diseño del
flujo.

Consecuencia para interpretar el historial: el incidente de los PR #68/#69 —que modificaron `src/`
fuera del ciclo y resolvieron de paso la decisión D2, marcada `[DECISIÓN HUMANA]`— **no fue una
anomalía, fue la norma volviéndose visible**. No hay una compuerta que restaurar; hay que
construirla por primera vez.

El usuario también nombró el problema de fondo con precisión: que el mismo agente diseñe los
criterios y juzgue si se cumplen es **una forma de look-ahead bias**.

## El diseño acordado: separar política de adjudicación

Los límites se fijan **una vez, por adelantado**, en términos que el humano sí domina —dinero,
tiempo, riesgo, alcance, irreversibilidad—. Después un adjudicador aplica esa política caso por
caso, y solo lo que no encaja escala.

Tres reglas que no se negocian:

1. **El adjudicador no puede ser el agente que propone el cambio.** Si el que quiere que se apruebe
   también decide si la política lo autoriza, el control se recrea un nivel más arriba y desaparece.
   Va a un modelo de **otro proveedor** — el usuario tiene acceso a la API de **Gemini**.
2. **Sesgo hacia escalar.** Ante duda razonable, no está cubierto. Cada escalamiento es evidencia de
   un hueco. El modo de falla que esto previene es el deslizamiento de autorizaciones: el
   adjudicador declara «cubierto» un caso nuevo y la política se expande sin que nadie la cambie.
3. **Cambiar la política nunca se pre-autoriza.** Aflojar un gate o subir un límite vuelve siempre
   al humano.

**Lo que la política NO puede cubrir**, por construcción: la decisión que nadie anticipó. D1 es el
ejemplo — «qué cuenta como un ensayo» no era pre-especificable porque la pregunta no existía todavía.

## Por qué una instrucción en una skill no alcanza

Una regla escrita en una skill es una instrucción **para el agente**, y el agente puede desviarse —
ya lo hizo. El control real tiene que ser algo mecánico que no se pueda argumentar: un artefacto que
debe existir, verificado por un script que **falla**. Sin eso es una intención, no un control.

## Estado y orden

1. **La entrevista está redactada y sin responder**: `docs/ENTREVISTA_POLITICA.md`, 20 preguntas en
   siete bloques (propósito, dinero, tiempo, rigor contra velocidad, lo irreversible, lo no
   negociable, escalamiento). El usuario la responde en otra sesión.
2. Con las respuestas se redacta `POLITICA.md`, versionado y con hash, para que cada decisión pueda
   citar qué cláusula la autorizó.
3. El borrador va a Gemini con una sola consigna: **«¿qué NO cubre esta política?»** — lo redacta el
   agente cuyos puntos ciegos busca cubrir.
4. Recién después se construyen las piezas: `scripts/consulta_adversarial.py` (API de Gemini, con
   procedencia: modelo, versión, prompt, commit), el ledger de decisiones (generalizando el patrón
   ya probado de `trial_ledger.py`), y `scripts/gate_check.py` que falla si no hay revisión
   registrada para el change en curso.

**No se toca el motor de pulse.** `approve_design` es código upstream dentro de la imagen Docker, y
forkearlo es un pasivo permanente para un operador solo. La revisión adversarial se agrega como
**precondición delante** de la compuerta, nunca como sustituto: que un agente pueda satisfacer
`approve_design` destruiría lo único que ese gate tiene.

## Precaución que ordena cómo consumir al adjudicador

ICML 2025 (Kim, Garg, Peng y Garg): **cuando dos modelos se equivocan, convergen en la misma
respuesta incorrecta el 60 % de las veces.** Un segundo modelo **no es un validador** — es una
fuente de desacuerdo. Se mira dónde disiente; «el otro modelo estuvo de acuerdo» no es evidencia y
no debe reportarse como tal.

(La cifra de 0,20–0,59 de correlación acuerdo-veracidad que circula viene de un preprint de un solo
autor sin revisión por pares, y sobre benchmarks de preguntas cerradas — la transferencia a crítica
de diseño no está verificada. Usar la de ICML.)

Ver `mem:d1-que-cuenta-como-ensayo` y `mem:d3-holdout-oos-intocable`.
