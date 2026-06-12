# Pulse — Árbol del Claude Code plugin (ASCII)

Estructura de `src/pulse_plugin/`. Útil para README, onboarding, comentarios en PR.

```text
src/pulse_plugin/
│
├── .claude-plugin/
│   └── plugin.json              ← manifest; declara mcpServers → arranca FastMCP backend
│
├── agents/                      ← 6 subagents, uno por fase SDD
│   ├── 1-explore.md
│   ├── 2-specify.md
│   ├── 3-design.md
│   ├── 4-apply.md
│   ├── 5-review.md
│   └── 6-close.md
│
├── skills/                      ← una skill por fase, invocable con /<phase>
│   ├── 1-explore/
│   │   └── SKILL.md
│   ├── 2-specify/
│   │   └── SKILL.md
│   ├── 3-design/
│   │   └── SKILL.md
│   ├── 4-apply/
│   │   └── SKILL.md
│   ├── 5-review/
│   │   └── SKILL.md
│   └── 6-close/
│       └── SKILL.md
│
└── hooks/
    └── hooks.json               ← PreToolUse / PostToolUse / SubagentStop


Convenciones reflejadas:
  · Box-drawing pesado (├── └──) en vez de guiones — más legible monoespaciado.
  · Comentarios alineados con `←` para anotar el rol de cada nodo.
  · Una entrada SKILL.md por carpeta (formato estándar de Claude Code skills).
  · Sin emojis, sin colores — sólo Unicode box-drawing.

Doc canónica: docs/architecture/06-claude-code-plugin.md
```
