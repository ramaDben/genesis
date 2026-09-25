# ast-grep Rules

Este directorio almacena las reglas estructurales de `ast-grep` para el repositorio genesis.

## Doctrina (Cognitive Asset Store)

De acuerdo a la arquitectura del proyecto, todas las reglas semánticas y de análisis estático (activos cognitivos) deben residir dentro de `.agents/rules/`. Las reglas de `ast-grep` permiten escanear y validar invariantes estructurales en el código, tales como:

- Dependencias unidireccionales entre las 4 capas de `src/genesis/`.
- Invariantes anti-lookahead (acceso forward-only en `on_bar`).

_(Puedes añadir archivos YAML aquí para que `sg scan` los recoja automáticamente)._

