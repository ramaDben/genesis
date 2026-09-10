# Change #103 — Compilador de Genomas Declarativos y Arquitecto de Estrategias (Fase 1)

Fecha: 2026-09-10
Estado: Fase `propose` iniciada.
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

## 2. Artefactos Inicializados en Pulse
- `.pulse/changes/103-compilador-de-genomas-declarativos-y-arquitecto-de-estrategias-fase-1/idea.md` (cierre de fase `explore`)
- `.pulse/changes/103-compilador-de-genomas-declarativos-y-arquitecto-de-estrategias-fase-1/proposal.md` (fase `propose`)
- `.pulse/changes/103-compilador-de-genomas-declarativos-y-arquitecto-de-estrategias-fase-1/state.yaml` (fase activa: `propose`)
