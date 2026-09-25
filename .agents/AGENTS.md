# AGENTS.md

> **Context Hierarchy**: This is a LOCAL nested cognitive context for the cognitive asset store (`.agents/`). It inherits globally from the root `../AGENTS.md`.

Guia local para agentes que modifiquen archivos bajo `.agents/**`.
Complementa el `AGENTS.md` de la raiz del repositorio y debe leerse junto a
`README.agents.md`, `README.cli-tools.md`, `README.mcp-tools.md` y
`rules/tooling-conventions.md`.

## Alcance

`.agents/` es el almacen declarativo de activos cognitivos del proyecto.
No contiene el motor ejecutable; contiene prompts, reglas, skills, templates y
manifests que las superficies cliente consumen o sincronizan.

- `agents/`: prompts de sistema para agentes y utilidades.
- `hooks/`: scripts de hooks ejecutados vía `run_hook.sh` (hoy sólo `session_context.py`) y su librería auxiliar.
- `rules/`: convenciones SSoT del proyecto (`tooling`, `github-memory`, `ast-grep-rules`).
- `skills/`: definiciones de habilidades y workflows reutilizables.
- `templates/`: plantillas Markdown para agentes, reglas y skills.
- `plugins/`: manifests y configuracion de integracion cliente/MCP.

## Reglas De Edicion

- Mantener este directorio como fuente comun portable. Las carpetas cliente
  (`.claude/`, `.codex/`, `.gemini/`, `.copilot/`, `.serena/`) no deben
  introducir una doctrina divergente.
- No crear nuevas etiquetas GitHub ni nuevas taxonomias sin autorizacion. La
  taxonomia canonica sigue siendo `domain:*`, `type:*`, `scope:*` (ver `rules/github-memory.md`).
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
- Los subagentes no deben hacer nested swarming: delegacion de profundidad 1
  (main thread -> subagente -> main thread).
- Los cambios que alteran comportamiento o contrato bajo `src/genesis/**` van por
  rama -> PR -> revision humana antes del merge.
- Los cambios issue-bound deben hidratar contexto desde GitHub usando
  `owner: "ramaDben"` y `repo: "genesis"` antes de implementar.

## Tooling & Architecture

- Usar `rg`, `fd`, `eza` y `ast-grep` como arsenal shell canonico. Evitar
  herramientas legacy como `grep` o `find` cuando haya alternativas modernas.
- Usar el enrutamiento MCP definido en `rules/tooling-conventions.md`: `github`, `filesystem`, `serena`, `sequentialthinking`, `omega-memory` y `context7`.
- Usar el servidor `github` para hidratar contexto según `rules/github-memory.md`.

## Verificacion

- Para cambios Markdown, revisar enlaces y nombres de archivos referenciados.
- Para cambios de prompts o skills, verificar consistencia con los nombres de
  agentes y rutas referenciadas.
- Para cambios de manifests o integraciones MCP, verificar paridad con las
  instrucciones de setup en los README locales.
- No mover ni regenerar archivos cliente derivados si el pedido solo afecta la
  fuente declarativa bajo `.agents/`.
