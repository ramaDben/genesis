## Reloj del servidor de Moneta y corrección de timestamp (2026-08-28)

Medido contra la cuenta demo real (1058855, MonetaMarkets-Demo): **UTC+2 en invierno (enero),
UTC+3 en verano (julio)**, y el diferencial contra `America/New_York` es **+7h constante en
ambos regímenes** (invierno 2-(-5)=7; verano 3-(-4)=7) — mismas fechas de transición DST que NY.
Mismo patrón NY+7 que `mem:datos-ftmo-y-respaldos` ya había medido para el servidor de FTMO
(coincidencia entre brokers, no verificado si es universal).

**Técnica usada para la corrida institucional (no una aproximación)**: restar 7h a los timestamps
crudos de MT5, y alimentar el resultado a `iter_bars(..., server_tz="America/New_York")` — deja
que el `ZoneInfo` real de genesis maneje las transiciones DST a lo largo de todo el rango
multi-año, en vez de un offset fijo único (`Etc/GMT-3`, usado antes solo para una prueba corta de
4 meses donde no cruzaba ninguna transición). Verificado con `smoke_test_tz.py`: el borde de
marzo 2024 pasa de 05:00 a 04:00 UTC exactamente en la transición, sin `DayBoundaryError`.

`MetaTrader5` SDK es win32-only — todo lo que toca la terminal viva corrió en Python nativo de
Windows (`C:\Python314\python.exe`), con `sys.path.insert(0, r"...\genesis\src")` porque el
paquete no está `pip install`ado ahí. Los backtests/validación (sin dependencia de MT5) corrieron
vía `uv run python` en WSL Ubuntu, que tiene el `pandas>=3.0.5` real del proyecto.
