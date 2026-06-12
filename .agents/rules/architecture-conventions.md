# architecture-conventions.md — Patrones y Arquitectura

Este documento es la **fuente única de verdad (SSoT)** sobre las convenciones arquitectónicas del motor Pulse y los patrones fundacionales (Ruflo Patterns).

---

## 1. Arquitectura Hexagonal y DDD

El ecosistema de `src/pulse/` está rigurosamente dividido siguiendo los principios de _Domain-Driven Design_ y Arquitectura Hexagonal.

- **`domain/`**: El núcleo. Solo contiene modelos puros en Python (basados en Pydantic V2). No posee side-effects, I/O ni dependencias externas (solo `stdlib` y `pydantic`). Los invariantes puros se validan sistémicamente mediante property-based testing (`hypothesis`).
- **`application/`**: Orquesta los casos de uso (`WorkflowEngine`, `ChangeLifecycleService`). Define puertos (`Protocols`) para externalizar dependencias como la persistencia o el version bump.
- **`infrastructure/`**: Implementación de los adaptadores (FastMCP server, SQLite repositories, Filesystem ops, ejecución de linters).

**Regla**: El flujo de dependencias siempre va hacia adentro: `infrastructure → application → domain`.

---

## 2. Ruflo Patterns

Pulse institucionaliza los **Ruflo Patterns** como pilares de IA-Engineering:

1. **Swarm (Delegación de Profundidad 1)**: El orquestador del hilo principal delega en los agentes de fase (ej. `explore-agent`, `apply-agent`). Está estrictamente **prohibido el "nested swarming"** (que un subagente spawnee a otro subagente de fase).
2. **AgentShield (Two-Stage Review)**: Una puerta determinista ejecutada como un subproceso durante `close_change`. Garantiza que el código cumpla con los formateadores (`dprint`), linters (`ruff`), tipado (`ty`) y pruebas (`pytest`) antes de permitir el avance del FSM.
3. **Hooks Adapter**: Un guardián _fail-closed_ operando a nivel de la herramienta del cliente AI. Intercepta llamadas destructivas (ej. edición de archivos) y evalúa el `validate_tool_use` para confirmar si la operación es legal en la fase FSM actual.
4. **Continuous Learning**: Patrón de retroalimentación mecánica por el cual, al cerrar un cambio (`close_change`), se extraen heurísticas y lecciones aprendidas en `.pulse/heuristics/<domain>.md` para evitar que los agentes repitan errores.
5. **EDD + TDD**: Desarrollo guiado por criterios de evaluación ejecutables y código _test-first_ (formalizado en `eval-tdd-conventions.md`).

---

## 3. Declarative Gates (Validaciones Dinámicas)

_(Introducido en el Issue #84)_

El sistema abandonó el uso de validaciones de fase hardcodeadas (ej. exigir `tasks.md` globalmente en todos los apply). En su lugar, el motor utiliza **Declarative Gates**:

- La lógica de validación FSM se persiste directamente como instancias de `GatePredicate` en el modelo `Change`.
- Las transiciones validan estos predicados acotados al `Change` en curso. Esto requiere que las manipulaciones de estado interactúen con el modelo serializado en lugar de asumir reglas estáticas.
