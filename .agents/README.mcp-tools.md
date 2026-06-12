# MCP Tools Reference

> **Context Hierarchy**: This is a LOCAL nested cognitive context for MCP tools in the Pulse ecosystem. It inherits globally from `../AGENTS.md`.

Este documento sirve como el **Catálogo SSoT (Single Source of Truth)** de todas las herramientas (tools) expuestas por el ecosistema de servidores Model Context Protocol (MCP) en el entorno Pulse.

Según dictamina la matriz de privilegios en `.agents/rules/tooling-conventions.md`, cada fase del Spec-Driven Development (SDD) tiene acceso focalizado ("targeted") a los servidores de esta lista.

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     MCP Servers Registry                    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    │            │             │              │            │
    ▼            ▼             ▼              ▼            ▼
┌────────┐  ┌──────────┐  ┌────────────┐  ┌─────────┐  ┌─────────┐
│ pulse- │  │  github  │  │ filesystem │  │ memory  │  │ omega-  │
│ engine │  │          │  │            │  │         │  │ memory  │
└────────┘  └──────────┘  └────────────┘  └─────────┘  └─────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
      ┌────────────┐     ┌──────────┐      ┌────────────┐
      │ sequential │     │  serena  │      │  context7  │
      │ thinking   │     │          │      │            │
      └────────────┘     └──────────┘      └────────────┘
```

---

## 1. `pulse-engine` (Core FSM y Hooks)

Servidor nativo del motor Pulse. Orquesta el ciclo de vida del _Change_, administra la Máquina de Estados (FSM) y expone los adaptadores de validación fail-closed.

**FSM y Transiciones:**

- `request_sdd_transition`: Solicita avanzar a la siguiente fase. Retorna el nuevo estado y el hint del agente.
- `view_project_dashboard`: Retorna la vista integral (`structuredContent`) del estado FSM y el Change activo.
- `mcp__pulse__get_current_phase`: Retorna un string plano con la fase actual. Usado como sonda ligera.

**Ciclo de Vida de Cambios (Change):**

- `create_change_from_issue`: Materializa idempotentamente un `Change` en la persistencia local basado en un issue de GitHub.
- `list_active_changes`: Lista en modo read-only los Changes activos.
- `approve_design`: **Gate Humano.** Aprueba un documento de arquitectura antes de codificar (`design` → `apply`). No utilizable por agentes autónomos de fase.
- `mark_tests_passed`: Registra el boolean de éxito en los tests durante la fase `apply`.
- `close_change`: Activa la fase de merge final (Two-Stage Review), ejecutando el AgentShield (linters/tests), bump de versión, commit y aprendizaje continuo heurístico.

**Patrón Hooks Adapter y Declarative Gates:**

- `mcp__pulse__validate_tool_use`: Hook fail-closed. Valida si una llamada a tool (ej. write_file) está permitida en la fase FSM actual para un glob específico.
- `mcp__pulse__log_audit_event`: Appendea eventos de uso de tools al log de auditoría del proyecto.
- _(Nuevo)_ El engine utiliza **Declarative Gates** persistidos localmente (`GatePredicate`) en el `Change` para validar las transiciones del ciclo de vida (ej. APPLY phase), erradicando las validaciones globales estáticas (alineado a los **Ruflo Patterns**).

---

## 2. `github` (FSM Memory y Colaboración)

Pilar de la memoria colaborativa. Pulse usa los issues y labels de GitHub como la única fuente de la verdad para el ciclo SDD.

**Issues y Contexto (FSM Memory):**

- `search_issues`: Busca issues (generalmente por label `domain:*` o `state:*`).
- `get_issue` / `list_issues`: Hidratación cruda de contexto de una tarea.
- `create_issue` / `update_issue`: Manejo del ciclo de vida asíncrono.
- `add_issue_comment`: Conversaciones inter-humanos/agentes.

**Git Ops Remoto:**

- `get_file_contents` / `create_or_update_file`: Modificación directa en rama (bypass filesystem local).
- `search_code` / `search_repositories` / `search_users`: Descubrimiento global de repositorios y snippets.
- `create_branch` / `list_commits` / `push_files`: Git workflow directo a la nube.
- `fork_repository` / `create_repository`: Inicialización de repositorios hijos.

**Pull Requests (Merge Phase):**

- `create_pull_request` / `list_pull_requests` / `get_pull_request` / `merge_pull_request`
- `get_pull_request_files` / `get_pull_request_status` / `update_pull_request_branch`
- `create_pull_request_review` / `get_pull_request_reviews` / `get_pull_request_comments`

---

## 3. `filesystem` (I/O Local)

Manipulación estándar de archivos locales. **Atención:** Todas las herramientas de mutación de este servidor están sujetas al gate `mcp__pulse__validate_tool_use`.

**Lectura y Descubrimiento:**

- `read_file` / `read_text_file` / `read_media_file` / `read_multiple_files`: Extracción de contenido del workspace.
- `search_files` / `get_file_info`: Búsqueda superficial.
- `list_directory` / `list_directory_with_sizes` / `directory_tree`: Análisis topológico del directorio.
- `list_allowed_directories`: Verificación de sandboxing.

**Mutación (Supervisada por Hooks):**

- `write_file` / `edit_file`: Modificación de contenido.
- `create_directory` / `move_file`: Operaciones estructurales en el sistema de archivos.

---

## 4. `memory` (Knowledge Graph Permanente)

Persistencia cognitiva que trasciende sesiones y proyectos. Define un sistema de entidades y relaciones (memoria semántica).

**Escritura (Construcción del Grafo):**

- `create_entities` / `delete_entities`: Manejo de nodos (Agentes, Patrones, Doctrinas).
- `create_relations` / `delete_relations`: Enlazado de conceptos (ej. "Pulse" `utiliza` "FastMCP").
- `add_observations` / `delete_observations`: Insights descriptivos ligados a una entidad.

**Lectura (Hidratación):**

- `read_graph`: Descarga topológica de las entidades y sus asociaciones.
- `search_nodes` / `open_nodes`: Interrogación granular del conocimiento previo.

---

## 5. `omega-memory` (Sesión y Protocolo Operativo)

Memoria rápida, episódica y procedural. Enruta las instrucciones operativas estándar (SOP) a los agentes orquestadores.

**Interacciones Core:**

- `omega_welcome`: Ejecutada al inicio de la sesión para brifing y sincronización.
- `omega_protocol`: Fetch de las reglas operativas estrictas (SOPs).
- `omega_store`: Almacena descubrimientos clave o lecciones de sesión de forma rápida.
- `omega_tools` / `omega_call`: Soporte dinámico o meta-interacciones del sistema OMEGA.

---

## 6. `sequentialthinking` (Razonamiento Lógico Dinámico)

Habilita el pensamiento secuencial estructurado (CoT o _Chain of Thought_). Es imperativo usar este servidor para tareas de alta complejidad (fase de `design` o debugging de FSM) donde el agente necesita desglosar hipótesis sin vomitar texto en la interfaz del usuario.

**Estructuración de Pensamiento:**

- `sequentialthinking`: Única tool que acepta _thought_steps_. Permite someter un bloque de pensamiento, marcar el _thought_number_, ajustar el total de pensamientos esperados e indicar si se requiere una revisión (_is_revision_). Ideal para iterar lógicamente sobre invariantes fallidas de código (EDD).

---

## 7. `serena` (LSP y Contexto Semántico)

Servidor de orquestación autónoma (invocado vía `uvx` asegurando la correcta resolución de dependencias). Provee a los agentes de fase `apply` y `review` las capacidades nativas de un IDE a través del Language Server Protocol (LSP).

**Capacidades de IDE (Code Navigation):**

- Búsqueda semántica por definición (`Go to Definition`).
- Evaluaciones estáticas de tipo al vuelo (`Hover`, firmas de métodos).
- Inspección de referencias estructurales y diagnósticos en tiempo real del workspace sin tener que reejecutar herramientas de shell.

---

## 8. `context7` (Integraciones y External Memory)

Proporcionado vía `npm:@upstash/context7-mcp`. Actúa como puente para integraciones de memoria extendidas, cachés de base de datos vectoriales e inyección de contexto transversal.

**Capacidades:**

- Suministra endpoints para ingestar o consultar métricas/vectores en arquitecturas de memoria distribuidas o _knowledge bases_ remotas externas a la carpeta `.pulse/`.

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
