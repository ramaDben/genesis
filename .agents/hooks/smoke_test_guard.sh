#!/usr/bin/env bash
# Pruebas del guardián de escritura con payloads reales de Claude Code.
cd ~/genesis || exit 1

UNC='//wsl.localhost/Ubuntu/home/bbenja11/genesis'

probar() {
  local nombre="$1" payload="$2"
  local salida
  salida=$(printf '%s' "$payload" | uv run .agents/hooks/sdd_validate_tool.py --client claude 2>/dev/null)
  if printf '%s' "$salida" | grep -q '"permissionDecision": "deny"'; then
    echo "DENY   | $nombre"
  elif [ "$salida" = "{}" ]; then
    echo "ALLOW  | $nombre"
  else
    echo "RARO   | $nombre -> $salida"
  fi
}

echo "--- via rapida (debe ALLOW) ---"
probar "docs/ ruta relativa" \
  '{"tool_name":"Write","tool_input":{"file_path":"docs/PRE_REGISTRO_HIPOTESIS.md"}}'
probar "docs/ ruta UNC de Windows" \
  "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$UNC/docs/PRE_REGISTRO_HIPOTESIS.md\"}}"
probar "docs/ ruta absoluta linux" \
  '{"tool_name":"Write","tool_input":{"file_path":"/home/bbenja11/genesis/docs/x.md"}}'
probar ".serena/memories" \
  '{"tool_name":"Write","tool_input":{"file_path":"'"$UNC"'/.serena/memories/nueva.md"}}'
probar "scripts/" \
  '{"tool_name":"Edit","tool_input":{"file_path":"scripts/run_pipeline.py"}}'

echo
echo "--- el ciclo SDD (fase explore, debe DENY) ---"
probar "src/genesis relativo" \
  '{"tool_name":"Write","tool_input":{"file_path":"src/genesis/backtest/simulator.py"}}'
probar "src/genesis por UNC" \
  "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$UNC/src/genesis/validation/verdict.py\"}}"
probar "tests/ (solo en apply)" \
  '{"tool_name":"Write","tool_input":{"file_path":"tests/validation/test_x.py"}}'
probar "serena replace_symbol_body sobre src/" \
  '{"tool_name":"mcp__serena__replace_symbol_body","tool_input":{"relative_path":"src/genesis/validation/verdict.py"}}'
probar "serena insert_after_symbol sobre src/" \
  '{"tool_name":"mcp__serena__insert_after_symbol","tool_input":{"relative_path":"src/genesis/strategy/contract.py"}}'
probar "serena replace_lines sobre src/" \
  '{"tool_name":"mcp__serena__replace_lines","tool_input":{"relative_path":"src/genesis/data/store.py"}}'
probar "filesystem MCP write sobre src/" \
  '{"tool_name":"mcp__filesystem__write_file","tool_input":{"path":"src/genesis/x.py"}}'

echo
echo "--- serena sobre la via rapida (debe ALLOW) ---"
probar "serena replace_symbol_body sobre scripts/" \
  '{"tool_name":"mcp__serena__replace_symbol_body","tool_input":{"relative_path":"scripts/run_pipeline.py"}}'
probar "serena write_memory" \
  '{"tool_name":"mcp__serena__write_memory","tool_input":{"relative_path":".serena/memories/x.md"}}'

echo
echo "--- fuera del workspace (debe ALLOW: sin jurisdiccion) ---"
probar "scratchpad de Windows" \
  '{"tool_name":"Write","tool_input":{"file_path":"C:\\Users\\bbrav\\AppData\\Local\\Temp\\claude\\x\\scratchpad\\nota.md"}}'
probar "scratchpad con slashes" \
  '{"tool_name":"Write","tool_input":{"file_path":"C:/Users/bbrav/AppData/Local/Temp/claude/x/scratchpad/nota.py"}}'
probar "/tmp de linux" \
  '{"tool_name":"Write","tool_input":{"file_path":"/tmp/prueba.py"}}'
probar "otro repo cualquiera" \
  '{"tool_name":"Edit","tool_input":{"file_path":"/home/bbenja11/otro-proyecto/src/x.py"}}'

echo
echo "--- no son herramientas de escritura (debe ALLOW) ---"
probar "Read" '{"tool_name":"Read","tool_input":{"file_path":"src/genesis/x.py"}}'
probar "Bash inofensivo" '{"tool_name":"Bash","tool_input":{"command":"ls"}}'

# ---------------------------------------------------------------------------
# Ejecución de comandos (agregado el 2026-09-12)
#
# `run_command`/`Bash` era un bypass completo: el chequeo por globs sólo mira
# los argumentos de ruta, y un comando no tiene. `sed -i` sobre `src/` pasaba.
# ---------------------------------------------------------------------------
echo
echo "--- comandos que escriben en rutas protegidas (debe DENY) ---"
probar "Bash sed -i sobre src/" \
  '{"tool_name":"Bash","tool_input":{"command":"sed -i s/a/b/ src/genesis/data/metadata.py"}}'
probar "Bash redireccion a src/" \
  '{"tool_name":"Bash","tool_input":{"command":"echo x > src/genesis/nuevo.py"}}'
probar "Bash cp sobre tests/" \
  '{"tool_name":"Bash","tool_input":{"command":"cp /tmp/x.py tests/data/test_x.py"}}'
probar "Bash git checkout sobre src/" \
  '{"tool_name":"Bash","tool_input":{"command":"git checkout HEAD -- src/genesis/"}}'

echo
echo "--- comandos que NO escriben ahi (debe ALLOW) ---"
probar "pytest sobre tests/" \
  '{"tool_name":"Bash","tool_input":{"command":"uv run pytest tests/data -q"}}'
probar "grep sobre src/" \
  '{"tool_name":"Bash","tool_input":{"command":"rg LookaheadError src/"}}'
probar "escritura fuera de rutas protegidas" \
  '{"tool_name":"Bash","tool_input":{"command":"echo x > docs/nota.md"}}'

# ---------------------------------------------------------------------------
# Antigravity CLI (agregado el 2026-09-12)
#
# agy manda `toolCall{name,args}` y espera `{"decision":"deny"}` en la raíz.
# Ninguna de las dos cosas estaba cubierta: el guardián no encontraba nombre de
# herramienta y respondía "allowing", y aun arreglado habría emitido el
# dialecto de Gemini, que agy ignora.  Estos casos existen para que el bypass
# no pueda volver en silencio.
# ---------------------------------------------------------------------------
probar_agy() {
  local nombre="$1" payload="$2" salida
  salida=$(printf '%s' "$payload" | uv run .agents/hooks/sdd_validate_tool.py --client antigravity 2>/dev/null)
  if printf '%s' "$salida" | grep -q '"decision": "deny"'; then
    echo "DENY   | $nombre"
  elif [ "$salida" = "{}" ]; then
    echo "ALLOW  | $nombre"
  else
    echo "RARO   | $nombre -> $salida"
  fi
}

echo
echo "--- Antigravity: dialecto toolCall + decision (debe DENY) ---"
probar_agy "agy write_to_file sobre src/" \
  '{"conversationId":"c","workspacePaths":["/home/bbenja11/genesis"],"toolCall":{"name":"write_to_file","args":{"TargetFile":"src/genesis/data/metadata.py"}}}'
probar_agy "agy replace_file_content sobre src/" \
  '{"conversationId":"c","toolCall":{"name":"replace_file_content","args":{"TargetFile":"src/genesis/backtest/simulator.py"}}}'
probar_agy "agy multi_replace_file_content sobre tests/" \
  '{"conversationId":"c","toolCall":{"name":"multi_replace_file_content","args":{"TargetFile":"tests/data/test_metadata.py"}}}'
probar_agy "agy run_command sed -i sobre src/" \
  '{"conversationId":"c","toolCall":{"name":"run_command","args":{"CommandLine":"sed -i s/a/b/ src/genesis/data/metadata.py"}}}'

echo
echo "--- Antigravity: via rapida (debe ALLOW) ---"
probar_agy "agy write_to_file sobre docs/" \
  '{"conversationId":"c","toolCall":{"name":"write_to_file","args":{"TargetFile":"docs/nota.md"}}}'
probar_agy "agy view_file sobre src/" \
  '{"conversationId":"c","toolCall":{"name":"view_file","args":{"TargetFile":"src/genesis/data/metadata.py"}}}'
probar_agy "agy run_command pytest" \
  '{"conversationId":"c","toolCall":{"name":"run_command","args":{"CommandLine":"uv run pytest tests/data -q"}}}'
