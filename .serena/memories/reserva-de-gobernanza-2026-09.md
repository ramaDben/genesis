*(2026-09-05 — decisión de reservar, no de abandonar. Esta memoria es el punto de reentrada.)*

# Gobernanza y compuerta humana: trabajo reservado

Todo el trabajo de gobernanza de la sesión del 2026-09-05 queda **en pausa deliberada** hasta una
fase más madura del proyecto. No está bloqueado ni descartado: está reservado, con las condiciones
de reanudación escritas para que nadie tenga que reconstruir el razonamiento.

Rastro en GitHub: hito **«Gobernanza y política de decisión»**, label `state:diferido`.

## El diagnóstico que originó todo

El usuario declaró que **ha pasado todos los `approve_design` sin leer**, porque las decisiones
llegan en un vocabulario técnico que no es el suyo. Consecuencia que reencuadra el precedente ya
registrado en `CLAUDE.md`: **la compuerta humana nunca funcionó**. Los PR #68 y #69 no fueron
anomalías — fueron el comportamiento normal de una compuerta que era un trámite.

Una compuerta que se aprueba sin leer no protege nada, y con el RPSF de la CMF en el horizonte
(`mem:proposito-real-y-alcance-de-genesis`) deja de ser un problema de higiene y pasa a ser un
problema de sustentación regulatoria.

## La salida diseñada, sin construir

**Separar política de adjudicación.** Los límites se fijan una vez, por adelantado, en el
vocabulario que el humano sí domina —dinero, tiempo, riesgo, alcance—; un adjudicador externo los
aplica caso por caso; solo lo que no encaja escala.

Tres reglas de diseño que se fijaron y **no se negocian**:

1. **El adjudicador no puede ser el agente que propone el cambio.** Va a un modelo de otro
   proveedor. El usuario tiene acceso a la API de Gemini.
2. **Sesgo hacia escalar.** Ante duda razonable, no está cubierto. Cada escalamiento es evidencia
   de un hueco en la política, no un fastidio.
3. **Cambiar la política nunca se pre-autoriza.** Aflojar un gate, ampliar alcance o subir un
   límite vuelve siempre al humano.

**Restricción de implementación, verificada:** el enforcement tiene que ser **mecánico** —un
`scripts/gate_check.py` que falla— y no una instrucción en una skill, porque una instrucción la
puede violar el mismo agente que debería obedecerla. Y **no se bifurca el engine de pulse**: las
skills son nuestras, el engine es un contenedor de upstream. La adaptación va en las skills y en un
chequeo propio, nunca en el engine.

## Lo que se descubrió investigando, y conviene no volver a investigar

- **Un segundo modelo es fuente de desacuerdo, no validador.** Estudio ICML 2025 (Kim, Garg, Peng,
  Garg): cuando dos modelos se equivocan, **convergen en la misma respuesta equivocada el 60 % de
  las veces**. El valor de la revisión externa está en el desacuerdo que produce, no en el acuerdo.
- **Y funcionó en la práctica:** una consulta a ciegas encontró dos errores ya integrados, incluido
  un error de categoría sobre el DSR (corregido el 2026-09-05, ver `mem:d1-que-cuenta-como-ensayo`).
  Lo caro no fue el modelo: fue redactar un briefing que expusiera el propio encuadre al ataque.
- **MCP (spec 2026-07-28) es stateless por diseño**, sin sesión en el protocolo base. Compartir
  contexto entre proveedores hay que construirlo por encima; no hay estándar que lo resuelva.
- **La versión mínima es un script que llama a una API**, no una «oficina multi-agente». Todo lo
  demás es infraestructura que el usuario declaró explícitamente que no quiere administrar.

## Qué construir cuando se reanude, en orden

1. `POLITICA.md` versionado y con hash, redactado desde `docs/ENTREVISTA_POLITICA.md`, para que cada
   decisión pueda citar qué cláusula la autorizó.
2. El borrador va a un modelo externo con **una sola consigna: «¿qué NO cubre esta política?»**. Lo
   va a redactar el mismo agente cuyos puntos ciegos busca cubrir.
3. Recién entonces: `scripts/consulta_adversarial.py`, el ledger de decisiones (generalizando
   `trial_ledger.py`) y `scripts/gate_check.py`.

El orden importa: construir el adjudicador antes de tener política es construir un juez sin ley.

## Qué reanuda esto

Cualquiera de las tres. No hace falta que se cumplan todas.

1. **Aparece capital real**, propio o ajeno.
2. **Un candidato se acerca a un GO** — la compuerta pasa a tener algo que proteger.
3. **Se decide construir el arquitecto** — A2 de la entrevista lo dejó condicionado a que el ledger
   de ensayos funcione, y esa condición es una cláusula de política todavía no escrita.

## Lo que se acepta a sabiendas mientras tanto

Que sigue rigiendo «solo un humano llama `approve_design`» con la debilidad ya diagnosticada. Se
asume porque hoy no hay capital ni candidatos en juego. **Deja de ser aceptable en el momento en que
se cumple cualquiera de las tres condiciones de arriba.**

Ver `mem:politica-de-decision-y-compuerta-humana`, `mem:proposito-real-y-alcance-de-genesis`,
`mem:d3-holdout-oos-intocable`, `mem:d1-que-cuenta-como-ensayo`.
