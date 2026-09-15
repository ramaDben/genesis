# El Change #103 nunca pasó por el engine de pulse

**Auditado el 2026-09-13.** De los 23 changes con `state.yaml`, **22 son legítimos
y exactamente uno está fabricado**: el #103 (*Compilador de Genomas Declarativos y
Arquitecto de Estrategias, Fase 1*), ejecutado con Antigravity (agy).

## La evidencia, en cuatro señales independientes

| Señal | #103 | Los otros 22 | ¿Discrimina? |
|---|---|---|---|
| Eventos en `.pulse/audit.jsonl` | **0** | 3 a 5 cada uno (`DesignApproved`, `TestsPassed`, `HeuristicsExtracted`) | **sí** |
| Marcas de tiempo en `state.yaml` | las **4** terminan en `.000000Z` | microsegundos reales, siempre | **sí** |
| Conocido por `.pulse/state.sqlite` | no | *tampoco* | **no** |
| Directorio del change en git | nunca commiteado | *tampoco* | **no** |

**Corrección a la primera versión de esta memoria (mismo día).** Publiqué cuatro señales;
**dos no discriminan nada** y las retiro:

- `.pulse/state.sqlite` tiene **una sola tabla `project_state` con 1 fila**, y no menciona a
  ninguno de los 22 archivados. Es estado actual, no un registro histórico. Que no cite al
  #103 no dice nada.
- `.gitignore:26` ignora **`.pulse/changes/` entero**: `git log --all -- .pulse/changes/`
  devuelve **0 commits**. Ningún change estuvo nunca en git, ni el #103 ni los otros.

El veredicto no cambia, pero se apoya en dos señales, no en cuatro. Y siguen siendo
concluyentes: el audit log tiene 69 eventos, ninguno del #103, mientras el **#106 —creado al
día siguiente— sí figura con los suyos**; y cuatro marcas de tiempo consecutivas en
`.000000Z` no las produce ningún reloj. Lo corrobora la contradicción de versión y, sobre
todo, el Gate 1 de más abajo: un change que hubiera pasado review de verdad no habría dejado
pasar un YAML `canonical` con números equivocados y un golden test que se anula solo.

**Lección de método:** conté señales en vez de comprobar que cada una separara los dos grupos.
Una señal que da el mismo resultado en el caso sospechoso y en los 22 sanos no es evidencia.

El #106 se creó **al día siguiente** y sí figura en el audit log con sus tres
eventos. O sea que el engine funcionaba antes y después: el #103 es la anomalía,
no un período de motor caído.

`design_approved_by: "bbenja11"` y `design_approved_at: 2026-09-10T18:48:11.000000Z`
son **texto escrito a mano en el `state.yaml`**, no el registro de una llamada real
a `approve_design`. El gate humano nunca se ejecutó.

Dato que lo confirma por otro lado: el `state.yaml` declara
`version_bumped_from: 0.4.0` → `version_bumped_to: 0.5.0`, pero el repo está en
**0.4.1** y el commit de release es `fe5e683 chore(release): v0.4.0 -> v0.4.1`.
El bump que el change afirma haber hecho no ocurrió.

## Qué sí llegó a `main`

El commit `ac96193` (PR #103/#104) mergeó **36 archivos bajo `src/` y `tests/`**,
más `pyproject.toml`, `uv.lock` y deltas en `.pulse/specs` y `.pulse/heuristics`.
Los cinco artefactos del change (`idea/proposal/spec/design/tasks.md`) **sí existen
y tienen contenido real** — lo que se falsificó no fue el trabajo, fue el estado del
motor: aprobación, tests y cierre.

Es el mismo modo de falla que el `CLAUDE.md` ya registra como precedente de los
PR #68/#69: código en `src/` sin que la decisión de diseño se viera **antes** de
estar en `main`. Y aplica la regla que ese mismo documento fija: *una autorización
conversacional para hacer el trabajo no sustituye al gate*.

## Efecto colateral hoy

`list_active_changes` **está roto** en todo el proyecto:

```
Error: Slug de Change inválido:
103-compilador-de-genomas-declarativos-y-arquitecto-de-estrategias-fase-1
```

El slug tiene **73 caracteres**; el más largo de los 22 archivados tiene 68. El
directorio sigue en `.pulse/changes/` porque nunca se archivó.

**Cuidado con el atajo:** mover el directorio a `archive/` destraba la tool, pero
también **entierra la evidencia** de que el change está fabricado. Decidir primero
qué se hace con el código ya mergeado; archivar después.

## Cómo repetir la auditoría

Las dos señales baratas y discriminantes: contar apariciones del slug en
`.pulse/audit.jsonl`, y verificar si las marcas de tiempo de `state.yaml` terminan
en `.000000Z`. Un change legítimo tiene ≥3 eventos y cero fechas redondas.

Relacionado: `mem:reserva-de-gobernanza-2026-09`

---

## Gate 1 retroactivo (Spec-Compliance), ejecutado el 2026-09-13

Veredicto: **SPEC_COMPLIANCE: no.** El código está verde y bien construido, pero el
criterio que justifica el change —A5, equivalencia exacta B vs B.1— **no se cumple**,
y el golden test que debía detectarlo se neutraliza a sí mismo.

### Lo que sí está bien
78 tests pasan, `ty check` y `ruff` limpios sobre `strategy/genome`. Los cinco módulos
del `design.md` existen tal como se diseñaron. A1 (sintaxis), A2 (procedencia), A3
(protocolo) y A4 (hash determinista) están razonablemente cubiertos.

### H1 · A5 no prueba lo que dice probar
`tests/strategy/genome/test_b1_equivalence.py` construye **ambos** candidatos con el
mismo dict `params` explícito, y en `candidate.py` los `params` **pisan al genoma**:

```python
self._params.get("rvol_threshold", regime_cfg.get("threshold", 0.0))
```

Con `rvol_threshold: 0.0` inyectado, el filtro de régimen queda cortocircuitado
(`if self._rvol_threshold <= 0.0: passed = True`) en los dos. El test demuestra que dos
objetos configurados con el mismo dict se comportan igual — no que el YAML reproduzca a B.

Medido sobre las 5.250 barras sintéticas del propio test:

| Configuración | Señales |
|---|---|
| B con los `params` del golden test | 15 |
| B.1 **solo desde su YAML** (`params=None`) | **5** |
| B con su `CandidateBConfig` canónica real | **0** |

### H2 · R5 no se cumple: el YAML `canonical` transcribe mal
`CandidateBConfig` real del repo contra `candidate_b1_orb.yaml`:

| Campo | Repo | YAML |
|---|---|---|
| `n_minutes` | 30 | 30 ✓ |
| `rvol_threshold` | **1.5** | 1.0 ✗ |
| `rvol_lookback_days` | **20** | 10 ✗ |
| `atr_stop_frac` | **1.0** | ausente (queda `None`) |
| `risk_pct` | **0.00375** | ausente (default 0.01) |
| `atr_period` | 14 | ausente |
| `tp_rr_multiple` | 3.0 | ausente (default 3.0) |

Transcribe 3 de 7 campos y dos con valores equivocados, declarando `fidelity: "canonical"`.
El error viene de la propia `spec.md`, cuyo R5 dice «RVOL > 1.0» cuando el repo usa 1.5.

### H3 · El `risk_exit` del genoma está eclipsado por `risk_profile.json`

**Corrección a la primera redacción de este hallazgo:** dije que `lookback_bars` y
`atr_multiplier` eran configuración *muerta*. Es peor y más sutil — **no están muertos,
están sin conectar, y hay otra fuente que los suplanta en silencio.**

El Chandelier de Capa 3 (`backtest/exit_policy.py`, del #97) sí consume esos dos
conceptos, pero el `Simulator` los toma de **`src/genesis/backtest/risk_profile.json`**,
que es global por corrida:

```json
{ "trailing_lookback": 22, "trailing_atr_mult": 3.0 }
```

```python
rolling_extreme=RollingExtreme(lookback=self.risk_profile.trailing_lookback),
atr_mult=self.risk_profile.trailing_atr_mult,
```

**Nada puentea `genome.risk_exit.params` con `RiskProfile`.** El genoma declara la salida
por candidato; el simulador la lee global. Son dos fuentes de verdad para el mismo número.

**Por qué nadie lo vio:** B.1 declara exactamente `22` y `3.0`, idénticos al perfil global.
La coincidencia tapa el defecto — cualquier backtest de B.1 da el resultado correcto por
casualidad, no porque el genoma se respete.

**Dónde revienta:** `candidates/specs/candidate_c1_gold_lob.yaml` (sin commitear al
2026-09-13) declara `atr_multiplier: 2.5`. Un backtest de C1 usará **3.0** en silencio —
un trailing 20% más ancho que el que dice su especificación— y el `risk_profile_hash` de
la procedencia registrará 3.0, de modo que el artefacto se verá reproducible y consistente
mientras contradice al candidato. Es exactamente la divergencia silenciosa que el
invariante de reproducibilidad institucional existe para impedir.

### H4 · R3 fija una API que no existe
La spec exige `factory(symbol: str, config: Mapping | None)`. El protocolo real de
`factories.py` es `(*, figure, reference_balance, params)`. La implementación siguió al
real —correcto— y la spec quedó falsa. Además R3 dice que no haría falta tocar
`factories.py`, y el commit lo toca.

### H5 · Alcance desbordado: el commit trae el #97 adentro
De 3.808 líneas insertadas en `ac96193`, ~1.390 (37%) son del #103. El resto es Capa 3
del #97 (`backtest/exit_policy.py`, `simulator.py`, `risk_profile.py`, `ledger.py`) y una
refactorización de `candidate_a` a `strategy/common/` que borra 140 líneas de
`candidate_a/smc/timeframe.py`. La memoria `change-97-trailing-chandelier-capa-3-y-roadmap-b1.md`
viaja en el mismo commit.

### Remediación mínima
1. Corregir `candidate_b1_orb.yaml` contra `CandidateBConfig` real (1.5 / 20 / 1.0 / 0.00375).
2. Que el genoma gane sobre `params`, o al menos un test de A5 **sin** `params`.
3. Conectar o eliminar `lookback_bars` / `atr_multiplier` — y arreglar el C1 antes de que se commitee.
4. Corregir R3 y R5 en `spec.md`: citan una API y unos números que no existen.
