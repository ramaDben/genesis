## Costura de inyección de candidatos (`strategy/factories.py`), PR #69 (2026-08-28)

Contexto: RFC `docs/research/PROPUESTA_LABORATORIO_DE_ESTRATEGIAS.md` §6.4 afirmaba que
`CANDIDATE_REGISTRY` era la fricción que impedía a la capa 4 ejecutar candidatos que no viven en
`CANDIDATE_REGISTRY` (p.ej. un genoma compilado en runtime). **Verificado por grep: falso** —
`CANDIDATE_REGISTRY` tiene cero referencias en `validation/` o `backtest/`, nunca estuvo en el
camino de ejecución. El bloqueador real: `CandidateB` estaba **hardcodeado** (con kwargs
específicos `n_minutes`/`atr_stop_frac`/`risk_pct`) en tres sitios de capa 4 (`wfa.py`,
`dsr_pbo.py`, `sensitivity.py`), y `GridConfig` usa el vocabulario de B. Propiedad correcta del
RFC (hay fricción), conclusión incorrecta (no era el registro).

**Fix**: `genesis.strategy.factories` (nuevo módulo) — `CandidateFactory` Protocol de firma
uniforme `(figure, reference_balance, params: Mapping[str, float]) -> StrategyCandidate`;
`candidate_b_factory` como implementación por defecto/torneo; `default_factory_for(candidate_id)`
resuelve por id, `CandidateFactoryError` (nueva en `strategy/errors.py`) si no hay fábrica.
**Vía paralela a `CANDIDATE_REGISTRY`, no reemplazo** — el torneo A/B/C sigue usando el registro
sin tocar.

`wfa.py`/`dsr_pbo.py`/`sensitivity.py` ganan `candidate_factory: CandidateFactory | None = None`
kwarg opcional; si no se pasa, resuelve por `default_factory_for(candidate_id)`.

**Prueba de que la costura funciona de verdad** (no solo que compila):
`tests/validation/test_factories.py::test_run_wfa_usa_la_fabrica_inyectada` construye un
candidato (`_CandidatoSinRegistrar`) que no hereda de nada y no está en `CANDIDATE_REGISTRY`,
inyecta una fábrica custom, corre `run_wfa` con ese `candidate_id`, y verifica que el candidato
fue instanciado **y ejecutado** sobre barras reales (`barras_vistas > 0`).

`candidate_config: Mapping[str, object] | None` en `CandidateValidationBundle` (ver
`mem:ledger-de-ensayos-decisiones-de-diseno`) ya es la pieza de enganche para la config del
genoma — confirmado usándola en una corrida real, no solo leído en el RFC.

Commit `52dcf2c` en `main`. Ver también `mem:arquitecto-estrategias-y-ledger-ensayos` — el orden
recomendado para desbloquear el laboratorio es: (1) esta costura [HECHO], (2) generalizar
`GridConfig` a un espacio de parámetros con nombre [no iniciado], (3) conectar esto al ledger de
ensayos ya existente (toca la Decisión D1, "qué cuenta como ensayo", deliberadamente diferida),
(4) `ContinuousSpec` (sesiones 24/7) + volumen/order-flow para cripto [solo discutido].
