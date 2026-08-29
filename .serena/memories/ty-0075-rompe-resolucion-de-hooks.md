*(2026-08-29)*

# `ty` 0.0.75 rompe la resolución de `pulse_hooks_lib` — bump #65 en espera

## Síntoma

Con `ty 0.0.75` (PR #65, sin mergear), `uv run ty check` falla con 5 diagnósticos:

```
error[unresolved-import]: Cannot resolve imported module `pulse_hooks_lib.runtime`
  --> .agents/hooks/sdd_context_injector.py:27:6
```

Reproducible con el venv del proyecto sobre el `main` actual — no es ruido de un CI viejo.

## Causa

`pulse_hooks_lib` no es dependencia del proyecto: lo aportan los hooks del plugin de pulse desde
`.agents/hooks/_lib/`. El `pyproject.toml` lo declaraba así:

```toml
[tool.ty]
environment = { python-version = "3.14", root = ["src", ".agents/hooks/_lib", "."] }
```

Hasta la **0.0.64** eso alcanzaba. Desde la **0.0.75**, `root` dejó de actuar como ruta de
resolución de módulos: en el listado de rutas buscadas que imprime el propio `ty`,
`.agents/hooks/_lib` ya no aparece (solo stdlib, site-packages y `src`).

## Lo que NO es — descartado con evidencia

El riesgo grave sería que `ty 0.0.75` ignorara toda la sección `[tool.ty]`, porque entonces
descartaría en silencio las cuatro reglas estrictas de `[tool.ty.rules]`
(`possibly-unresolved-reference`, `unresolved-attribute`, `invalid-argument-type`,
`invalid-return-type`, todas en `error`) y el type checking se relajaría sin que nadie lo note.

**Descartado**: metiéndole una regla inexistente responde `warning[unknown-rule]`. La config se
lee; solo `root` cambió de semántica.

## Arreglo verificado, sin aplicar

El flag de línea de comandos resuelve los 5:

```
$ uv run ty check --extra-search-path .agents/hooks/_lib
All checks passed!
```

La clave TOML documentada para lo mismo es `extra-paths` bajo `[tool.ty.environment]`, pero
**no surtió efecto** — ni como tabla inline ni como sección propia — pese a que la sección sí se
lee. Puede ser bug de la 0.0.75 o interacción con el `pyproject.toml` **anidado** que existe en
`.agents/hooks/_lib/` (proyecto `pulse-hooks-lib` aparte, con su propio `uv.lock`). No se aisló.

Si se decide aplicar, el flag va en los dos sitios que invocan a `ty`:

- `mise.toml`, tarea `ty` (~línea 127): `run = "uv run ty check"`
- `.github/workflows/ci.yml`, paso *ty check*

## Estado

PR #65 **abierto a propósito**, con este diagnóstico comentado en el hilo. `ty` queda en 0.0.64.
Los otros cuatro bumps (`pyarrow` 25.0.1, `numpy` 2.5.2, `hypothesis` 6.165.10, `ruff` 0.16.5) se
agruparon y mergearon en el **#73** — de a uno se pisaban en `uv.lock`.

## Nota aparte sobre ruff 0.16

`ruff format` amplió su alcance a los bloques de código dentro de Markdown (272 archivos
examinados contra 200 antes), y con eso `.agents/templates/rule-template.md` queda sin formatear.
**No bloquea**: ni CI ni `mise run ci` validan formato, solo corren `ruff check .`. Pero el
próximo `mise run format` va a tocar ese archivo.

Ver `mem:entorno-de-desarrollo` y `mem:preferencias-de-herramientas`.
