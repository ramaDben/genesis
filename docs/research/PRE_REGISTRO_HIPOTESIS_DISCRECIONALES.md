# Pre-registro de las hipótesis discrecionales

*(2026-09-07 — borrador. Las dos decisiones marcadas `[DECISIÓN HUMANA]` no están tomadas, y
hasta que lo estén este documento no habilita ninguna corrida. Refs #88.)*

## Por qué este documento va antes de correr

La entrevista de estatutos reencuadró el primer trabajo de genesis, y quedó registrado en
`mem:proposito-real-y-alcance-de-genesis`, bloque B1:

> El primer trabajo de genesis no es buscar edge genéricamente: es **arbitrar las hipótesis
> discrecionales que el operador ya acumuló**.

De ahí sale una acción que el mismo bloque describe como «gratis y todavía no hecha»:
pre-registrar esas hipótesis por escrito **antes** de correr nada (RFC §9 regla 2). El motivo no
es formalismo. Bajo D1 (`mem:d1-que-cuenta-como-ensayo`, ratificada sin enmiendas), una hipótesis
formada antes de tocar los datos y especificada por adelantado es un ensayo con **cero grados de
libertad**, la categoría más barata que existe. Escrita después de la primera corrida deja de ser
un ensayo limpio, y esa degradación es irreversible: no hay redacción posterior que la recupere.

Y hay una trampa que el propio B1 nombra y que este documento no puede disolver, solo declarar:

> Las hipótesis nacieron mirando estos mismos gráficos. Testearlas sobre el mismo período no es
> fuera de muestra. Es la versión humana del problema de anticipación.

## Procedencia de las hipótesis

Salen del **Playbook de trading cuantitativo intermercado** del repo `grupo-analisis-mercado`, que
es el sistema discrecional que el operador viene usando y documentando. Ese Playbook no es una
corazonada: tiene un motor de régimen implementado (`macro_bias_engine.py`), fichas por activo con
sus vectores de transmisión y literatura citada, y un motor de tickets que emite entrada, stop y
objetivo de forma determinista.

Tres cosas que importan para el conteo de ensayos:

1. **Las hipótesis se formaron antes de que genesis existiera**, sobre observación discrecional de
   velas, estructura de precio y, más recientemente, regímenes macro. No se derivaron de una
   búsqueda sobre los datos de genesis.
2. **Los umbrales ya están fijados y publicados** en `config/playbook_config.yaml` del otro repo,
   con su fecha. No se van a ajustar para que un candidato pase: eso es exactamente lo que la
   cláusula A2 prohíbe («no se afloja un gate para que un candidato pase»).
3. **El período de observación del operador no está delimitado**, y eso es lo que hace inevitable
   la trampa de B1. Este documento lo declara como limitación conocida en vez de disimularlo.

## Las hipótesis, en forma falsificable

### H1 — La taxonomía de cinco climas tiene poder discriminativo

**Enunciado.** El estado macro se puede clasificar en cinco regímenes mutuamente excluyentes
(`R0_CALMA_RANGO`, `R1_SHOCK_INFLACIONARIO`, `R2_GOLDILOCKS_EXPANSION`,
`R3_ESTANFLACION_SHOCK`, `R4_RECESION_VUELO_CALIDAD`) a partir de la curva soberana de EE.UU., el
cobre y el petróleo, y **el régimen condiciona qué operativa tiene sentido**.

**Especificación previa.** El clasificador ya existe y es determinista: `evaluar_regimen_candidato`
más `aplicar_histeresis`, con los umbrales de `playbook_config.yaml`. Fechado sobre la historia
disponible desde 2003 da **5.951 días hábiles y 580 episodios**, repartidos R0 64,8 %, R2 17,9 %,
R3 10,9 %, R4 3,7 %, R1 2,7 %.

**Qué la falsifica.** Que las métricas de la misma operativa no se distingan entre climas más allá
del ruido de muestra. Si un candidato rinde igual en R0 que en R2 y R4, la taxonomía no está
aportando información y el régimen es decoración.

**Advertencia sobre el costo.** Cada definición de régimen que se pruebe y se descarte es un ensayo
bajo D1. Esta hipótesis se pre-registra con **una sola** definición, la ya publicada. Probar
variantes de umbral convierte al régimen en dimensión de selección y se paga aparte.

### H2 — Los tres setups capturan estructura, no ruido

**Enunciado.** Tres gatillos, mutuamente excluyentes y elegidos por el clima:

| Setup | Nombre en el motor | Cuándo | Condiciones |
|---|---|---|---|
| Ruptura por compresión | `BREAKOUT_ADC` | climas direccionales | canal Donchian 50 comprimido, cierre fuera, cuerpo ≥ 50 % del rango, rango ≥ 1,0 × ATR, RSI no extremo |
| Retroceso al promedio | `PULLBACK_EMA` | climas direccionales | ADX ≥ 20, EMA 20 > 50 > 100, la vela toca la EMA 20 y cierra del lado de la tendencia |
| Rebote en rango | `MEANREV_R0` | solo R0, ADX < 20 | la vela previa cierra fuera de la banda de Bollinger y la actual reingresa, con RSI extremo |

**Qué la falsifica.** Que la tasa de acierto y la expectativa de cada setup no se separen de lo que
daría una entrada aleatoria en el mismo clima, con los mismos costos.

**Limitación medida y declarada.** El primero de los tres **no dispara nunca** con el umbral de
compresión publicado: sobre 44.510 barras H1 de los cinco activos del Playbook, el ancho del canal
Donchian 50 medido en múltiplos del ATR tiene mínimo histórico **2,65** y mediana **8,14**, contra
un umbral de 2,5. Cero ocurrencias. Así que `BREAKOUT_ADC` se pre-registra como **no evaluable con
su parámetro actual**: o se mide con un umbral alcanzable, y entonces el umbral es una dimensión
de selección que se paga, o queda fuera de esta ronda. No se puede reportar como probado.

### H3 — La salida asimétrica supera al objetivo fijo en clima direccional

Ésta es la hipótesis que motivó abrir el frente, y es la más nítida de las tres.

**Enunciado.** En climas direccionales el Playbook prohíbe el objetivo rígido y manda salir por
*Chandelier Trailing Stop* (máximo de 22 barras menos 3,0 × ATR, monótono). La hipótesis es que esa
doctrina **domina** a cualquier objetivo fijo sobre la misma señal y el mismo stop inicial, porque
la distribución de retornos de seguimiento de tendencia tiene la cola derecha pesada y un techo
fijo la corta.

**Predicción falsificable, cuantificada.** Sobre la misma señal, mismo stop inicial y resultados
expresados en múltiplos del riesgo: la expectativa por operación del Chandelier es positiva y la de
todo objetivo fijo es nula o negativa, con una tasa de acierto **menor** en el Chandelier.

**Qué la falsifica.** Que un objetivo fijo iguale o supere la expectativa del Chandelier con costos
reales incluidos; o que la ventaja del Chandelier desaparezca al descontar spread, comisión y
deslizamiento; o que dependa de un solo activo.

**Estado de la evidencia: NO es evidencia.** Ver la sección siguiente, que existe precisamente para
que este número no se cite como validado.

## Lo que NO es evidencia, declarado antes de que alguien lo cite

El 2026-09-07, en el repo `grupo-analisis-mercado`, se corrió una medición sobre 241 señales de
retroceso al promedio dentro de episodios de clima direccional, comparando cinco salidas sobre la
misma señal y el mismo stop:

| Salida | Aciertos | R medio | R total |
|---|---|---|---|
| Objetivo fijo 1,0 × ATR | 56 % | −0,05 | −13,2 |
| Objetivo fijo 1,5 × ATR | 47 % | −0,05 | −13,0 |
| Objetivo fijo 2,0 × ATR | 43 % | +0,01 | +2,8 |
| Objetivo fijo 3,0 × ATR | 33 % | −0,00 | −0,0 |
| Chandelier 3,0 × ATR, N=22 | 31 % | **+0,30** | **+73,4** |

El resultado es consistente con H3. **Y no vale como validación**, por seis razones que se dejan
escritas para que nadie tenga que redescubrirlas:

1. **Sin costos.** Ni spread, ni comisión, ni deslizamiento, ni swap. La omisión favorece a la
   estrategia que rota más seguido por ganancias chicas, o sea al objetivo fijo, así que el sesgo
   va contra la conclusión y no a su favor. Pero sigue siendo una medición sin costos, y G3 exige
   costos completos.
2. **Sobre los mismos datos de los que salieron las hipótesis.** Es la trampa de B1, literal.
3. **Sin registrar en el ledger.** Bajo la decisión 2 de D1, una corrida de diagnóstico cuenta
   igual. Comparar cinco salidas es seleccionar sobre la dimensión de salida: **son cinco ensayos
   ya gastados** y no anotados en ninguna parte.
4. **Sin descuento por búsqueda.** No hay DSR, no hay PBO, no hay walk-forward ni purged K-fold.
   Un R medio crudo no es un veredicto.
5. **Con un defecto propio ya corregido.** La primera versión del script escribía el clima R1 con
   un nombre que no existe (`R1_INFLACION_SOBRECALENTAMIENTO` en vez de `R1_SHOCK_INFLACIONARIO`),
   así que **descartó los 22 episodios de R1 en silencio**. Corregido, la conclusión no cambió
   (241 señales en vez de 236; +0,30 R en vez de +0,28). Se deja anotado porque es exactamente la
   clase de falla que una corrida de genesis debe hacer imposible: un contrato por nombre que nadie
   verifica.
6. **Muestra chica y concentrada.** 241 señales en total, y el resultado del Chandelier lo carga
   un solo activo. Dos climas aportan 5 y 2 señales respectivamente: ahí no hay nada que concluir.

**Consecuencia operativa:** H3 entra a genesis como hipótesis pre-registrada, no como hallazgo
previo que haya que confirmar. La diferencia importa: un hallazgo previo invita a buscar hasta
reproducirlo.

## Clasificación de dimensiones bajo D1

D1 no es una lista, es un criterio: *cuenta como ensayo toda dimensión sobre la que
**seleccionas**; no cuenta ninguna sobre la que **exiges**.* La pregunta operativa es *«¿habrías
reportado este resultado si hubiera salido bien?»*.

### Exigidas — cuestan cero ensayos

| Dimensión | Valor exigido | Por qué no es selección |
|---|---|---|
| Clasificador de régimen | la definición publicada, sin variantes | no se elige entre definiciones; se usa una |
| Umbrales del Playbook | los de `playbook_config.yaml`, con su fecha | fijados antes; ajustarlos violaría A2 |
| Stop inicial | 1,5 × ATR H1, o swing de 20 velas si cae en `[0,5, 1,5] × ATR` | es la ley de riesgo, no un parámetro a optimizar |
| Riesgo por operación | 1,0 % del capital | ídem |
| Condiciones de cada setup | las de la tabla de H2 | especificadas por adelantado |

### Seleccionadas — cuestan ensayos

| Dimensión | Ensayos | Nota |
|---|---|---|
| Cuál de los tres setups se reporta | 3 | elegir el que rinde es selección |
| Símbolos, si se acepta un subconjunto | 1 por símbolo | el caso GO-PARCIAL del corolario de D1 |
| Umbral de compresión de `BREAKOUT_ADC`, si se busca uno alcanzable | ≥ 1 por valor probado | ver la limitación de H2 |

### `[DECISIÓN HUMANA]` 1 — la doctrina de salida

Es la decisión que abrió este frente, y tiene dos formas con precios distintos. **No se puede
tener las dos.**

- **Exigida** significa: *el candidato debe pasar todos los gates con objetivo fijo **y** con
  Chandelier*. Cuesta **cero ensayos** y **endurece** el listón, porque si una rama falla no hay
  GO. Pero no contesta la pregunta del operador: no le dice qué doctrina usar, le dice que su
  estrategia debe funcionar bajo las dos.
- **Seleccionada** significa: *se corren las dos y se reporta la que gana*. Contesta la pregunta y
  se paga.

Y el precio no es 2. «Chandelier» no es un valor, es una familia con al menos dos parámetros
(`N` barras del máximo y `k` múltiplo del ATR). Una grilla modesta de 3 × 3, más el objetivo fijo,
son **10 ensayos** por lo que en conversación suena a «una dimensión». Ése es el número que hay que
declarar.

### `[DECISIÓN HUMANA]` 2 — el presupuesto de ensayos (D4)

D1 dejó explícito que el ledger **no tiene reset sancionado y el listón solo sube**, así que D4 es
el único freno que existe. Este pre-registro no puede fijarlo: es el techo que el dueño del
proyecto le pone a su propia búsqueda.

Lo que sí puede decir es el piso implícito de lo pre-registrado acá: **3 setups + 1 por símbolo
aceptado**, más **10 si la doctrina de salida se declara seleccionada**, más los 5 ya gastados en
el diagnóstico del 2026-09-07 que corresponde anotar en el ledger cuando se cablee.

## Precondiciones técnicas, verificadas contra el código en `ebbf2e6`

Ninguna de estas cuatro es opinión. Las tres primeras hacen que una corrida de estas hipótesis, hoy,
produzca un número que parece un veredicto y no lo es.

### 1. El conteo de ensayos no está cableado, y hay un punto ciego peor que el ledger vacío

`ledger/trials.jsonl` mide **0 bytes**: ningún runner llama `record_trial_completions`, con tres
backtests reales ya corridos (`mem:corrida-institucional-2026-08-us500-primera-e2e-real`).

Y hay algo más específico: `_N_TRIALS_SIGNAL = 9` y `_N_TRIALS_EXECUTION = 27`
(`src/genesis/validation/wfa.py:56-57`) son **constantes literales** que no miran `GridConfig`, y
`n_trials_execution_total` (`wfa.py:548`) **no alimenta ningún gate** (`dsr_pbo.py:66` lo describe
como un cambio de una línea pendiente). La doctrina de salida encaja naturalmente como eje de
**ejecución**, que es donde vive `risk_pct`. Montada ahí, **amplía el espacio de búsqueda sin mover
el denominador del DSR ni un punto, sin error y sin warning.**

Es el «G4 dejaría de proteger en silencio» del `CLAUDE.md`, por un camino distinto al del ledger.

**Orden que sale de esto: el ledger va antes que la doctrina de salida.** Habilitar un eje de
selección antes de poder contarlo no es correr un riesgo estadístico, es agregar el primer eje de
búsqueda que el sistema es estructuralmente incapaz de contar. Es la misma prelación que el
`CLAUDE.md` ya declara por otro motivo («el ledger va antes que el arquitecto»).

### 2. La capa 3 no puede representar la salida de H3

`EntryIntent` tiene cuatro campos y ninguno es geometría (`strategy/contract.py:40-43`).
`RiskLevelsProvider.risk_levels` se invoca **una sola vez**, en `backtest/simulator.py:504`, dentro
del bloque de entradas nuevas, y el par se congela en `OpenPosition` (`simulator.py:554-563`), que
es `frozen=True`. El único `trailing` de `src/` es `MaxLossLimitKind.TRAILING`
(`backtest/risk_profile.py:27`), que es el ancla del drawdown de la firma y no un stop que se mueva.

**Genesis hoy no puede representar ninguna salida por stop móvil**, y el spec v1.4 declara en la
fila del simulador que soporta «trailing estructural (A)»: está declarado y no construido
(`docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md:459`).

Habilitarlo es cambio de comportamiento bajo `src/genesis/backtest/**` ⇒ **ciclo SDD completo con
compuerta humana**. El punto de diseño que no se puede resolver por convención: el máximo rodante y
el ATR solo pueden incorporar barras cerradas hasta `t-1`. Mover el stop con el `high` de la barra
en curso y resolver el fill dentro de esa misma barra es anticipación pura, y **no la cazaría
ninguna excepción**, porque `LookaheadError` protege el reloj, no la geometría. Tiene que quedar
cerrado por property test.

### 3. El universo y la aritmética de ventanas no alcanzan

De los cinco activos del Playbook, el store versionado cubre dos: **XAUUSD** y **NAS100** (el
equivalente del US100 del Playbook). **WTI, BRENT y USDCLP no tienen datos ni `SessionSpec`**
(`src/genesis/data/sessions.py` declara US500, NAS100, US30, GER40, XAUUSD, EURUSD, GBPUSD, USDJPY).

Y la cobertura es corta: `data/csv/XAUUSD.csv` y `NAS100.csv` van del **2025-11-03 al 2026-06-30**,
unos 8 meses, ~209.000 filas M1 cada uno. Las ventanas institucionales por defecto son IS = 252 y
OOS = 126 días, o sea **378 días hábiles para una sola ventana**, contra unos 170 disponibles.
**No entra ni una ventana.**

Las dos salidas, y las dos cuestan:

- **Exportar más historia** por la capa 1 (`data/mt5_export.py` ya existe). Es la única que permite
  una corrida institucional de estas hipótesis.
- **Correr con ventanas reducidas**, que es diagnóstico y bajo la decisión 2 de D1 **cuenta como
  ensayo igual**. Además `window_config` viaja dentro de `candidate_config`, así que una corrida con
  ventanas reducidas **no se deduplica** contra la institucional: son dos ensayos, no uno.

Reportar un resultado de ventanas reducidas como si fuera institucional es lo que ya pasó una vez
(el `WFE = 4.28` que resultó ser ruido de muestra chica con 48 trades OOS, ver
`mem:corrida-institucional-2026-08-us500-primera-e2e-real`).

### 4. D3 sigue abierta y se encarece con cada corrida

No existe ningún holdout (`mem:d3-holdout-oos-intocable`, verificado). La decisión está **reservada**
en el issue #81, y es irreversible en una sola dirección: se puede declarar hoy, no mañana sobre
datos ya mirados. Correr estas hipótesis **gasta parte de esa opción**. Se declara acá para que la
decisión de reservar, si se toma, no se tome después de haberla perdido.

## Qué se compromete a reportar este pre-registro

Para que un pre-registro sirva tiene que atarse las manos por adelantado:

1. **Se reporta el resultado de las tres hipótesis, salga como salga.** Un `no-go` de H1 es
   informativo y se publica igual: es la respuesta a la pregunta del hito de tres meses, que es
   «¿aprendimos si acá hay edge que encontrar?», no «¿encontramos edge?».
2. **No se ajusta ningún umbral del Playbook después de ver un resultado.** Si un umbral cambia, es
   una hipótesis nueva y un ensayo nuevo, y se pre-registra aparte.
3. **Todo ensayo se anota en el ledger**, incluidos los de diagnóstico, incluidos los cinco ya
   gastados el 2026-09-07.
4. **No se declara probado el setup que no dispara.** `BREAKOUT_ADC` queda fuera o se mide con un
   umbral declarado como selección.

## Qué falta para habilitar la primera corrida

| # | Qué | Vía | Bloquea |
|---|---|---|---|
| 1 | `[DECISIÓN HUMANA]` la doctrina de salida: exigida o seleccionada | decisión | H3 entera |
| 2 | `[DECISIÓN HUMANA]` el presupuesto de ensayos (D4) | decisión | todo |
| 3 | Cablear `record_trial_completions` y derivar `_N_TRIALS_*` de `GridConfig` | ciclo SDD | el conteo honesto de todo |
| 4 | Salida por trailing en la capa 3 | ciclo SDD | H3, si se declara seleccionada |
| 5 | Historia suficiente para una ventana institucional | capa 1 | H1, H2 y H3 a ventanas institucionales |

El orden no es negociable en un punto: **3 antes que 4**. Lo demás admite paralelo.

---

Ver `mem:proposito-real-y-alcance-de-genesis` (bloque B1),
`mem:d1-que-cuenta-como-ensayo`, `mem:d3-holdout-oos-intocable`,
`mem:ledger-de-ensayos-decisiones-de-diseno` y
`mem:corrida-institucional-2026-08-us500-primera-e2e-real`.
