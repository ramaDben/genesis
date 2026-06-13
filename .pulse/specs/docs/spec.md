
<!-- change:1-a-docs-spec-spec-definitivo-de-genesis-torneo-de-candidatos -->
# Spec — Issue A: Spec definitivo de genesis (torneo de candidatos)

**Fase**: specify
**Slug**: 1-a-docs-spec-spec-definitivo-de-genesis-torneo-de-candidatos
**Issue**: [#1 — A — docs(spec): Spec definitivo de genesis (torneo de candidatos)](https://github.com/bbenja11/genesis/issues/1)
**SSoT de referencia**: `docs/SPEC_GENESIS_v1.1_PropTrading_TorneoCandidatos.md`
**Fecha**: 2026-06-13
**Tipo**: doc-only (ninguna tarea modifica `src/`; TDD no aplica; criterios de aceptación en formato `rg`/`fd`)

---

## Objetivo

Producir el spec definitivo de genesis cerrando los siete puntos normativos marcados como
"a fijar" o "verificar en Issue A" en el SSoT v1.1 (§11). El artefacto resultante es un
único documento Markdown en `docs/` (addendum o versión v1.2) que sustituye o extiende las
secciones correspondientes y desbloquea la cadena B–K. Ningún punto queda marcado como
"a fijar" o "borrador" al terminar este issue.

---

## Alcance IN

| Categoría | Descripción |
|---|---|
| **R1** | Ficha definitiva de The5ers (§1.3): resolver la base del `daily_loss_limit` (equity vs balance vs el mayor de ambos) y el ancla horaria del corte diario; confirmar o corregir todos los demás campos del borrador. |
| **R2** | Especificación normativa del contrato plugin `StrategyCandidate` (§2.1/§5.1): métodos requeridos, invariante forward-only, esquema mínimo de `EntryIntent`, regla de aislamiento entre candidatos. Sin firma Python. |
| **R3** | Sección normativa completa del Candidato B (§2.3): fijar valores de N (rango), criterio de entrada, stop, sizing, sesiones de contado por índice y cierre forzado. La tabla "a fijar en Issue A" debe quedar con todos sus campos cerrados. |
| **R4** | Universos por candidato: cerrar normativamente los símbolos de A, B y C (incluyendo nombres de símbolo MT5 exactos disponibles en The5ers). |
| **R5** | Umbrales G/C/P/T definitivos (§7): pasar todos los umbrales de "iniciales" a "definitivos" tras el sanity-check de coherencia aritmética (G1 con frecuencia operativa de B; G4/T1 con presupuesto de grid). Solo ajustar lo incoherente; nunca relajar gates. |
| **R6** | Presupuesto de grid y métrica de selección IS del WFA (§6): fijar presupuesto máximo de trials IS por candidato por ventana y confirmar DSR-IS como métrica de selección. |
| **R7** | Bandas de incubación (§10): fijar duración mínima, métricas de consistencia y criterios de salida por degradación y por violación de firma. |

## Alcance OUT (YAGNI — explícitamente fuera del Issue A)

- `prop_profile_the5ers.json`: artefacto de datos estructurado → **Issue B**.
- Stub Python del contrato `StrategyCandidate` (`contract.py`): firma Python ejecutable → **Issue C**.
- Implementación de `sessions.py` con los horarios de sesión → **Issue B**.
- Universo del Candidato A en detalle de símbolo (más allá de la lista normativa) → **Issue F**.
- Candidato C (TSMOM): implementación y validación → **Issue K** (post-veredicto A/B); el universo se lista aquí normativamente.
- Todo código ejecutable bajo `src/`.
- Creación de nuevos issues, PRs o labels.

---

## Requisitos funcionales

### R1 — Ficha definitiva de The5ers

Mapeo a idea.md §"Ambigüedades críticas" y proposal.md §"Ambigüedad crítica de mayor riesgo".

**R1.1** La sección §1.3 del spec definitivo establece sin ambigüedad la base del
`daily_loss_limit`: indica si se calcula sobre (a) equity flotante intradía, (b) balance al
cierre del día anterior, o (c) el mayor de ambos; y precisa cuál de las dos bases aplica
para el gate P3 de `prop_sim`.

**R1.2** La sección §1.3 fija el ancla horaria del corte diario (`daily_reset_time`) en
formato `HH:MM` y zona horaria explícita (UTC o equivalente), alineada con el servidor MT5
de The5ers.

**R1.3** Todos los campos del §1.3 que en el borrador v1.1 estaban marcados como "preliminar"
o "verificar" aparecen con valores definitivos verificados contra los términos vigentes de
The5ers. El campo `equity_basis` del `prop_profile.json` (§1.1) queda resuelto.

**R1.4** Los nombres de símbolo MT5 exactos disponibles en la plataforma de The5ers para los
índices US500, NAS100, US30 y GER40 quedan listados en §1.3 o en la sección de universos
(R4), de forma que `mt5_export.py` pueda usarlos directamente.

### R2 — Especificación normativa del contrato plugin

Mapeo a proposal.md §"2. Especificación normativa del contrato plugin".

**R2.1** El spec define normativamente que `StrategyCandidate` requiere como mínimo el método
`on_bar(bar) → list[EntryIntent]`; describe su semántica incremental (solo consume el estado
de barras con `confirmed_time ≤ t_actual`) y prohíbe explícitamente acceder a barras futuras.

**R2.2** El spec declara el invariante forward-only como contrato normativo: ningún output de
`on_bar(t)` puede depender de barras con `confirmed_time > t`. La violación levanta
`LookaheadError` (mecanismo de enforcement en Issue C).

**R2.3** El spec define los campos mínimos de `EntryIntent`: dirección (long/short),
sizing_hint (fracción de riesgo o lotes), metadatos de candidato (identificador del
candidato, `config_version`). Especifica que el `EntryIntent` es una intención, no una
orden: el embudo del Inspector puede rechazarla y registrar el motivo.

**R2.4** El spec establece la regla de aislamiento: cada candidato registra sus propios
trials; no hay estado compartido entre candidatos; el DSR de cada candidato se calcula
exclusivamente con su historia de trials.

**R2.5** El spec especifica el esquema mínimo de parámetros: cada candidato declara sus
propios parámetros bajo el namespace `candidates.<letra>.*` en `inspector_config.json`.

### R3 — Sección normativa del Candidato B

Mapeo a proposal.md §"3. Sección normativa del Candidato B" y SSoT §2.3 tabla "a fijar".

**R3.1** La tabla del §2.3 queda completa: el campo "Rango de apertura" especifica N ∈ {5,
15, 30} minutos como espacio de búsqueda IS; ningún valor queda marcado como "a fijar".

**R3.2** El criterio de entrada queda fijado: ruptura confirmada con cierre de vela M1 fuera
del extremo del rango (no ruptura intrabar), en la dirección de la primera vela de la sesión.

**R3.3** La regla de stop queda fijada: extremo opuesto del rango como regla primaria; el
parámetro de fracción ATR queda incluido en el espacio de búsqueda IS con su rango explícito.

**R3.4** El sizing queda fijado: vol-targeting con riesgo fijo en % de cuenta por trade; el
rango de búsqueda IS del % de riesgo queda explícito en el spec.

**R3.5** Las sesiones de contado por índice quedan fijadas: apertura y cierre en UTC para
US500, NAS100, US30 y GER40, con nota de ajuste por DST del mercado subyacente.

**R3.6** El cierre forzado queda especificado como invariante: la posición se cierra al último
tick de precio disponible antes del cierre de sesión de contado; `SessionBoundaryError` si
la posición sobrevive al corte.

**R3.7** La regla de noticias queda integrada: sin entrada en ventanas restringidas por la
ficha de la firma según el calendario económico (capa 1, `calendar.py`).

### R4 — Universos por candidato

Mapeo a proposal.md §"4. Universos por candidato".

**R4.1** El universo del Candidato B queda cerrado normativamente: US500, NAS100, US30,
GER40 — sin extensión en v1. Listados con sus nombres de símbolo MT5 exactos en The5ers.

**R4.2** El universo del Candidato A queda listado: índices en horario de contado (de R4.1),
oro y majors en ventana de solapamiento Londres–NY. Símbolos MT5 concretos disponibles en
The5ers incluidos.

**R4.3** El universo del Candidato C queda listado normativamente: FX + metales + índices
para TSMOM. Símbolos MT5 concretos disponibles en The5ers incluidos. (Implementación
diferida a Issue K; el universo se fija aquí para que el DSR de torneo sea calculable.)

**R4.4** Para cualquier símbolo listado en R4.1–R4.3 cuyo nombre en The5ers difiera del
nombre convencional (e.g., SP500 vs US500), el spec indica la correspondencia explícita.

### R5 — Umbrales G/C/P/T definitivos

Mapeo a proposal.md §"5. Umbrales G/C/P/T definitivos" e idea.md §"análisis de coherencia
ligero".

**R5.1** El spec incluye un sanity-check explícito de alcanzabilidad de G1 ≥ 300 trades OOS:
calcula el número esperado de trades OOS con ~700–1.000 apuestas/año del Candidato B en 4
índices bajo una ventana OOS de 6–12 meses; concluye si G1 es alcanzable o requiere ajuste.
(Solo se ajusta si hay incoherencia aritmética; el umbral nunca se relaja hacia abajo.)

**R5.2** El spec incluye un sanity-check explícito de coherencia de G4/T1 (DSR ≥ 0.95) con
el presupuesto de grid fijado en R6: con N_trials del WFA IS y los parámetros libres del
Candidato B, el spec indica si DSR ≥ 0.95 es alcanzable o requiere reducir el presupuesto.

**R5.3** Todos los umbrales del §7 aparecen en el spec definitivo marcados como "definitivos"
(no "iniciales"). Si algún sanity-check detecta incoherencia, el umbral ajustado se
documenta con la justificación aritmética; los demás se ratifican sin cambio.

**R5.4** Los gates G/C/P/T nunca se relajan respecto a los valores del §7 del SSoT v1.1. Si
se ajusta un umbral, la dirección del ajuste es siempre hacia mayor exigencia o sin cambio.

### R6 — Presupuesto de grid y métrica de selección IS

Mapeo a proposal.md §"6. Presupuesto de grid y métrica de selección IS".

**R6.1** El spec fija el presupuesto máximo de trials IS por candidato por ventana WFA
(número entero concreto), derivado del número de parámetros libres y el espacio de búsqueda
de cada candidato; el cálculo es reproducible desde los valores del spec.

**R6.2** El spec confirma DSR-IS como métrica de selección IS del WFA (o justifica
explícitamente si se adopta otra métrica); la elección es la misma que ya señala §6 del SSoT.

**R6.3** El presupuesto fijado en R6.1 es coherente con DSR ≥ 0.95 según el sanity-check
de R5.2: la deflación del DSR esperada con ese presupuesto no hace el gate inalcanzable.

### R7 — Bandas de incubación

Mapeo a proposal.md §"7. Bandas de incubación" y SSoT §10.

**R7.1** El spec fija la duración mínima del forward test de incubación en N semanas (valor
entero concreto), aplicable a todos los candidatos.

**R7.2** El spec define las métricas de consistencia que actúan como criterio de salida por
degradación: como mínimo incluye (a) distribución de slippage real vs backtest, (b) tasa de
rechazo del Inspector por símbolo, y (c) Sharpe rolling sobre la ventana de incubación.
Cada métrica tiene umbral explícito o banda de tolerancia concreta.

**R7.3** El spec establece que cualquier breach diario o total de firma durante la incubación
cancela el forward test inmediatamente (criterio de salida por violación de firma).

**R7.4** Los criterios de salida de R7.2 y R7.3 aplican de forma idéntica a todos los
candidatos (A, B, ensemble); las métricas específicas por candidato (sweeps para A,
aperturas para B) son aditivas, no sustitutivas.

---

## Criterios de aceptación (evals ejecutables — doc-only)

Dado que este issue es doc-only (ninguna tarea toca `src/`), los criterios de aceptación se
expresan como aserciones `rg`/`fd` verificables mecánicamente.

### CA-R1: Ficha definitiva de The5ers

**CA-R1.1** — Resolución de la base del `daily_loss_limit`

```
DADO   el archivo producido en docs/ (spec definitivo v1.2 o addendum)
CUANDO rg 'daily_loss_limit' <ruta_doc>
ENTONCES retorna ≥1 línea que no contiene la cadena 'verificar' ni 'borrador'
         ni 'a fijar'
```

**CA-R1.2** — Ancla horaria del corte diario

```
DADO   el archivo producido en docs/
CUANDO rg 'daily_reset_time' <ruta_doc>
ENTONCES retorna ≥1 línea que incluye un patrón de hora explícita (e.g., 'UTC',
         'HH:MM') y no contiene 'verificar' ni 'a fijar'
```

**CA-R1.3** — Ausencia de campos borrador en §1.3

```
DADO   el archivo producido en docs/
CUANDO rg 'borrador|a fijar|verificar en Issue A' <ruta_doc>
ENTONCES retorna 0 coincidencias en el cuerpo normativo del documento
         (se admite en changelog o notas históricas, no en secciones normativas)
```

**CA-R1.4** — Nombres de símbolo MT5 de The5ers documentados

```
DADO   el archivo producido en docs/
CUANDO rg 'MT5|símbolo' <ruta_doc>
ENTONCES retorna ≥4 líneas (una por índice del Candidato B) con el nombre de
         símbolo exacto disponible en The5ers
```

### CA-R2: Contrato plugin normativo

**CA-R2.1** — Presencia del invariante forward-only

```
DADO   el archivo producido en docs/
CUANDO rg 'forward.only|LookaheadError|confirmed_time' <ruta_doc>
ENTONCES retorna ≥2 coincidencias (invariante documentado en al menos dos lugares:
         definición normativa y cláusula de error)
```

**CA-R2.2** — Campos mínimos de EntryIntent documentados

```
DADO   el archivo producido en docs/
CUANDO rg 'EntryIntent' <ruta_doc>
ENTONCES retorna ≥1 coincidencia que incluye la lista de campos mínimos requeridos
```

**CA-R2.3** — Regla de aislamiento entre candidatos documentada

```
DADO   el archivo producido en docs/
CUANDO rg 'aislamiento|trials.*candidato|candidato.*trial' <ruta_doc>
ENTONCES retorna ≥1 coincidencia que afirma la ausencia de estado compartido
```

### CA-R3: Sección normativa del Candidato B

**CA-R3.1** — Tabla §2.3 completamente cerrada

```
DADO   el archivo producido en docs/
CUANDO rg 'a fijar|a definir|TBD' <ruta_doc>
ENTONCES retorna 0 coincidencias en el bloque de la tabla del Candidato B
```

**CA-R3.2** — N del rango de apertura fijado

```
DADO   el archivo producido en docs/
CUANDO rg 'N ∈|N_minutos|rango.*{5|15|30}' <ruta_doc>
ENTONCES retorna ≥1 coincidencia con el espacio de búsqueda IS explícito
```

**CA-R3.3** — SessionBoundaryError documentada como invariante

```
DADO   el archivo producido en docs/
CUANDO rg 'SessionBoundaryError' <ruta_doc>
ENTONCES retorna ≥1 coincidencia en el contexto del cierre forzado del Candidato B
```

**CA-R3.4** — Sesiones de contado con horarios en UTC

```
DADO   el archivo producido en docs/
CUANDO rg 'UTC|apertura.*contado|contado.*apertura' <ruta_doc>
ENTONCES retorna ≥4 coincidencias (una por cada índice: US500, NAS100, US30, GER40)
```

### CA-R4: Universos por candidato

**CA-R4.1** — Los cuatro índices del Candidato B presentes con símbolo MT5

```
DADO   el archivo producido en docs/
CUANDO rg 'US500|NAS100|US30|GER40' <ruta_doc>
ENTONCES retorna ≥4 coincidencias distintas, cada una con su nombre de símbolo MT5
         en The5ers
```

**CA-R4.2** — Universo del Candidato A listado

```
DADO   el archivo producido en docs/
CUANDO rg 'Candidato A.*universo|universo.*Candidato A|oro.*majors|Londres.*NY' <ruta_doc>
ENTONCES retorna ≥1 coincidencia con lista de símbolos explícita
```

**CA-R4.3** — Universo del Candidato C listado

```
DADO   el archivo producido en docs/
CUANDO rg 'Candidato C.*universo|universo.*Candidato C|TSMOM.*universo' <ruta_doc>
ENTONCES retorna ≥1 coincidencia con lista de símbolos explícita
```

### CA-R5: Umbrales G/C/P/T definitivos

**CA-R5.1** — Ausencia de la etiqueta "iniciales" en el §7

```
DADO   el archivo producido en docs/
CUANDO rg 'valores iniciales|inicial' <ruta_doc>
ENTONCES retorna 0 coincidencias en el contexto de los umbrales G/C/P/T
         (se admite en changelog histórico del v1.1 → v1.2)
```

**CA-R5.2** — Sanity-check de G1 documentado con cálculo

```
DADO   el archivo producido en docs/
CUANDO rg 'G1.*300|300.*OOS|sanity.check.*G1|alcanzabilidad.*G1' <ruta_doc>
ENTONCES retorna ≥1 coincidencia que incluye un cálculo numérico o rango explícito
```

**CA-R5.3** — Sanity-check de DSR/G4 documentado con presupuesto de grid

```
DADO   el archivo producido en docs/
CUANDO rg 'DSR.*0\.95|0\.95.*DSR|G4.*presupuesto|presupuesto.*DSR' <ruta_doc>
ENTONCES retorna ≥1 coincidencia que relaciona el presupuesto de trials con DSR ≥ 0.95
```

**CA-R5.4** — Los gates no se relajan (comprobación de valores mínimos)

```
DADO   el archivo producido en docs/
CUANDO rg 'G1' <ruta_doc>
ENTONCES el valor numérico junto a G1 es ≥ 300 (nunca inferior al SSoT v1.1)
```

### CA-R6: Presupuesto de grid y métrica de selección IS

**CA-R6.1** — Presupuesto de trials IS fijado como número entero

```
DADO   el archivo producido en docs/
CUANDO rg 'presupuesto.*trials|trials.*presupuesto|budget.*IS|IS.*budget' <ruta_doc>
ENTONCES retorna ≥1 coincidencia con un número entero concreto (no un rango abierto)
```

**CA-R6.2** — Métrica de selección IS confirmada

```
DADO   el archivo producido en docs/
CUANDO rg 'DSR.IS|DSR-IS|métrica.*selección.*IS|selección IS' <ruta_doc>
ENTONCES retorna ≥1 coincidencia que confirma DSR-IS como métrica de selección IS
```

### CA-R7: Bandas de incubación

**CA-R7.1** — Duración mínima de incubación fijada

```
DADO   el archivo producido en docs/
CUANDO rg 'incubación.*semanas|semanas.*incubación|duración.*incubación' <ruta_doc>
ENTONCES retorna ≥1 coincidencia con un número entero de semanas explícito
```

**CA-R7.2** — Tres métricas de consistencia con umbrales

```
DADO   el archivo producido en docs/
CUANDO rg 'slippage.*incubación|tasa.*rechazo.*Inspector|Sharpe.*rolling' <ruta_doc>
ENTONCES retorna ≥3 coincidencias (una por métrica), cada una con umbral o banda numérica
```

**CA-R7.3** — Criterio de salida por violación de firma documentado

```
DADO   el archivo producido en docs/
CUANDO rg 'breach.*incubación|violación.*firma.*incubación|cancela.*forward' <ruta_doc>
ENTONCES retorna ≥1 coincidencia que afirma la cancelación inmediata del forward test
```

### CA-Global: Artefacto producido y sin residuos doc-only

**CA-G1** — Existencia del artefacto en docs/

```
DADO   el directorio docs/ del repositorio
CUANDO fd 'SPEC_GENESIS_v1\.2|ADDENDUM.*SPEC|spec.*definitivo' docs/
ENTONCES retorna ≥1 archivo (el nuevo artefacto existe)
```

**CA-G2** — Ninguna modificación en src/

```
DADO   el diff del commit que cierra el Issue A
CUANDO git diff --name-only HEAD~1 HEAD | rg '^src/'
ENTONCES retorna 0 resultados (cambio es estrictamente doc-only)
```

**CA-G3** — El SSoT no contiene más puntos "a fijar" ni "borrador" activos

```
DADO   el archivo del spec definitivo producido
CUANDO rg 'a fijar|borrador|verificar en Issue' <ruta_doc>
ENTONCES retorna 0 coincidencias en secciones normativas activas
```

---

## Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| Rg-1 | La verificación externa de The5ers no resuelve la base del `daily_loss_limit` con certeza (e.g., documentación ambigua en la web). | Documentar la ambigüedad residual en una nota explícita y adoptar la interpretación más conservadora (el mayor de equity flotante y balance del día anterior); registrar como pregunta abierta para la fase de implementación de `prop_sim`. |
| Rg-2 | Los nombres de símbolo MT5 en The5ers difieren de los convencionales, y la correspondencia no puede verificarse sin acceso a la plataforma. | Documentar la lista de correspondencias posibles y marcar como "a confirmar en Issue B" (al conectar la cuenta demo); no bloquear el spec definitivo por esto. |
| Rg-3 | El sanity-check de G1 detecta que con una ventana OOS muy corta el umbral 300 no es alcanzable para algún índice. | El spec lo documenta y propone extender la ventana OOS mínima o excluir ese índice del universo de ese candidato; los gates no se relajan. |
| Rg-4 | El presupuesto de grid coherente con DSR ≥ 0.95 resulta tan pequeño que limita la búsqueda útil. | Documentar el techo de trials como restricción de diseño del WFA; el design-agent de Issue H debe honrar ese techo. |
| Rg-5 | Los umbrales de bandas de incubación son arbitrarios sin datos previos. | Documentarlos como "valores de primera iteración revisables post-incubación"; los criterios de salida por violación de firma son invariantes y no admiten revisión. |

---

## Preguntas abiertas para el design-agent (Issues B y C)

Las siguientes preguntas no bloquean la spec del Issue A pero deben resolverse en las
fases de diseño e implementación de los issues dependientes:

**PA-1** (Issue B): Confirmar en la cuenta demo de The5ers los nombres de símbolo MT5
exactos para US500, NAS100, US30 y GER40. El spec del Issue A lista los nombres esperados
y el Issue B confirma o corrige.

**PA-2** (Issue B): Profundidad de historia de ticks disponible en The5ers. Si la ventana
de ticks es inferior a la necesaria para el modelo de spread por hora, `quality.py` debe
reportarlo; el gate G1 puede requerir extender el universo temporal de M1.

**PA-3** (Issue C): La firma Python exacta del protocolo `StrategyCandidate` (tipado de
`on_bar`, clase base o Protocol, sistema de registro de candidatos). El spec del Issue A
fija la especificación normativa; Issue C elige la forma Python que la implementa.

**PA-4** (Issue C): Mecanismo de enforcement de `LookaheadError`: si es una guard en el
método `on_bar` del simulador, en el store, o en ambos.

**PA-5** (Issue H/I): Forma concreta del grid IS para el Candidato B (grid lineal,
log-lineal, Sobol) dentro del presupuesto fijado en R6.1. El spec del Issue A fija el
presupuesto máximo de trials; el diseño del WFA elige la estrategia de muestreo.

---

## Dependencias y cadena de bloqueo

```
Issue A (este spec) — doc-only, sin dependencias ascendentes
    └── Issue B (feat/data) — depende de R1, R3 (sesiones), R4 (universos)
          └── Issue C (feat/strategy) — depende de R2 (contrato normativo)
                ├── Issue D (smc_engine + diagnóstico señal desnuda A) — paralelo a E
                ├── Issue E (Candidato B completo) ★ prioridad — paralelo a D
                │     └── Issue G (backtest/simulador) — paralelo a D/E
                │           └── Issue H (WFA + MC) — depende de R6 (presupuesto grid)
                │                 └── Issue I (DSR + PBO + sensibilidad)
                │                       └── Issue J (prop_sim + verdict + torneo T1/T2)
                │                             └── Issue K (Candidato C + ensemble)
                └── Issue F (Candidato A completo) — condicional al resultado de D
```

---

## Referencias

- SSoT v1.1: `docs/SPEC_GENESIS_v1.1_PropTrading_TorneoCandidatos.md` — §1.3, §2.1, §2.3, §6, §7, §10, §11
- idea.md: `.pulse/changes/1-a-docs-spec-spec-definitivo-de-genesis-torneo-de-candidatos/idea.md`
- proposal.md: `.pulse/changes/1-a-docs-spec-spec-definitivo-de-genesis-torneo-de-candidatos/proposal.md`
- Issue GitHub: https://github.com/bbenja11/genesis/issues/1
- Doctrina EDD/TDD: `.agents/rules/eval-tdd-conventions.md` — Excepción doc-only (Q5): criterios `rg`/`fd`
- Tooling: `.agents/rules/tooling-conventions.md`
- CLAUDE.md del repo: arquitectura 4 capas, invariantes forward-only, reproducibilidad
