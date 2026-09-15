*(2026-09-14 — análisis y decisión. El código descrito fue revertido, no llegó a `main`.)*

# El back-fill de `tick_size`: por qué se revirtió

## Qué era

Un lector tolerante de cuatro líneas en `ArtifactMetadata.from_json`
(`src/genesis/data/metadata.py`, sin commitear): si el `symbol_figure` del payload no traía
`tick_size`, lo **fabricaba** como `10^-digits`.

```python
if figure_raw is not None and "tick_size" not in figure_raw:
    figure_raw = dict(figure_raw)
    digits = int(figure_raw.get("digits", 0))
    figure_raw["tick_size"] = round(10.0 ** (-digits), digits) if digits > 0 else 1.0
```

Venía con su test (`test_artifact_metadata_restores_legacy_symbol_figure_missing_tick_size`), que
deserializaba una ficha real de `US500.cash`.

## El problema que resolvía era real

Los sidecars `.meta.json` de `data/raw/` **son** `ArtifactMetadata` serializados
(`mt5_export.py:342-343`). Censo del 2026-09-14, contado en WSL:

| | Total | Desglose por carpeta |
|---|---|---|
| **Sin `tick_size`** | **2.036** | GER40.cash 270, US500.cash 261, US30.cash 261, XAUUSD 254, US100.cash 252, EURUSD 246, GBPUSD 246, USDJPY 246 |
| Con `tick_size` | 161 | SP500 122, BTCUSDT 30, US100.cash 9 |

Dos consumidores directos: `scripts/run_pipeline.py:126` (`_symbol_figure_from_store`) y
`scripts/enrich_btcusdt_metadata.py:40`. Sin el back-fill, correr el pipeline contra cualquiera de
esos ocho símbolos aborta.

**Los 2.036 son CFDs y forex. Ni un solo sidecar de futuros carece de `tick_size`.** Mantenía vivo
exactamente el universo que el proyecto cerró — ver `mem:pivote-a-prop-de-futuros-cme-2026-09`.

## Los cinco motivos por los que se revirtió

1. **La identidad es falsa en CME.** El ES cotiza con 2 decimales y tick de **0.25**; la fórmula da
   0.01. Como `value_per_point = tick_value / tick_size` (`symbols.py:36`), eso infla el valor por
   punto **25×**. Y `value_per_point` se consume en el P&L de cada trade y en los costos
   (`backtest/simulator.py`) y en el dimensionamiento de posición (`strategy/candidate_b/candidate.py`,
   `strategy/genome/candidate.py`). Acierta para los CFDs y yerra para el destino: está en lo cierto
   sobre el pasado y equivocado sobre el futuro.
2. **Contradice tres cosas escritas.** El docstring de su propio consumidor
   (`run_pipeline.py:123`: *"Lee la ficha real del símbolo del sidecar del export; nunca la
   inventa"*); el de `SymbolFigure` (`symbols.py:18-20`: *"NO DEBE normalizarse antes de
   persistir"*, Change #55); y la tarea D5 del #109.
3. **Enmascara bugs del exportador, no solo artefactos viejos.** El código no distingue *"artefacto
   viejo legítimo"* de *"artefacto nuevo roto"*. Si el exportador CME omite `tick_size` por un bug
   propio, un crash diagnóstico se vuelve corrupción silenciosa. **Este argumento no depende del
   pivote.** Vino de la revisión cruzada.
4. **Contamina el denominador del DSR — y no por el hash.**
   `ledger_extra_trials = len(snapshot.trial_ids - own_trial_ids)` (`verdict.py:915`) es una
   diferencia de conjuntos **sin filtro por símbolo, bróker ni clase de activo**; alimenta G4
   (`verdict.py:219`) y T1 (`verdict.py:514`). Cada corrida CFD que el back-fill habilita escribe un
   `TrialRecord` que penaliza **para siempre** el DSR de los candidatos de futuros.
5. **No hacía falta un fail-fast nuevo.** `metadata.py:101-103` ya envuelve
   `(KeyError, ValueError, TypeError)` en `GenesisDataError` con el mensaje de la excepción **y el
   JSON completo recibido**. Revertir alcanza; no hay change SDD que justificar para renombrar un
   error que ya aborta con contexto.

## Lo que se descartó en el camino

- **Que el back-fill moviera algún hash de procedencia.** No lo hace. `firm_profile_hash`
  (`data/profile.py:100-116`) solo hashea el contrato de la firma; `TrialIdentityContext`
  (`trial_ledger.py:293-303`) son cuatro campos y ninguno incluye la ficha; y `dataset_hash` se
  calcula sobre los bytes del parquet en **escritura**, mientras el back-fill ocurre en **lectura**.
  La analogía con D5 (*"corrompe el denominador del DSR"*) era retórica; el daño real llega por el
  camino 4, que es distinto.
- **Un fail-fast con `DataConfigError` propio.** Sobra, por el motivo 5.

## Hallazgo lateral, sin resolver: "ceguera de ficha"

`compute_trial_id` (`trial_ledger.py:113-136`) hashea `candidate_config`, `dataset_hash_by_symbol`,
`firm_profile_hash` y `risk_profile_hash`. **`SymbolFigure` no entra por ningún lado.** Dos corridas
idénticas salvo `tick_size` (0.25 vs 0.01) producen el **mismo `trial_id`** y colisionan en el
ledger pese a describir supuestos de liquidación distintos.

No lo causa el back-fill y es anterior a él. El #109 está reescribiendo `TrialIdentityContext` en su
tarea D5: es el momento de decidirlo.

Relacionadas: `mem:pivote-a-prop-de-futuros-cme-2026-09`,
`mem:revision-cruzada-atrapa-inferencias-que-ningun-test-atrapa`.
