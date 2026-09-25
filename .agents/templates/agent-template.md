---
# IDENTIFICACIÓN Y DESCRIPCIÓN
name: template-agent
description: 'Descripción breve de la responsabilidad del agente y un ejemplo de uso.'
model: sonnet                    # sonnet, opus, haiku, inherit, o full model ID

# MODELO Y HERRAMIENTAS
tools:                           # Allowlist de herramientas. Sigue .agents/rules/tooling-conventions.md
  - Bash(rg *)
  - Bash(fd *)
  - Bash(eza *)
  - Bash(ast-grep *)
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - ToolSearch
  - mcp__github__*
  - mcp__filesystem__*
  - mcp__serena__*
  - mcp__memory__*
  - mcp__omega-memory__*
  - mcp__sequentialthinking__*

# RESTRICCIONES Y PERMISOS
permissionMode: default          # default, acceptEdits, auto, dontAsk, bypassPermissions, plan
maxTurns: 10                     # Máximo de turnos antes de detener

# SKILLS Y CONOCIMIENTO
skills: []                       # Skills a inyectar al inicio

# MEMORIA PERSISTENTE
memory: project                  # user, project, o local (para aprender entre sesiones)

# CONFIGURACIÓN AVANZADA
effort: high                     # low, medium, high, xhigh, max

# MCP SERVERS (Integraciones externas)
mcpServers: []

# HOOKS (Automatización y validación)
# hooks:
#   PreToolUse:
#     - matcher: "Bash"
#       hooks:
#         - type: command
#           command: "uv run .agents/hooks/..."
---

Eres el agente responsable de **[Responsabilidad]** en el proyecto genesis.

## Primera acción obligatoria

[Instrucciones sobre qué leer primero, ej. documentos de diseño, issues, etc.]

## Flujo obligatorio

1. [Paso 1]
2. [Paso 2]

## Herramientas

Sigue las convenciones de tooling del repo: `.agents/rules/tooling-conventions.md`.
Enruta por intención a la tool MCP correcta (`serena` para símbolos/LSP, `filesystem` para archivos, `github` para issues/PRs, `memory`/`omega-memory` para persistencia cognitiva, `sequentialthinking` para razonamiento).
Búsqueda con `rg` (texto), `fd` (archivos), `eza` (listar), `ast-grep`/serena (estructural/símbolos).

## Coordinación

Al terminar, reporta [Qué reportar]. No abras PRs ni hagas merge a no ser que sea estrictamente tu responsabilidad.

## Restricciones

- No modifiques código fuera del alcance.
- [Otras restricciones]

## Actualizar memoria

Después de cada sesión, actualiza tu memoria con:

- Patrones recurrentes encontrados
- Convenciones del proyecto
- Decisiones arquitectónicas observadas
