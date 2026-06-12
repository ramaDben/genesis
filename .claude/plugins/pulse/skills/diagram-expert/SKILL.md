---
name: diagram-expert
description: Genera diagramas ASCII/Unicode para arquitecturas, flujos de usuario, FSMs, secuencias y árboles de archivos. Texto puro, versionable en git, legible en cualquier terminal o markdown sin renderer.
when_to_use: Cuando el usuario pida "diagrama", "mapea el flujo", "visualiza la arquitectura", "muestra la estructura", o cuando una explicación se beneficie de un esquema visual. Nunca uses Mermaid, PlantUML ni Draw.io — sólo ASCII/Unicode.
allowed-tools: Read Write Edit Glob Grep
---

# Diagram Expert (ASCII-only)

## Principio

"Above all else, show the data." — Tufte.
Antes de escribir prosa, pregunta: _¿se entiende mejor con un dibujo?_ Si sí, dibújalo.
Texto plano = versionable, diffeable, render-free, copiable a comentarios de código.

## Restricción dura

**Sólo ASCII / Unicode box-drawing.** Nada de Mermaid, PlantUML, Draw.io ni imágenes binarias.
Si el diagrama no cabe en monoespaciado, divídelo — no cambies de formato.

## Glifos canónicos

```
Cajas pesadas       Cajas finas         Doble (énfasis)
┏━━━┓               ┌───┐               ╔═══╗
┃   ┃               │   │               ║   ║
┗━━━┛               └───┘               ╚═══╝

Conectores rectos   Curvas / esquinas   Cruces y T
─ │ ━ ┃             ╭ ╮ ╰ ╯             ┼ ┬ ┴ ├ ┤

Flechas             Decisiones          Sombreado
→ ← ↑ ↓ ↔ ↕         <decision?>         ░ ▒ ▓ █
► ◄ ▲ ▼             /yes\ /no\
```

## Reglas de composición

1. **Una idea por diagrama.** Si supera ~25 líneas o > 12 cajas, parte en _Overview_ + _Detail_.
2. **Alineación monoespaciada.** Cuenta caracteres; mantén anchos consistentes por columna.
3. **Jerarquía por peso de línea:**
   - `━━━` / `┃` / `┏┓┗┛` → elemento primario o boundary.
   - `───` / `│` / `┌┐└┘` → elemento secundario.
   - `- - -` / `┄ ┆` → dependencia opcional, eventual o async.
4. **Etiqueta cada flecha** con el verbo o evento (`→ submit`, `→ on_success`).
5. **Leyenda** al pie si usas más de un estilo de línea o un símbolo no obvio.
6. **No emojis decorativos.** Cero chartjunk.

## Vocabulario por dominio

| Dominio          | Patrón                                                                                          |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| **Arquitectura** | Cajas apiladas por capa (top = entry, bottom = data). Boundary externo con `┏━┓` doble grueso.  |
| **User flow**    | Top→bottom. `( Start )` círculos con paréntesis, `[ Screen ]`, `< decision? >`, `{{ action }}`. |
| **FSM / State**  | Estados en cajas, transiciones `──evento──▶`. Estado inicial con `●──▶`, final con `──▶◉`.      |
| **Sequence**     | Lifelines verticales `│`, mensajes horizontales `──msg──▶`, retornos con `◀- -reply- -`.        |
| **Tree**         | `├── │   └──` estándar Unix. Comentarios alineados con `← descripción`.                         |

## Workflow en Pulse

1. **Localizar antes de crear:** `glob("docs/architecture/**/*.md")` — evita duplicar diagramas.
2. **Ubicación canónica:** ADRs numerados en `docs/architecture/NN-tema.md`. Borradores → `docs/ideas/<slug>/`.
3. **Editar > crear:** si ya existe un bloque ASCII, usa `Edit` puntual en vez de reescribir el archivo.
4. **Encajonar en triple-backtick** (sin lenguaje, o `` ```text ``) para preservar el monoespaciado en GitHub.

## Anti-patterns

- Mermaid, PlantUML, Draw.io, SVG embebido — fuera de scope para esta skill.
- Cajas con anchos desalineados entre filas → el lector pierde la vista.
- Flechas sin etiqueta cuando hay > 1 transición saliente de un nodo.
- Cruces innecesarios — reordena los nodos para que las líneas no se trencen.
- Diagramas > 80 columnas (rompe wrap en terminales y diff views).

## Ejemplos de referencia (alineados a Pulse)

Plantillas listas en `${CLAUDE_SKILL_DIR}/examples/`:

- `hexagonal-architecture.md` — capas Domain / Application / Infrastructure + boundary FastMCP.
- `sdd-state-machine.md` — FSM de las 6 fases SDD (`state:1-explore` → `state:6-close`).
- `fastmcp-sequence.md` — secuencia cliente LLM → servidor FastMCP → skill/resource.
- `plugin-tree.md` — árbol del paquete `src/pulse_plugin/`.

## Output final (obligatorio)

Tras escribir o editar un diagrama, devuelve este resumen:

- **Tipo:** Architecture / Flow / Sequence / State / Tree
- **Ubicación:** `path/relativo.md` (o _Inline_)
- **Tamaño:** N cajas, M flechas, A×B caracteres aprox.
- **Decisiones de diseño:** qué cortaste, qué jerarquía usaste, por qué.
- **Cómo leerlo:** flujo dominante (top→bottom, left→right) y leyenda si aplica.
