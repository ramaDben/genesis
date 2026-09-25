# MCP Tools Reference

> **Context Hierarchy**: This is a LOCAL nested cognitive context for MCP tools. It inherits globally from `../AGENTS.md`.

Este documento sirve como el **Catálogo SSoT (Single Source of Truth)** de todas las herramientas (tools) expuestas por el ecosistema de servidores Model Context Protocol (MCP) en este repo.

El enrutamiento por intención está en `.agents/rules/tooling-conventions.md`.

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     MCP Servers Registry                    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    │            │             │              │            │
    ▼            ▼             ▼              ▼            ▼
            ┌──────────┐  ┌────────────┐  ┌─────────┐  ┌─────────┐
            │  github  │  │ filesystem │  │ memory  │  │ omega-  │
            │          │  │            │  │         │  │ memory  │
            └──────────┘  └────────────┘  └─────────┘  └─────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
      ┌────────────┐     ┌──────────┐      ┌────────────┐
      │ sequential │     │  serena  │      │  context7  │
      │ thinking   │     │          │      │            │
      └────────────┘     └──────────┘      └────────────┘
```

---

## 1. `github` (Memoria y Colaboración)

Pilar de la memoria colaborativa: los issues y labels de GitHub son la fuente de verdad del estado del trabajo.

**Issues y Contexto:**

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

## 2. `filesystem` (I/O Local)

Manipulación estándar de archivos locales.

**Lectura y Descubrimiento:**

- `read_file` / `read_text_file` / `read_media_file` / `read_multiple_files`: Extracción de contenido del workspace.
- `search_files` / `get_file_info`: Búsqueda superficial.
- `list_directory` / `list_directory_with_sizes` / `directory_tree`: Análisis topológico del directorio.
- `list_allowed_directories`: Verificación de sandboxing.

**Mutación:**

- `write_file` / `edit_file`: Modificación de contenido.
- `create_directory` / `move_file`: Operaciones estructurales en el sistema de archivos.

---

## 3. `memory` (Knowledge Graph Permanente)

Persistencia cognitiva que trasciende sesiones y proyectos. Define un sistema de entidades y relaciones (memoria semántica).

**Escritura (Construcción del Grafo):**

- `create_entities` / `delete_entities`: Manejo de nodos (Agentes, Patrones, Doctrinas).
- `create_relations` / `delete_relations`: Enlazado de conceptos (ej. "genesis" `utiliza` "hypothesis").
- `add_observations` / `delete_observations`: Insights descriptivos ligados a una entidad.

**Lectura (Hidratación):**

- `read_graph`: Descarga topológica de las entidades y sus asociaciones.
- `search_nodes` / `open_nodes`: Interrogación granular del conocimiento previo.

---

## 4. `omega-memory` (Sesión y Protocolo Operativo)

Memoria rápida, episódica y procedural. Enruta las instrucciones operativas estándar (SOP) a los agentes orquestadores.

**Interacciones Core:**

- `omega_welcome`: Ejecutada al inicio de la sesión para brifing y sincronización.
- `omega_protocol`: Fetch de las reglas operativas estrictas (SOPs).
- `omega_store`: Almacena descubrimientos clave o lecciones de sesión de forma rápida.
- `omega_tools` / `omega_call`: Soporte dinámico o meta-interacciones del sistema OMEGA.

---

## 5. `sequentialthinking` (Razonamiento Lógico Dinámico)

Habilita el pensamiento secuencial estructurado (CoT o _Chain of Thought_). Es imperativo usar este servidor para tareas de alta complejidad (diseño o debugging) donde el agente necesita desglosar hipótesis sin vomitar texto en la interfaz del usuario.

**Estructuración de Pensamiento:**

- `sequentialthinking`: Única tool que acepta _thought_steps_. Permite someter un bloque de pensamiento, marcar el _thought_number_, ajustar el total de pensamientos esperados e indicar si se requiere una revisión (_is_revision_). Ideal para iterar lógicamente sobre invariantes fallidas de código (EDD).

---

## 6. `serena` (LSP y Contexto Semántico)

Servidor de orquestación autónoma (invocado vía `uvx` asegurando la correcta resolución de dependencias). Provee a los agentes las capacidades nativas de un IDE a través del Language Server Protocol (LSP).

**Capacidades de IDE (Code Navigation):**

- Búsqueda semántica por definición (`Go to Definition`).
- Evaluaciones estáticas de tipo al vuelo (`Hover`, firmas de métodos).
- Inspección de referencias estructurales y diagnósticos en tiempo real del workspace sin tener que reejecutar herramientas de shell.

---

## 7. `context7` (Integraciones y External Memory)

Proporcionado vía `npm:@upstash/context7-mcp`. Actúa como puente para integraciones de memoria extendidas, cachés de base de datos vectoriales e inyección de contexto transversal.

**Capacidades:**

- Suministra endpoints para ingestar o consultar métricas/vectores en arquitecturas de memoria distribuidas o _knowledge bases_ remotas externas a la carpeta `.pulse/`.

