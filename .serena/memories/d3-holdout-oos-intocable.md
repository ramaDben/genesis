*(2026-08-29 — hallazgo verificado + decisión enmarcada, NO tomada)*

# D3: el holdout OOS intocable — no existe ninguno

Issue **#81**, abierto el 2026-08-29. Es la única decisión que separa a la fase 0 del RFC de estar
completa, ahora que D1 quedó ratificada (`mem:d1-que-cuenta-como-ensayo`).

## Lo verificado — resuelve el «pendiente de verificar» del §9 R5

- **Cero menciones de `holdout` en `src/`, `scripts/` y `tests/`** [VERIFICADO por búsqueda].
- `_windowing.py::iter_is_oos_bounds` enumera ventanas mientras entren:
  `while k * step + is_window + oos_window <= n_days`. El WFA consume el historial hasta la última
  ventana completa.
- **Las tres etapas que nombra la regla 5 cubren lo mismo**: `run_sensitivity` reusa esa geometría
  compartida (para eso existe `_windowing.py`), y `run_purged_cv(oos_ledger, ...)` consume el ledger
  OOS que produjo el WFA, no el frame crudo.

**Hay un residuo al final y NO es un holdout.** Los días posteriores al `oos_end` de la última
ventana no los toca nadie, pero es el resto de una división: nadie lo declaró, su tamaño cambia cada
vez que se extiende el dataset, y nada impide que la próxima corrida se lo coma. Sin medir todavía
para el dataset actual — es la tarea previa barata del #81.

## Por qué es más urgente que D1, aunque parezca menor

**Es irreversible en una sola dirección.** Un holdout se puede declarar hoy; no se puede declarar
mañana sobre datos que ya se miraron. Cada corrida previa encarece la respuesta, y pasado cierto
punto la opción «reservar» deja de existir.

## El costo, cuantificado

La corrida institucional real dio `n_windows = 5` y `trades_oos = 405`, y **G1 exige ≥ 300**. Son
~81 trades por ventana ⇒ reservar un ancho OOS (126 días) cuesta ~1 ventana y deja ~324, un margen
del 8 %. Reservar dos anchos probablemente **rompe G1** con el dataset actual. Con tres años de
historial, el holdout se paga en ventanas.

## Las tres decisiones del #81

1. **¿Se reserva, y cuánto?** — A: no reservar / B: un ancho OOS / C: dos anchos.
2. **¿Qué pasa al mirarlo?** — informativo (barato, pero un número que no obliga se racionaliza) o
   gate nuevo (contrato de capa 4, ciclo SDD, y el umbral hay que fijarlo a ciegas).
3. **¿Cuántas veces se puede mirar?** — es **D1 aplicada al holdout**: mirar, fallar, ajustar y
   volver a mirar es selección sobre el holdout, cada mirada cuenta como ensayo, y después de la
   segunda el tramo ya no es virgen.

## Nota de implementación (no decisión)

Si sale B o C, no hace falta tocar `_windowing.py`: basta recortar el rango antes de que llegue al
WFA. Lo que sí hace falta es que **el borde del holdout viaje en el artefacto** como una clave de
identidad más, junto a los hashes de dataset y perfiles — un holdout que no queda en el manifiesto
no es auditable.
