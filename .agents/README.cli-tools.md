# CLI Tools Reference

> **Context Hierarchy**: This is a LOCAL nested cognitive context for CLI tools. It inherits globally from `../AGENTS.md`.

Este documento sirve como el **Catálogo SSoT** de las herramientas de línea de comandos canónicas (instaladas y gestionadas vía `mise`) en este repo.

Para asegurar un rendimiento predecible y determinismo en el I/O, el repo impone el uso estricto de la siguiente **Targeted CLI Matrix**, reemplazando las utilidades POSIX obsoletas.

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
- **Regla:** Es la herramienta obligatoria cuando un agente necesite localizar implementaciones de un método a lo largo de todo el codebase mediante expresiones regulares convencionales o texto plano.

### `ast-grep` (`sg`)

- **Reemplaza a:** `grep`, `sed` y scripts manuales basados en regex cuando se analizan ASTs complejos.
- **Propósito:** Búsqueda estructural semántica. Permite encontrar patrones abstractos de código ignorando por completo el formato, los comentarios, los _line breaks_ y las convenciones de espaciado.
- **Regla:** Obligatorio para refactorizaciones profundas donde se requiere encontrar todos los _call sites_ lógicos de una función o el uso estructural de una clase.

---

## 2. Exploración del Workspace (Filesystem Ops)

### `fd` (fd-find)

- **Reemplaza a:** `find`
- **Propósito:** Búsqueda inteligente de rutas, directorios y archivos. Ignora dinámicamente carpetas redundantes (`.git`, `.venv`) y lee el `.gitignore`.
- **Regla:** Debe usarse para listar dinámicamente archivos de un dominio específico o buscar especificaciones difusas (ej. `fd "spec.md" .pulse/specs/`).

### `eza`

- **Reemplaza a:** `ls`, `tree`
- **Propósito:** Listado hiper-optimizado de directorios con atributos meta.
- **Regla:** Su uso primario es invocarlo con la flag `--tree` para visualizar topologías complejas de carpetas, con el fin de generar modelos mentales o diagramas ASCII (`/diagram-expert`) para artefactos de documentación.

---

## 3. GitHub Memory, Metadatos y Orquestación

### `gh` (GitHub CLI)

- **Reemplaza a:** `curl` crudo contra la REST API o scripts de clonado manuales.
- **Propósito:** Interfaz directa y autenticada de bajo nivel hacia el motor de estado (GitHub).
- **Regla:** Para flujos estándar, use **siempre** las herramientas MCP del servidor `github` (`mcp__github__*`). El CLI `gh` está reservado **exclusivamente como fallback** para operaciones que el MCP aún no soporte (ej. queries complejas y personalizadas de GraphQL, o edición administrativa profunda de Labels/Webhooks).

### `yq`

- **Reemplaza a:** `jq` (limitado a JSON), o edición a ciegas con `sed`.
- **Propósito:** Analizador y procesador in-place de archivos YAML, JSON, XML y propiedades.
- **Regla:** Vital cuando es imperativo mutar configuraciones estandarizadas (como `prek.toml` o los workflows en `.github/workflows/*.yml`) sin destruir la indentación, la sintaxis declarativa o los comentarios circundantes.

### `mdq`

- **Reemplaza a:** Analizadores manuales (`sed`, `awk`) sobre archivos Markdown.
- **Propósito:** Parseador estructural de Markdown (actúa como un `jq` para archivos `.md`).
- **Regla:** Obligatorio cuando los agentes requieran interrogar o extraer información estructurada (tablas, frontmatter, títulos) de los archivos `.md` del _Cognitive Asset Store_ (`.agents/`), heurísticas o especificaciones (`.pulse/specs/`), garantizando un parseo predecible basado en el Abstract Syntax Tree (AST) de Markdown.

### `mise`

- **Reemplaza a:** `make`, `nvm`, `pyenv`.
- **Propósito:** Orquestador canónico de dependencias, variables de entorno y tasks.
- **Regla:** Las herramientas de calidad corren **siempre** a través de la task definida en `mise-tasks/*.toml` (ej. `mise run ci`, `mise run lint`). Los agentes nunca invocan linters huérfanos.

### `uvx` / `uv`

- **Reemplaza a:** `pip`, `pipx`, `poetry`.
- **Propósito:** Gestor de dependencias ultrarrápido y ejecutor de herramientas aisladas en Python.
- **Regla:** Motor principal para la resolución y ejecución _on-the-fly_ de utilidades Python. Por ejemplo, servidores MCP como `serena` se invocan canónicamente a través de `uvx` para garantizar aislamiento de entorno sin fricción.

---

## 4. Code Formatting & Validation

### `prek`

- **Reemplaza a:** `pre-commit`
- **Propósito:** Gestor ultrarrápido de Git hooks escrito en Rust, compatible con la configuración de `pre-commit`.
- **Regla:** Es el estándar canónico para la inicialización del proyecto y validación de hooks. Instala dinámicamente entornos aislados para validar las políticas del repositorio antes de un commit.

### `dprint` & `ruff`

- **Reemplaza a:** `prettier`, `black`, `isort`, `flake8`
- **Propósito:** Plataforma de formateo y linting estricto.
- **Regla:** Herramienta estandarizada para formateo y calidad de código.
  - `dprint` maneja archivos JSON, Markdown y TOML.
  - `ruff` (integrado vía `mise run lint` / `mise run format`) delega el formateo y linting hiper-rápido del dominio Python.

### `ty`

- **Reemplaza a:** `mypy`, `pyright` (uso crudo)
- **Propósito:** Chequeo estricto de tipos de Python de manera determinista.
- **Regla:** Es el comprobador de tipos canónico (parte de `mise run ci`).

### `pytest`

- **Propósito:** Framework estándar de pruebas y validación funcional.
- **Regla:** Es el motor central para el EDD y TDD guiado por propiedades (`hypothesis`). Los componentes aislados (como la librería de hooks `_lib`) resuelven sus suites de manera autónoma usando `uv run pytest` con sus propias dependencias dev. Parte de `mise run ci`.

### `pretty_yaml` (g-plane/pretty_yaml)

- **Reemplaza a:** Formateadores de YAML más lentos (Node) o menos fiables.
- **Propósito:** Formateador nativo en Rust para archivos YAML.
- **Regla:** Herramienta recomendada y gestionada para formatear archivos `.yaml` y `.yml` complejos, tales como los `.github/workflows`, garantizando mínima alteración destructiva.

---

## 5. Metrics & Analytics

### `tokei`

- **Reemplaza a:** `cloc`, `wc` y scripts manuales de conteo.
- **Propósito:** Analizador extremadamente rápido (Rust) de métricas de código.
- **Regla:** Debe usarse para generar volcados estructurales de métricas (vía `tokei --output json .`). Estas métricas se utilizan en la validación heurística o para la toma de decisiones arquitecturales complejas Se invoca convencionalmente a través de la tarea de `mise` (ej. `mise run metrics`).

### `tokei-pie`

- **Propósito:** Generador visual de gráficos (PNG) a partir de la salida JSON de `tokei`.
- **Regla:** Obligatorio cuando se deban generar reportes gráficos sobre la distribución y peso del código (lenguajes, blanks, comments). Se invoca convencionalmente a través de la tarea de `mise` (ej. `mise run metrics:pie`).

