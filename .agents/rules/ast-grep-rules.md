# ast-grep Rules

Este directorio almacena las reglas estructurales de `ast-grep` para el repositorio Pulse.

## Doctrina (Cognitive Asset Store)

De acuerdo a la arquitectura del proyecto, todas las reglas semánticas y de análisis estático (activos cognitivos) deben residir dentro de `.agents/rules/`. Las reglas de `ast-grep` permiten escanear y validar invariantes estructurales en el código, tales como:

- Dependencias unidireccionales (DDD Hexagonal).
- Validaciones Pydantic V2.
- Convenciones de FastMCP Tool schemas.

_(Puedes añadir archivos YAML aquí para que `sg scan` los recoja automáticamente)._

---

## 🌐 Pulse Ecosystem & Standards

Este componente es parte del ecosistema central de **Pulse**, regido por las siguientes convenciones y arquitecturas globales (ver SSoT en `.agents/rules/` y la memoria del proyecto):

- **Arquitectura Hexagonal + DDD**: Dependencias unidireccionales (`infrastructure → application → domain`), con un núcleo puro de Pydantic V2 y pruebas basadas en propiedades (`hypothesis`).
- **FSM y SDD**: Ciclo de vida estricto (Explore → Specify → Design → Apply → Review → Close) impulsado por Spec-Driven Development, utilizando **GitHub como FSM Memory** para orquestar el estado a través de issues y labels.
- **Standard MCP Toolchain**: Todos los agentes operando en este entorno deben estar equipados con la matriz de privilegios de Pulse: `sequentialthinking`, `omega-memory`, `memory`, `serena`, `github`, `filesystem`, `pulse-engine` y `context7`.
- **Patrones Ruflo**:
  - **Swarm**: Orquestación desde el hilo principal con delegación de profundidad 1 (sin subagentes anidados).
  - **Hooks Adapter**: Gates de validación fail-closed (`validate_tool_use`) inyectados vía PreToolUse hooks.
  - **AgentShield & Declarative Gates**: Validaciones de revisión deterministas previas al cierre de tareas (dprint, ruff, pytest) encapsuladas en la FSM.
  - **Continuous Learning**: Captura mecánica y auditada de heurísticas de arquitectura al finalizar iteraciones.
