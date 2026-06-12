# eval-tdd-conventions.md — Doctrina EDD + TDD

Esta regla es la **fuente única de verdad (SSoT)** de la doctrina EDD (Eval-Driven Development) y
TDD (Test-Driven Development / test-first) para el ciclo SDD de Pulse. Las 4 superficies de agentes
(`src/pulse_plugin/agents/`, `.claude/agents/`, `.gemini/agents/`, `.codex/agents/`) referencian
este documento en vez de duplicar su contenido.

---

## EDD (Eval-Driven Development) — Ruflo Pattern

El EDD y TDD conforman uno de los patrones fundacionales (Ruflo Patterns) de Pulse, asegurando la rigurosidad y validación antes de la implementación.

Los agentes de las fases **specify** y **design** emiten criterios de aceptación **ejecutables**,
nunca prosa libre. Un criterio ejecutable es aquel que puede verificarse mecánicamente (un comando,
una aserción, un test) sin ambigüedad.

- El **specify-agent** produce criterios ejecutables en `delta_spec.md` (formato BDD o aserciones
  `rg`/`fd` concretas).
- El **design-agent** incluye criterios de aceptación ejecutables por tarea en `tasks.md` (input/
  fixture/output o referencia al eval del `delta_spec.md`).

---

## TDD (test-first en apply)

El **apply-agent**, para cada tarea de `tasks.md` que modifica código ejecutable en `src/`:

1. Escribe el test primero (**RED** — el test falla porque la implementación no existe aún).
2. Implementa el código mínimo para hacer pasar el test (**GREEN**).
3. Refactoriza si aplica, con la suite verde.
4. Reporta el resultado de `uv run pytest` con la salida real (no afirmar verde sin evidencia).

---

## Eval ejecutable (definición y formato BDD)

Un eval ejecutable sigue el formato **DADO / CUANDO / ENTONCES**:

```
DADO   [precondición / estado del sistema]
CUANDO [acción o evento — comando o invocación concreta]
ENTONCES [resultado observable y verificable]
```

Las verificaciones admitidas son cualquiera de las tres formas siguientes:

- `rg '<patrón>' <archivo>` retorna ≥ 1 coincidencia (presencia / enlace / formato).
- `fd '<nombre>' <dir>` confirma existencia de archivo.
- Test de pytest con caso fixture/input/output concreto (solo Changes con código en `src/`).
- Validaciones declarativas: Aserciones sobre los `GatePredicate` persistidos en el `Change` (Introducido en Issue #84).

### Ejemplo positivo (eval ejecutable)

```
DADO el archivo .agents/rules/eval-tdd-conventions.md
CUANDO  rg 'DADO|CUANDO|ENTONCES' .agents/rules/eval-tdd-conventions.md
ENTONCES retorna >=1 coincidencias
```

---

## Frases prohibidas

Las siguientes frases **NO son evals ejecutables** y deben rechazarse en review:

- "debe funcionar correctamente"
- "debe ser robusto"
- "debe manejar los casos de error"
- "debe ser legible"
- "debe estar bien documentado"
- Cualquier frase que no pueda verificarse mediante un comando o una aserción concreta.

Si un criterio de aceptación usa estas frases, el review-agent lo devuelve para reescritura como
eval ejecutable antes de avanzar la FSM.

---

## Excepción doc-only (Q5)

Un Change es **doc-only** cuando **ninguna tarea** de `tasks.md` modifica código ejecutable bajo
`src/` (engine o plugin Python). Consecuencias:

- **No** se añaden tests de pytest nuevos (no hay código que testear).
- Los criterios de aceptación se expresan como evals `rg`/`fd` (presencia/enlace/formato).
- La suite de pytest **existente** debe quedar verde antes de reportar complete (E9).
- Verificación mecánica: `git diff --name-only | rg '^src/pulse/'` → 0 resultados.

La excepción **no aplica** si cualquier tarea toca `src/`: en ese caso TDD se activa para esas
tareas individualmente.

> Aclaración: `src/pulse_plugin/*.md` (assets de plugin, Markdown) son documentación, no rompen
> la excepción. El engine ejecutable está bajo `src/pulse/**/*.py`.

---

## Granularidad (Q4)

La unidad de activación TDD es la **tarea individual de `tasks.md`**, no el Change completo:

- Si una tarea modifica `src/` → TDD test-first se activa para esa tarea.
- Si otra tarea en el mismo Change es doc-only → no requiere test de pytest nuevo.
- Un Change puede mezclar tareas TDD y tareas doc-only; el apply-agent aplica la regla tarea a tarea.

---

## Referencias

- `.agents/rules/tooling-conventions.md` — shell canónico (`rg`/`fd`/`eza`/`ast-grep`) y matriz MCP
  por fase.
- `AGENTS.md` § _SDD Orchestration_ — flujo FSM, gate humano design→apply, swarm depth-1.
- Issue #90 — epic EDD+TDD (decisiones Q1..Q5 que originaron esta regla).
- Issue #91 — C1: doctrina en agentes specify/design/apply (implementación de esta regla).
- Issue #40 — Patrones Ruflo (formalización de Swarm, AgentShield, Hooks Adapter).
- Issue #84 — Declarative Gates (migración hacia predicados persistidos en Change).
