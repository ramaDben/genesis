# Pulse — Secuencia FastMCP (ASCII)

Cómo un cliente LLM invoca una Skill cognitiva expuesta por el servidor FastMCP de Pulse. Lifelines verticales, mensajes horizontales con número de paso.

```text
   Client          FastMCP          Settings        Use Case      Resource         Anthropic
  (Claude)         (server)        (pydantic)     (application)  (.agents/skills)    (API)
     │                │                 │              │              │                │
     │  1. initialize │                 │              │              │                │
     ├───────────────▶│                 │              │              │                │
     │                │  2. load env    │              │              │                │
     │                ├────────────────▶│              │              │                │
     │                │   PULSE_*       │              │              │                │
     │                │◀- - - - - - - - ┤              │              │                │
     │  3. capabili-  │                 │              │              │                │
     │     ties       │                 │              │              │                │
     │◀───────────────┤                 │              │              │                │
     │                │                 │              │              │                │
     │  4. tools/call │                 │              │              │                │
     │   run_skill()  │                 │              │              │                │
     ├───────────────▶│                 │              │              │                │
     │                │  5. read spec   │              │              │                │
     │                ├────────────────────────────────────────────▶  │                │
     │                │◀- - - - markdown + frontmatter - - - - - - - ┤                │
     │                │  6. orchestrate │              │              │                │
     │                ├──────────────────────────────▶ │              │                │
     │                │                 │              │  7. msgs.    │                │
     │                │                 │              │     create   │                │
     │                │                 │              ├─────────────────────────────▶ │
     │                │                 │              │◀- - - - - response - - - - - ┤
     │                │  8. result      │              │              │                │
     │                │     (Pydantic)  │              │              │                │
     │                │◀────────────────────────────── ┤              │                │
     │  9. JSON       │                 │              │              │                │
     │◀───────────────┤                 │              │              │                │
     │                │                 │              │              │                │


  Leyenda:
    ──▶  llamada síncrona (request)
    ◀- - retorno / respuesta
    │    lifeline del participante


  Secretos:
    PULSE_ANTHROPIC_API_KEY vive sólo en Settings como SecretStr.
    Nunca cruza el boundary hacia el Client (paso 9 es metadata + payload, no key).
```

**Doc canónica:** `docs/architecture/02-fastmcp-integration.md`, `docs/architecture/04-environment-and-settings.md`.
