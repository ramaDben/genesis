# GEMINI.md — genesis

Reglas de operación y gobernanza para agentes en el workspace `genesis`.

## Gate 0: Invariante de Admisión Teórica de Estrategias

Antes de escribir código, scripts, proponer parámetros numéricos o implementar cualquier nueva estrategia o variación de candidato:

1. **Consulta Obligatoria a 2 Fuentes**:
   - **Fuente 1 (Academia Canónica - SSRN / JFE / JF / QJE)**: Identificar paper de referencia, autores, año y mecanismo económico o fricción de microestructura que explica por qué existe el edge.
   - **Fuente 2 (Cuantitativa Institucional Libre - AQR, Man AHL, Alpha Architect)**: Contrastar cómo lo operan los fondos sistemáticos, clusters de volatilidad, advertencias de régimen y modos de falla (ej. reversión a la media por expansión previa, costos de transacción).
2. **Dossier de Admisión Previo**:
   - La primera respuesta del agente ante una idea o patrón debe presentar el dossier con los hallazgos de ambas fuentes antes de cualquier formulación técnica o corrida en el pipeline.
3. **SSoT del Protocolo**:
   - Consultar y cumplir estrictamente con `docs/PROTOCOLO_ADMISION_ESTRATEGIAS.md`.

## Entorno y Ejecución
- Entorno host: Windows PowerShell.
- Comandos en repo: siempre dentro de WSL2 vía `wsl -d Ubuntu -- bash -lc "..."`.
- Dependencias vía `uv`.
