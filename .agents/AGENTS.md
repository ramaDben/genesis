# AGENTS.md

> **Context Hierarchy**: This is a LOCAL nested cognitive context for the cognitive asset store (`.agents/`). It inherits globally from the root `../AGENTS.md`.

Guia local para agentes que modifiquen archivos bajo `.agents/**`.
Complementa el `AGENTS.md` de la raiz del repositorio y debe leerse junto a
`README.agents.md`, `README.cli-tools.md`, `README.mcp-tools.md` y
`rules/tooling-conventions.md`.

## Alcance

`.agents/` es el almacen declarativo de activos cognitivos del proyecto Pulse.
No contiene el motor ejecutable; contiene prompts, reglas, skills, templates y
manifests que las superficies cliente consumen o sincronizan.

- `agents/`: prompts de sistema para agentes de fase y utilidades.
- `hooks/`: PolicyHook scripts ejecutados vía `uv run` (guards, injectors) y librerías auxiliares.
- `rules/`: convenciones SSoT del proyecto (`tooling`, `eval-tdd`, `architecture`, `github-memory`, `ast-grep-rules`).
- `skills/`: definiciones de habilidades y workflows reutilizables.
- `templates/`: plantillas Markdown para artefactos SDD.
- `plugins/`: manifests y configuracion de integracion cliente/MCP.

## Reglas De Edicion

- Mantener este directorio como fuente comun portable. Las carpetas cliente
  (`.claude/`, `.codex/`, `.gemini/`, `.copilot/`, `.serena/`) no deben
  introducir una doctrina divergente.
- No crear nuevas etiquetas GitHub ni nuevas taxonomias sin autorizacion. La
  taxonomia canonica sigue siendo `domain:*`, `state:*`, `type:*`, `scope:*`.
- Preservar exactamente las fases SDD: `explore`, `propose`, `specify`, `design`,
  `break-to-tasks`, `apply`, `review`, `close`.
- No duplicar reglas largas si ya existe un SSoT en `rules/` o en un README
  local; referenciarlo y mantener una sola fuente editable.
- Al cambiar una regla, prompt, skill o manifest, buscar referencias con `rg`
  y actualizar los consumidores afectados en el mismo cambio.
- Mantener los diagramas en ASCII/Unicode versionable. Usar Mermaid solo si el
  usuario lo pide explicitamente.
- No guardar secretos, tokens, rutas privadas innecesarias ni datos personales
  en prompts, skills, templates o manifests.

## Skills Y Agentes

- Las skills deben ser pequenas, accionables y con disparadores claros:
  proposito, cuando usarla, pasos, artefactos esperados y guardrails.
- Los agentes de fase no deben hacer nested swarming. La orquestacion SDD es de
  profundidad 1: main thread -> agente de fase -> main thread.
- Los agentes y skills deben solicitar transiciones con
  `request_sdd_transition` cuando produzcan evidencia concreta.
- Nadie debe invocar `approve_design` salvo un humano/operador. El gate
  `design` -> `apply` es obligatorio.
- Los cambios issue-bound deben hidratar contexto desde GitHub usando
  `owner: "Bajmein"` y `repo: "pulse"` antes de implementar.

## Tooling & Architecture

- Usar `rg`, `fd`, `eza` y `ast-grep` como arsenal shell canonico. Evitar
  herramientas legacy como `grep` o `find` cuando haya alternativas modernas.
- Usar la matriz de MCP definida en `rules/tooling-conventions.md`, que impone el uso del **Standard MCP Toolchain**: `pulse-engine`, `github`, `filesystem`, `serena`, `sequentialthinking`, `omega-memory`, y `context7`.
- **Ruflo Patterns & Declarative Gates**: Los agentes deben adherir estrictamente a la doctrina de la arquitectura (Swarm depth-1, AgentShield, Hooks Adapter con `_lib` aislado, Continuous Learning) descrita en `rules/architecture-conventions.md`.
- **FSM Memory**: Usar el servidor `github` para hidratar contexto y memoria FSM según `rules/github-memory.md`.

## Verificacion

- Para cambios Markdown, revisar enlaces y nombres de archivos referenciados.
- Para cambios de prompts o skills, verificar consistencia con los nombres de
  fase, agentes y rutas del plugin.
- Para cambios de manifests o integraciones MCP, verificar paridad con las
  instrucciones de setup en los README locales.
- No mover ni regenerar archivos cliente derivados si el pedido solo afecta la
  fuente declarativa bajo `.agents/`.
