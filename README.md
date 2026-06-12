# genesis

Pipeline de validación institucional para prop firms — **torneo de candidatos de estrategia** bajo gates mecánicos (Spec Génesis v1.1). Estructura de tooling tomada de [Bajmein/pulse](https://github.com/Bajmein/pulse) y adaptada a Windows.

- **SSoT**: [`docs/SPEC_GENESIS_v1.1_PropTrading_TorneoCandidatos.md`](docs/SPEC_GENESIS_v1.1_PropTrading_TorneoCandidatos.md)
- **Gobernanza**: [`CLAUDE.md`](CLAUDE.md) (comandos/convenciones) · [`AGENTS.md`](AGENTS.md) (flujo SDD)

## Setup (Windows)

Requisitos: [mise](https://mise.jdx.dev), [uv](https://docs.astral.sh/uv/), Docker Desktop, Git for Windows (provee el `bash` que usan las tasks), `gh` autenticado con acceso a `Bajmein/pulse`.

```powershell
cd C:\Users\bbrav\genesis
mise trust
mise install          # python 3.14, uv, LSPs y utilidades CLI (cargo:* requiere toolchain Rust)
mise run setup        # uv sync --all-groups
mise run ci           # lint + ty + test
```

Copia `.env.example` a `.env` y completa los tokens (no se commitea).

## Plugin SDD de pulse (`/pulse:*`)

El plugin vive en `.claude/plugins/pulse/` (skills, agentes por fase, hooks) y el marketplace local en `.claude-plugin/marketplace.json`. Registro en Claude Code:

```powershell
claude plugin marketplace add C:\Users\bbrav\genesis
claude plugin install pulse@genesis
```

Alternativa por sesión (sin instalar): `claude --plugin-dir .claude\plugins\pulse`.

Con el plugin activo, el flujo SDD completo queda disponible como skills:
`/pulse:explore → propose → specify → design → break-to-tasks → apply → review → close` (más `orchestrate`, `diagram-expert` y `pulse-sdd-transition`).

## MCP

`.mcp.json` (scope proyecto) define: `pulse-engine` (Docker, imagen `ghcr.io/bajmein/pulse/mcp-pulse:latest`, repo montado en `/work`), `serena`, `filesystem` y `memory`. Los servers `github`, `context7` y `sequential-thinking` ya están a scope de usuario en esta máquina.

```powershell
mise run docker:pull   # actualizar imagen del engine
mise run mcp:list      # salud de los MCPs
```

## Configuración opcional de Claude Code

`.claude/settings.json.example` trae la config sugerida (permisos, hook de inyección de fase SDD, enforcement de rg/fd). Revísala y renómbrala a `settings.json` si quieres activarla — los hooks ejecutan `.agents/hooks/sdd_context_injector.py` en cada prompt.

## Estado del proyecto

Esqueleto inicial: `src/genesis/{data,strategy,backtest,validation}` vacíos. Próximo paso: **Issue A** (`docs(spec)`: spec definitivo — fija umbrales, universos, ficha The5ers) vía `/pulse:explore`. Las dependencias runtime (`MetaTrader5`, `pandas`, `pyarrow`, …) se agregan en el Issue B; hay wheels de MetaTrader5 para Python 3.14 en Windows (`cp314-win_amd64`).
