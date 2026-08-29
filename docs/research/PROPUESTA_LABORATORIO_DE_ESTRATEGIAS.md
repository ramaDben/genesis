# Propuesta — Laboratorio de Estrategias (Academy Lab)

**Estado:** documento de estudio / RFC. No es un spec aprobado ni el `design.md` de un Change.
**Fecha:** 2026-08-11
**Origen:** lluvia de ideas externa (conversación con Perplexity, `Downloads/hay quienes hayan
backtesteado las ideas de bollin.md`) + verificación contra el código real del repo.

---

## 0. Qué es y qué no es este documento

**Es**: la consolidación de una propuesta para convertir genesis de *evaluador de un torneo de
tres candidatos* en un **laboratorio de investigación de estrategias publicadas**, con trazabilidad
intelectual y un contador de ensayos honesto.

**No es**: una autorización para implementar. Ninguna sección de aquí ha pasado por
`/pulse:specify` ni por `approve_design`. Las decisiones marcadas **[DECISIÓN HUMANA]** no las
puede tomar un agente.

**Convención de confianza** usada en todo el documento:

| Marca | Significado |
|---|---|
| **[VERIFICADO]** | Leído en el código o en artefactos del repo en la sesión del 2026-08-11 |
| **[PROPUESTO]** | Diseño nuevo, no existe todavía |
| **[DECISIÓN HUMANA]** | Requiere criterio del dueño del proyecto, no es una decisión técnica |

---

## 1. El punto de partida: qué es genesis hoy

### 1.1 Lo que existe **[VERIFICADO]**

Las cuatro capas están construidas. La capa de validación es, con diferencia, la más madura:

| Capa | Módulos relevantes para esta propuesta |
|---|---|
| 1. Datos | Export MT5 (M1 + ticks), calendario, sesiones, calidad, store Parquet, ficha de firma |
| 2. Estrategia | `contract.py` (`StrategyCandidate`), `inspector.py`, `common/` (VWAP, zonas), `candidate_a/`, `candidate_b/` |
| 3. Backtest | `simulator.py` (event-driven), `costs.py`, `ledger.py`, `metrics.py`, `risk_profile.py` |
| 4. Validación | `wfa.py`, `montecarlo.py`, `purged_cv.py`, `dsr_pbo.py`, `sensitivity.py`, `prop_sim.py`, `verdict.py`, `signal_diagnostic.py`, `trial_ledger.py` |

### 1.2 La asimetría que define el problema

genesis tiene **maquinaria de validación de grado institucional** y un **catálogo de candidatos
casi vacío**:

| Candidato | Estado **[VERIFICADO]** |
|---|---|
| A — CT sweep-fade | Parcial. `smc/` y `diagnostics.py` existen, pero **A no está en `CANDIDATE_REGISTRY`**: no es ejecutable. |
| B — ORB intradía | Ejecutable. Implementa `StrategyCandidate` y `RiskLevelsProvider`. |
| C — TSMOM | Diferido. El Issue K nunca se creó. |

Es decir: hay **un solo candidato ejecutable**. Toda la maquinaria de torneo, DSR de torneo y
gates T1/T2 —que compara candidatos entre sí— está construida y sin nada real que comparar.

**Esa asimetría es exactamente el argumento a favor del laboratorio.** El cuello de botella de
genesis no es la validación: es el suministro de hipótesis que validar.

### 1.3 Lo que NO existe **[VERIFICADO]**

- No hay paquete `indicators/`.
> **Enmienda del 2026-08-29.** Las dos afirmaciones de esta subsección quedaron obsoletas y se
> dejan tachadas en vez de borrarlas, para que el razonamiento original siga siendo legible.
> Lo que cambió: el 2026-08-28 el Candidato B se corrió de punta a punta sobre ~3 años de M1
> real de Moneta (US500), con las ventanas normativas y sin fixtures — veredicto `no-go`
> (WFE 0.35, DSR 0.0019, `p_pass` 0.122). El 2026-08-29 ese flujo quedó versionado en
> `scripts/run_pipeline.py`. Lo que **no** cambió: `ledger/trials.jsonl` sigue vacío, porque
> aquellas corridas usaron scripts que no lo invocaban. El argumento central de la propuesta
> —el cuello de botella es el suministro de hipótesis, no la validación— se sostiene intacto.

- ~~No hay runner ni CLI que ejecute el pipeline end-to-end.~~ Los `design.md` archivados de los
  issues G, H, I y J lo dejaron fuera de alcance de forma **explícita y repetida** ("mismo criterio
  que G con la CLI"). El único flujo completo es `tests/validation/test_integration_pipeline_j.py`,
  sobre fixtures sintéticas.
- `ledger/trials.jsonl` está **vacío** — sigue siéndolo, pero ya no por la razón que decía este
  documento (~~ningún candidato se ha corrido nunca sobre datos reales~~): se corrieron tres
  backtests reales el 2026-08-28 sin cablear el ledger. Son ensayos quemados que el DSR de la
  próxima corrida no contará: exactamente el sub-conteo que el #53 existe para impedir.

---

## 2. La visión y su orden forzoso

El README ya fija el destino:

> El destino es una **búsqueda automatizada de estrategias** — un arquitecto que proponga
> candidatos y aprenda del veredicto.

Y fija la razón por la que el orden no es negociable: el DSR deflacta por el número de ensayos,
pero antes de #53 solo contaba **la grilla interna de una corrida**. Una búsqueda que ocurre
*entre* corridas era invisible para el denominador. Con 500 candidatos propuestos, cada corrida
reportaría un DSR respetable calculado sobre 9 intentos cuando hubo 4.500, y **G4 dejaría de
proteger sin emitir señal de que dejó de hacerlo**.

De ahí el orden:

```
ledger de ensayos  →  laboratorio  →  arquitecto
   (#53, HECHO)       (esta propuesta)   (después)
```

Dos invariantes de la visión **ya decididos** y que esta propuesta hereda sin discusión:

1. El arquitecto emitirá un **genoma declarativo** sobre una gramática cerrada de primitivas
   forward-only, materializado por un ejecutor fijo y auditado. **Nunca un `on_bar` escrito por un
   modelo**: `LookaheadError` protege el framework, no la lógica que le metan adentro.
2. Su señal de retorno **no incluirá OOS** — solo métricas IS, diagnóstico de señal y taxonomía de
   rechazos. Un buscador que ve el OOS y ajusta *se convierte* en el mecanismo de sobreajuste.

---

## 3. Pieza 1 — El ledger de ensayos

### 3.1 Qué hace hoy **[VERIFICADO]**

`genesis.validation.trial_ledger` persiste un `TrialRecord` por `(candidate_id, symbol)` evaluado
en `ledger/trials.jsonl` (JSON Lines, versionado en git).

- El `trial_id` es un hash determinista de la **configuración completa del candidato** más las
  claves de identidad institucional de la corrida (`dataset_hash_by_symbol`, `firm_profile_hash`,
  `risk_profile_hash`). Derivación única sancionada: `TrialLedger.trial_id_for_config`.
- `run_verdict(..., ledger=...)` toma **un único snapshot de lectura** al inicio y calcula
  `extra = |trial_ids_del_ledger \ trial_ids_de_los_candidatos_de_esta_corrida|`. Ese `extra` sube
  al DSR efectivo (G4) y a T1.
- `run_verdict` **solo lee**. La escritura vive en el borde (`record_trial_completions`), junto a
  `write_verdict_artifacts`.
- **Invariante con property test**: el ledger solo puede **endurecer** un gate, nunca relajarlo —
  para todo `extra >= 0`, `dsr_efectivo(extra) <= dsr_efectivo(0)`.
- **Fuera de alcance**: concurrencia entre escritores. `append_trial` no es atómico entre procesos.
  Cualquier arquitecto que lance corridas en paralelo debe resolver esto antes de escalar.

### 3.2 La pregunta que el ledger NO resuelve

El ledger sabe **contar** ensayos. No sabe **qué es** un ensayo. Y esa definición es la decisión
más consecuente de toda la propuesta: determina si el laboratorio es viable o si se autoestrangula.

### 3.3 La regla propuesta **[PROPUESTO]** **[DECISIÓN HUMANA]**

> **Cuenta como ensayo toda dimensión sobre la que SELECCIONAS.
> No cuenta ninguna dimensión sobre la que EXIGES.**

El criterio operativo es la prueba de los grados de libertad del investigador: *¿habrías reportado
este resultado si hubiera salido bien?* Si la respuesta es sí, es un ensayo.

| Dimensión | ¿Cuenta? | Razón |
|---|---|---|
| Barrido de parámetros del que eliges el mejor | **Sí** | Es un máximo sobre N draws de la nula |
| Plantillas de las que eliges la ganadora | **Sí** | Selección |
| Autores de los que eliges el ganador | **Sí** | Selección |
| Activos donde **exiges** que todos pasen | **No** | Es una conjunción, no un máximo: más activos lo hace *más difícil*, no más fácil |
| Activos donde **eliges** el que funcionó | **Sí** | Selección disfrazada de robustez |
| Timeframes de los que eliges el mejor | **Sí** | Selección |

**Lo importante: esta regla no es nueva, es la generalización de lo que genesis ya hace.**
`n_trials_signal_total` cuenta la grilla interna del WFA (donde seleccionas los mejores parámetros
IS) y T1 suma `(n_candidatos_torneo − 1)` (donde seleccionas el ganador del torneo). Ambas son
dimensiones de **selección**. El ledger solo extiende la misma semántica entre corridas. Adoptarla
es consistencia, no convención nueva.

### 3.4 La matemática que la hace tolerable

El DSR deflacta usando el máximo esperado bajo la hipótesis nula, que crece con el cuantil normal
de `1 − 1/N`:

| N ensayos | `Z⁻¹(1 − 1/N)` | Crecimiento vs. N=100 |
|---|---|---|
| 100 | 2.33 | — |
| 1.000 | 3.09 | +33 % |
| 10.000 | 3.72 | +60 % |

**El crecimiento es logarítmico, no lineal.** Multiplicar los ensayos por 100 sube el listón ~60 %.
Eso significa que un laboratorio que acumula miles de ensayos **es viable**: no se autoestrangula.
Pero cada ensayo sigue siendo un gasto irreversible que encarece permanentemente todo lo que venga
después.

### 3.5 Por qué, ante la duda, hay que contar de más

El error es **asimétrico** (registrado como D2 en las memorias de #53):

- **Sub-contar** relaja el gate **en silencio**. El resultado es un `GO` falso que cuesta dinero
  real, y no hay señal de que ocurrió.
- **Sobre-contar** solo cuesta oportunidades perdidas, y **te enteras**: ves el candidato que
  quedó cerca del umbral.

Combinado con el crecimiento logarítmico, sobre-contar es barato. **No optimices esto.**

> **Refinamiento diferido**: la corrección por correlación (que Bollinger 19/2.1 y 20/2.0 no son
> dos ensayos independientes sino ~1, y que el N *efectivo* es menor que el nominal) es legítima
> y está en la literatura. Pero es una optimización **en la dirección peligrosa** — reduce el
> denominador. Déjala para cuando el listón sea demostrablemente vinculante, nunca antes.

---

## 4. Pieza 2 — Indicadores como primitivas incrementales

### 4.1 La restricción que la propuesta externa no vio

El documento de origen propone `src/genesis/indicators/bollinger.py` con funciones que calculan
columnas sobre un dataframe. Ese es un modelo mental **vectorizado**, y es incompatible con genesis.

**El contrato real [VERIFICADO]** (`src/genesis/strategy/contract.py`):

```python
class StrategyCandidate(Protocol):
    candidate_id: str

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        """Procesa una barra ya cerrada y retorna las intenciones de entrada emitidas."""
```

Consecuencias que la propuesta externa nunca menciona:

1. El candidato ve **una barra a la vez**, ya cerrada. No hay dataframe, no hay `.rolling()`.
2. El estado es **incremental y forward-only**. Violarlo levanta `LookaheadError`.
3. La propiedad central verificada con `hypothesis`: **ningún output de `on_bar(t)` cambia si se
   mutan barras posteriores a `t`**. Todo indicador nuevo hereda esta obligación de test.
4. `on_bar` retorna **solo entradas** (`EntryIntent`). Las salidas no viajan por aquí: van por el
   protocolo separado de niveles de riesgo (`RiskLevelsProvider`, que implementa el candidato B).
   El genoma tiene que expresar las salidas por esa otra vía.

### 4.2 Es factible, y esa es la buena noticia

Bollinger y MACD son **naturalmente incrementales**:

| Primitiva | Estado incremental necesario |
|---|---|
| SMA(n) | Buffer circular de n valores + suma corrida |
| Desviación estándar(n) | Suma y suma de cuadrados corridas (o Welford para estabilidad numérica) |
| Bollinger (upper/middle/lower/bandwidth/%B) | Deriva de los dos anteriores |
| EMA(n) | Un solo float: `ema += α(x − ema)` |
| MACD (línea/señal/histograma) | Tres EMAs anidadas |
| ATR(n) | EMA/SMA del true range, que solo necesita la barra previa |

Ninguno requiere ver el futuro. La conversión es mecánica. **Pero hay que escribirlos como
estimadores online desde el principio**, no portar código vectorizado.

### 4.3 Criterio de admisión de una primitiva **[PROPUESTO]**

Una primitiva entra a la gramática solo si cumple las cuatro:

1. Estado acotado y actualizable en O(1) o O(ventana) por barra.
2. Su valor en `t` depende exclusivamente de barras `≤ t`.
3. Tiene un período de calentamiento explícito y declarado (emite "no disponible", nunca un valor
   parcial silencioso).
4. Pasa el property test de invarianza ante mutación de barras futuras.

**Quedan excluidas por construcción**: cualquier cosa que requiera normalización sobre el historial
completo (z-scores globales, percentiles calculados sobre todo el dataset, ranking cross-sectional
que mire adelante). El documento de origen sugiere "bandwidth bajo su percentil histórico" — ojo:
solo vale si el percentil se calcula sobre una ventana **expansiva hacia atrás**, nunca sobre el
dataset entero.

---

## 5. Pieza 3 — Autores, doctrinas, hipótesis y procedencia

### 5.1 La separación en tres niveles

La propuesta externa acierta al insistir en no mezclar tres cosas distintas:

```
AUTOR          →  la escuela o fuente intelectual        (Bollinger, Appel, Elder)
   ↓
HIPÓTESIS      →  la afirmación económica falsable       ("los extremos de volatilidad revierten")
   ↓
ESTRATEGIA     →  una implementación concreta            (BB 20/2 mean reversion, salida en media)
```

Un autor tiene varias hipótesis; una hipótesis genera múltiples estrategias. Confundirlos produce
la conclusión inútil de "Bollinger funciona" o "MACD no funciona", cuando la pregunta correcta es
**qué regla tiene expectativa positiva bajo qué régimen, activo y estructura de costos**.

### 5.2 Procedencia intelectual: el vacío real de genesis

Esta es **la única aportación genuinamente nueva** de la propuesta externa, y apunta a un hueco
real.

genesis hoy tiene **reproducibilidad de corridas** [VERIFICADO]: `config_version` + hash de dataset
+ `firm_profile_hash` + semillas + commit de git en cada artefacto. Puedes re-ejecutar una corrida
y obtener bit a bit lo mismo.

Lo que **no** tiene es **procedencia de ideas**: de dónde salió la regla, qué decía el original,
qué interpretaste tú, y qué agregaste por tu cuenta.

Por qué importa: cuando una regla publicada es ambigua —y casi todas lo son— **tu interpretación es
un grado de libertad del investigador**. "Comprar en la banda inferior" no dice si es al tocarla, al
cerrar fuera, o al volver a entrar. Elegir la variante que funcionó *después* de verlas todas es
sobreajuste, pero hoy no queda registrado en ninguna parte.

### 5.3 Los cuatro grados de fidelidad **[PROPUESTO]**

Toda estrategia del laboratorio se etiqueta con exactamente uno:

| Grado | Definición | Grados de libertad gastados |
|---|---|---|
| **Canónico** | La regla publicada con sus parámetros publicados | **Cero** |
| **Interpretado** | Una desambiguación explícita de una regla ambigua, elegida *a priori* | Uno por ambigüedad resuelta |
| **Optimizado** | Parámetros elegidos por barrido | Uno por dimensión barrida |
| **Combinado** | Dos o más autores/reglas mezclados | Los de sus partes, más la elección de combinación |

Este etiquetado no es documentación decorativa: **alimenta directamente el conteo de ensayos** de
la §3.3. Un canónico cuesta 1 ensayo; un optimizado sobre una grilla de 20 cuesta 20.

### 5.4 Qué registrar por cada regla **[PROPUESTO]**

```
author              — identificador del autor
work                — obra, capítulo o artículo
concept             — la doctrina (mean_reversion, trend_following, momentum, volatility)
original_rule       — la regla tal como fue publicada, en texto
market_assumption   — bajo qué régimen el autor afirma que funciona
interpretation      — qué desambiguaste tú, y por qué esa opción y no otra
fidelity            — canónico | interpretado | optimizado | combinado
parent              — de qué regla deriva (null si es canónica)
```

---

## 6. Pieza 4 — El genoma declarativo

### 6.1 Por qué declarativo

Ya está decidido en el README: nunca un `on_bar` escrito por un modelo. La razón es precisa:
`LookaheadError` protege **el framework**, no la lógica que le metan adentro. Si un generador puede
escribir Python arbitrario, puede escribir un lookahead que el framework no detecte.

Un genoma declarativo sobre una gramática cerrada elimina esa clase de fallo por construcción: solo
existen las primitivas admitidas en §4.3, todas ya verificadas forward-only.

### 6.2 Anatomía **[PROPUESTO]**

```
genome:
  primitives:      qué indicadores, con qué parámetros
  regime_filter:   condición de contexto (opcional, máximo 1)
  entry_trigger:   condición de disparo (exactamente 1)
  exit_rules:      condiciones de salida (1-2), vía RiskLevelsProvider
  direction:       long | short | both
  provenance:      el bloque de §5.4
```

Restricciones de complejidad **[PROPUESTO]** **[DECISIÓN HUMANA]** — límites duros para que el
espacio no explote:

```
MAX_PRIMITIVES         = 3
MAX_ENTRY_CONDITIONS   = 4
MAX_EXIT_CONDITIONS    = 2
MAX_OPTIMIZED_PARAMS   = 3
```

### 6.3 El compilador

Una función pura `compile(genome) -> StrategyCandidate`. El genoma es datos; el ejecutor es código
fijo y auditado que ya pasó los property tests. Esto da la propiedad clave: **añadir una estrategia
nueva no añade código nuevo que pueda violar el anti-lookahead**.

El genoma también es el `candidate_config` que ya acepta `CandidateValidationBundle`
[VERIFICADO]: el campo es un `Mapping[str, object] | None` deliberadamente sin esquema fijo,
precisamente para que el genoma entre por ahí sin tocar el contrato del ledger. **La pieza de
enganche ya está construida.**

### 6.4 Fricción verificada: `CANDIDATE_REGISTRY` es por letra

**[VERIFICADO]** `CANDIDATE_REGISTRY` es un `dict[str, type[StrategyCandidate]]` indexado por
**una letra** (`A`, `B`, `C`), poblado con el decorador `@register_candidate("B")`, que lanza
`DuplicateCandidateError` ante colisión.

Eso funciona perfecto para un torneo de tres candidatos y **no escala a un laboratorio**. Un
generador que produce 200 genomas no tiene 200 letras, y el registro por decorador asume clases
escritas a mano en tiempo de import, no objetos construidos en runtime.

~~**Es un cambio de contrato de la capa 2, no un detalle de implementación.** Hay que decidirlo
explícitamente **[DECISIÓN HUMANA]**: si el registro por letra se mantiene para el torneo A/B/C
y el laboratorio usa una vía paralela, o si se generaliza el identificador. Ambas opciones tienen
consecuencias sobre los artefactos ya emitidos (el `candidate_id` viaja hasta el manifest).~~

> **Corrección del 2026-08-29 — síntoma correcto, causa equivocada.** Todo lo descrito arriba
> sobre el registro es cierto, pero no era la fricción: `CANDIDATE_REGISTRY` **no tiene ninguna
> referencia en `validation/` ni en `backtest/`** (verificado por búsqueda), o sea que nunca
> estuvo en el camino de ejecución. El bloqueador real era que `CandidateB` estaba escrito a mano
> en tres sitios de la capa 4 (`wfa.py`, `dsr_pbo.py`, `sensitivity.py`), con sus kwargs propios.
>
> Eso abarata la decisión D2 en vez de encarecerla: no hacía falta tocar el contrato de capa 2 ni
> el `candidate_id` que viaja al manifest. Se resolvió con `genesis.strategy.factories`
> (PR #69, commit `52dcf2c`): un `CandidateFactory` de firma uniforme, **vía paralela** al
> registro, que el torneo A/B/C sigue usando sin cambios. Un test inyecta y ejecuta un candidato
> que no está en el registro ni hereda de nada, para probar que la costura sirve de verdad.

---

## 7. Pieza 5 — El arquitecto

El arquitecto es el generador que propone genomas. **Va último**, y esta propuesta lo describe solo
para que las piezas anteriores no se diseñen de una forma que lo imposibilite.

### 7.1 Su señal de retorno

Ya decidido: **sin OOS**. El arquitecto ve métricas IS, el diagnóstico de señal desnuda y la
taxonomía de rechazos. Nunca el resultado de validación.

La taxonomía de rechazos importa más de lo que parece: gracias al Change #51 [VERIFICADO], el
veredicto ya distingue un `NO_GO` por desempeño de un candidato que **nunca llegó a operar** porque
el sizer produjo lotes inviables (`sizing_evidence_insufficient`). Un generador que recibe `NO_GO`
en vez de "sin evidencia" **aprende de ruido y descarta familias enteras que nunca se probaron**.
Esa señal ya está construida y es un prerrequisito del arquitecto que ya está pagado.

### 7.2 Concurrencia — el bloqueador conocido

`append_trial` no es atómico entre procesos [VERIFICADO]. Un arquitecto que lance corridas en
paralelo necesita locking o un escritor único serializado. **Pendiente, sin diseño.**

---

## 8. Pieza 6 — Campañas y experimentos

### 8.1 Pre-registro **[PROPUESTO]**

Antes de correr nada, se escribe: la hipótesis, por qué la crees económicamente, qué vas a barrer,
cuál es la regla de selección, y **qué la falsaría**. Registrado **antes** de la corrida.

Sin esto, la regla de selección se ajusta retroactivamente a lo que salió — que es el mecanismo de
sobreajuste con otro nombre. El pre-registro es lo que convierte la §3.3 de una intención en una
restricción verificable: si la regla de selección está escrita de antemano, se puede auditar cuántos
ensayos correspondía contar.

### 8.2 Por qué NO un registro paralelo

El documento de origen propone `experiments/registry.py` + JSON de campañas. **No hacerlo.** El
ledger de #53 ya es el registro persistente, con `trial_id` determinista y derivación única
sancionada. Un segundo registro al lado se desincroniza y reintroduce exactamente el problema de
sub-conteo que #53 resolvió.

La campaña debe ser **metadata que apunta al ledger**, no un almacén paralelo de resultados.

---

## 9. Cómo dirigir el laboratorio — las cinco reglas

**El reencuadre que lo ordena todo: el recurso escaso no es cómputo, es presupuesto estadístico.**
Cada ensayo encarece permanentemente todo lo que venga después. Eso descarta de entrada el "genero
500 candidatos y veo cuál pega": es gastar el presupuesto entero en una lotería.

### Regla 1 — Empieza por lo canónico, que es gratis en grados de libertad

Bollinger 20/2 y MACD 12/26/9 con sus parámetros publicados son **un ensayo cada uno, con cero
grados de libertad**. Es el test más informativo por unidad de presupuesto que existe. Si el
canónico muere con tus costos y tus activos, eso es enormemente informativo y costó 1. Solo si
muestra señales de vida gastas presupuesto en variantes.

### Regla 2 — Pre-registro antes de correr

Ver §8.1.

### Regla 3 — Los filtros baratos ahorran CPU, NO presupuesto estadístico

Contraintuitivo y es donde más gente se equivoca. Si pruebas 100 hipótesis, 95 mueren en el
diagnóstico de señal desnuda, y reportas la mejor de las 5 sobrevivientes — **estadísticamente
sigue siendo un máximo sobre 100**, no sobre 5. El pre-filtro cambió qué computaste, no cuántas
veces miraste los datos con intención de seleccionar.

Usa el kill-switch de `diagnostics.py` para no quemar CPU. **No descuentes esos ensayos del
contador.**

### Regla 4 — Hipótesis primero, generador al final

No construyas el generador antes de haber corrido a mano dos o tres reglas canónicas. El generador
es la máquina de gastar presupuesto más rápido que existe, y hasta no haber visto *cómo* mueren las
reglas canónicas no sabes qué espacio de búsqueda vale la pena. Además es el camino más barato en
esfuerzo.

### Regla 5 — Reserva un OOS que nadie toca

Un período final que no participa de WFA, ni de purged CV, ni de sensibilidad — intocable hasta el
veredicto definitivo. Es lo único que te dice cuánto de todo lo anterior fue autoengaño.

**Pendiente de verificar**: si el WFA de genesis hoy consume todo el historial disponible o si ya
existe un holdout estricto. Si no existe, hay que crearlo **antes** de la primera campaña, porque
un holdout declarado después de haber mirado los datos no es un holdout.

---

## 10. Qué del documento de origen NO incorporar

| Propuesta externa | Por qué se descarta |
|---|---|
| Función de score ponderada (`0.30·sharpe + 0.20·sortino − 0.25·drawdown …`) | Genesis usa gates binarios mecánicos precisamente para que **un umbral no se pueda comprar con otro**. Con esa fórmula, un drawdown inaceptable se compensa con un Sharpe alto. Es lo contrario de "los gates nunca se relajan". |
| Rankear/seleccionar sobre resultados de validación (OOS) | Ya decidido en el README: la señal del arquitecto excluye OOS. El pipeline "descubrimiento → validación → ranking" del documento reintroduce el mecanismo de sobreajuste. |
| `experiments/registry.py` como almacén paralelo | Duplica y desincroniza el ledger de #53. Ver §8.2. |
| Indicadores vectorizados sobre dataframe | Incompatible con el contrato event-driven forward-only. Ver §4.1. |
| Métricas genéricas (Sharpe/Sortino/expectancy) como criterio | genesis no decide eso: decide si algo **sobrevive un challenge** — límites de pérdida diaria, drawdown máximo, probabilidad de breach. Una estrategia con Sharpe excelente puede ser `NO_GO` por reventar el límite diario. |
| Su auditoría de "errores de genesis" (sección final) | Inferida de nombres de directorios, no de leer el código. Ver §10.1. |

### 10.1 La auditoría del documento de origen es poco confiable

| Afirmación | Realidad **[VERIFICADO]** |
|---|---|
| "No hay evidencia de CI/CD" | Existe `mise run ci` (ruff + bandit + vulture + deptry + ty + pytest). El PR #56 mergeó con checks verdes el 2026-08-11. |
| "No hay semillas / git sha / data version" | Es un invariante ya implementado: `config_version` + hash de dataset + `firm_profile_hash` + semillas + commit en cada artefacto. |
| "No hay validación de datos" | La capa 1 tiene controles de calidad desde el Issue B (#2). |
| "Costos estáticos, riesgo de falsos positivos" | Hay modelo de costos con stress, y **G9 gatea sobre profit factor a 1.5× de costos**. |
| "Performance" | **Parcialmente válido** — hay issues reales abiertos (#24, #38, #46). |

*(Señal de fiabilidad: el documento de origen contiene literales rotos en sus bloques de código —
`sixteen`, `fifty`, `Aus?`. Es salida de LLM no revisada.)*

---

## 11. Impacto por capa

| Capa | Impacto | Detalle |
|---|---|---|
| 1. Datos | **Bajo** | Quizás más símbolos/timeframes si se quiere comparar entre activos |
| 2. Estrategia | **~90 % del trabajo** | Primitivas incrementales, plantillas, genoma, compilador, generador. Y el cambio de contrato del registro (§6.4) |
| 3. Backtest | **Ninguno** | El documento de origen acierta en no tocarlo |
| 4. Validación | **Bajo mecánicamente, alto semánticamente** | Poco código nuevo, pero la semántica del conteo de ensayos queda bajo presión máxima. `verdict.py` pasa a ser el filtro de selección |
| Transversal | **Nuevo** | La procedencia (autor/fuente/interpretación) no encaja limpio en ninguna capa: es metadata de identidad del candidato |

---

## 12. Decisiones abiertas **[DECISIÓN HUMANA]**

Ninguna de estas la puede tomar un agente. Están ordenadas por consecuencia.

| # | Decisión | Por qué es humana |
|---|---|---|
| **D1** | **Qué cuenta como un ensayo** (§3.3) | Define si el laboratorio es honesto. Es una postura sobre qué significa rigor estadístico en tu proyecto, no un detalle técnico |
| **D2** | Destino del `CANDIDATE_REGISTRY` por letra (§6.4) | Cambio de contrato de capa 2; el `candidate_id` viaja hasta el manifest |
| **D3** | ¿Existe ya un holdout OOS intocable? Si no, definirlo antes de la primera campaña (§9 R5) | Un holdout declarado después de mirar los datos no es un holdout |
| **D4** | Presupuesto de ensayos: ¿hay un techo declarado? | Fuerza priorización y hace explícito el costo de cada campaña |
| **D5** | Límites de complejidad del genoma (§6.2) | Determina el tamaño del espacio de búsqueda |
| **D6** | Qué autores y en qué orden | Elder tiene metodologías compuestas (Triple Screen) mucho más caras de formalizar que Bollinger o MACD |
| **D7** | Concurrencia del ledger (§7.2) | Bloqueador duro para cualquier búsqueda paralela |

---

## 13. Orden de implementación sugerido **[PROPUESTO]**

Cada fase es candidata a su propio Change del ciclo SDD. **Ninguna está aprobada.**

| Fase | Qué | Costo relativo | Desbloquea |
|---|---|---|---|
| **0** | Resolver D1 y D3 (decisiones, sin código) | Nulo | Todo lo demás |
| **1** | Primitivas incrementales: SMA, stddev, EMA, ATR + Bollinger y MACD derivados, con property tests forward-only | Bajo | Fases 2+ |
| **2** | **Dos estrategias canónicas a mano** como `StrategyCandidate` (BB 20/2 mean reversion, MACD 12/26/9 crossover) | Bajo | La primera señal real, por 2 ensayos |
| **3** | El runner end-to-end que hoy no existe (§1.3) | **Medio-alto** | Cualquier corrida real, incluida la del candidato B |
| **4** | Bloque de procedencia + grados de fidelidad | Bajo | Trazabilidad |
| **5** | Genoma declarativo + compilador; resolver D2 | Alto | El arquitecto |
| **6** | Generador con gramática cerrada y pre-registro | Alto | La búsqueda automatizada |

**Nota de secuencia**: la fase 3 (runner) es un prerrequisito compartido — hoy bloquea igualmente
la primera corrida real del candidato B, que ya es ejecutable y nunca se ha corrido. Conviene
tratarla como Change independiente, no como parte del laboratorio.

---

## 14. Resumen ejecutivo

1. genesis tiene validación de grado institucional y **un solo candidato ejecutable**. El cuello de
   botella es el suministro de hipótesis, no la capacidad de validarlas.
2. El laboratorio propuesto **es** el arquitecto que el README ya tiene decidido; los autores
   (Bollinger, Appel, Elder) son la semilla inicial de la gramática, no el fin.
3. Su prerrequisito —el ledger de ensayos (#53)— **está construido**. El timing es correcto.
4. La decisión que lo determina todo es **qué cuenta como un ensayo**. La regla propuesta —contar
   dimensiones de *selección*, no de *exigencia*— es la generalización de lo que genesis ya hace en
   `n_trials_signal_total` y T1.
5. El hurdle del DSR crece **logarítmicamente**: el laboratorio es viable. Pero cada ensayo es un
   gasto irreversible, así que se dirige como un presupuesto: **canónico primero, pre-registrado,
   con el generador como último paso y no como el primero**.
6. Del documento de origen se conservan el encuadre de hipótesis y la idea de procedencia. Se
   descartan la función de score ponderada, el ranking sobre OOS, el registro paralelo, el modelo
   vectorizado y la auditoría.

---

## 15. Referencias internas

| Recurso | Dónde |
|---|---|
| SSoT del proyecto | `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` |
| Visión y invariantes decididos | `README.md` §Visión |
| Ledger de ensayos | `src/genesis/validation/trial_ledger.py`, `ledger/README.md` |
| Contrato de capa 2 | `src/genesis/strategy/contract.py` |
| Señal de evidencia insuficiente | Issue #51, `verdict.py` |
| Ledger de ensayos (diseño) | Issue #53, memorias `ledger-de-ensayos-decisiones-de-diseno` y `arquitecto-estrategias-y-ledger-ensayos` |
| Documento de origen | `Downloads/hay quienes hayan backtesteado las ideas de bollin.md` (externo, no versionado) |
