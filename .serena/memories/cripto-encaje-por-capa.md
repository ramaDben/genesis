*(2026-08-29 — análisis, no decisión)*

# Incorporar un universo cripto con volumen de exchange: qué encaja y qué no

Cero menciones de cripto en `docs/`, `src/` o el README **[VERIFICADO]** por búsqueda. No está
contemplado en ninguna parte del spec.

## Entra sin fricción

- **Capa 4 completa.** WFA, Monte Carlo, purged K-fold, DSR/PBO y sensibilidad no saben qué
  activo miran.
- **Capa 2.** El contrato `StrategyCandidate` es agnóstico por diseño.
- **El corte diario ya es parámetro.** `FirmProfile` tiene `daily_reset_time` + `daily_reset_tz`,
  así que el 24/7 de cripto **no** rompe el límite de pérdida diaria: el corte lo define la firma,
  no el mercado.
- **El store es agnóstico a la fuente.** El esquema de barra es
  `timestamp, open, high, low, close, tick_volume`; un exportador de exchange escribe lo mismo.
  Solo `mt5_export.py` está atado a MT5.

## Exige extensión real

- **`SymbolFigure` está modelada sobre contratos MT5**: `tick_value`, `tick_size`, `volume_step`,
  `stops_level`, `freeze_level`, `digits`, `swap_long`, `swap_short`, `swap_rollover_day`. Spot
  cripto no tiene swap; los perpetuos tienen **funding rate**, que no es swap (periódico, cambia
  de signo, lo fija el mercado). `swap_rollover_day` (swap triple del miércoles) no tiene análogo.
  No es cosmético: **G3 exige «PF OOS con costos completos, swap incluido»**.
- **`costs.py` cobra `commission_per_lot`.** Los exchanges cobran maker/taker en **puntos básicos
  del nocional**. Modelo distinto, no parámetro distinto.
- **`sessions.py`** es una tabla normativa de sesión de contado por índice resuelta con
  `zoneinfo`. En cripto no existe sesión de contado. Hay precedente de extensión aditiva
  (`FixedUtcWindowSpec`, agregada para el universo FX), pero hay que decidir si 24/7 es «sin
  ventana» o «ventana con menos liquidez».

## La trampa silenciosa — el campo que cambia de significado

`tick_volume: int` en MT5 es **conteo de ticks**, un proxy. Desde un exchange sería **volumen
negociado real**. Mismo nombre, semántica distinta. Y `strategy/common/vwap_engine.py` ya lo
consume como si fuera volumen ("suma acumulada de precio_típico × volumen").

Dos datasets donde la misma columna significa cosas distintas, sin marca que los separe. Si se
incorpora cripto, el marcador de semántica va en la metadata del export, explícito.

## Lo que cripto aporta y hoy no existe

Volumen real. La maquinaria ponderada por volumen de genesis corre sobre un proxy; con datos de
exchange mediría lo que dice medir. Y habilita una familia de primitivas —OBV, perfil de volumen,
delta— hoy inadmisible bajo el criterio del §4.3 del RFC porque no se puede hacer honestamente
sobre conteo de ticks. Ver `mem:arquitecto-estrategias-y-ledger-ensayos`.

## Las dos preguntas bloqueantes, sin responder

1. **¿Alguna prop firm del alcance fondea cripto bajo estas reglas?** No verificado. Los cinco
   gates P salen de `prop_sim`, y todo el veredicto es «¿sobrevive un challenge?». Si nadie
   fondea cripto con límite diario y objetivo de beneficio, la familia P queda sin significado.
   El proyecto ya tiene el mecanismo: `mt5-export confirm-firm-profile`.

2. **¿Cripto es un universo que se EXIGE o entre el que se SELECCIONA?** Es la decisión **D1**
   aplicada (issue #76):
   - exigir que pase en índices **y** en cripto → conjunción, lo hace más difícil, **no cuenta
     ensayos**;
   - correr ambos y quedarse con el que funcionó → **selección disfrazada de robustez**, y
     multiplica el denominador del DSR.

   Incorporar cripto **antes** de resolver D1 duplica el espacio de búsqueda sin que el contador
   se entere — exactamente lo que el ledger existe para impedir.

## Orden recomendado

1. Resolver D1 (issue #76) — decide si cripto suma ensayos.
2. Verificar que exista una firma que fondee cripto; si no, esto es investigación, no torneo.
3. Change de capa 1: exportador de exchange + marcador de semántica de volumen.
4. Change de capa 3: costos por nocional y funding.

Los dos primeros son gratis y decisivos. Los dos últimos van por el ciclo SDD, de a uno (guarda G2).
