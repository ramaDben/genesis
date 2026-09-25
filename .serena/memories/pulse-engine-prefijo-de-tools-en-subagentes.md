# El MCP de pulse se llama `plugin_pulse_pulse-engine`, no `pulse-engine`

> **OBSOLETA desde 2026-09-25:** pulse se retiró del repo. Ver `mem:pulse-retirado-2026-09-25`.

**Fecha de la observación: 2026-09-14.** Verificado en sesión, no supuesto.

## El hecho

Las tools del engine de pulse están registradas en la sesión con el prefijo

```
mcp__plugin_pulse_pulse-engine__<tool>
```

y **no** con `mcp__pulse-engine__<tool>`, que es como las nombran las definiciones de los
subagentes del plugin (`allowed-tools: mcp__pulse-engine__*`) y las instrucciones de las skills
`/pulse:*`.

## La trampa que costó una transición

En la fase design del Change #109 (2026-09-14) el `design-agent` escribió su `design.md` completo
y después **no pudo** llamar `request_sdd_transition`: buscó la tool por el nombre de la skill,
`ToolSearch` respondió *No matching deferred tools found*, y el agente concluyó —y almacenó en
OMEGA— que **«el MCP `pulse-engine` no está conectado en esta sesión»**. Era falso: el server
estaba arriba y respondió `ok: true` a la primera llamada desde el hilo principal, con el prefijo
correcto.

El modo de falla es el peligroso: no da error de conexión, da *tool inexistente*. Se parece a un
server caído y se diagnostica como tal.

## Qué hacer

- **En el hilo principal**: cargar con
  `ToolSearch("select:mcp__plugin_pulse_pulse-engine__request_sdd_transition, ...")`.
- **Al delegar a un subagente de pulse**: no asumir que puede mover el FSM. Pedirle el artefacto y
  que **devuelva los argumentos** de la transición; el hilo principal la ejecuta. Es además lo
  correcto por otra razón: quien delega es quien tiene que ver la evidencia antes de avanzar la fase.
- **Ante un `No matching deferred tools found` de una tool MCP**: buscar por palabra clave
  (`ToolSearch("pulse transition")`) antes de declarar el server caído. El único server que sí
  estaba caído en esa sesión era `github` (401), y eso sí se reportó como fallo de conexión
  explícito al arrancar.

`mem:pulse-engine-sin-plugin` documenta la vía alternativa (JSON-RPC directo al contenedor) para
cuando el server de verdad no está.
