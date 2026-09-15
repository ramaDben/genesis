# Protocolo Institucional de Admisión de Estrategias (Gate 0)

> **SSoT de Gobernanza Teórica para Nuevos Candidatos de Estrategia en Génesis.**  
> Previene la minería de datos ciega (*data snooping*) y el sobreajuste (*overfitting*) exigiendo fundamento microestructural y contraste empírico cuantitativo antes de admitir cualquier candidato en el `TrialLedger`.

---

## 1. Principio Fundamental: Gate 0
Ninguna estrategia puede ser implementada, programada o simulada en el pipeline de Génesis sin haber superado previamente el **Gate 0 de Admisión Teórica**.

El Gate 0 exige que todo patrón o hipótesis responda a una ineficiencia estructural de mercado respaldada por dos pilares de información independientes y rigurosos.

---

## 2. Los Dos Pilares Obligatorios

### Pilar 1: Academia Canónica (SSRN / JFE / JF / QJE / RePEc)
* **Objetivo**: Identificar el mecanismo económico o la fricción de microestructura de mercado que sostiene la anomalía.
* **Requisitos**:
  1. Paper formal publicado o working paper académico de alta reputación.
  2. Autores, año y cita bibliográfica completa.
  3. Explicación de la fuente de rentabilidad: ¿Es una prima de riesgo (compensación por asumir un riesgo indeseado) o una fricción estructural (barreras de liquidez, desbalance de inventario, flujos forzados de fondos o rebalanceo de fin de mes)?

### Pilar 2: Cuantitativa Institucional Libre (AQR, Man AHL, Alpha Architect)
* **Objetivo**: Validar cómo los fondos sistemáticos institucionales observan, ejecutan y advierten sobre dicha anomalía en condiciones reales de mercado.
* **Requisitos**:
  1. Publicaciones, *whitepapers* o blogs de investigación de firmas líderes cuantitativas (ej. AQR Capital Management, Man Institute / Man AHL, Alpha Architect, Two Sigma, CFM).
  2. Identificación de **modos de falla**: ¿En qué regímenes de mercado se destruye la estrategia?
  3. Fricciones de implementación: Impacto de spread, costos de rollover/swaps, slippage y capacidad de capital.

---

## 3. Estructura del Genoma Declarativo con Metadata Gate 0
Todo archivo de candidato bajo `candidates/specs/candidate_<id>.yaml` debe incorporar la metadata institucional de forma auditable:

```yaml
metadata:
  id: "CANDIDATE-<ID>"
  economic_rationale: "Explicación concisa del mecanismo de microestructura."
  sources:
    academic:
      paper: "Título del Paper"
      authors: "Autores (Año)"
      journal: "Revista o SSRN"
    institutional:
      firm: "AQR / Man AHL / Alpha Architect"
      concept: "Concepto cuantitativo aplicado"
      failure_mode: "Régimen o condición donde la anomalía falla"

universe:
  symbol: "CANONICAL_SYMBOL"
  timeframe: "M15"
  session: "SESSION_NAME"

alpha:
  regime_filter:
    ...
  entry_trigger:
    ...

risk_exit:
  kind: "..."
  params:
    ...
```

---

## 4. Transición a Validación Empírica (Gate 1 a Gate 4)
Una vez aprobado el Gate 0:
1. El genoma se compila determinísticamente vía `compile_genome`.
2. Se inscribe en el `TrialLedger` (`ledger/trials.jsonl`) registrando su hash y su configuración.
3. Se somete al WFA, Purged CV, DSR/PBO y PropSim institucional bajo `scripts/run_pipeline.py`.
