*(2026-08-29 — decisión humana tomada, no propuesta)*

# D1: qué cuenta como un ensayo — RATIFICADA

Issue #76, cerrado el 2026-08-29. Es la primera de las siete decisiones humanas del RFC del
laboratorio y estaba **bloqueando cuatro frentes**: el ledger vacío, el arquitecto de estrategias,
la incorporación de cripto (`mem:cripto-encaje-por-capa`) y la visión multi-venue del usuario.

## Lo decidido

**Decisión 1 — ratificada tal cual, sin enmiendas:**

> Cuenta como ensayo toda dimensión sobre la que SELECCIONAS.
> No cuenta ninguna dimensión sobre la que EXIGES.

**Decisión 2 — opción A: una corrida de diagnóstico cuenta igual.** Es sobre-conteo respecto de la
regla, pero va en la dirección segura del §3.5 y es la única salida imposible de manipular.

## Por qué, en corto (el argumento completo está en el comentario del #76)

- **La regla no es una lista, es un criterio** — *¿habrías reportado este resultado si hubiera
  salido bien?* Por eso clasifica dimensiones que todavía no existen (mandatos, venues, empalme de
  futuros) sin volver a legislar. Una enumeración se rompe con cada eje nuevo.
- **Ya era la semántica del código**: `n_trials_signal_total` cuenta la grilla del WFA y T1 suma
  `(n_candidatos − 1)`; ambas son selección.
- **Sin enmiendas a propósito**: casi toda enmienda concebible a una regla de conteo reduce el
  denominador.
- **B se descartó porque reduce el denominador sin dejar rastro** de qué se excluyó, y porque con
  un arquitecto corriendo en volumen, «diagnóstico» se vuelve el cajón de los ensayos incómodos.
  Aritméticamente A cuesta poco: ×10 ensayos sube el listón 33 %, y la única corrida real dio
  `DSR = 0.0019` contra 0.95 — ningún veredicto habría cambiado.

  **Corrección (2026-09-05).** Una redacción anterior decía «se falla por ~500x». Es un error
  de categoría: `_dsr.py` devuelve `_standard_normal_cdf(...)`, o sea el DSR **es una
  probabilidad**, no una magnitud. 0.19 % contra 95 % no es un cociente de 500 — es casi
  certeza de que no hay edge descontada la búsqueda. Lo detectó una revisión externa, no la
  revisión interna.

**Criterio de revisión declarado:** volver sobre la decisión 2 solo si un candidato falla G4 **y**
el ledger muestra que los registros de diagnóstico son la causa. En ese caso se va a **C**
(registrar ambas, marcadas), nunca a B.

## Las dos consecuencias verificadas — NO «arreglar» ninguna

Parecen contradecirse y no lo hacen: describen los dos regímenes.

- **La biblioteca colapsa.** `compute_trial_id` (`validation/trial_ledger.py`) hashea
  `candidate_config + dataset_hash_by_symbol + firm_profile_hash + risk_profile_hash` — **no
  incluye `symbol`**. Un bundle multi-símbolo escribe una fila por símbolo con el *mismo*
  `trial_id`, y `read_summary` deduplica: un ensayo. Correcto para el caso conjuntivo.
- **El runner separa.** `scripts/run_pipeline.py::_candidate_config` mete `"symbols": [symbol]` en
  la config y evalúa **un símbolo por invocación** ⇒ tres símbolos, tres `trial_id`, tres ensayos.
  Es sobre-conteo cuando se *exige* que pase en todos — pero en **GO-PARCIAL**, que acepta un
  subconjunto de símbolos, es literalmente el renglón «activos donde eliges el que funcionó» y el
  conteo es **exacto**.

> Corolario operativo: «arreglar» el sobre-conteo del caso conjuntivo rompería el conteo honesto
> del caso selectivo. Si alguien encuentra esto en seis meses y lo toma por bug, es deliberado.

`window_config` también viaja dentro de `candidate_config`, así que una corrida de diagnóstico con
ventanas reducidas **no** se deduplica contra la institucional — es el mecanismo por el que la
opción A tiene efecto real.

## Lo que se aceptó con los ojos abiertos

`dataset_hash_by_symbol` participa del `trial_id`: extender el dataset genera ensayos nuevos y los
viejos siguen contando para siempre. El ledger no olvida y **no tiene reset sancionado — el listón
solo sube**. El crecimiento logarítmico lo hace tolerable (§3.4), pero convierte a **D4**
(presupuesto declarado de ensayos) en el único freno que existe.

## Qué sigue abierto

- **D3** (holdout OOS intocable), la otra decisión de fase 0 del RFC: **enmarcada en el issue #81**
  el 2026-08-29, pendiente de decisión humana. Ver `mem:d3-holdout-oos-intocable`.
- `ledger/trials.jsonl` sigue **vacío**: la decisión desbloquea el cableado, no lo ejecuta.
  Ninguna corrida ha llamado `record_trial_completions` todavía
  (`mem:corrida-institucional-2026-08-us500-primera-e2e-real`).

Documento visual: `docs/research/GUIA_QUE_CUENTA_COMO_ENSAYO.html` (2 svg).
Ver `mem:ledger-de-ensayos-decisiones-de-diseno` y `mem:arquitecto-estrategias-y-ledger-ensayos`.
