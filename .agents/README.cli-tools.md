# CLI Tools Reference

> **Context Hierarchy**: This is a LOCAL nested cognitive context for CLI tools in the Pulse ecosystem. It inherits globally from `../AGENTS.md`.

Este documento sirve como el **Catálogo SSoT** de las herramientas de línea de comandos canónicas (instaladas y gestionadas vía `mise`) en el ecosistema Pulse.

Para asegurar un rendimiento predecible, determinismo en el I/O, y compatibilidad con el ecosistema de _Hooks Adapters_ (`sdd_validate_tool_hook.py`), Pulse impone el uso estricto de la siguiente **Targeted CLI Matrix**, reemplazando las utilidades POSIX obsoletas.

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                  Canonical CLI Tools Registry               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    │            │             │              │            │
    ▼            ▼             ▼              ▼            ▼
┌────────┐  ┌──────────┐  ┌────────────┐  ┌─────────┐  ┌─────────┐
│   rg   │  │ ast-grep │  │  fd-find   │  │   eza   │  │   gh    │
└────────┘  └──────────┘  └────────────┘  └─────────┘  └─────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
┌────────────┐     ┌───────────┐      ┌───────────┐     ┌─────────┐
      │     yq     │     │    mdq    │      │mise / uvx │     │ dprint  │
      └────────────┘     └───────────┘      └───────────┘     └─────────┘
                                                                   │
                                                            ┌──────┴──────┐
                                                            ▼             ▼
                                                      ┌───────────┐ ┌────────────┐
                                                      │ dprint-py │ │pretty_yaml │
                                                      └───────────┘ └────────────┘
                                                            │
                                                            ▼
                                                       ┌───────────┐
                                                       │   tokei   │
                                                       └───────────┘
                                                             │
                                                             ▼
                                                       ┌───────────┐
                                                       │ tokei-pie │
                                                       └───────────┘
```

---

## 1. Búsqueda y Navegación de Código (Code Discovery)

### `rg` (ripgrep)

- **Reemplaza a:** `grep`
- **Propósito:** Búsqueda textual recursiva de extrema velocidad orientada a líneas. Respeta el `.gitignore` nativamente.
- **Regla SDD:** Es la herramienta obligatoria cuando el agente de `explore` o `apply` necesite localizar implementaciones de un método a lo largo de todo el codebase mediante expresiones regulares convencionales o texto plano.

### `ast-grep` (`sg`)

- **Reemplaza a:** `grep`, `sed` y scripts manuales basados en regex cuando se analizan ASTs complejos.
- **Propósito:** Búsqueda estructural semántica. Permite encontrar patrones abstractos de código ignorando por completo el formato, los comentarios, los _line breaks_ y las convenciones de espaciado.
- **Regla SDD:** Obligatorio para refactorizaciones profundas (`apply-agent` y `design-agent`) donde se requiere encontrar todos los _call sites_ lógicos de una función o el uso estructural de una clase.

---

## 2. Exploración del Workspace (Filesystem Ops)

### `fd` (fd-find)

- **Reemplaza a:** `find`
- **Propósito:** Búsqueda inteligente de rutas, directorios y archivos. Ignora dinámicamente carpetas redundantes (`.git`, `.venv`) y lee el `.gitignore`.
- **Regla SDD:** Debe usarse para listar dinámicamente archivos de un dominio específico o buscar especificaciones difusas (ej. `fd "spec.md" .pulse/specs/`).

### `eza`

- **Reemplaza a:** `ls`, `tree`
- **Propósito:** Listado hiper-optimizado de directorios con atributos meta.
- **Regla SDD:** Su uso primario en el ecosistema Agentic de Pulse es invocarlo con la flag `--tree` para visualizar topologías complejas de carpetas, con el fin de generar modelos mentales o diagramas ASCII (`/diagram-expert`) para artefactos de documentación de la fase `specify`.

---

## 3. GitHub Memory, Metadatos y Orquestación

### `gh` (GitHub CLI)

- **Reemplaza a:** `curl` crudo contra la REST API o scripts de clonado manuales.
- **Propósito:** Interfaz directa y autenticada de bajo nivel hacia el motor de estado (GitHub).
- **Regla SDD:** Para flujos estándar FSM, use **siempre** las herramientas MCP del servidor `github` (`mcp__github__*`). El CLI `gh` está reservado **exclusivamente como fallback** para operaciones que el MCP aún no soporte (ej. queries complejas y personalizadas de GraphQL, o edición administrativa profunda de Labels/Webhooks).

### `yq`

- **Reemplaza a:** `jq` (limitado a JSON), o edición a ciegas con `sed`.
- **Propósito:** Analizador y procesador in-place de archivos YAML, JSON, XML y propiedades.
- **Regla SDD:** Vital para la fase `apply` cuando es imperativo mutar configuraciones estandarizadas (como `prek.toml` o los workflows en `.github/workflows/*.yml`) sin destruir la indentación, la sintaxis declarativa o los comentarios circundantes.

### `mdq`

- **Reemplaza a:** Analizadores manuales (`sed`, `awk`) sobre archivos Markdown.
- **Propósito:** Parseador estructural de Markdown (actúa como un `jq` para archivos `.md`).
- **Regla SDD:** Obligatorio cuando los agentes requieran interrogar o extraer información estructurada (tablas, frontmatter, títulos) de los archivos `.md` del _Cognitive Asset Store_ (`.agents/`), heurísticas o especificaciones SDD, garantizando un parseo predecible basado en el Abstract Syntax Tree (AST) de Markdown.

### `mise`

- **Reemplaza a:** `make`, `nvm`, `pyenv`.
- **Propósito:** Orquestador canónico de dependencias, variables de entorno y tasks.
- **Regla SDD:** Las herramientas estandarizadas como AgentShield corren **siempre** a través de la task definida en `mise-tasks/*.toml` (ej. `mise run ci`, `mise run lint`). Los agentes nunca invocan linters huérfanos.

### `uvx` / `uv`

- **Reemplaza a:** `pip`, `pipx`, `poetry`.
- **Propósito:** Gestor de dependencias ultrarrápido y ejecutor de herramientas aisladas en Python.
- **Regla SDD:** Motor principal para la resolución y ejecución _on-the-fly_ de utilidades Python. Por ejemplo, servidores MCP como `serena` se invocan canónicamente a través de `uvx` para garantizar aislamiento de entorno sin fricción.

---

## 4. Code Formatting & Validation

### `prek`

- **Reemplaza a:** `pre-commit`
- **Propósito:** Gestor ultrarrápido de Git hooks escrito en Rust, compatible con la configuración de `pre-commit`.
- **Regla SDD:** Es el estándar canónico para la inicialización del proyecto y validación de hooks. Instala dinámicamente entornos aislados para validar las políticas del repositorio antes de un commit.

### `dprint` & `ruff`

- **Reemplaza a:** `prettier`, `black`, `isort`, `flake8`
- **Propósito:** Plataforma de formateo y linting estricto.
- **Regla SDD:** Herramienta estandarizada para formateo y calidad de código.
  - `dprint` maneja archivos JSON, Markdown y TOML.
  - `ruff` (integrado vía `mise run lint` / `mise run format`) delega el formateo y linting hiper-rápido del dominio Python.
  - El AgentShield confía plenamente en `dprint` y `ruff` para su fase de revisión.

### `ty`

- **Reemplaza a:** `mypy`, `pyright` (uso crudo)
- **Propósito:** Chequeo estricto de tipos de Python de manera determinista.
- **Regla SDD:** Es el comprobador de tipos canónico requerido por el AgentShield durante el cierre del Change.

### `pytest`

- **Propósito:** Framework estándar de pruebas y validación funcional.
- **Regla SDD:** Es el motor central para el EDD y TDD guiado por propiedades (`hypothesis`). Los componentes aislados (como el motor FSM o la librería de hooks `_lib`) resuelven sus suites de manera autónoma usando `uv run pytest` con sus propias dependencias dev. Requerido obligatoriamente por el AgentShield.

### `pretty_yaml` (g-plane/pretty_yaml)

- **Reemplaza a:** Formateadores de YAML más lentos (Node) o menos fiables.
- **Propósito:** Formateador nativo en Rust para archivos YAML.
- **Regla SDD:** Herramienta recomendada y gestionada para formatear archivos `.yaml` y `.yml` complejos, tales como los manifiestos FSM o los `.github/workflows`, garantizando mínima alteración destructiva.

---

## 5. Metrics & Analytics

### `tokei`

- **Reemplaza a:** `cloc`, `wc` y scripts manuales de conteo.
- **Propósito:** Analizador extremadamente rápido (Rust) de métricas de código.
- **Regla SDD:** Debe usarse para generar volcados estructurales de métricas (vía `tokei --output json .`). Estas métricas se utilizan en la validación heurística o para la toma de decisiones arquitecturales complejas durante la fase de `design`. Se invoca convencionalmente a través de la tarea de `mise` (ej. `mise run metrics`).

### `tokei-pie`

- **Propósito:** Generador visual de gráficos (PNG) a partir de la salida JSON de `tokei`.
- **Regla SDD:** Obligatorio cuando se deban generar reportes gráficos sobre la distribución y peso del código (lenguajes, blanks, comments). Se invoca convencionalmente a través de la tarea de `mise` (ej. `mise run metrics:pie`).

---

## 🌐 Pulse Ecosystem & Standards

Este componente es parte del ecosistema central de **Pulse**, regido por las siguientes convenciones y arquitecturas globales (ver SSoT en `.agents/rules/` y la memoria del proyecto):

- **Arquitectura Hexagonal + DDD**: Dependencias unidireccionales (`infrastructure → application → domain`), con un núcleo puro de Pydantic V2 y pruebas basadas en propiedades (`hypothesis`).
- **FSM y SDD**: Ciclo de vida estricto (Explore → Specify → Design → Apply → Review → Close) impulsado por Spec-Driven Development, utilizando **GitHub como FSM Memory** para orquestar el estado a través de issues y labels.
- **Standard MCP Toolchain**: Todos los agentes operando en este entorno deben estar equipados con la matriz de privilegios de Pulse: `sequentialthinking`, `omega-memory`, `serena`, `github`, `filesystem`, `pulse-engine` y `context7`.
- **Patrones Ruflo**:
  - **Swarm**: Orquestación desde el hilo principal con delegación de profundidad 1 (sin subagentes anidados).
  - **Hooks Adapter**: Gates de validación fail-closed (`validate_tool_use`) inyectados vía PreToolUse hooks.
  - **AgentShield & Declarative Gates**: Validaciones de revisión deterministas previas al cierre de tareas (dprint, ruff, pytest) encapsuladas en la FSM.
  - **Continuous Learning**: Captura mecánica y auditada de heurísticas de arquitectura al finalizar iteraciones.
