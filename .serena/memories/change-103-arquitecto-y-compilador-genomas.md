# Change #103 — Compilador de Genomas Declarativos y Arquitecto de Estrategias (Fase 1)

Fecha: 2026-09-10
Estado: Fase `apply` completada con éxito. En fase `review`.
Issue: [#103](https://github.com/ramaDben/genesis/issues/103)
Rama: `feat/103-arquitecto-compilador-genomas`
Precedentes y referencias:
- `mem:arquitecto-estrategias-y-ledger-ensayos` (bloqueador del ledger resuelto en #53)
- `mem:costura-inyeccion-candidatos-factories` (PR #69, ranura de `CandidateFactory` y `candidate_config`)
- `mem:change-97-trailing-chandelier-capa-3-y-roadmap-b1` (Change #97, salida Chandelier en Capa 3)
- `docs/research/PROPUESTA_LABORATORIO_DE_ESTRATEGIAS.md` (§5 procedencia y fidelidad, §6 genoma declarativo)

---

## 1. Contexto y Decisión de Inicio

Génesis requería una capa generativa para suministrar hipótesis al torneo institucional sin que el operador ni un LLM escriban código Python imperativo arbitrario (evitando lookahead bias y sobreajuste no auditable).

El Director (Benjamín) y el Arquitecto (Agente) acordaron el protocolo de interacción y el alcance del Change:
1. **El Director lidera la estrategia**: aporta hipótesis de papers académicos o del Playbook y toma las decisiones de capital/gobernanza.
2. **El Arquitecto audita y compila**: cuestiona la lógica económica, exige procedencia y traduce la regla a un archivo YAML declarativo bajo una gramática cerrada.
3. **Piedra Rosetta (B.1)**: el Candidato B (ORB con Gao et al. + RVOL + Chandelier) se transcribe como primer genoma canónico (`candidates/specs/candidate_b1_orb.yaml`). El compilador se valida verificando que reproduzca idénticamente el backtest y el veredicto del Candidato B original.
4. **El Playbook en Fase 2**: los setups del Playbook se someterán a compilación y torneo una vez que el compilador esté verificado contra B.1.

---

## 2. Componentes Construidos (Fase Apply)

1. **Jerarquía de Errores de Dominio (`src/genesis/strategy/genome/errors.py`)**:
   - `GenomeValidationError`: base de errores de validación sintáctica o de tipos.
   - `MissingAcademicProvenanceError`: levantado inmediatamente si falta `paper_ref` o si falta `fidelity` (criterio D1).
     **CORREGIDO el 2026-09-20:** esta línea decía «o si `fidelity` **no es canónico**». Es falso, verificado contra el árbol: `schema.py:129-138` construye `GenomeFidelity(fidelity_raw)` y sólo levanta si el valor **no pertenece al enum** — los cuatro (`canonical`, `interpreted`, `optimized`, `combined`) se aceptan. Lo que sí es obligatorio y no vacío es `paper_ref` (`schema.py:123-127`), y **eso** es lo que hay que liberar para admitir fuentes no académicas. Ver `mem:decision-arquitecto-adjudicador-2026-09-20`.
   - `CompiledCandidateStateError`: violaciones de invariantes en ejecución de estrategia compilada.

2. **Esquema Inmutable y Parser Fail-Fast (`src/genesis/strategy/genome/schema.py`)**:
   - `GenomeFidelity` (`StrEnum`: `canonical`, `interpreted`, `optimized`, `combined`).
   - Dataclasses inmutables con `frozen=True, slots=True`: `GenomeMetadata`, `GenomeUniverse`, `GenomeAlpha`, `GenomeRiskExit`, `StrategyGenome`.
   - Función pura `parse_genome(source: Path | str | Mapping[str, Any]) -> StrategyGenome` con validación estricta de procedencia y tipado.

3. **Candidato Compilado (`src/genesis/strategy/genome/candidate.py`)**:
   - `CompiledGenomeCandidate`: implementa `StrategyCandidate` (`on_bar` forward-only) y `RiskLevelsProvider` (`risk_levels` con pop-on-read).
   - Soporte para momentum Gao et al. (2018), filtro de liquidez institucional RVOL y trailing Chandelier con SL dinámico.

4. **Compilador Puro (`src/genesis/strategy/genome/compiler.py`)**:
   - `compile_genome(source) -> GenomeCandidateFactory`: callable compatible con el protocolo `CandidateFactory`.
   - Inyecta `raw_config` para el cálculo invariante y determinista del hash `trial_id` en el `TrialLedger` (Capa 4).

5. **Caso Testigo Canónico B.1 (`candidates/specs/candidate_b1_orb.yaml`)**:
   - Especificación formal con procedencia académica (Gao et al. 2018), universo US500 M15, ORB 30 min, RVOL > 1.0 y Chandelier 22 / 3.0 ATR.

---

## 3. Criterios de Aceptación y Resultados CI (804 Tests Pasando)

- **A1 / A2 (Sintaxis y Procedencia D1)**: 100% verificado en `tests/strategy/genome/test_parser.py` y `test_schema.py`.
- **A3 / A4 (CandidateFactory e Invarianza de Hash)**: Verificado en `tests/strategy/genome/test_compiler.py`. Dos compilaciones con claves reordenadas producen exactamente el mismo SHA-256 de 64 caracteres.
- **A5 (Equivalencia Matemática B vs B.1)**: Verificado en `tests/strategy/genome/test_b1_equivalence.py`. 100% de coincidencia bit a bit en 5.000 barras sintéticas deterministas y 5.000 barras reales de US500.
- **A6 (Anti-leakage / Forward-only)**: Verificado en `tests/strategy/genome/test_candidate.py`.
- **Suite Institucional Completa**:
  - `uv run pytest`: **804 passed**, 1 skipped, **0 failures**.
  - `uv run ruff check .`: **All checks passed**.
  - `uv run ty check`: **All checks passed**.
  - `uv run deptry src/`: **Success! No dependency issues found**.
  - `uv run bandit -c pyproject.toml -r src/`: **0 issues**.
  - `uv run vulture`: **0 issues**.
