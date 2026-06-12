---
name: pulse-sdd-transition
description: Solicita transiciones del FSM Spec-Driven Development de Pulse mediante la tool MCP `request_sdd_transition`. Usa esta skill cuando haya que mover una tarea entre `explore`, `specify`, `design`, `apply`, `review` o `close` con evidencia concreta.
allowed-tools: mcp__pulse-engine__request_sdd_transition mcp__pulse-engine__mcp__pulse__get_current_phase mcp__pulse-engine__view_project_dashboard
---

# Pulse SDD Transition

## Proposito

Usa la tool MCP `request_sdd_transition` del servidor `pulse-engine` para solicitar cambios de fase en el FSM SDD de Pulse. Toda transicion debe incluir la fase destino y una lista no vacia de artefactos de evidencia.

## Workflow

1. Confirma que la fase destino sea una de:
   `explore`, `specify`, `design`, `apply`, `review`, `close`.

2. Reune evidencia antes de transicionar.
   Usa rutas reales, preferentemente relativas al repo, hacia specs, disenos, archivos implementados, tests, notas de revision u otros artefactos que justifiquen el cambio.

3. Si la fase actual importa y no esta clara, consulta primero:
   `mcp__pulse-engine__mcp__pulse__get_current_phase`.

4. Solicita la transicion con:
   `mcp__pulse-engine__request_sdd_transition`.

## Shape de la Tool

```json
{
  "input_data": {
    "target_phase": "apply",
    "evidence_artifacts": [
      "docs/specs/example.md",
      "src/pulse/example.py"
    ]
  }
}
```

- `input_data.target_phase`: fase FSM destino.
- `input_data.evidence_artifacts`: lista no vacia de rutas que prueban que la transicion corresponde.

## Guardrails

- No inventes rutas de evidencia.
- No crees labels nuevas de GitHub para fases; Pulse usa la taxonomia canonica `state:*`.
- Si el usuario solo quiere inspeccionar estado, usa `view_project_dashboard` o `mcp__pulse__get_current_phase`, no `request_sdd_transition`.
- Si falta evidencia, localizala en el repo o pide el artefacto antes de solicitar la transicion.

## Ejemplos

Mover a `design` despues de crear una spec:

```json
{
  "input_data": {
    "target_phase": "design",
    "evidence_artifacts": ["docs/specs/pulse-feature.md"]
  }
}
```

Mover a `review` despues de implementar y probar:

```json
{
  "input_data": {
    "target_phase": "review",
    "evidence_artifacts": [
      "src/pulse_plugin/skills/apply/SKILL.md",
      "tests/test_apply_skill.py"
    ]
  }
}
```
