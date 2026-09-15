
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

<!-- change:18-docs-spec-firma-de-datos-alternativa-ftmo-ficha-candidata-cuenta -->
# Specification: firma de datos alternativa FTMO — ficha candidata, cuenta de datos y veredictos por firma (§1.3/§4.1)

> Change doc-only (Issue #18). Ningún archivo bajo `src/genesis/` cambia. Formaliza como delta
> documental sobre el SSoT vigente `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md`
> (577 líneas) las decisiones ya fijadas en `proposal.md`: versión completa v1.3 (archivo nuevo
> que reemplaza a v1.2, patrón v1.1→v1.2), ficha FTMO + tabla de símbolos con placeholders
> explícitos "a confirmar por la corrida operativa", ampliación de §7.5 (no nueva §7.7) para el
> condicionamiento por firma, y gap heredado de `SymbolFigure`/universo del Candidato A
> declarado no-objetivo.

## Objetivo

Actualizar el SSoT del proyecto de `v1.2` a `v1.3` (archivo nuevo
`docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`, que reemplaza íntegramente a v1.2 como
spec vigente) para que reconozca normativamente:

1. Más de una **ficha de firma candidata** (The5ers + FTMO), no solo una "ficha definitiva".
2. Una **tabla de símbolos MT5 esperados en FTMO** para el universo combinado A+B (8 símbolos).
3. Una **cuenta de datos genérica** ("de la firma activa"), no atada por nombre propio a The5ers.
4. El **condicionamiento explícito de todo artefacto/veredicto a la firma de datos** que lo
   produjo (`firm_profile_hash`, no-transferibilidad, forma canónica `GO (candidato X, firma Y)`).

Esto cierra el vacío normativo señalado por la inaccesibilidad de la cuenta demo/trial de The5ers
(2026-07-11) y la corrida operativa paralela sobre FTMO Free Trial (Issue D #16, ya cerrado en
código), sin bloquear ni depender de esa sesión paralela.

## Alcance IN / OUT

### IN (este change)

- Crear `docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` como archivo nuevo, íntegro,
  que reemplaza a v1.2 como SSoT vigente (v1.2 permanece en el repo como registro histórico, no
  se borra — mismo patrón que v1.1 tras la migración a v1.2).
- Nueva entrada de changelog `v1.2 → v1.3` al inicio del documento.
- Reestructurar §1.3 de "Firma objetivo v1: The5ers — ficha definitiva" a una sección de
  **fichas de firma candidatas** con dos fichas hermanas: The5ers (contenido preservado, sin
  cambios sustantivos) + FTMO (nueva, con placeholders explícitos).
- Nueva tabla de símbolos MT5 esperados en FTMO para el universo combinado A+B (8 símbolos),
  mismo formato de columnas que la tabla existente de The5ers.
- Generalizar §4.1 ("Cuenta de datos") de "una cuenta demo/trial de The5ers" a "una cuenta
  demo/trial de la firma de datos activa (The5ers o FTMO)", preservando verbatim el resto del
  párrafo (incl. `AccountScopeError`).
- Ampliar §7.5 (Veredicto) con un párrafo normativo de condicionamiento por firma
  (`firm_profile_hash`, no-transferibilidad, forma canónica obligatoria).
- Documentar explícitamente los no-objetivos de este change (ver abajo) dentro del propio v1.3.

### OUT (no-objetivos explícitos / YAGNI)

- **No** se crea `src/genesis/data/profiles/ftmo.json` ni ningún archivo JSON de ficha de firma
  versionada nueva — la ficha FTMO vive solo como especificación textual (tabla + prosa) en el
  SSoT. Su creación como artefacto de código queda para un change posterior.
- **No** se modifica `src/genesis/data/profiles/the5ers.json` ni
  `inspector_config.json` — permanecen bit-a-bit idénticos.
- **No** se modifica ningún archivo bajo `src/genesis/` (ni tests bajo `tests/` que ejerciten ese
  código) — es un change puramente documental.
- **No** se crea la excepción `FirmMismatchError` en código; queda solo como nota de trabajo
  futuro en el párrafo nuevo de §7.5, sin normarla en detalle ni asignarle un issue.
- **No** se resuelve el gap heredado del Change #16 (Issue D): `SymbolFigure` real de oro/majors
  (XAUUSD/EURUSD/GBPUSD/USDJPY, universo del Candidato A) sigue sin confirmar en ninguna ficha de
  firma versionada, para ninguna firma. v1.3 documenta este gap como no-objetivo explícito, no lo
  cierra.
- **No** se verifican en esta fase los términos reales vigentes de FTMO (daily loss %, max loss
  %, tipo estático/trailing, `server_tz`, fases challenge/free trial) ni los nombres de símbolo
  MT5 reales — se documentan como placeholders "default conservador — a confirmar por la corrida
  operativa/contra términos vigentes de FTMO", mismo patrón que The5ers usó en v1.1→v1.2.
- **No** se toca §11 (Gobernanza SDD) más allá de lo estrictamente necesario para mantener
  coherencia; este issue no forma parte de la cadena A–K.

## Requisitos funcionales

### R1 — Archivo v1.3 nuevo que reemplaza a v1.2 como SSoT vigente

Crear `docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` con encabezado que declare
`Estado: definitivo (SSoT vigente). Reemplaza íntegramente al v1.2.` (mismo patrón textual que el
encabezado actual de v1.2 respecto a v1.1, `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:3`).
`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` permanece sin borrar en el repo.

**Criterios de aceptación:**
- DADO el archivo `docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  CUANDO `rg -n "Reemplaza íntegramente al v1\.2" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia.
- DADO el repo tras aplicar el change
  CUANDO `fd "SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md" docs`
  ENTONCES el archivo v1.2 sigue existiendo (no se borra).
- DADO `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md`
  CUANDO `git diff --name-only -- docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md`
  ENTONCES no retorna resultados (el archivo v1.2 no se edita).

### R2 — Changelog `v1.2 → v1.3`

Nueva entrada de changelog al inicio del documento v1.3, mismo formato de lista numerada que
`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:7-17` (changelog v1.1→v1.2), que documente
la causa (inaccesibilidad de la cuenta demo/trial de The5ers, pivote operativo a FTMO) y enumere
los puntos cerrados (fichas candidatas, tabla de símbolos FTMO, generalización de §4.1,
condicionamiento por firma en §7.5).

**Criterios de aceptación:**
- DADO `docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  CUANDO `rg -n "Changelog v1\.2 → v1\.3" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia.
- DADO esa misma sección de changelog
  CUANDO `rg -n "The5ers" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` acotado a las
  primeras 30 líneas del archivo
  ENTONCES menciona la inaccesibilidad de la cuenta demo/trial como motivo del cambio de versión.

### R3 — §1.3 reestructurada como "fichas de firma candidatas"

Convertir el encabezado único `### 1.3. Firma objetivo v1: The5ers — ficha definitiva`
(`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:64`) en una sección `1.3` con dos
sub-fichas hermanas: The5ers (tabla de valores y tabla de símbolos preservadas sin cambio de
contenido respecto a v1.2) y FTMO (nueva, mismo patrón de campos de §1.1:
`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:39-51` — `phases`, `daily_loss_limit`,
`max_loss_limit`, `daily_reset_time`, `equity_basis`, `consistency_rule`, `news_restrictions`,
`weekend_holding`, `profit_split`/`payout_cycle`, `challenge_cost`, `max_lots`/`max_positions`).

**Criterios de aceptación:**
- DADO `docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  CUANDO `rg -n "Fichas de firma candidatas" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia.
- DADO ese mismo archivo
  CUANDO `rg -n "The5ers" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` y
  `rg -n "FTMO" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES ambas retornan ≥ 1 coincidencia dentro de §1.3.
- DADO la tabla de valores de The5ers en v1.3
  CUANDO se compara línea a línea contra `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:66-79`
  ENTONCES el contenido de valores (daily_loss_limit 5%, daily_reset_time
  `00:00 America/New_York`, max_loss_limit 10%, etc.) es idéntico.

### R4 — Contenido normativo mínimo de la ficha FTMO

La ficha FTMO nueva en §1.3 debe incluir, como mínimo, los mismos campos que la tabla de The5ers
(`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:66-79`): plataforma, `daily_loss_limit`
(% y base de cálculo), `daily_reset_time` + zona horaria explícita (`server_tz`), `max_loss_limit`
(% y tipo estático/trailing), fases challenge/free trial, `news_restrictions`, `weekend_holding`.
Cada valor no verificado contra fuente externa debe marcarse explícitamente como
`"default conservador — a confirmar contra términos vigentes de FTMO / contra la corrida
operativa"` (mismo patrón textual que
`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:70-71` usa para The5ers).

**Criterios de aceptación:**
- DADO la ficha FTMO en v1.3
  CUANDO `rg -n "default conservador" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia dentro de la sub-ficha FTMO.
- DADO la ficha FTMO en v1.3
  CUANDO `rg -n "daily_reset_time" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` y
  `rg -n "server_tz|zona horaria" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES ambas retornan ≥ 1 coincidencia dentro de la sub-ficha FTMO.
- DADO la ficha FTMO en v1.3
  CUANDO se listan sus campos documentados
  ENTONCES cubre como mínimo: `daily_loss_limit`, `max_loss_limit`, `daily_reset_time`+zona
  horaria, fases challenge/free trial, `news_restrictions`, `weekend_holding` (ningún campo del
  patrón §1.1 queda omitido sin justificación explícita).

### R5 — Tabla de símbolos MT5 esperados en FTMO (universo combinado A+B, 8 símbolos)

Nueva tabla de símbolos MT5 esperados en FTMO, mismo formato de columnas que la tabla existente
(`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:85-90`: *Nombre convencional* / *Símbolo
MT5 esperado* / *Alias posibles* / *Subyacente*), cubriendo los 8 símbolos del universo combinado
A+B: US500, NAS100, US30, GER40 (universo B, `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:196-201`)
+ XAUUSD, EURUSD, GBPUSD, USDJPY (símbolos adicionales del universo A,
`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:209-218`). Los nombres de símbolo FTMO se
documentan como "esperados, a confirmar por la corrida operativa", nunca como definitivos.

**Criterios de aceptación:**
- DADO la tabla de símbolos FTMO en v1.3
  CUANDO se cuentan sus filas de datos
  ENTONCES contiene exactamente 8 filas: US500, NAS100, US30, GER40, XAUUSD, EURUSD, GBPUSD,
  USDJPY.
- DADO esa tabla
  CUANDO `rg -n "Nombre convencional.*Símbolo MT5 esperado.*Alias posibles.*Subyacente" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  (o el patrón de cabecera equivalente ya usado en v1.2) ENTONCES retorna ≥ 1 coincidencia para la
  tabla FTMO (mismo formato de columnas que la tabla existente de The5ers).
- DADO esa tabla
  CUANDO `rg -n "a confirmar" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` acotado al
  párrafo posterior a la tabla FTMO
  ENTONCES retorna ≥ 1 coincidencia (nota de "a confirmar por la corrida operativa").

### R6 — §4.1 generaliza "cuenta de datos" a la firma activa

Reescribir el primer punto de la política de extracción
(`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:296`: *"una cuenta demo/trial de The5ers
sobre el mismo servidor MT5..."*) a una forma genérica del tipo *"una cuenta demo/trial de la
firma de datos activa (The5ers o FTMO) sobre el mismo servidor MT5..."*, preservando verbatim el
resto del párrafo, incluyendo la referencia al guard `AccountScopeError`
(`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:298`) sin modificarla.

**Criterios de aceptación:**
- DADO §4.1 en v1.3
  CUANDO `rg -n "firma de datos activa" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia.
- DADO §4.1 en v1.3
  CUANDO `rg -n "The5ers o FTMO|The5ers.*FTMO" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia dentro de §4.1.
- DADO §4.1 en v1.3
  CUANDO `rg -n "AccountScopeError" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia con el mismo texto que
  `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:298` (verificación textual sin cambios
  en el guard descrito).

### R7 — Condicionamiento por firma en §7.5 (ampliación, no nueva sección)

Ampliar §7.5 (Veredicto, `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:449-454`) con un
párrafo normativo nuevo que establezca: (a) todo artefacto/veredicto registra `firm_profile_hash`
como parte de su metadata de reproducibilidad (coherente con
`src/genesis/data/profile.py:100-116` `firm_profile_hash()` y con
`src/genesis/validation/verdict.py:983,1004,1044,1062` donde `firm_profile_hash` ya es parámetro
obligatorio); (b) un veredicto no es transferible entre firmas sin re-corrida completa (un GO
obtenido con datos FTMO no es válido para The5ers ni viceversa); (c) `GO (candidato X, firma Y)`
es la forma canónica obligatoria del veredicto cuando existe más de una firma candidata — nunca
`GO (candidato X)` a secas. Incluir una nota explícita de que una eventual excepción
`FirmMismatchError` queda como trabajo futuro, sin normarla en detalle ni crearla en código.

**Criterios de aceptación:**
- DADO §7.5 en v1.3
  CUANDO `rg -n "firm_profile_hash" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia dentro de §7.5.
- DADO §7.5 en v1.3
  CUANDO `rg -n "no (es )?transferible|no-transferib" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia dentro de §7.5.
- DADO §7.5 en v1.3
  CUANDO `rg -n "GO \(candidato X, firma Y\)|forma canónica" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia que declara esa forma obligatoria (no solo descriptiva, como
  ya ocurre en v1.2).
- DADO §7.5 en v1.3
  CUANDO `rg -n "FirmMismatchError" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia explícitamente marcada como nota de trabajo futuro (no como
  requisito de implementación).
- DADO el repo completo tras aplicar el change
  CUANDO `rg -n "class FirmMismatchError" src/genesis`
  ENTONCES no retorna resultados (la excepción no se crea en código).
- DADO v1.3
  CUANDO se verifica que la ampliación vive en §7.5
  ENTONCES `rg -n "^### 7\.7" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` no retorna
  resultados (no se crea una nueva subsección 7.7).

### R8 — No-objetivos documentados explícitamente en v1.3

v1.3 documenta, en una nota o sub-apartado explícito (dentro de §1.3, §2.x o §11, según mejor
encaje editorial), los no-objetivos de este change: (a) el gap heredado de `SymbolFigure`
real/universo del Candidato A (`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:220`,
"a confirmar en Issue B" pendiente) no se resuelve aquí para ninguna firma; (b) no se crea
`profiles/ftmo.json`; (c) `profiles/the5ers.json` e `inspector_config.json` permanecen
intactos; (d) no hay cambios en `src/genesis/`.

**Criterios de aceptación:**
- DADO v1.3
  CUANDO `rg -n "no se (resuelve|extiende)|fuera de alcance|no-objetivo" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES retorna ≥ 1 coincidencia que mencione explícitamente el gap de `SymbolFigure`/universo
  del Candidato A como no resuelto por este change.
- DADO el repo tras aplicar el change
  CUANDO `git diff --stat -- src/genesis/data/profiles/the5ers.json src/genesis/strategy/inspector_config.json`
  ENTONCES no retorna resultados (ambos archivos intactos).
- DADO el repo tras aplicar el change
  CUANDO `fd "ftmo.json" src/genesis`
  ENTONCES no retorna resultados (no se crea ficha JSON de FTMO).

### R9 — Preservación íntegra del resto del documento

Todas las secciones de v1.2 no mencionadas en R1–R8 (§1.1, §1.2, §2.1–§2.5 salvo la nota de
no-objetivo de R8, §3, §5, §6, §7.1–§7.4, §7.6, §8, §9, §10, §11) se preservan en v1.3 con
contenido normativo idéntico, salvo ajustes de numeración/referencias cruzadas estrictamente
necesarios por la reestructuración de §1.3.

**Criterios de aceptación:**
- DADO v1.2 y v1.3
  CUANDO se compara la tabla de gates G/C/P/T (`docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md:406-468`)
  contra la tabla equivalente en v1.3
  ENTONCES los valores numéricos de los umbrales (G1 ≥ 300, G3 ≥ 1.3, G4 ≥ 0.95, P1 ≥ 50%, T1 ≥
  0.95, etc.) son idénticos, sin relajaciones.
  ENTONCES `rg -n "≥ 300|≥ 0\.95|≥ 1\.3" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  retorna las mismas coincidencias numéricas que en v1.2 para esas filas.
- DADO §11 (Gobernanza SDD) en v1.3
  CUANDO `rg -n "Issue A|Issue B|Issue K" docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`
  ENTONCES la tabla de issues A–K permanece presente y sin alterar su cadena de dependencias.

## Invariantes (verificación mecánica global)

- **Gates nunca se relajan**: ningún umbral numérico de §7.1–§7.4 cambia entre v1.2 y v1.3 (R9).
- **`profiles/the5ers.json` e `inspector_config.json` intactos**:
  `git diff --name-only -- src/genesis/data/profiles/the5ers.json src/genesis/strategy/inspector_config.json`
  no retorna resultados tras aplicar el change (R8).
- **Sin artefactos ejecutables nuevos**: no se crean scripts, CLIs ni excepciones de código.
- **Sin cambios en `src/genesis/`**: `git diff --name-only | rg '^src/genesis/'` → 0 resultados
  (excepción doc-only de `.agents/rules/eval-tdd-conventions.md`, adaptada de `src/pulse/` a
  `src/genesis/` para este repo).
- **Suite de pytest existente permanece verde**: `uv run pytest` sin fallos nuevos tras aplicar
  el change (no debería haber cambios de comportamiento, pues no se toca código).

## Riesgos

- **Deriva de la corrida operativa paralela**: si la sesión paralela que ejecuta el diagnóstico
  sobre FTMO Free Trial concluye con valores reales (server_tz, nombres de símbolo confirmados,
  términos daily/max loss) antes de que este change llegue a `apply`, los placeholders de R4/R5
  quedarían desactualizados el mismo día en que se escriben. Mitigación: si ocurre, se abre un
  change de seguimiento `docs(spec): backfill ficha FTMO confirmada` en vez de bloquear este
  change (decisión ya fijada en `proposal.md`, sección "Decisiones propuestas... punto 2").
- **Ambigüedad de "verificación externa" para FTMO**: a diferencia de The5ers (Issue A tuvo
  acceso a fuente externa antes de cerrar v1.1→v1.2), este change doc-only no verifica términos
  FTMO contra una fuente externa vigente — depende de que el checklist "default conservador — a
  confirmar" sea aceptado como suficiente por el humano en el gate `DESIGN → APPLY`.
- **Fricción editorial de reestructurar §1.3**: convertir una sección de "ficha única" en
  "fichas candidatas" sin romper referencias cruzadas de §2.x/§7.3/§7.5 que hoy asumen
  implícitamente "la firma" (singular) requiere cuidado en `design` para no introducir
  inconsistencias de numeración.

## Preguntas abiertas (para design / humano)

1. **Ubicación editorial exacta de la nota de no-objetivo (R8)**: ¿vive como nota al pie de §1.3
   (junto a la tabla de símbolos FTMO), como ampliación de la nota ya existente en §2.x línea 220,
   o como entrada explícita en el nuevo changelog de v1.3? No bloquea specify; se decide en
   design con el mejor encaje editorial del documento completo.
2. **Confirmación humana de la decisión de versión completa v1.3** (vs. addendum): ya
   recomendada en `proposal.md` como punto a escalar; sigue pendiente de ratificación humana
   explícita antes de `design`.
3. **Sincronía con la sesión paralela FTMO**: si concluye antes de `apply` con datos reales,
   ¿specify/design deben incorporarlos ahora o se documenta como change de seguimiento? Ver
   Riesgos arriba — la decisión propuesta es "change de seguimiento", pero requiere
   confirmación humana explícita.
4. ~~Ruta real de `inspector_config.json`~~ — **resuelta en esta fase**: confirmada en
   `src/genesis/strategy/inspector_config.json` (ya reflejada en los criterios de aceptación de
   R8 e Invariantes arriba). Sin ambigüedad restante.

<!-- change:20-docs-spec-backfill-de-la-ficha-ftmo-valores-confirmados-por-el-s -->
# Specification: Backfill de la ficha FTMO (§1.3.2) con valores confirmados por el sondeo de la corrida D

**Issue**: #20 · **Change**: `20-docs-spec-backfill-de-la-ficha-ftmo-valores-confirmados-por-el-s`
**Tipo**: doc-only (sin código en `src/genesis/`)

## Objetivo

Cerrar en el SSoT los placeholders "default conservador — a confirmar" que la ficha FTMO
(§1.3.2 de `docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`, issue #18 / PR #19,
commit `97f173c`) dejó deliberadamente abiertos, sustituyéndolos por los valores que el
sondeo operativo de la corrida D (2026-07-12) y el dashboard FTMO del usuario confirmaron
empíricamente, sin tocar ningún gate ni crear código nuevo.

## Alcance

### IN

1. Archivo nuevo `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` (copia íntegra de
   v1.3 + edición quirúrgica de las zonas listadas en Requisitos).
2. Bloque "Changelog v1.3 → v1.4" al inicio del archivo nuevo, narrando el backfill y su fuente.
3. Sustitución de 4 celdas de la ficha §1.3.2 (`server_tz`, `daily_reset_time`,
   `daily_loss_limit`, `max_loss_limit`) y de la nota/estado de la tabla de símbolos.
4. Nota nueva "Historia disponible en el Free Trial (FTMO)" en §1.3.2, con referencia cruzada
   breve desde §4.1.
5. Verificación de si algún archivo versionado fuera de `docs/` apunta al nombre de archivo del
   SSoT y, si aplica, decisión documentada de actualizarlo o no (ver R11).

### OUT (YAGNI / no-alcance, heredado del issue y el proposal)

- No se reconcilian ni generan veredictos de trading (bug de zona horaria de `iter_ticks`,
  issue hermano #21, paralelo y no bloqueante).
- No se crea `profiles/ftmo.json` versionado ni ningún loader/esquema de código nuevo.
- `profiles/the5ers.json` y `src/genesis/strategy/inspector_config.json` no se tocan.
- Los gates G/C/P/T (§7.1-7.4) y el criterio mecánico de archivo (§2.2.1) no se relajan ni
  se modifican — quedan idénticos por construcción (fuera de las zonas editadas).
- No se resuelve el gap de `SymbolFigure` real de oro/majors del universo del Candidato A
  (persiste como no-objetivo heredado de v1.3, §2.x).
- No se resuelve la regla de cambio DST de `server_tz` — queda documentada como pendiente,
  no como cerrada.
- Los placeholders sin evidencia empírica (`min_profitable_days`, `news_restrictions`,
  `weekend_holding`, `consistency_rule`, `profit_split`/`payout_cycle`, `challenge_cost`,
  `max_lots`/`max_positions`, EAs, "Programa de referencia") permanecen "a confirmar".
- No se edita ni se borra `docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` (queda
  intacto como snapshot histórico, igual que v1.1 y v1.2).
- No se mueven, versionan ni comprometen a git los artefactos de `out/run_d/`; su cita en
  v1.4 es como fuente informativa de sesión, no como fuente normativa (ver R1 y R9).
- No se cita `firm_profile_hash` (`465ae475…`) en el spec: no hay `profiles/ftmo.json`
  versionado al que anclarlo todavía (ver Riesgos/Preguntas abiertas).

## Requisitos funcionales

### R1 — Vehículo: archivo nuevo v1.4, no addendum, no edición in-place

Se crea `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` como copia completa de
`docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` con edición quirúrgica únicamente en
las zonas de R2-R9. `docs/SPEC_GENESIS_v1.3_...md` **no se edita ni se borra**. Encabezado de
v1.4: título "Spec Génesis v1.4", fecha 2026-07-12, "Estado: definitivo (SSoT vigente).
Reemplaza íntegramente al v1.3.".

**Decisión fijada**: sigue el precedente v1.1→v1.2 y v1.2→v1.3 (archivo nuevo + changelog),
descartando addendum-en-v1.3 y edición in-place (rompería trazabilidad histórica: v1.3
documentó honestamente qué no se sabía el 2026-07-11).

### R2 — `server_tz` confirmado con matiz DST pendiente

Fila `server_tz` de §1.3.2 pasa de `Europe/Prague (CET/CEST)` / "a confirmar" a
`Europe/Athens` (GMT+2/+3, estilo EET/EEST), offset **+3** confirmado el 2026-07-12
(sondeo corrida D, issue #20). Debe documentar explícitamente que es un best-fit de una
sola observación de verano y que la regla de cambio DST (fechas UE vs. EE. UU.) queda
**pendiente**, resoluble con probes M1 de la semana 2025-10-26 → 2025-11-02.

**Decisión fijada**: se redacta como "confirmado (offset base) con matiz DST pendiente" —
no como "parcialmente confirmado" ni se traslada a la lista de placeholders sin evidencia,
porque el offset base sí tiene evidencia directa.

### R3 — `daily_reset_time` desanclado de `server_tz`

Fila `daily_reset_time` de §1.3.2 se corrige: el reset del daily loss de FTMO sigue siendo
medianoche **`Europe/Prague`** (CE(S)T, términos vigentes de FTMO) — zona **distinta** de
`server_tz` (`Europe/Athens`, R2). La redacción actual de v1.3 (línea 140) trata ambas zonas
como si fueran una sola ("en el `server_tz` de FTMO, típicamente Europe/Prague") y debe
eliminarse esa equivalencia. Se recalcula la equivalencia UTC sobre `Europe/Prague`
(23:00 UTC en CET/invierno, 22:00 UTC en CEST/verano) — sin cambio respecto al valor
numérico de v1.3, pero con atribución de zona corregida.

### R4 — `daily_loss_limit` confirmado (5%)

Fila `daily_loss_limit` de §1.3.2: se retira "a confirmar contra términos vigentes de
FTMO / la corrida operativa"; se confirma **5%** (Free Trial 50.000 USD → 2.500 USD),
citando el dashboard FTMO del usuario, 2026-07-12, como fuente. El valor numérico no
cambia respecto a v1.3.

### R5 — `max_loss_limit` confirmado (10% estático)

Fila `max_loss_limit` de §1.3.2: se retira "a confirmar contra términos vigentes de FTMO";
se confirma **10%, tipo estático, ancla balance inicial** (Free Trial 50.000 USD →
5.000 USD), citando el dashboard FTMO del usuario, 2026-07-12. El valor numérico no cambia
respecto a v1.3.

### R6 — Tabla de símbolos: estado "confirmados"

La nota de apertura de la tabla de símbolos (§1.3.2, "esperados, a confirmar por la corrida
operativa") y su nota de cierre pasan a "confirmados (patrón PA-1, sondeo corrida D, issue
#20, 2026-07-12)". **Ningún nombre de símbolo ni alias cambia**: los 8 (`US500.cash`,
`US100.cash`, `US30.cash`, `GER40.cash`, `XAUUSD`, `EURUSD`, `GBPUSD`, `USDJPY`) coincidieron
exactamente con los reales resueltos por el terminal. La confirmación del `SymbolFigure`
real de oro/majors sigue **fuera de alcance** (§2.x) — cláusula que se conserva.

### R7 — Nota nueva de historia disponible del Free Trial

Se añade una subsección nueva dentro de §1.3.2 (después de la tabla de símbolos):
"Historia disponible en el Free Trial (FTMO)", con el contenido: ticks con profundidad
≥12 meses para los 8 símbolos, con hueco puntual confirmado (`NAS100`, sin ticks el
2025-07-07); M1 disponible desde ~2025-10-22 para los 4 índices + `XAUUSD`, y desde
~2025-11 a ~2025-12 para los 3 majors FX (`EURUSD`, `GBPUSD`, `USDJPY`). Fuente: sondeo
`probe_depth.py`, issue #20, 2026-07-12. Se añade una referencia cruzada breve (una
oración) desde §4.1 (bullet "Realidad de profundidad de ticks") apuntando a esta nota.

**Decisión fijada**: la nota vive en §1.3.2 (característica de *esa* firma de datos
específica), no en §4.1 (política general), con referencia cruzada desde §4.1 — se
prefiere esta ubicación porque el issue ancla el checklist explícitamente en §1.3.2 y
porque §4.1 ya tiene un bullet general análogo que sirve de punto de enlace sin duplicar
contenido.

### R8 — Changelog v1.3 → v1.4

Nuevo bloque "### Changelog v1.3 → v1.4" al inicio de v1.4 (antes del bloque "Changelog
v1.2 → v1.3" heredado, que permanece intacto), listando los 4 campos sustituidos (R2-R5),
el cambio de estado de la tabla de símbolos (R6), la nota nueva (R7), y declarando
explícitamente qué placeholders permanecen intactos (lista de R6 del proposal / checklist
del issue): `min_profitable_days`, `news_restrictions`, `weekend_holding`,
`consistency_rule`, `profit_split`/`payout_cycle`, `challenge_cost`, `max_lots`/
`max_positions`, EAs, "Programa de referencia". Cita como fuente "sondeo de la corrida D,
issue #20, 2026-07-12" y "dashboard FTMO del usuario, 2026-07-12" (para los límites de
pérdida), **nunca** rutas literales de `out/run_d/*.json`.

**Decisión fijada** (estrategia de cita de fuente): se cita issue + fecha como fuente
auditable normativa — precedente de §1.3.1 (The5ers cita "Issue B", no un archivo). Las
rutas `out/run_d/probe_mt5.py` / `probe_depth.py` pueden mencionarse únicamente como
referencia informativa entre paréntesis (nombres de script, no rutas de salida), marcadas
explícitamente como artefactos ad-hoc no versionados — nunca como fuente normativa
primaria, porque `out/` está untracked, sin hash de dataset ni commit (invariante de
reproducibilidad institucional, CLAUDE.md raíz).

### R9 — Placeholders sin evidencia: intactos, listados textualmente

El changelog de v1.4 (R8) y la ficha §1.3.2 conservan sin cambio de contenido los
siguientes campos, todos con su marca "a confirmar" original de v1.3: `min_profitable_days`,
Plazo, `news_restrictions`, `weekend_holding`, `consistency_rule`, `profit_split`/
`payout_cycle`, `challenge_cost`, `max_lots`/`max_positions`, EAs, "Programa de
referencia", `equity_basis`. Este requisito es negativo por diseño: el eval de R9 verifica
la **ausencia** de cambios en estas filas.

### R10 — Gates, criterio mecánico y artefactos de código: intactos

§7.1-7.4 (gates G/C/P/T), §2.2.1 (criterio mecánico de archivo) y §7.5 (condicionamiento
por firma, incl. `firm_profile_hash` y forma canónica `GO (candidato X, firma Y)`) quedan
byte-a-byte idénticos entre v1.3 y v1.4. No se crea `profiles/ftmo.json`;
`profiles/the5ers.json` y `src/genesis/strategy/inspector_config.json` no se tocan
(verificable: `git status --porcelain` sobre ambos permanece vacío tras el change).

### R11 — Punteros a "SSoT" en archivos versionados fuera de `docs/`: sin cambios (decisión explícita)

`CLAUDE.md`, `AGENTS.md` y `README.md` en la raíz del repo referencian el SSoT por nombre
de archivo **`docs/SPEC_GENESIS_v1.1_PropTrading_TorneoCandidatos.md`** (verificado:
`CLAUDE.md:5`, `AGENTS.md:7`, `README.md:5`). El precedente v1.2→v1.3 (PR #19) **no
actualizó** estos punteros pese a introducir v1.3 — siguen apuntando a v1.1 hoy. Este
change es consistente con ese precedente y **no actualiza** estos tres archivos: se trata
como decisión de alcance explícita (no un olvido), documentada aquí para que quede
trazable. Si en el futuro se decide fijar los punteros a la versión vigente en vez de a
v1.1, eso es un change de mantenimiento documental aparte, no parte de este backfill.

## Redacción exacta esperada (spec-delta) — celdas y filas de §1.3.2 en v1.4

| Campo | v1.3 (actual) | v1.4 (nuevo, redacción esperada) |
|---|---|---|
| `server_tz` | `Europe/Prague (CET/CEST). *Default conservador — a confirmar contra `account_info`/`symbol_info` del terminal FTMO en la corrida operativa (patrón PA-1).*` | `**Europe/Athens** (GMT+2/+3, estilo EET/EEST) — offset **+3** confirmado el 2026-07-12 (sondeo corrida D, issue #20): último tick de forex del viernes etiquetado 23:54 con cierre real 21:00 UTC; índices US a 23:49 con cierre real 20:49 UTC. Best-fit IANA usado por la corrida. **Pendiente**: la regla de cambio DST (fechas UE vs. EE. UU.) no es decidible con una sola observación de verano; se resuelve con probes M1 de la semana 2025-10-26 → 2025-11-02 (ver nota de historia disponible más abajo).` |
| `daily_reset_time` | `**`00:00`** en el `server_tz` de FTMO (típicamente Europe/Prague, CET/CEST). Equivalencia UTC: 23:00 UTC (CET, invierno) / 22:00 UTC (CEST, verano). *Default conservador — `server_tz` y hora exacta a confirmar...*` | `**`00:00` `Europe/Prague`** (CE(S)T, términos vigentes de FTMO) — zona **distinta** del reloj del servidor de datos (`server_tz` = `Europe/Athens`, fila anterior); no colapsar ambas zonas en una sola. Equivalencia UTC: 23:00 UTC (CET, invierno) / 22:00 UTC (CEST, verano). Confirmado (sondeo corrida D + dashboard FTMO, issue #20, 2026-07-12).` |
| `daily_loss_limit` | `...*Default conservador — a confirmar contra términos vigentes de FTMO / la corrida operativa.*` | `...**Confirmado** (Free Trial 50.000 USD → límite 2.500 USD; dashboard FTMO del usuario, 2026-07-12).` (resto de la celda sin cambios) |
| `max_loss_limit` | `**10%**, tipo **estático** (ancla: balance inicial). *Default conservador — tipo estático/trailing y ancla a confirmar...*` | `**10%**, tipo **estático** (ancla: balance inicial). **Confirmado** (Free Trial 50.000 USD → límite 5.000 USD; dashboard FTMO del usuario, 2026-07-12).` |
| Nota apertura tabla símbolos | `...**esperados, a confirmar por la corrida operativa** (patrón PA-1), nunca definitivos.` | `...**confirmados (patrón PA-1, sondeo corrida D, issue #20, 2026-07-12)**; coinciden exactamente con los nombres esperados en v1.3.` |
| Nota cierre tabla símbolos | `Nota: los nombres esperados y sus alias derivan del sondeo `out/run_d/probe_mt5.py`... Estos nombres se confirman contra el terminal FTMO en la corrida operativa y se corrigen aquí en un backfill posterior si difieren...` | `Nota: los nombres y alias fueron **confirmados** por el sondeo de la corrida D (`probe_mt5.py`, issue #20, 2026-07-12) contra el terminal FTMO real; coincidieron exactamente con los esperados en v1.3 (incl. sufijo `.cash` en los 4 índices). La confirmación del `SymbolFigure` real de oro/majors sigue **fuera de alcance** — ver §2.x.` |
| Subsección nueva (tras la tabla de símbolos) | *(no existe en v1.3)* | `##### Historia disponible en el Free Trial (FTMO)`\n\n`Confirmado por sondeo de la corrida D (`probe_depth.py`, issue #20, 2026-07-12): los **ticks** están disponibles con profundidad ≥12 meses para los 8 símbolos, con un hueco puntual observado (`NAS100`, sin ticks el 2025-07-07). El **M1** solo está disponible desde ~2025-10-22 para los 4 índices + `XAUUSD`, y desde ~2025-11 a ~2025-12 para los 3 majors FX (`EURUSD`, `GBPUSD`, `USDJPY`). Ventana material para cualquier corrida sobre esta firma — ver también §4.1.` |
| §4.1, bullet "Realidad de profundidad de ticks" | (párrafo existente, líneas 399, sin referencia a FTMO) | Se añade al final del bullet existente: `Para FTMO, ver el detalle de ventana M1/ticks confirmado por sondeo en §1.3.2 ("Historia disponible en el Free Trial").` |

## Criterios de aceptación (evals ejecutables)

```
DADO el directorio docs/ del repo
CUANDO se ejecuta `fd 'SPEC_GENESIS_v1.4' docs/`
ENTONCES retorna exactamente 1 archivo: docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md
```

```
DADO docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `git diff --no-index docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md` (o `git status --porcelain docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`)
ENTONCES no hay diferencias/cambios de tracking sobre el archivo v1.3 (permanece byte a byte idéntico al commit `97f173c`)
```

```
DADO docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `rg -i 'a confirmar|default conservador' docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md -n`
ENTONCES ninguna coincidencia aparece en las filas `server_tz`, `daily_reset_time`, `daily_loss_limit`, `max_loss_limit`, ni en la nota de apertura/cierre de la tabla de símbolos de §1.3.2
Y sí aparecen coincidencias en: `min_profitable_days`, `news_restrictions`, `weekend_holding`, `consistency_rule`, `profit_split`/`payout_cycle`, `challenge_cost`, `max_lots`/`max_positions`, EAs, "Programa de referencia" (placeholders deliberadamente intactos)
```

```
DADO docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `rg 'Europe/Athens' docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md`
ENTONCES retorna >=1 coincidencia (server_tz confirmado)
```

```
DADO docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `rg 'Europe/Prague' docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md`
ENTONCES retorna >=1 coincidencia en la fila `daily_reset_time` (zona de reset, distinta de server_tz)
Y `rg 'Europe/Athens.*Europe/Prague|Europe/Prague.*Europe/Athens' docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` no colapsa ambas zonas en una misma oración salvo en la nota explícita que las distingue
```

```
DADO docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `rg 'issue #20|2026-07-12' docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md -c`
ENTONCES retorna un conteo >= 6 (una cita por cada campo sustituido: server_tz, daily_reset_time, daily_loss_limit, max_loss_limit, tabla de símbolos, nota de historia)
```

```
DADO docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `rg 'out/run_d' docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md`
ENTONCES si hay coincidencias, todas están explícitamente marcadas como referencia informativa ad-hoc no versionada (nunca como fuente normativa primaria); no hay ninguna ruta `out/run_d/*.json` citada como única fuente de un valor confirmado
```

```
DADO docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `rg -c 'Historia disponible en el Free Trial' docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md`
ENTONCES retorna 1 (la subsección existe una sola vez, dentro de §1.3.2)
Y `rg -A2 'Realidad de profundidad de ticks' docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` incluye una referencia a "§1.3.2" en las 2 líneas siguientes (cross-ref desde §4.1)
```

```
DADO docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `git diff --no-index docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md`
ENTONCES ningún hunk cae en las líneas correspondientes a §7.1-7.4, §2.2.1 ni §7.5 (gates y criterio mecánico intactos)
Y todos los hunks caen dentro de: encabezado, bloque changelog nuevo, §1.3.2 (filas/nota de la tabla de símbolos, subsección nueva), y el bullet de §4.1 con la referencia cruzada
```

```
DADO el repo en su estado tras el change
CUANDO se ejecuta `git status --porcelain src/genesis/data/profiles/the5ers.json src/genesis/strategy/inspector_config.json`
ENTONCES no produce salida (ambos archivos sin cambios de tracking)
Y `fd 'ftmo.json' src/genesis/data/profiles/` no encuentra ningún archivo nuevo bajo control de versiones
```

```
DADO el repo en su estado tras el change
CUANDO se ejecuta `rg 'SPEC_GENESIS_v1\.1' CLAUDE.md AGENTS.md README.md`
ENTONCES retorna >=1 coincidencia en cada uno de los 3 archivos (punteros sin cambios, consistente con la decisión R11 y el precedente v1.2→v1.3)
```

```
DADO el repo en su estado tras el change
CUANDO se ejecuta `git diff --name-only | rg '^src/'`
ENTONCES no retorna ninguna coincidencia (change doc-only, ningún archivo bajo src/ modificado)
```

```
DADO el repo en su estado tras el change
CUANDO se ejecuta `mise run test` (o `uv run pytest`)
ENTONCES la suite existente pasa en verde (excepción doc-only de `.agents/rules/eval-tdd-conventions.md`: no se añaden tests nuevos, solo se exige que la suite existente no se rompa)
```

## Riesgos

- **DST no resuelto**: `Europe/Athens` es una única observación de verano (offset +3);
  riesgo de que un lector interprete que la regla de transición DST completa ya está
  confirmada. Mitigación: R2 exige redacción explícita "offset confirmado / regla DST
  pendiente", nunca "confirmado" a secas para toda la fila.
- **Colapso `server_tz`/`daily_reset_tz`**: riesgo de que una edición apresurada dependa
  todavía de la ecuación anterior "reset = server_tz". Mitigación: R3 exige revisar ambas
  filas juntas y el eval verifica explícitamente que no se colapsan en una misma zona.
- **Fuente no perenne**: `out/run_d/` no está versionado y podría limpiarse; la única
  fuente auditable perenne que queda es el issue #20 (GitHub), dependencia externa al
  repo. Riesgo residual aceptado — mismo patrón que The5ers/§1.3.1 (cita "Issue B").
- **Falsos positivos/negativos en el eval de "solo N zonas tocadas"**: si el changelog no
  lista textualmente los placeholders que permanecen intactos (R9), el eval de ausencia
  de cambios podría no distinguir entre un placeholder deliberadamente conservado y uno
  olvidado. Mitigación: R9 exige el listado textual completo.
- **Deriva de alcance hacia `profiles/ftmo.json`**: riesgo de que apply/design se tienten
  a versionar el perfil de código aprovechando que ya existen los valores. Mitigación: R10
  y el eval de `git status --porcelain` sobre `the5ers.json`/`inspector_config.json` +
  ausencia de `profiles/ftmo.json` nuevo.

## Preguntas abiertas (elevar al humano antes de `DESIGN → APPLY`)

1. **`firm_profile_hash` (`465ae475…`)**: este spec fija que **no se cita** en v1.4 (no
   existe `profiles/ftmo.json` versionado al que anclarlo). Si el humano prefiere dejar
   una nota de trabajo mencionándolo como referencia futura, es una decisión de diseño a
   confirmar en `design.md`, no reabre este spec.
2. **Regla DST de `server_tz`**: queda explícitamente pendiente (R2). No bloquea este
   backfill, pero condiciona cualquier corrida futura sobre la ventana 2025-10-26 →
   2025-11-02; conviene que quede rastreada como seguimiento (¿issue nuevo o nota en
   §1.3.2 basta?).
3. **Punteros a "SSoT" (R11)**: este spec fija "no tocar" por consistencia con el
   precedente v1.2→v1.3. Si el humano prefiere aprovechar este change para corregir los
   tres punteros a v1.1 (deuda documental preexistente, no introducida por este change),
   eso ampliaría el alcance doc-only declarado en el issue — requiere decisión explícita
   antes de `design`.

<!-- change:106-spec-v1-5-reorientar-el-torneo-de-cfds-mt5-a-futuros-cme-en-prop -->
# Specification: SPEC v1.5 — reorientar el SSoT del torneo a futuros CME en prop de futuros

Change #106 (Issue #106). Dominio `docs`. Fase `specify`.

> Contrato de entrada: `idea.md` (problema y hallazgos verificados) y `proposal.md` (Decisiones 1–7).
> SSoT a suceder: `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` (729 líneas, vigente).
> Este documento fija **qué secciones se tocan, con qué texto, y cómo se verifica**. No decide nada
> que no esté ya decidido en `proposal.md`, salvo las tres inconsistencias que la redacción exacta
> hizo visibles — R13, R14 y R12 — elevadas al gate humano en la última sección.

---

## Objetivo

Producir `docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md` como SSoT vigente, describiendo el
torneo sobre **futuros CME operados en una prop firm de futuros (MyFundedFutures Rapid EOD 50K)** en
lugar de índices CFD sobre MT5 en firmas tipo The5ers/FTMO, y migrar los punteros versionados que lo
referencian. Sin tocar `src/**` ni `tests/**`, y sin relajar ningún umbral G/C/P/T.

## Alcance

### IN

1. `docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md` — archivo **nuevo**, sucesor completo de
   v1.4, con changelog explícito v1.4 → v1.5 al inicio.
2. Migración de los punteros al SSoT en archivos `*.md` versionados: `CLAUDE.md:5`, `AGENTS.md:7`,
   `README.md:168`, `docs/research/PROPUESTA_LABORATORIO_DE_ESTRATEGIAS.md:615`.
*(`docs/PROTOCOLO_ADMISION_ESTRATEGIAS.md` quedó verificado y **fuera** de esta lista: no referencia
el SSoT por nombre de archivo, ni el universo CFD, ni las firmas históricas — ver R16.)*

### OUT (no-alcance explícito)

1. **Todo `src/**` y `tests/**`.** Incluye el puntero al SSoT en el docstring de
   `src/genesis/strategy/contract.py:1`, que **queda apuntando a v1.4** — ver R16.
2. La implementación de `TRAILING_EOD`, la denominación en dólares del `max_loss_limit`, el
   congelamiento del umbral, el DLL con semántica de pausa y el balance inicial 0 con saldo negativo.
   Change posterior de capa 3.
3. El exportador CME, el empalme de continuos, las sesiones CME, el registro de fichas por venue.
   Change posterior de capa 1.
4. El presupuesto de contratos compartido entre símbolos en tiempo real (engancha con #96).
5. Revertir el parche de `src/genesis/data/metadata.py` (`tick_size = 10^-digits`).
6. Medir M2K y decidir su admisión al universo.
7. Implementar el cálculo de C3 en capa 4 (el spec lo define y lo ancla; el código va en otro change).
8. Corregir la fidelidad declarada de `candidates/specs/candidate_b1_orb.yaml` (issue #107).

---

## Requisitos funcionales

### R1 — Vehículo: archivo nuevo v1.5, no addendum, no edición in-place

Se crea `docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md`. El v1.4 **no se modifica ni se
borra**: queda como histórico, igual que v1.1, v1.2 y v1.3, que siguen presentes en `docs/`.
Precedente: change #20 (v1.3 → v1.4), que estableció "archivo nuevo, no addendum, para que el
`git log` muestre el documento completo en cada versión".

Encabezado del archivo nuevo:

- **Fecha**: 2026-09-11
- **Estado**: definitivo (SSoT vigente). Reemplaza íntegramente al v1.4.
- **Objetivo de negocio**: sin cambio de redacción respecto de v1.4.

### R2 — Changelog v1.4 → v1.5

Bloque `### Changelog v1.4 → v1.5` inmediatamente después del encabezado, **antes** del changelog
v1.3 → v1.4, que se conserva íntegro junto con los anteriores.

El changelog debe abrir declarando la naturaleza del cambio —**reorientación de destino operativo,
no backfill**— y distinguirlo del precedente #20, que sí fue backfill doc-only sin cambio de rumbo.
Debe enumerar, con numeración propia, las secciones tocadas: §1 (nuevo §1.0), §1.1, §1.3, §2.3, §2.x,
§4.1, §7.2, §7.3, §7.5, §7.6, §11.1. Debe cerrar con:

- **Qué NO cambia**: gates G1–G9, C1–C2, P1–P2, P4–P6, T1–T2 (umbrales idénticos); §2.1 contrato
  plugin; §3 arquitectura; §5 capas 2–3; §6 flujo de validación y presupuesto de grid; §8 errores;
  §9 testing; §10 incubación.
- **Fuera de alcance**, con la lista de OUT de arriba.

### R3 — §1.0 (nuevo) — Criterio normativo de admisión de firmas

Sección nueva, insertada entre el encabezado de `## 1. Modelo de negocio y restricciones prop` y
`### 1.1. Ficha de la firma`, numerada **§1.0**.

Contenido normativo:

> Una firma solo es admisible como firma objetivo de Génesis si **permite ejecución automatizada**.
> Sin esa condición un veredicto GO no es ejecutable y el pipeline entero produce un número que nadie
> puede usar. El criterio es previo a la ficha: una firma que prohíbe automatizar no se modela.

Más el relevamiento del 2026-09-11, con cita textual y la conclusión de sector:

| Firma | Automatización | Cita oficial (leída en su sitio, 2026-09-11) |
|---|---|---|
| Apex Trader Funding | ❌ | *"No Automation or Algorithm Usage allowed"* |
| Take Profit Trader | ❌ | UTP #1 *"No Trading Bots or Algos"*; PRO: *"All trades must be manually executed"* |
| The5ers Futures | ❌ | *"No. These practices are strictly forbidden."* |
| MyFundedFutures | ✅ | *"Traders may make use of automated trading strategies tailored to their own specific settings…"* |
| Topstep | ✅ | API oficial de pago; **prohíbe VPS/VPN/servidores remotos** |
| Tradeify | ✅ | Con verificación (propiedad demostrable, video en vivo activando el código) |

> **Tres de seis firmas relevadas lo prohíben.** No es una anécdota de una firma: es una
> característica del sector, y significa que la premisa de Génesis —validar sistemas mecánicos— es
> compatible con una minoría de la industria. El criterio de §1.0 es la consecuencia normativa.

Debe incluir la nota de procedencia: relevamiento sobre páginas oficiales, no agregadores; los
agregadores que encabezan la búsqueda afirmaban lo contrario para Apex y Take Profit Trader.

### R4 — §1.1 — Ficha de firma extendida (`prop_profile.json`)

La tabla de campos mínimos se reemplaza por la versión extendida. Filas modificadas y nuevas:

| Campo | v1.4 | v1.5 |
|---|---|---|
| `max_loss_limit` | `%` + `static \| trailing` | **monto absoluto en divisa de la cuenta** + `static \| trailing_intraday \| trailing_eod` |
| `threshold_lock_at` | — | **nuevo**: nivel de balance/equity donde el umbral trailing deja de moverse |
| `daily_loss_limit` | obligatorio, `%` | **opcional**, monto absoluto, con semántica declarada `breach \| pause` |
| `payout_buffer` | — | **nuevo**: beneficio realizado exigido antes del primer retiro |
| `min_net_profit_between_payouts` | — | **nuevo** |
| `max_lots`, `max_positions` | escalares por símbolo | **`contract_budget`**: presupuesto **compartido entre instrumentos y en tiempo real**, con equivalencia declarada (10 micros = 1 mini) |
| `news_restrictions` | ventanas por fase | ventanas + **lista T1 explícita** + variación entre evaluación y fondeada |
| `funded_starting_balance` | — | **nuevo**: la etapa fondeada puede arrancar en 0, con saldo negativo permitido |
| `automation_allowed` | — | **nuevo**, booleano, con cita de la fuente. Falso ⇒ la firma no es admisible (§1.0) |

Además, dos notas normativas obligatorias:

1. **Semántica de doble tiempo de `trailing_eod`**: el umbral se **calcula** al cierre de la sesión
   sobre el balance de cierre, y se **aplica contra equity flotante** intradía. No es un detalle de
   implementación: decide si un trade que sube y devuelve rompe la cuenta.
2. **Bloqueo explícito de la simulación multi-activo concurrente**: `contract_budget` se **declara**
   en la ficha, pero el spec **prohíbe** simular varios instrumentos concurrentemente contra un
   presupuesto compartido hasta que exista el árbitro de exposición (#96). Sin él la capa 3 daría por
   ejecutadas operaciones que la cuenta real rechazaría, y **sobreestimaría `p_pass`** — el único
   número que el proyecto existe para producir.

La nota de v1.4 sobre `equity_basis` resuelto como `equity` para The5ers se conserva, marcada como
aplicable a las fichas históricas de §1.3.1/§1.3.2.

### R5 — §1.3 — Ficha de firma activa: MyFundedFutures Rapid EOD 50K

Nueva subsección **§1.3.0**, colocada **antes** de The5ers y FTMO, marcada como **ficha activa**.
Todos los valores provienen de `help.myfundedfutures.com` leído el 2026-09-11 (fuente primaria); cada
fila cita su origen.

**Etapa evaluación (Rapid EOD, 50K):**

| Campo | Valor |
|---|---|
| `automation_allowed` | **true** — *"Traders may make use of automated trading strategies…"* (sin HFT) |
| Objetivo de profit | **$3.000** |
| `max_loss_limit` | **$2.000**, tipo **`trailing_eod`** |
| `threshold_lock_at` | **balance inicial + $100** (50K ⇒ $52.100; alcanzado al cerrar sobre $52.000). Política única |
| `daily_loss_limit` | **ninguno** |
| `contract_budget` | **3 mini / 30 micro**, total y compartido entre instrumentos, en tiempo real |
| `consistency_rule` | **30%** — condición de **terminación**, no de fallo: excederla obliga a operar más días |
| `min_profitable_days` | **4 días mínimos** |
| `news_restrictions` | T1 **permitido** en evaluación; flat 2 min antes / 2 min después de cualquier dato |
| `challenge_cost` | **no verificado** — ver §11.1 |

**Etapa sim funded (Rapid EOD):**

| Campo | Valor |
|---|---|
| `funded_starting_balance` | **$0**, saldo negativo permitido hasta que el MLL suba a breakeven ("expected and normal") |
| `max_loss_limit` | **$2.000**, **`trailing_eod`** (no cambia de tipo al fondearse) |
| `contract_budget` | 3 mini / 30 micro |
| `news_restrictions` | T1 **prohibido** |
| Cuentas fondeadas | **3** |
| `profit_split` | **90/10** |
| `payout_buffer` | **$2.100** antes del primer retiro |
| `min_net_profit_between_payouts` | **$500** |
| `payout_cycle` | **diario, sin tope** |
| Consistencia de payout | **ninguna** |

**Nota normativa obligatoria — por qué Rapid EOD y no Rapid estándar:**

> El plan Rapid **estándar** cambia el drawdown de EOD a **intraday trailing (HWM de equity)** al
> pasar a fondeada. Se pasaría la evaluación bajo una regla y se operaría bajo otra, más dura. Eso
> invalida la validación justo cuando empieza a importar: el `p_pass` medido no describiría la
> cuenta que se opera. Rapid **EOD** conserva el mismo tipo de drawdown en las dos etapas.

**Nota normativa obligatoria — hedging y su ambigüedad declarada:**

> MFFU prohíbe el hedging solo sobre el **mismo subyacente** (ejemplo suyo: NQ contra MNQ), y su
> texto dice *"hedging through different unrelated assets is permitted"*. **MES, MNQ y MYM son
> *related* aunque no compartan subyacente**, y MFFU remite a la regla 534 de CME sobre wash trades.
> La ambigüedad entre "mismo subyacente" y "no relacionados" **no se resuelve leyendo**: queda en
> §11.1 como pendiente a confirmar con soporte **antes** de operar direcciones opuestas dentro del
> clúster de índices. Mientras no se confirme, el spec **no autoriza** posiciones simultáneas de
> signo opuesto entre MES, MNQ y MYM.

**Nota de riesgo de plataforma (nueva, aplicable a cualquier firma):**

> Si la firma reescribe su rulebook, la validación **caduca**: el `trial_id`, el `firm_profile_hash`
> y el `p_pass` quedan describiendo un contrato que ya no existe. Apex demostró en 2026 que las
> firmas lo hacen (todo su producto anterior quedó etiquetado "Legacy"). La ficha de firma registra
> la **fecha de lectura** de cada parámetro, y una ficha con más de 6 meses debe reverificarse contra
> fuente primaria antes de emitir un veredicto.

### R6 — §1.3.1 y §1.3.2 — The5ers y FTMO conservadas, marcadas como históricas

Las fichas de The5ers y FTMO se **conservan íntegras**, sin editar sus valores, precedidas de una
nota: son **fichas históricas del régimen CFD/MT5**, no admisibles bajo §1.0 en su producto de
futuros, y se mantienen porque los artefactos y veredictos ya producidos están condicionados a ellas
(§7.5, no-transferibilidad). El patrón multi-firma `--firm`/`--profile` se conserva: la ficha de MFFU
es la **activa**, no la única posible.

Nota de matiz obligatoria sobre The5ers: su página general de prácticas prohibidas **sí** permite EAs
con código fuente propio, pero eso aplica a su producto **CFD**; su producto de **futuros** los
prohíbe. Dos regímenes distintos en la misma firma — el criterio de §1.0 se evalúa **por producto**,
no por marca.

### R7 — §2.3 — Candidato B: universo CME y tabla de sesiones

La fila *Universo* de la tabla normativa pasa de `CFDs de índices: US500, NAS100, US30, GER40` a
**`Futuros CME: MES, MNQ, MYM, MGC (front month sin ajustar) — ver §2.x`**.

La tabla *Sesiones de contado por índice* se reemplaza por una tabla de **anclaje del rango de
apertura por instrumento**:

| Instrumento | Ancla del rango de apertura | Cierre de la ventana operativa | Nota DST / estado |
|---|---|---|---|
| MES | Apertura de contado del S&P 500 — **14:30 UTC** (horario estándar) | 21:00 UTC | DST US (NY): en EDT las horas UTC se desplazan −1 h. Sin cambio respecto de v1.4 |
| MNQ | Apertura de contado del Nasdaq 100 — **14:30 UTC** | 21:00 UTC | Ídem |
| MYM | Apertura de contado del Dow 30 — **14:30 UTC** | 21:00 UTC | Ídem |
| MGC | **PENDIENTE — no verificado** | **PENDIENTE** | Ver nota obligatoria abajo |

**Nota normativa obligatoria — el oro no tiene apertura de contado:**

> El Candidato B define su rango de apertura sobre la **apertura de contado** del subyacente. Los
> tres micro-índices la tienen (la apertura del mercado de acciones). **MGC no.** El oro de COMEX
> cotiza en Globex casi 23 horas y no existe una "apertura de contado" análoga. El ancla del rango de
> apertura de MGC **queda declarada como pendiente**, a resolver contra la **página de producto
> oficial de CME** (fuente primaria) en el change de capa 1, junto con la tabla de sesiones. No se
> rellena con memoria del modelo.
>
> Consecuencia de alcance declarada: **mientras el ancla de MGC no esté verificada, el Candidato B
> no puede correrse sobre MGC.** Eso no excluye a MGC del universo del torneo —su admisión es por
> propiedades intrínsecas del activo (§2.x), no por la estrategia—; excluye a MGC del **universo
> efectivo del Candidato B** hasta que el ancla se cierre. El universo efectivo de cada corrida se
> registra en la metadata del artefacto.
>
> **El denominador de C1 NO se contrae** (normativo). Un instrumento que no se puede evaluar cuenta
> como **no superado**, no como ausente: con el universo de §2.x, C1 ≥ 60% sigue exigiendo **3 de 4**
> aunque MGC no sea evaluable, lo que obliga al Candidato B a pasar en **los tres micro-índices**.
> Contraer el denominador a los evaluables convertiría un pendiente de datos en una rebaja del gate
> —2 de 3 = 67% pasaría, cuando 2 de 4 = 50% no— y permitiría que un sistema mono-factorial de renta
> variable estadounidense (MES + MNQ, correlación de retornos 0,947) superara C1 sin validación
> cruzada real. **Un pendiente no es una excepción.**

El bloque *Propiedades estructurales* se re-deriva: la estimación de ~700–1.000 apuestas/año se
mantiene **solo** para los tres micro-índices sobre la misma sesión RTH, y se marca como **estimación
heredada del régimen CFD, a re-medir sobre datos CME reales** en el change de capa 1. Ver R14.

El bloque de evidencia académica del Candidato B se conserva **sin cambios de redacción**. La
discrepancia entre `fidelity: canonical` declarada en `candidates/specs/candidate_b1_orb.yaml` y lo
que Gao, Han, Li & Zhou (2018) realmente documenta se trata en el **issue #107**, fuera de este
change.

### R8 — §2.x — Universos por candidato

- **Universo del Candidato B** pasa a MES, MNQ, MYM, MGC, con tabla de símbolo/subyacente/multiplicador
  en vez de nombre MT5/alias. El multiplicador se deriva de la ficha (`tick_value / tick_size`), no se
  transcribe a mano.
- **Criterio de admisión al universo (nuevo, normativo), intrínseco al activo:**

  > Un instrumento entra al universo del torneo por sus **propiedades propias**: liquidez y
  > profundidad de libro suficientes, costo de transacción aceptable respecto del tick, existencia de
  > contrato **micro** que permita dimensionar contra el umbral de la firma, y ficha de contrato
  > **pública y auditable**. La **correlación no es criterio de admisión**: ponerla aquí acoplaría el
  > SSoT —agnóstico a la estrategia por diseño— a un candidato concreto, porque la estructura de
  > correlación de un ORB no es la de un CT sweep-fade ni la de un TSMOM. La correlación se gobierna
  > en capa 4 con el gate C3 (§7.2), por candidato.

- **Tamaño mínimo del universo para emitir veredicto (nuevo, normativo).** Hueco preexistente en
  v1.4, detectado al preguntar si se puede correr sobre un solo símbolo. C1 es un **porcentaje** del
  universo del candidato, y con un universo de un solo símbolo **pasar en ese símbolo da 100% ≥ 60%:
  C1 se satisface trivialmente**. La única evaluación se valida a sí misma, y el gate que sostiene
  toda la validación cruzada entre instrumentos deja de decir nada:

  > Ninguna campaña sobre un universo de **un solo instrumento** puede emitir veredicto GO, GO-PARCIAL
  > ni GO-ACOTADO. **C1 solo tiene contenido con `|U| ≥ 2`**, y ese es el mínimo normativo. No es una
  > constante elegida: es el punto exacto en que C1 deja de ser vacío.

  Observación que el spec debe declarar, porque el umbral **no** endurece de forma monótona con el
  tamaño: `|U| = 2` exige **2 de 2** (100%), más estricto que `|U| = 3` (2 de 3) y que `|U| = 4`
  (3 de 4). Un universo chico no es un universo indulgente — salvo en el caso degenerado de 1.

  **Dos defensas más, que ya existen y conviene escribir juntas:**

  1. **El universo vive en el SSoT.** Achicar el universo de un candidato es un cambio de §2.x, o sea
     un change del ciclo SDD con gate humano. No es un parámetro de corrida.
  2. **Achicarlo después de medir es selección.** Por D1 (§2.x.1), restringir el universo habiendo
     visto resultados cuenta como ensayo y suma al denominador del DSR. Elegir el símbolo que anduvo
     bien y declararlo "el universo" es el caso de manual que el ledger (#53) existe para atrapar.

  **Lo que sí está permitido con un solo símbolo:** corridas **exploratorias o de diagnóstico** que
  **no emiten veredicto** — el precedente es el diagnóstico de señal desnuda de §2.2.1. Quedan
  registradas en el ledger como ensayos, con la misma consecuencia sobre el DSR de cualquier búsqueda.

- **M2K (micro Russell)**: fuera del universo v1.5 **por falta de datos**, no por criterio. Entra en
  v1.6 por vía declarada de antemano: a priori por los criterios intrínsecos de arriba, o
  condicionado a medición **contando cada evaluación como ensayo de selección** (§7, R9).
- **Universos de los Candidatos A y C**: se conservan las tablas de v1.4 **sin editar valores**,
  precedidas de una nota que las marca como **heredadas del régimen CFD/MT5 y no vigentes bajo la
  firma activa**; se re-derivan cuando cada candidato entre en alcance. El no-objetivo heredado sobre
  el `SymbolFigure` real de oro/majors se conserva textualmente.

### R9 — §2.x / §7 — Régimen D1 declarado: selección, y se paga

Subsección nueva **§2.x.1 — Régimen de búsqueda sobre el universo (D1)**, normativa:

> El propósito del universo múltiple es **buscar en qué instrumentos funciona un candidato**, no
> exigir que funcione en todos. Bajo la regla D1 ratificada —*cuenta como ensayo toda dimensión sobre
> la que SELECCIONAS; no cuenta ninguna sobre la que EXIGES*— eso es **selección**: **cada instrumento
> del universo cuenta como un ensayo** y suma al denominador del DSR.

Más la consecuencia operativa, que es lo que este requisito obliga a escribir:

> **El ledger de ensayos persistente (issue #53) pasa de deseable a prerrequisito.** La selección
> entre instrumentos ocurre **entre corridas**; hoy `n_trials` solo cuenta la grilla interna de una.
> Sin ledger se buscaría en cuatro instrumentos y el DSR se enteraría de uno, y **G4 dejaría de
> proteger en silencio**. Ninguna campaña sobre el universo de §2.x puede emitir veredicto antes de
> que el ledger exista.

Sustento a citar, con volumen y páginas (verificado contra fuente):

- Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*, SSRN 2460551.
- White (2000), *Econometrica* 68:1097–1126; Sullivan, Timmermann & White (1999), *J. Finance*
  54:1647–1692.
- Bailey, Borwein, López de Prado & Zhu (2014), *Notices of the AMS* 61(5):458–471 (*Minimum
  Backtest Length*).
- Harvey, Liu & Zhu (2016), *RFS* 29(1):5–68.

Nota obligatoria sobre no-colapsabilidad de contadores: los ensayos del régimen CFD/MT5 **no son
comparables** con los del régimen CME y no deben acumularse en el mismo denominador. El cambio de
ficha de firma y de universo cambia `candidate_config` y por lo tanto el `trial_id`; eso es correcto
y deseado (D2/R5, sin lista blanca).

### R10 — §4.1 — Capa 1 sin MT5

1. **Invariante de cuenta**: se conserva el texto y se añade que con CME el proveedor de datos es
   **independiente del broker**, de modo que el invariante "cuenta de datos ≠ cuenta de capital" y el
   guard `AccountScopeError` quedan **trivialmente satisfechos**. Se documenta la simplificación en
   vez de arrastrar una defensa que ya no defiende nada; el guard **no se elimina** (eso sería tocar
   `src/**`).
2. **Empalme de continuos**: front month **sin ajustar**; corte decidido por volumen pero **aplicado
   únicamente en la frontera de cierre de sesión, nunca intradía**. Justificación a escribir: si el
   cruce de volumen cae dentro de RTH, cortar ahí corrompe el rango de apertura de ese mismo día; un
   ORB intradía nunca sostiene a través del roll; y el ajuste hacia atrás corrompe los niveles de
   precio de los que depende el rango.
3. **El salto de nivel en el roll se declara, no se ignora** (normativo): sin ajuste, la serie tiene
   un gap artificial de base/carry en cada vencimiento. El spec debe especificar cómo lo tratan los
   indicadores con memoria multi-día (ATR de dimensionamiento, filtros de volatilidad, rangos
   previos). No declararlo inyecta volatilidad falsa cuatro veces al año, en marzo, junio, septiembre
   y diciembre.

   **v1.5 toma la decisión, no la delega** (corregido tras la revisión independiente): la barra de
   empalme se **marca en la metadata y se excluye** del cómputo de todo indicador con memoria
   multi-día; el lookback **no se reinicia**, se saltea la barra contaminada. Delegarlo al change de
   capa 1 habría dejado un hueco normativo con consecuencia cuantitativa directa: el ATR **dimensiona
   la posición en dólares**, así que un gap de base/carry contaminando el lookback deforma el sizing
   de decenas de sesiones posteriores, y las dos alternativas dan ATR distintos. Reiniciar el lookback
   además destruye historia útil cuatro veces al año sin necesidad.

   El change de capa 1 puede **anular** esta elección únicamente con evidencia medida sobre datos CME
   reales, registrada como delta al spec — no por conveniencia de implementación.
4. **`tick_volume` cambia de semántica**: de conteo de ticks (MT5) a **volumen negociado real** (CME).
   Misma columna, significado distinto, y `strategy/common/vwap_engine.py` ya la consume como si
   fuera volumen. El spec exige un **marcador explícito en la metadata del export** (`volume_kind`):
   dos datasets donde la misma columna significa cosas distintas no pueden convivir sin marca.
5. **Proveedor de datos**: decisión **abierta declarada** (Databento / Rithmic / Tradovate / CME
   DataMine), no resuelta aquí. Va a §11.1.
6. La fila de `mt5_export.py` en la tabla de §4 se marca como **componente del régimen histórico**;
   su reemplazo (exportador CME) se nombra pero no se especifica — change de capa 1.

### R11 — §7.2 — C3: restricción de dimensionamiento de canasta, **no** gate de muerte

**Corrección de fondo (2026-09-11, decisión del dueño).** Las dos versiones anteriores de este
requisito colapsaban dos preguntas distintas en un mismo veredicto:

| Pregunta | La responde | Qué significa fallar |
|---|---|---|
| ¿El edge **generaliza** entre instrumentos? | **C1** (≥ 60% del universo pasa G1–G9) | No hay ventaja robusta ⇒ **NO-GO** |
| ¿La canasta **entra** en el presupuesto de la cuenta? | **C3** | No alcanza el capital para operar tantos a la vez ⇒ **se opera una canasta más chica** |

Matar a un candidato por la segunda es emitir "no hay ventaja" cuando lo que ocurre es "no alcanza el
colchón". Son diagnósticos distintos y el spec debe separarlos. **C1 y C3 son ortogonales**: un
candidato puede tener edge en 3 de 4 instrumentos (C1 ✓) y aun así solo poder operar 1 a la vez.

Por lo tanto **C3 deja de ser un gate de pase/fallo y pasa a ser una restricción normativa de
dimensionamiento**: no decide si el candidato vive, decide **cuántos instrumentos puede llevar la
cuenta simultáneamente**. Se añade a §7.2 junto a C1 y C2, que no se tocan, marcada explícitamente
como restricción y no como gate:

| # | Criterio | Umbral definitivo | Efecto al incumplirse |
|---|---|---|---|
| C3 | Drawdown conjunto intradía p95 en **días de señal simultánea**, sobre la canasta operada | ≤ 50% del `max_loss_limit` | **Se reduce la canasta**, no se emite NO-GO |

**Cómo se determina la canasta (normativo, sin búsqueda):**

> Para cada tamaño `k ∈ [1, |supervivientes|]`, la composición de la canasta la fija una **regla
> declarada antes de la campaña** (§2.x.1, #88) — una sola canasta por tamaño, nunca un conjunto de
> alternativas. Se evalúa C3 sobre **todas** esas canastas y se define
>
> `k_max = max { k : C3(k) ≤ 50% del max_loss_limit }`
>
> **No se desciende parando en el primer tamaño que cumple.** Esa versión anterior presuponía
> monotonía —que si `k` no cumple, `k+1` tampoco— y la monotonía **no se sostiene**: el p95 no es
> subaditivo, y sobre todo el conjunto de condicionamiento *cambia con `k`*, porque "días de señal
> simultánea" es un conjunto distinto para cada canasta. Además, podar el miembro menos correlacionado
> (MGC frente a los tres índices) puede **empeorar** la cola conjunta en lugar de mejorarla. Evaluar
> todos los `k` cuesta cuatro corridas y elimina el supuesto.
>
> **Con `k = 1` no hay cola conjunta y C3 queda vacío**, porque no existe simultaneidad con nadie.
> C3 **no** se transforma en otro gate ahí: simplemente no aplica, y la protección la dan dos gates
> que ya existen y que sí corren sobre un instrumento único —
> **P3** (a nivel de cuenta: probabilidad de que la pérdida intradía de un solo día consuma el colchón;
> con `k = 1` la cuenta *es* ese instrumento, así que P3 mide exactamente la cota intradía que C3
> mediría) y **G6** (MC MaxDD multi-día p95 ≤ 50% del `max_loss_limit`).
>
> *Corrección registrada:* la versión anterior afirmaba que C3 con `k = 1` "degenera en G6". Es falso
> y lo detectó la segunda revisión independiente: C3 mide excursión **intradía** por medición directa
> sobre días condicionados, G6 mide MaxDD **multi-día acumulado** por Monte Carlo. No son la misma
> magnitud. El gate que cubre el hueco es **P3**, no G6 — y solo existe como cobertura porque la
> primera revisión corrigió que P3 es de cuenta y vinculante. **C3 no emite NO-GO en ningún caso.**

**El presupuesto que ata es el colchón, no el techo de contratos:**

> El `contract_budget` de Rapid EOD (30 micros) **no restringe**: cuatro micro-índices están lejísimos
> del techo. Lo que restringe es el colchón de $2.000, vía el riesgo por trade. Por lo tanto `k_max`
> **no es un dato de la firma: es el resultado de una calibración que el proyecto controla**, y el
> spec exige reportar la pareja (`risk_pct`, `k_max`) con fecha de pre-registro, no solo `k_max`.

#### La grilla de riesgo de v1.4 queda **anulada** para futuros prop (PA-106-5, ampliado)

La segunda revisión independiente convirtió lo que yo había anotado como un hueco de definición en un
hallazgo bastante peor. Hay **dos** denominadores posibles y **los dos rompen**:

| Denominador | Qué da con la grilla `{0,25%, 0,375%, 0,5%}` de §2.3/§6.2 | Veredicto |
|---|---|---|
| **% del balance** (v1.4) | En sim funded el balance **arranca en $0** y puede ir negativo | **Indefinido** |
| **% del nominal** ($50.000) | $125 / $187,50 / $250 por trade — o sea **6,25% a 12,5% del colchón real de $2.000 en un solo trade**, y cuatro stops simultáneos = $500 a $1.000, hasta el 50% de la cuenta en una mañana | **Operable pero temerario** |
| **% del `max_loss_limit`** ($2.000) | $5 / $7,50 / $10 por trade. Un stop ordinario de 50 puntos en MNQ cuesta **$100 por micro**; 4 ticks de MES ya son $5 | **Físicamente inoperable** |

Ninguna de las tres sirve. **v1.5 decide el denominador y declara la grilla pendiente de re-derivación,
con las dos cotas que la acotan** — no inventa números:

> **Denominador normativo del sizing en fichas de futuros prop: el `max_loss_limit`** (el colchón), que
> es el presupuesto real de la cuenta y no depende de un balance que puede ser cero o negativo.
>
> Los valores de la grilla de `risk_pct` **no se heredan de v1.4**: quedan pendientes de re-derivación
> contra las distancias de stop reales en datos CME, sujetos a dos cotas que el spec sí fija:
>
> - **Piso de operabilidad**: `risk_per_trade ≥` el costo de un stop típico del candidato en **un**
>   contrato micro. Por debajo de eso el sizing no puede expresarse en contratos enteros.
> - **Techo de canasta**: `k_max × risk_per_trade ≤ 50% del max_loss_limit`, que es C3 escrito como
>   restricción de sizing en vez de como medición.
>
> La grilla debe caber entre las dos cotas. Si no cabe ninguna configuración, la conclusión es que la
> cuenta es demasiado chica para el candidato — y eso se reporta, no se fuerza.

**Esto también toca §6.2**: el presupuesto `N_trials_IS = 27` (3×3×3) supone tres valores de
`risk_pct`. Si la re-derivación deja menos de tres valores operables, el conteo de trials cambia y el
sanity-check de G4 debe rehacerse. Queda declarado junto con R14.

Y un **requisito de reporte sin umbral**, que no es un gate:

> La matriz de correlación OOS del P&L diario entre los instrumentos de la canasta y su **número
> efectivo de apuestas** `n_eff = n / (1 + (n−1)·ρ̄)` se **reportan obligatoriamente** en el artefacto
> del veredicto. El veredicto declara la amplitud efectiva de la canasta; no se le aplica umbral.

**Por qué un solo gate y no dos** (corrección posterior a la revisión independiente; ver PA-106-3):

El umbral de C3 **≤ 50% del `max_loss_limit`** es la **forma exacta de G6**, aplicada a la canasta
conjunta restringida a días de señal simultánea en vez de a un símbolo aislado. Es un anclaje real: el
mismo número, la misma magnitud (drawdown contra el presupuesto de la firma) y la misma dirección de
consecuencia.

El anclaje que **se descarta** es el que había propuesto para un gate de Pearson: `C3a < 0.3` "porque
T2 usa 0.3". No se sostiene por tres razones, y las tres importan:

1. **Poblaciones distintas.** T2 mide correlación entre **candidatos estratégicos** diseñados para no
   parecerse. C3a habría medido correlación entre **activos** operados por la **misma** estrategia.
   Dos índices de gran capitalización estadounidense con el mismo gatillo a la misma hora comparten
   una beta de mercado estructural; su línea base no es la de dos estrategias distintas.
2. **Consecuencia radicalmente asimétrica.** Fallar T2 **no descalifica** a nadie: se descarta el
   ensemble y se opera el mejor individual. Fallar C3a habría sido **NO-GO fatal** de todo el
   candidato, y además con poda prohibida. Tomar prestado el número mientras se invierte la
   consecuencia no es un anclaje: es un número con otra vida.
3. **Redundancia con los gates P.** `prop_sim` simula la **cuenta conjunta**; la correlación ya está
   incorporada en P1–P5 por construcción. Un gate de Pearson aparte no agregaba protección — agregaba
   una condición de muerte sobre una magnitud que el pipeline ya valora en otro lado.

Lo que sí faltaba, y es lo que C3 aporta, es una cota **explícita y legible sobre la cola conjunta**,
que ni Pearson ni el promedio de `prop_sim` exhiben.

**Nota normativa obligatoria — por qué el gate mira la cola y no Pearson:**

> Correlación lineal baja del P&L **no es independencia**. En la medición que motivó este gate, las
> señales del ORB coinciden en dirección el **88%** de los días entre MES y MNQ; un shock macro a los
> pocos minutos de la apertura golpea los stops de los tres índices a la vez, y ahí la **dependencia
> de cola tiende a 1**. Sobre un umbral trailing de $2.000 ese es el escenario de ruina, y ninguna
> correlación de Pearson lo captura. Un gate de Pearson habría mirado hacia el lado equivocado.

**Nota normativa obligatoria — C3 es computable sin el árbitro de exposición (#96):**

> C3 se calcula por **superposición de las curvas de equity intradía por símbolo**, restringida a los
> días de señal simultánea. Esa superposición **ignora el `contract_budget` compartido**, y por eso
> es una **cota superior conservadora**: la cuenta real no habría podido sostener más posiciones de
> las que el presupuesto permite, nunca menos. C3 por lo tanto **no depende de #96** y no cae bajo el
> bloqueo de simulación concurrente de §1.1. Lo que sí depende de #96 es **operar** la canasta y
> emitir cualquier gate P sobre ella — ver §11.1, donde #96 queda listado como bloqueante.

**Lo que sustituye a la prohibición de poda (normativo):**

La versión anterior prohibía reducir la canasta y convertía el incumplimiento en NO-GO. Eso era el
error conceptual que este requisito corrige. Pero la razón por la que existía esa prohibición sigue
siendo válida —**reducir la canasta es elegir, y elegir es data mining si se hace mirando el
resultado**—, así que se sustituye por tres reglas que atacan el mismo riesgo sin matar al candidato:

1. **La reducción es por tamaño, no por búsqueda.** Se desciende desde el universo completo y se para
   en el primer `k` que cumple. Está prohibido evaluar subconjuntos alternativos del mismo tamaño
   hasta dar con uno que pase: eso sí sería minería, y de la cara.
2. **La composición de la canasta la fija una regla declarada antes de la campaña** (#88), y el tipo
   de regla determina qué hace falta para que sea admisible:
   - **Regla intrínseca** (mayor liquidez, menor costo relativo al tick, mayor número de trades): no
     mira desempeño, **no agrega ensayos**, admisible siempre.
   - **Regla de desempeño** ("el mejor por Sharpe / PF / P&L"): es **selección**. Admisible
     **únicamente si el ledger de ensayos (#53) está operativo y alimenta el `n_trials` de G4** con
     los instrumentos evaluados. *La corrección aquí importa:* yo había escrito que ya "está pagada"
     por §2.x.1, y eso confunde el **principio** con el **mecanismo**. §2.x.1 declara que cada
     instrumento cuenta como ensayo; el mecanismo que lo hace efectivo es el ledger, que **no
     existe**. Hoy G4 se calcula por símbolo sobre su propia grilla y no ve los otros tres, y T1
     deflacta por número de **candidatos**, no de instrumentos. Sin ledger, una regla de desempeño no
     está pagada: está sin contabilizar.
   - §2.x.1 ya prohíbe emitir veredicto sin ledger, así que el caso no debería presentarse — pero
     escribirlo como "está pagada" invitaba a olvidarse de por qué.
3. **La reducción se declara en el veredicto.** Una canasta recortada por capital produce un GO con
   canasta chica, no un GO a secas: ver R13(d).

**Recomendación explícita del spec, no obligación:** elegir "el mejor por métrica" es la opción más
ruidosa que hay. DeMiguel/Garlappi/Uppal y Bates & Granger dicen lo mismo desde hace décadas — el
ganador de la muestra es en parte suerte. Cuando el capital obliga a quedarse con uno, una regla
**intrínseca** (el más líquido, el de menor costo relativo al tick) es preferible a una de desempeño,
porque no agrega ensayos y no hereda el sesgo del ganador. El spec **registra la recomendación y deja
la elección de la regla al pre-registro**, que es donde corresponde.

**Evidencia del porqué, a incluir en el spec como tal — no como justificación del universo:**

Dos mediciones sobre `data/raw/*/m1/`, ventana 2025-10-30 → 2026-06-30:

| Par | Corr. de **retornos** (130 d) | Corr. del **resultado ORB** (170 d) |
|---|---|---|
| MES–MNQ | 0,947 | 0,281 |
| MES–MYM | 0,847 | 0,445 |
| MES–MGC | 0,435 | 0,131 |
| MNQ–MYM | 0,684 | 0,099 |
| MNQ–MGC | 0,407 | 0,162 |
| MYM–MGC | 0,429 | 0,033 |

Límites de la medición, a declarar textualmente en el spec: N = 170 ⇒ error estándar ≈ 0,077, o sea
los valores bajo ~0,15 no se distinguen de cero **ni de 0,25**; ventana de 8 meses y un solo régimen;
el proxy de ORB no tiene stops, costos, filtro RVOL ni salida Chandelier. **La medición no fija
ningún umbral** — el umbral de C3 viene del anclaje a G6; la medición justifica por qué el gate existe
y por qué mira la cola y no Pearson. Los mismos números entran además, sin umbral, en el requisito de
reporte de amplitud efectiva.

### R12 — §7.3 — Gate P3 anclado al control vinculante de la ficha

La fila P3 se reemplaza por:

| # | Criterio | Umbral definitivo |
|---|---|---|
| P3 | P(en un mes fondeado, la pérdida intradía de **un solo día** consuma el **colchón disponible hasta el umbral vinculante** al inicio de ese día) | < 2% |

Con la definición normativa:

> El **umbral vinculante** es el `daily_loss_limit` de la ficha si está declarado, y el
> `max_loss_limit` trailing si no lo está. En MFFU Rapid EOD 50K el denominador arranca en **$2.000**
> y es una cantidad que el simulador ya sigue: la distancia entre el equity y el umbral trailing, que
> varía a lo largo del camino y **se congela** cuando el umbral se bloquea (`threshold_lock_at`).

Justificación a escribir, de las dos salidas descartadas:

> Marcar P3 como **N/A** porque Rapid EOD no tiene límite diario sería un **bypass**: una estrategia
> que pierde $1.800 en una mañana y recupera $1.700 a la tarde no viola ninguna regla de MFFU, pero
> está a $200 de liquidar la cuenta, y sacaría GO. **Inventar** un límite diario propio metería una
> constante de política de riesgo dentro del SSoT, que debe ser mecánico y derivado del contrato.

Delimitación frente a P4, explícita:

> **P3 es de un día** — la cola izquierda de la distribución diaria; atrapa la estrategia de buen
> camino promedio con un día catastrófico cada tanto. **P4 es del camino** — la acumulación a lo
> largo de meses; atrapa la que sangra de a poco.

**Nota normativa obligatoria — delimitación de ámbito frente a G7 (corregida, ver PA-106-2):**

> P3 y G7 **no miden lo mismo y ninguno domina al otro**, porque operan en ámbitos distintos que el
> propio v1.4 ya separa en los títulos de sus secciones: **G7 es un gate G — "robustez por símbolo y
> candidato"** (§7.1), evaluado por Monte Carlo **sobre un símbolo aislado**; **P3 es un gate P —
> "economía prop a nivel de cuenta"** (§7.3), evaluado por `prop_sim` **sobre la cuenta conjunta**.
>
> La diferencia es material bajo el universo de §2.x. Con señales que coinciden en dirección el 88%
> de los días entre MES y MNQ, caídas intradía moderadas **por símbolo** pasan G7 holgadamente y, sin
> embargo, sumadas en la cuenta consumen el colchón de $2.000 en una sola mañana. **G7 no puede ver
> ese evento**: no existe en ninguna de sus corridas por símbolo.
>
> Segunda diferencia, propia de la etapa fondeada: los retiros **vacían** el excedente sobre el
> colchón. Tras un payout, la distancia al umbral trailing al inicio del día puede ser de unos pocos
> cientos de dólares, y un día adverso ordinario la consume. La MC de G7 corre sobre una curva
> continua **sin retiros de capital**, así que tampoco ve ese evento.
>
> Por lo tanto **P3 vincula**, y es la única salvaguarda de la cuenta fondeada contra el shock
> intradía de cartera. El umbral se mantiene en **< 2%**.

Los gates G6 y G7 **no cambian de redacción**: referencian `max_loss_limit` simbólicamente y la
denominación en dólares se hereda de §1.1 sin tocarlos.

### R13 — §7.5 — Veredicto: regla de supervivientes y precedencia de C1

Tres cambios en §7.5, y **ninguno relaja un gate**:

**(a) Regla de veredicto — se conservan TODOS los supervivientes, no el mejor (nuevo):**

> Un candidato que supera los gates en varios instrumentos se opera en **todos los que el presupuesto
> de riesgo de la cuenta permita llevar a la vez** (`k_max`, §7.2 C3), **equiponderados**. Mientras
> `k_max` alcance para todos los supervivientes, **no se selecciona el de mejor métrica**: el ganador
> de la muestra es en parte suerte, y preferirlo empeora el resultado esperado fuera de muestra.
>
> Cuando `k_max` es menor que el número de supervivientes, la canasta se recorta **por capital**, con
> la regla de composición declarada de antemano (§7.2). Eso **no** convierte al veredicto en NO-GO ni
> en GO-PARCIAL: es un GO con canasta acotada — ver (d).

Sustento a citar (verificado contra fuente):

- DeMiguel, Garlappi & Uppal (2009), *RFS* 22(5):1915–1953 — sobre 14 modelos y 7 datasets ninguno
  bate consistentemente a 1/N fuera de muestra.
- Bates & Granger (1969), *JORS* 20:451–468; Timmermann, *Forecast Combinations* (Handbook of
  Economic Forecasting, cap. 4) — las combinaciones baten a la elección del mejor modelo individual
  ex ante, y las simples suelen dominar a las refinadas.
- Asness, Moskowitz & Pedersen (2013), *Value and Momentum Everywhere*, *J. Finance* 68(3):929–985 —
  primas consistentes en ocho mercados y clases de activo; promediar entre mercados mitiga el ruido
  que no es común a la señal.

**(b) GO-PARCIAL: precedencia explícita de C1 (endurecimiento, corrige ambigüedad de v1.4):**

La redacción de v1.4 —*"GO-PARCIAL: pasa en subconjunto de símbolos → incubación restringida"*— se
lee como si un subconjunto cualquiera bastara, lo que contradice C1 (≥60% del universo). Se
reemplaza por:

> **GO-PARCIAL**: el candidato pasa **C+P+T** —lo que incluye **C1 ≥ 60% del universo**— pero no en
> la totalidad de sus instrumentos. La incubación se restringe a los supervivientes, equiponderados
> (regla (a)). **GO-PARCIAL nunca es una vía para eludir C1**: un candidato que falla C1 es NO-GO.
> Con el universo de cuatro instrumentos de §2.x, C1 ≥ 60% exige **3 de 4**.

**(c) Corolario de un solo instrumento — como fundamento de C1, no como regla con excepción:**

> Que un candidato aparezca en **exactamente uno** de varios instrumentos emparentados es **evidencia
> en contra** del candidato, no un éxito parcial: un edge estructural se apoya en un mecanismo, y los
> mecanismos no respetan fronteras de ticker (*Value and Momentum Everywhere*).
>
> **Esto no es una cláusula de veredicto adicional ni una regla aparte: es la fundamentación económica
> del umbral del 60% de C1**, y se redacta como tal, adosada a C1 y no a §7.5 como regla propia.
> Escribirla como regla específica de "un solo instrumento" sugeriría —falsamente— que pasar en dos sí
> calificaría: no califica. Para cualquier universo de `n ≥ 2`, aprobar en uno da `1/n ≤ 50% < 60%`, y
> con el universo de §2.x aprobar en dos da 50%: **ambos son NO-GO mecánico por C1**, sin necesidad de
> ninguna regla nueva.

Y, explícitamente, la **cláusula que no se escribe** y por qué:

> No se admite ninguna excepción por **hipótesis pre-registrada** que rescate a un candidato que
> falla C1. Una hipótesis pre-registrada (issue #88) **interpreta** un resultado; no **relaja** un
> gate, y los gates no se relajan. Su rol en el universo es otro: toda ampliación futura del universo
> (por ejemplo M2K, §2.x) debe declararse antes de medir, y toda selección entre instrumentos debe
> contarse como ensayo (§2.x.1).

**(c-bis) Orden de evaluación normativo — hueco detectado en la segunda revisión (§6.1 y §7.5):**

Si `prop_sim` corre sobre la canasta completa de supervivientes y **después** C3 la recorta, el
veredicto certifica métricas de cuenta —P1 probabilidad de pasar, P4 supervivencia, P5 payout— de un
portafolio **que no es el que se va a operar**. Con una canasta de 1 en vez de 3 cambian la frecuencia
de trades, el tiempo hasta el objetivo de profit y el ratio de la regla de consistencia del 30%. El
número que el proyecto existe para producir describiría otra cuenta.

v1.5 fija el orden y lo hace normativo:

```
WFA + G1–G9 (por símbolo)
   └─► C1, C2 (¿el edge generaliza?)
        └─► C3 → k_max y composición de la canasta operada
             └─► prop_sim + P1–P6 SOBRE ESA CANASTA, no sobre el conjunto de supervivientes
                  └─► T1, T2
                       └─► Veredicto
```

> **Si la canasta de tamaño `k_max` no supera los gates P, el veredicto es NO-GO.** Está **prohibido**
> reintentar con canastas más chicas hasta que alguna pase: eso sería exactamente la búsqueda sobre
> subconjuntos que la regla de composición pre-registrada existe para impedir, y entraría por la
> puerta de atrás.

Esto obliga a ajustar §6.1 (flujo), donde hoy los gates P no dependen de una canasta previamente
determinada.

**(d) GO acotado por capital — forma nueva de veredicto (normativo):**

> **GO-ACOTADO (candidato X, firma Y, canasta {…})**: el candidato pasa C+P+T sobre una canasta de
> tamaño `k_max` **menor** que el número de instrumentos en los que superó los gates, porque el
> presupuesto de riesgo de la cuenta no permite llevarlos todos a la vez. **Es un GO**, no un NO-GO
> degradado ni un GO-PARCIAL: la ventaja existe y generaliza (C1 lo certificó); lo que falta es
> capital.
>
> El artefacto registra obligatoriamente: los instrumentos que superaron los gates, `k_max`, la
> calibración `risk_pct` que lo produjo, la regla de composición aplicada y su fecha de pre-registro.
> Un GO-ACOTADO cuyo `k_max` se explique por una calibración de riesgo elegida después de ver los
> resultados **no es un GO**: es minería.

**Distinción que el spec debe hacer explícita, porque las tres se parecen y significan cosas
opuestas:**

| Veredicto | Qué falló | Lectura |
|---|---|---|
| **NO-GO** | C1, o los gates G/P/T | No hay ventaja robusta, o no rentabiliza bajo las reglas |
| **GO-PARCIAL** | Nada; pasó C1 pero no en el 100% del universo | La ventaja existe pero no es universal |
| **GO-ACOTADO** | Nada; el capital no alcanza para la canasta completa | La ventaja existe y generaliza; **falta cuenta, no edge** |

**Piso de `k_max ≥ 2`: propuesto por la revisión independiente y RECHAZADO (registrado con su razón).**

La segunda revisión propuso exigir `k_max ≥ 2` y emitir NO-GO por "capacidad insuficiente de cuenta"
cuando solo se pueda operar un instrumento, invocando el principio de combinación 1/N (DeMiguel et
al.; Asness et al.). **No se adopta**, por tres razones:

1. **Aplica un principio de construcción de cartera a una restricción de factibilidad.** 1/N dice qué
   hacer *cuando podés sostener N*: no concentres. Si el capital solo permite 1, no hay elección entre
   concentrar y diversificar — es exactamente la confusión entre "¿hay ventaja?" y "¿entra en la
   cuenta?" que este requisito existe para deshacer.
2. **C1 sigue exigiendo 3 de 4.** Un GO-ACOTADO con `k = 1` solo es alcanzable por un candidato que
   demostró ventaja en **al menos tres** instrumentos. La validación cruzada ocurrió; lo que se acota
   es la ejecución. "Mono-factorial sin validar" describe otra cosa.
3. **La cola en `k = 1` no queda descubierta**: la cubren G6 (MaxDD multi-día), G7 (probabilidad de
   breach) y P3 (ruina intradía de un día a nivel de cuenta), los tres corriendo sobre la cuenta real.

Lo que sí se conserva del señalamiento: operar uno **renuncia** al beneficio de diversificación, y el
artefacto debe decirlo — el `n_eff` reportado será 1 y el veredicto lo muestra. Un GO-ACOTADO no
pretende ser tan bueno como un GO completo; pretende no confundirse con un NO-GO.

**Alternativa estructural que el spec debe registrar, no resolver:** MFFU Rapid EOD admite **3 cuentas
fondeadas**. Un instrumento por cuenta da tres colchones de $2.000 **independientes** en vez de uno
compartido, y elimina el riesgo de cola conjunta a nivel de cuenta: un shock macro mata una cuenta, no
las tres a la vez. El costo son tres suscripciones y tres evaluaciones. La disyuntiva **una cuenta
multi-activo vs. varias cuentas mono-activo** ya estaba abierta antes de este change; v1.5 la deja
declarada en §11.1 con sus términos, y **no la resuelve** — depende de precios que no están
verificados (PA de §11.1).

El resto de §7.5 —condicionamiento por firma, `firm_profile_hash`, no-transferibilidad, forma
canónica `GO (candidato X, firma Y)`, nota de trabajo futuro sobre `FirmMismatchError`— se conserva
**sin cambios**, salvo que la forma canónica se **extiende** a `GO (candidato X, firma Y, canasta
{…})`: la canasta es parte inseparable de la identidad del veredicto, por la misma razón que la firma.
Y la no-transferibilidad ahora cubre también el **cambio de régimen** CFD → CME: un veredicto del
mundo CFD no es válido en el mundo CME bajo ninguna circunstancia.

### R14 — §7.6 — Sanity-checks re-derivados

- **Sanity-check G1 ≥ 300**: el cálculo de v1.4 parte de ~700–1.000 apuestas/año en **4 índices** con
  dos sesiones distintas (3 US + GER40). El universo de v1.5 tiene 3 micro-índices sobre **una sola**
  sesión RTH, más MGC con ancla pendiente (R7). El spec debe **re-derivar** el cálculo sobre el
  universo efectivo del Candidato B y **declarar el resultado como estimación heredada del régimen
  CFD, a confirmar contra datos CME reales** en el change de capa 1. Si la re-derivación no alcanzara
  300 trades OOS, la salida es extender la ventana temporal o excluir el instrumento — **los gates no
  se relajan** (texto de v1.4, conservado).
- **Sanity-check G4/T1 DSR ≥ 0.95**: el análisis de v1.4 asume `N_trials_IS = 27` (grid 3×3×3). Bajo
  el régimen de **selección** de §2.x.1, el número efectivo de ensayos incluye **también** los
  instrumentos sobre los que se selecciona. El spec debe declarar que el sanity-check de v1.4 **queda
  invalidado como está** y se recalcula cuando exista el ledger (#53), y que hasta entonces
  **no se emite veredicto** sobre el universo múltiple. Esta es la consecuencia mecánica de R9; sin
  ella el spec afirmaría alcanzabilidad sobre un contador que ya no aplica.

### R15 — §11.1 — Pendientes declarados

Se añaden a la lista de preguntas abiertas, con el mismo formato `PA-n (Issue X)` de v1.4, y **no se
rellenan con supuestos**:

| Pendiente | Qué falta | Por qué bloquea |
|---|---|---|
| Ancla del rango de apertura de **MGC** | Página de producto oficial de CME | Sin él, el Candidato B no corre sobre MGC (R7) |
| **Política de VPS de MFFU** | Búsqueda de "VPS" / "virtual private server" en su help center: **cero resultados**. Ausencia de regla no es permiso | Decide la arquitectura de operación post-GO |
| **Comisiones por contrato** | No publicadas; dependen de la plataforma (Tradovate / Rithmic / NinjaTrader) | Insumo obligatorio de `costs.py`, que bloquea **G3** (PF OOS con costos completos), **G9** (PF con stress ×1.5) **y todos los gates P**. No es solo economía: sin comisiones verificadas los gates de robustez tampoco corren |
| **Árbitro de exposición (#96)** | No existe | Bloquea **operar** la canasta contra el `contract_budget` compartido y emitir gates P sobre ella. No bloquea C3, que se computa por superposición (R11) |
| **Denominador del sizing (`risk_pct`)** — PA-106-5 | v1.4 lo define como **% del balance**, y en sim funded el balance arranca en **$0** y puede ir negativo: ahí es indefinido | Sin denominador, `k_max` no se calcula y C3 no se evalúa. Candidato natural: el `max_loss_limit`. **Es una decisión del spec, no un dato externo** |
| **Una cuenta multi-activo vs. varias mono-activo** | MFFU admite **3 cuentas fondeadas** en Rapid EOD. Tres colchones de $2.000 independientes eliminan el riesgo de cola conjunta que C3 acota; el costo son 3 suscripciones y 3 evaluaciones, y el **precio del plan no está verificado** | Decide la arquitectura de la operación y puede volver a C3 irrelevante. Abierta desde antes de este change; v1.5 la declara con sus términos y no la resuelve |
| **Precio del plan Rapid EOD 50K** | No verificado | Entra en `challenge_cost` y en la economía del embudo (§1.2) |
| **Hedging entre instrumentos *related*** | Ambigüedad entre "mismo subyacente" y "no relacionados"; confirmar con soporte | Decide si la canasta MES/MNQ/MYM puede tomar signos opuestos (R5) |
| **Datos de M2K** | No existen en el store | Sin ellos su admisión al universo no se evalúa (R8) |
| **Proveedor de datos CME** | Databento / Rithmic / Tradovate / CME DataMine | Change de capa 1 (R10) |

Las preguntas PA-1 a PA-5 de v1.4 se conservan, marcadas como **cerradas o caducas por el cambio de
régimen** según corresponda: PA-1 y PA-2 (símbolos y profundidad de ticks en The5ers) quedan
**caducas**; PA-3, PA-4 y PA-5 (contrato plugin, enforcement de `LookaheadError`, forma del grid)
siguen **vigentes** porque son agnósticas al venue.

### R16 — Punteros al SSoT

Se migran a v1.5, revirtiendo explícitamente el precedente de #20 (que los dejó apuntando a v1.1 y
lo documentó como decisión de alcance):

| Archivo | Línea | Acción |
|---|---|---|
| `CLAUDE.md` | 5 | `v1.4` → `v1.5` |
| `AGENTS.md` | 7 | `v1.4` → `v1.5` |
| `README.md` | 168 | `v1.4` → `v1.5` (texto del enlace y destino) |
| `docs/research/PROPUESTA_LABORATORIO_DE_ESTRATEGIAS.md` | 615 | `v1.4` → `v1.5` |
| `docs/PROTOCOLO_ADMISION_ESTRATEGIAS.md` | — | **No se toca** — verificado el 2026-09-11: no contiene ninguna referencia al SSoT por nombre de archivo, ni al universo CFD, ni a The5ers/FTMO |

**Excepción declarada, no olvido:** `src/genesis/strategy/contract.py:1` referencia
`docs/SPEC_GENESIS_v1.4...md` §11.1 (PA-3) en su docstring. **No se toca**: está bajo `src/**`, que
es no-alcance de este change y que el guardián de escritura bloquea fuera de la fase `apply`. La
referencia sigue siendo **correcta** —PA-3 se conserva vigente en v1.5 (R15)—, solo apunta a la
versión histórica. Se migra en el primer change que toque ese archivo por otro motivo.

**Los artefactos archivados en `.pulse/changes/archive/**` no se tocan**: son registro histórico
inmutable de decisiones fechadas.

### R17 — Gates intactos: verificación por enumeración

Ningún umbral de G, C, P o T se relaja. El spec v1.5 debe conservar **literalmente idénticos**:

- **G1** ≥ 300, **G2** ≥ 0.5, **G3** ≥ 1.3, **G4** ≥ 0.95, **G5** < 25%, **G6** ≤ 50% del
  `max_loss_limit`, **G7** < 5%, **G8** < 30%, **G9** ≥ 1.15.
- **C1** ≥ 60%, **C2** ≥ 0.8. (**C3** es **añadido** y **no es un gate de pase/fallo**: es una
  restricción de dimensionamiento cuyo incumplimiento reduce la canasta. No sustituye ni debilita a
  ninguno.)
- **P1** ≥ 50%, **P2** ≤ 2, **P4** ≥ 6 meses, **P5** > 0, **P6** = 0. (**P3** cambia de **definición**
  —qué mide— pero **no de umbral**: sigue < 2%.)
- **T1** ≥ 0.95, **T2** < 0.3.

### R18 — Prohibición de tocar código

`git status --porcelain` restringido a `src/` y `tests/` debe mostrar, al terminar el change,
**exactamente las mismas entradas que al empezar**. Baseline capturado el 2026-09-11 al entrar en
`specify` (modificaciones previas de la sesión con `agy`, ajenas a este change):

```
 M src/genesis/data/metadata.py
 M tests/data/test_metadata.py
```

Ninguna entrada nueva, y ninguna de esas dos con contenido distinto al del baseline. El parche de
`metadata.py` (`tick_size = 10^-digits`) se revierte en un change aparte — es no-alcance aquí (OUT 5).

---

## Redacción exacta esperada (spec-delta) — celdas que cambian de valor

| Ubicación | v1.4 (actual) | v1.5 (esperado) |
|---|---|---|
| §1.1, fila `max_loss_limit` | `DD máximo (% y tipo: estático o trailing; ancla del trailing)` | `DD máximo — **monto absoluto en la divisa de la cuenta** y tipo: `static` \| `trailing_intraday` \| `trailing_eod`; ancla y **nivel de congelamiento** (`threshold_lock_at`)` |
| §1.1, fila `daily_loss_limit` | `Límite de pérdida diaria (% y base de cálculo: el mayor de equity flotante intradía y balance del día anterior)` | `**Opcional.** Límite de pérdida diaria en monto absoluto, con base de cálculo y **semántica declarada** (`breach` = rompe la cuenta \| `pause` = suspende el día). Una ficha sin DLL declarado es válida; ver §7.3 (P3)` |
| §1.1, fila `max_lots`, `max_positions` | `Límites de exposición si existen` | `**`contract_budget`** — techo de exposición **total y compartido entre instrumentos, en tiempo real**, con equivalencia declarada entre tamaños (10 micros = 1 mini). La simulación multi-activo concurrente contra este presupuesto queda **bloqueada** hasta #96` |
| §2.3, fila `Universo` | `CFDs de índices: US500, NAS100, US30, GER40 (apertura de contado de cada uno) — ver §2.x para símbolos MT5` | `Futuros CME, front month **sin ajustar**: MES, MNQ, MYM, MGC — ver §2.x. El **universo efectivo** de una corrida excluye los instrumentos cuyo ancla de rango de apertura no esté verificada (hoy: MGC)` |
| §7.2, tabla de gates C | *(C1, C2)* | *(C1, C2 idénticos)* + fila **C3** (`≤ 50% del max_loss_limit`), marcada **restricción de dimensionamiento**, con columna *Efecto al incumplirse* = "se reduce la canasta" + regla de `k_max` + requisito de reporte de correlación y `n_eff`, sin umbral |
| §7.3, fila P3 | `P(breach del límite diario en un mes fondeado) \| < 2% — evaluado sobre equity flotante intradía… El breach también ocurre si la pérdida contra el balance del día anterior cruza el 5%…` | `P(en un mes fondeado, la pérdida intradía de **un solo día** consuma el colchón disponible hasta el **umbral vinculante** al inicio de ese día) \| **< 2%** — el umbral vinculante es el `daily_loss_limit` si la ficha lo declara, y el `max_loss_limit` trailing si no. Ver nota de dominancia con G7` |
| §7.5, viñeta GO-PARCIAL | `**GO-PARCIAL**: pasa en subconjunto de símbolos → incubación restringida.` | `**GO-PARCIAL**: pasa **C+P+T** —incluido **C1 ≥ 60% del universo**— pero no en la totalidad de sus instrumentos → incubación restringida a los supervivientes, **equiponderados**. Nunca es vía para eludir C1: fallar C1 es NO-GO. Con \|U\| = 4, C1 exige **3 de 4**` |
| `CLAUDE.md:5`, `AGENTS.md:7`, `README.md:168`, `PROPUESTA_LABORATORIO…:615` | `SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` | `SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md` |

---

## Criterios de aceptación (evals ejecutables)

```
DADO el directorio docs/ del repo
CUANDO se ejecuta `fd 'SPEC_GENESIS_v1\.5' docs/`
ENTONCES retorna exactamente 1 archivo: docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md
```

```
DADO docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `git status --porcelain docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md`
ENTONCES la salida es vacía (el v1.4 permanece byte a byte idéntico; queda como histórico)
Y lo mismo para v1.1, v1.2 y v1.3
```

```
DADO el repo completo
CUANDO se ejecuta `rg -l 'SPEC_GENESIS_v1\.4' --glob '!.pulse/changes/**' --glob '!docs/SPEC_GENESIS_v1*'`
ENTONCES la única coincidencia es src/genesis/strategy/contract.py (excepción declarada en R16)
```

```
DADO docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `rg -n 'US500|NAS100|US30|GER40|The5ers|FTMO|MetaTrader|MT5' docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md`
ENTONCES toda coincidencia cae dentro de: el changelog v1.4→v1.5 o anteriores, §1.3.1/§1.3.2 (fichas
  históricas), §2.x (universos heredados de los Candidatos A y C), o §4 (fila de mt5_export.py marcada
  como régimen histórico)
Y ninguna coincidencia aparece en §2.3 (definición normativa del Candidato B) ni en §7
```

```
DADO docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `rg -n 'MES|MNQ|MYM|MGC' docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md`
ENTONCES aparecen en §1.3.0 (hedging), §2.3 (universo y anclas) y §2.x (tabla del universo)
```

```
DADO docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md
CUANDO se extraen los umbrales de §7.1–§7.4
ENTONCES son idénticos a los de v1.4 para G1–G9, C1, C2, P1, P2, P4, P5, P6, T1, T2
Y P3 conserva el umbral `< 2%` con definición nueva
Y C3 (`≤ 50% del max_loss_limit`) es la única fila añadida, marcada como restricción de dimensionamiento
Y no existe ninguna fila de gate con umbral de correlación de Pearson entre instrumentos
```

```
DADO docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md
CUANDO se busca en §7.2 y §7.5 el efecto de incumplir C3
ENTONCES dice "se reduce la canasta" y en ningún lugar dice que incumplir C3 produzca NO-GO
Y §7.5 define GO-ACOTADO con su tabla de distinción frente a NO-GO y GO-PARCIAL
Y la forma canónica del veredicto incluye la canasta: `GO (candidato X, firma Y, canasta {…})`
```

```
DADO docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md
CUANDO se ejecuta `rg -n 'no verificado|PENDIENTE|a confirmar' docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md`
ENTONCES aparecen al menos: ancla de MGC, política de VPS, comisiones por contrato, precio del plan,
  hedging entre instrumentos related, datos de M2K, proveedor de datos CME
Y ninguno de ellos aparece rellenado con un valor concreto en la ficha de §1.3.0
```

```
DADO docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md
CUANDO se busca la nota de delimitación de ámbito P3/G7 en §7.3
ENTONCES existe, y afirma que G7 es por símbolo y P3 a nivel de cuenta, y que P3 SÍ vincula
Y NO aparece en ninguna parte del documento la afirmación de que G7 domina a P3 o de que P3 es no vinculante
```

```
DADO docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md
CUANDO se busca en §7.5 la palabra "pre-registrada"
ENTONCES aparece únicamente para declarar que NO rescata a un candidato que falla C1
Y no existe ninguna cláusula que admita GO-PARCIAL por debajo del 60% de C1
```

```
DADO el repo
CUANDO se ejecuta `git status --porcelain src/ tests/`
ENTONCES la salida es idéntica a la de antes del change (ninguna entrada nueva)
```

```
DADO el ciclo SDD
CUANDO el change llega a review
ENTONCES `mise run ci` pasa sin cambios respecto del baseline (change doc-only; no debería tocarlo,
  se corre como red de seguridad)
```

---

## Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | **El spec describe una firma que puede reescribir su rulebook.** Apex lo hizo en 2026 y dejó todo su producto anterior como "Legacy" | R5 exige fecha de lectura por parámetro y reverificación obligatoria a los 6 meses |
| 2 | **`p_pass` sobreestimado mientras la capa 3 no implemente `trailing_eod` en dólares.** El modelo actual (% del pico móvil) da más aire a medida que el pico sube | R4 bloquea explícitamente la simulación multi-activo concurrente; el change de capa 3 es prerrequisito de cualquier veredicto sobre esta ficha. Declararlo en el spec no lo arregla, pero impide emitir un GO sobre él |
| 3 | **El ledger (#53) no existe y el régimen es de selección.** Sin él G4 deja de proteger en silencio | R9 y R14 lo convierten en prerrequisito explícito y declaran invalidado el sanity-check de alcanzabilidad hasta entonces |
| 4 | **La canasta puede quedar reducida a 1 instrumento** si el drawdown conjunto no cabe en medio presupuesto | Ya no produce NO-GO: produce **GO-ACOTADO** con la canasta declarada (R13.d). El riesgo que queda es el inverso — que `risk_pct` se calibre *después* de ver resultados para agrandar `k_max`. R11 lo prohíbe explícitamente y exige registrar la pareja (`risk_pct`, `k_max`) con fecha de pre-registro |
| 5 | **El universo efectivo del Candidato B se reduce a 3 instrumentos** si el ancla de MGC no se cierra. Contraer el denominador de C1 habría sido una rebaja encubierta del gate (2 de 3 pasa; 2 de 4 no) | R7 fija el denominador en el **universo normativo**: lo no evaluable cuenta como no superado. El Candidato B queda obligado a pasar en los tres micro-índices mientras MGC siga pendiente — más exigente, no menos |
| 6 | **Deriva documental**: v1.5 nace declarando siete pendientes | Es la alternativa correcta a rellenarlos con memoria del modelo. R15 los centraliza en §11.1 con su bloqueo asociado |
| 7 | **El docstring de `contract.py` queda apuntando a v1.4** | R16 lo declara como excepción trazable, no como olvido; la referencia sigue siendo correcta en contenido |

---

## Preguntas abiertas — elevar al humano antes de `DESIGN → APPLY`

Las tres primeras surgieron **al redactar la delta exacta**, no estaban en `proposal.md`, y cambian
texto normativo. Ninguna se resuelve sola.

### PA-106-1 — El "corolario duro" tal como se aprobó en `propose` relajaría C1

`proposal.md` admite GO-PARCIAL para un candidato que pasa en **un solo** instrumento si existe una
hipótesis pre-registrada. Con `|U| = 4`, pasar en uno es **C1 = 25% < 60%** ⇒ el candidato **ya falla
los gates C**. Admitir GO-PARCIAL ahí sería **relajar C1**, contra el invariante del proyecto.

**Resolución propuesta y ya escrita en R13:** el corolario se conserva como **fundamento económico de
C1** (un mecanismo que aparece en uno de cuatro emparentados es evidencia en contra), C1 lo hace
cumplir mecánicamente, y **no se escribe ninguna excepción**. La hipótesis pre-registrada (#88)
interpreta resultados y gobierna la ampliación futura del universo; no rescata gates.

**Qué se pierde:** nada operativo. **Qué se gana:** §7.5 deja de tener una cláusula que se lee como
bypass. **Requiere tu visto bueno** porque revierte una decisión tomada en `propose`.

### PA-106-2 — ~~P3 queda no vinculante~~ → **RESUELTA: P3 sí vincula** (corregida 2026-09-11)

**La versión original de esta pregunta contenía un error de mi parte**, detectado por la revisión
independiente con `gemini-3.8-flash-high`. Se deja registrada con su corrección porque el gate humano
aprueba el razonamiento, no solo la conclusión.

**Lo que afirmé:** con Rapid EOD (sin DLL) el evento de P3 es un **subconjunto** del de G7, con
umbral más laxo (2% mensual ≈ 21% anual, contra 5% anual), luego G7 domina y P3 no vincula.

**Por qué era falso:** la aritmética de umbrales era correcta, pero el argumento de subconjunto
presuponía que P3 y G7 miden sobre el **mismo ámbito**, y no lo hacen. El propio v1.4 los separa en
los títulos: §7.1 *"Gates G — robustez **por símbolo** y candidato"* frente a §7.3 *"Gates P —
economía prop **a nivel de cuenta**"*. Un evento de ruina de **cartera** —tres stops simultáneos por
un mismo shock macro consumiendo el colchón en una mañana— **no aparece en ninguna corrida por
símbolo de G7**. Y en etapa fondeada, los retiros vacían el excedente sobre el colchón, cosa que la
MC de G7 (curva continua, sin retiros) tampoco modela.

**Resolución adoptada:** P3 conserva definición generalizada y umbral `< 2%`, y §7.3 gana una nota
que **delimita ámbitos** en vez de declarar dominancia. P3 es la única salvaguarda de la cuenta
fondeada contra el shock intradía de cartera. Sin decisión pendiente del gate humano sobre este
punto: el error está corregido, no en disputa.

**Lección que sí conviene registrar:** la aritmética de dos umbrales no dice nada si las dos
magnitudes se miden sobre poblaciones distintas. Fue el paso que salté.

### PA-106-3 — ~~C3a = 0.3 excluiría MES + MYM~~ → **RESUELTA: se elimina el gate de Pearson**

**Segunda corrección de la revisión independiente.** La pregunta original preguntaba si aceptar que
`C3a < 0.3` dejara fuera la canasta MES+MYM (correlación medida 0,445). La respuesta correcta no era
ninguna de las tres opciones que ofrecí: era **que el gate de Pearson no debía existir**.

**Por qué el anclaje a T2 no se sostiene** — tres razones, desarrolladas en R11:

1. T2 mide entre **candidatos** diseñados para no parecerse; C3a medía entre **activos** de la misma
   estrategia, que comparten beta estructural. Poblaciones distintas, líneas base distintas.
2. Fallar T2 **no mata** al candidato (se descarta el ensemble); fallar C3a lo mataba. El número
   viajaba, la consecuencia no.
3. `prop_sim` simula la **cuenta conjunta**: la correlación ya está incorporada en P1–P5. El gate de
   Pearson no agregaba protección, agregaba una condición de muerte redundante.

**Resolución adoptada:** queda **un solo gate C3** —drawdown conjunto intradía p95 en días de señal
simultánea ≤ 50% del `max_loss_limit`, anclado a **G6**— más un **requisito de reporte sin umbral**
de la matriz de correlación y del número efectivo de apuestas `n_eff`. Se mide lo que importa (ruina
conjunta), se reporta lo que informa (amplitud efectiva), y no se inventa ninguna constante.

**Segunda corrección, del dueño del proyecto (2026-09-11), sobre lo que yo había dejado en pie.**
Todavía escribí que si el peor día conjunto no cabe en medio presupuesto, el Candidato B era **NO-GO**.
Eso seguía mezclando dos preguntas: *"¿hay ventaja?"* la responde C1; *"¿entra la canasta en la
cuenta?"* es una pregunta de **capital**. No alcanzar el colchón para llevar cuatro instrumentos a la
vez no dice nada malo de la estrategia — dice que la cuenta es chica.

**Resolución final:** C3 deja de ser gate y pasa a ser **restricción de dimensionamiento**: determina
`k_max`, el número de instrumentos que la cuenta puede llevar simultáneamente. Incumplirla **reduce la
canasta**, no mata al candidato. El veredicto resultante es **GO-ACOTADO** (R13.d). El único NO-GO que
sobrevive por esta vía es el de `k_max = 1` fallando, que es **G6** — un solo instrumento que no cabe
en medio presupuesto —, y ese sí es un problema de la estrategia.

Lo que se conserva del razonamiento anterior es el control anti-minería: la reducción es **por tamaño
descendente, sin buscar subconjuntos**, con regla de composición pre-registrada, y con la calibración
`risk_pct` fijada antes de ver resultados. Ahí sí no se cede.

### PA-106-4 — Ancla del rango de apertura de MGC

No es decidible sin fuente primaria (página de producto de CME). Queda declarada en R7 y R15, y su
consecuencia —MGC fuera del universo **efectivo** del Candidato B hasta cerrarla— está escrita. No
requiere decisión tuya ahora; requiere que la aceptes como pendiente declarado en vez de rellenada.

---

## Trazabilidad

| Requisito | Origen |
|---|---|
| R1, R2 | Precedente change #20; `proposal.md` §2 |
| R3 | `proposal.md` Decisión 1; `idea.md` §1.1 |
| R4 | `proposal.md` Decisión 2; `idea.md` §2.2, §2.4 |
| R5, R6 | `proposal.md` Decisión 3; `idea.md` §3.2 |
| R7, R8 | `proposal.md` Decisión 4; `idea.md` §3.4 |
| R9 | `proposal.md` Decisión 4 (régimen de selección); `idea.md` §3.8 |
| R10 | `proposal.md` Decisión 5; `idea.md` §3.5 |
| R11 | `proposal.md` Decisión 4 (gate C3); `idea.md` §2.5 |
| R12 | `proposal.md` Decisión 6; `idea.md` §3.6 |
| R13 | `proposal.md` Decisión 4 (veredicto y corolario), **con la corrección de PA-106-1** |
| R14 | Consecuencia mecánica de R9 sobre §7.6 de v1.4 — no estaba en `proposal.md` |
| R15 | `proposal.md` Decisión 7; `idea.md` §3.7 |
| R16 | `proposal.md` §4 invariante 2 |
| R17, R18 | `proposal.md` §3 No-Objetivos y §4 invariante 1 |
