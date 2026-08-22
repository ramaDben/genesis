# Qué herramienta usar para cada cosa (instrucción del usuario, 2026-08-02)

Regla operativa **obligatoria**, también para los subagentes (incluidos los de Sonnet del
ciclo SDD). Motivo declarado por el usuario: **abaratar el consumo de tokens**.

| Tarea | Herramienta |
|---|---|
| Buscar, leer, editar y actualizar **código Python** | **serena MCP** |
| Editar archivos que **no** son Python (`.md`, `.json`, `.toml`, `.yaml`) | **filesystem MCP** |
| Razonamiento de tareas difíciles | **sequential-thinking MCP** |

## Por qué serena abarata

`find_symbol` / `get_symbols_overview` / `replace_symbol_body` / `insert_after_symbol` /
`replace_in_files` operan sobre el **símbolo**, no sobre el archivo: no hay que cargar el
módulo entero en contexto para cambiar una función. `search_for_pattern` sustituye al Grep
seguido de Read completo.

Patrón correcto:
1. `get_symbols_overview(archivo)` para el mapa.
2. `find_symbol("Clase/metodo", include_body=True)` para el cuerpo exacto.
3. `replace_symbol_body(...)` o `insert_after_symbol(...)` para el cambio.

Antipatrón (caro): `Read` del archivo completo → `Edit` con old_string largo.

## Al delegar en subagentes

El prompt del subagente **debe** incluir esta instrucción explícitamente: los subagentes no
heredan las preferencias de la conversación y por defecto usan Read/Edit/Grep.

Ver también `mem:entorno-de-desarrollo` (rutas UNC del workspace de WSL, que sí requieren
Read/Write normales porque serena apunta al proyecto de Windows).
