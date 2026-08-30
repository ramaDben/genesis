*(2026-08-29)*

# Convención de diagramas y documentos visuales

## El skin es el default del plugin, y es deliberado

Los diagramas de `docs/research/` usan **el skin de fábrica** de `diagram-design`
**[VERIFICADO]** por conteo de colores en los tres archivos previos:

```
paper #f5f5f5 · ink #2d3142 · muted #4f5d75 · soft #7a8399 · accent #eb6c36
Instrument Serif (títulos) + Geist (nombres) + Geist Mono (técnico)
```

En genesis el default **es** la casa. Customizarlo rompería la consistencia con lo que ya está
versionado. El gate de §0 de la skill se resuelve por ahí, sin preguntar.

**No hay perfil `genesis` ni marcador `.diagram-design`** — decisión explícita del usuario el
2026-08-29: la paleta propia todavía no está decidida, y hasta entonces se sigue con el genérico.
Cuando se decida, se guarda como perfil con nombre más el marcador en la raíz.

## El repo manda, el artefacto es la vista

Los documentos visuales viven en `docs/research/` como **HTML completos y versionados**
(`<!doctype html>`, `<html lang="es">`, head propio), igual que los tres diagramas previos.

El artefacto publicado es una **vista derivada**, no una fuente paralela: el tool de artefactos
envuelve el contenido en su propio `<!doctype html>` y exige recibir solo el interior, así que el
fragmento se genera desde el canónico con un script, nunca se mantiene a mano. Un archivo no puede
servir a los dos: publicar el documento completo produce etiquetas anidadas y pierde el `<title>`.

Trampa pagada: la primera versión de la guía se escribió como fragmento y se movió al repo tal
cual — no era HTML válido como archivo suelto.

## Verificación obligatoria antes de publicar

La copia instalada del plugin trae `scripts/self_check.py` (contrato de SVG accesible), pero
**no** trae `verify-geometry.py`, así que las seis reglas de conectores del §6 no se comprueban
solas. Hay un verificador propio en el scratchpad de sesión que cubre lo mecanizable: diagonales,
grilla de 4 px y máscaras de etiqueta pisando nodos posteriores.

Dos precisiones que una versión ingenua de ese chequeo se come, y que producen 17 falsos positivos:

- el alcance es **por SVG** — comparar una máscara de una figura contra un nodo de otra explota;
- una máscara **contenida por completo** en un nodo es un badge chip, válido por §6; solo el
  solapamiento **parcial** es fallo.

Detalle de grilla: la plantilla del plugin coloca los badge chips en `Y+6` con texto en `Y+15`,
que cae fuera de la grilla de 4 px del §7. En este repo van en `Y+8` / `Y+17`.

## Qué hay hoy

| Archivo | Qué |
|---|---|
| `DIAGRAMA_EVALUADOR_CAJA_NEGRA.html` | 1 svg |
| `DIAGRAMA_LABORATORIO_ESTRATEGIAS.html` | 2 svg |
| `DIAGRAMA_SISTEMA_GENESIS_LABORATORIO.html` | 1 svg |
| `GUIA_GENESIS_DE_CERO_A_CIEN.html` | guía de onboarding, 5 svg (PR #77) |
| `GUIA_RFC_LABORATORIO.html` | lectura guiada del RFC, 4 svg (PR #78) |

Las dos guías largas se apartan del patrón de 1–2 svg por archivo a propósito: son progresiones,
no diagramas sueltos. El plugin lo contempla con `template-full.html`.

Ver `mem:entorno-de-desarrollo`.
