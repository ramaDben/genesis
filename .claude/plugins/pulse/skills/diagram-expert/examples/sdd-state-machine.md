# Pulse — FSM del flujo SDD (ASCII)

Las labels `state:*` de GitHub proyectan esta FSM. Cada Issue avanza por los seis estados; los rollbacks son legales y comunes.

```text
   ●  new issue
   │
   ▼
 ┌──────────────┐  research done    ┌──────────────┐  spec approved   ┌──────────────┐
 │ 1 · Explore  │ ────────────────▶ │ 2 · Specify  │ ───────────────▶ │ 3 · Design   │
 │              │ ◀──────────────── │              │ ◀─────────────── │              │
 └──────────────┘  missing context  └──────────────┘    spec gap      └──────┬───────┘
                                                                             │
                                                          design approved    │
                                                             ┌───────────────┘
                                                             ▼
 ┌──────────────┐    PR merged      ┌──────────────┐   PR opened     ┌──────────────┐
 │  6 · Close   │ ◀──────────────── │  5 · Review  │ ◀────────────── │  4 · Apply   │
 │              │                   │              │ ──────────────▶ │              │
 └──────┬───────┘                   └──────────────┘ changes request └──────────────┘
        │
        ▼
        ◉  done


 Notas:
   ┌─────────────────────────────────────────────────────────┐
   │  · Sólo "4 · Apply" produce cambios en src/ o tests/.   │
   │  · Sólo "5 · Review" puede mover a "6 · Close" (vía     │
   │    merge de PR; nunca a mano sin PR).                   │
   │  · Cada PR debe terminar en `Refs #<issue>`             │
   │    (git-conventions).                                   │
   └─────────────────────────────────────────────────────────┘
```

**Leyenda:**

- `●` estado inicial · `◉` estado final.
- `▶` / `◀` transición etiquetada con el evento que la dispara.
- Rollbacks (`2→1`, `3→2`, `5→4`) son ciclos esperados, no errores.
