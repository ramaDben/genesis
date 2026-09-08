# Pre-registro de las hipótesis discrecionales

*(2026-09-07 — borrador. **La doctrina de salida ya está decidida: es exigida.** Las decisiones que
siguen marcadas `[DECISIÓN HUMANA]` no lo están, y hasta que lo estén este documento no habilita
ninguna corrida. Refs #88.)*

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

### H3 — La estrategia funciona con la salida asimétrica que el Playbook declara

**La doctrina de salida ya no es una hipótesis a arbitrar: es una dimensión EXIGIDA.** Decisión del
director el 2026-09-07, y la sección de dimensiones explica el porqué y lo que costó averiguarlo.

**Enunciado.** Con la salida por *Chandelier Trailing Stop* (máximo de 22 barras menos 3,0 × ATR,
monótono, `ratchet`) y sin ningún objetivo fijo, la estrategia tiene expectativa positiva neta de
costos y sobrevive los gates.

**Especificación previa, sin grados de libertad.** El par `(N = 22, k = 3,0)` viene de LeBeau y
Lucas (1992) y se verificó *walk-forward* el 2026-09-02 sobre 9.800 barras H1 por activo. No se
eligió mirando este backtest: se adoptó una norma previa. Por eso cuesta **cero ensayos**.

**Qué la falsifica.** Que la expectativa por operación sea nula o negativa una vez descontados
spread, comisión y deslizamiento; o que el resultado dependa de un solo activo; o que la
probabilidad de incumplir el límite de pérdida de la firma haga la cuenta inviable.

**Lo que esta hipótesis NO pregunta, y es deliberado.** No pregunta si el trailing es mejor que un
objetivo fijo. Esa comparación **ya se pagó** y su resultado no vuelve a estar en discusión: el
objetivo fijo queda fuera del método, no compitiendo con él. Volver a compararlos sería gastar el
presupuesto dos veces por la misma pregunta.

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

**Y un segundo defecto propio, del mismo día y de la misma clase.** La primera medición del híbrido
modelaba el tramo parcial como el resultado **final** del trailing recortado a un techo. Está mal:
ese tramo cobra al **tocar** el nivel, y el Chandelier devuelve hasta 3 × ATR desde el máximo, así
que una operación que tocó `+2 R` puede terminar en `+0,5 R`. El error sesgaba **contra** el
híbrido, y arrojó una destrucción del 104 % donde la simulación correcta da **59 %**. La detectó una
revisión externa, no la revisión interna, que es el mismo patrón que ya había pasado con la
corrección del DSR en D1.

Se deja escrito porque la dirección de un sesgo no vuelve válido un número: la conclusión no
cambió, pero el número publicado estaba mal, y un pre-registro que tolera eso no sirve para nada.

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

### Decisión tomada — la doctrina de salida es EXIGIDA (2026-09-07)

**La salida es el Chandelier `(N = 22, k = 3,0)` con `ratchet`, sin objetivo fijo y sin cierres
parciales.** No se compara contra nada: entra como premisa del método, no como eje de selección.
Costo: **cero ensayos**.

Se llegó ahí investigando si existía un híbrido legítimo, y conviene dejar por qué no, porque la
pregunta va a volver.

**No existe un nivel de objetivo que se pueda derivar.** Se evaluaron los cuatro candidatos que el
propio modelo ADC + ATR ofrece, y ninguno sobrevive:

| Candidato | Por qué no |
|---|---|
| El impulso proyectado, `1,5 × ATR(H1)` | Es el impulso de **ruptura**, trasplantado a un setup de retroceso donde el mercado no viene de comprimir. Y ese nivel ya está medido como perdedor |
| El punto medio del canal | En tendencia alcista queda **debajo** de la entrada, y el motor ya lo usa como regla de invalidación en contra |
| El borde del canal | Cruzar el máximo de 50 barras es la señal de **agregar**, no de liquidar (Donchian, base del Turtle) |
| El ATR restante del día | Es un gate por diseño, decae con el reloj (el objetivo dependería de la hora de la señal) y le impone horizonte de una sesión a algo cuya tenencia mediana es 9,7 h repartida en 2 a 4 sesiones |

**Y hay una razón aritmética que cierra la puerta.** Con el stop inicial en `1,5 × ATR` y el
trailing a `3,0 × ATR` del máximo, el stop arrastrado **no supera al inicial hasta que el precio
avanza `1,5 × ATR`**, y alcanza el precio de entrada solo en **`+3,0 × ATR`**. Así que un parcial
antes de `+3,0 × ATR` no está derivado de nada; y en `+3,0 × ATR` la posición ya es libre de riesgo,
donde cerrar una parte es lo contrario de lo razonable.

**La fracción a cerrar tampoco tiene anclaje.** Kelly (1956) dimensiona apalancamiento y el
*volatility targeting* dimensiona el lote inicial; ninguno prescribe liquidaciones parciales. Toda
fracción es un parámetro libre.

**Medido, además, el híbrido no protege la cuenta**, que era el único argumento serio a su favor.
Con 1 % de riesgo por operación (o sea 1 R = 1 % de la cuenta), sobre 99 días con operaciones:

| Variante | Peor día | Días ≤ −4 R | Días ≤ −5 R |
|---|---|---|---|
| Chandelier puro | −10,00 | 6 | 4 |
| 33 % en 2,0 R + trailing | −10,00 | 6 | 2 |
| 50 % en 1,5 R + trailing | −10,00 | 6 | 2 |

El peor día y la cantidad de días que reventarían un límite del 4 % son **idénticos**. El motivo es
estructural: los días que explotan son días en que todo pierde, y **en una operación perdedora el
parcial nunca se gatilla**. El híbrido recorta arriba y no protege abajo.

Lo que sí protege la cuenta es otra cosa, y no es la salida: **un peor día de −10 R son diez
operaciones simultáneas al 1 % perdiendo juntas.** Eso es concurrencia y dimensionamiento, y se
trata aparte.

**Lo que costó averiguarlo, declarado:** unas **25 variantes de salida comparadas**, que bajo D1 son
ensayos y van al ledger. Calibrar un híbrido de verdad habría costado **96 combinaciones** (4
niveles × 4 fracciones × 3 reglas de stop del remanente × 2 políticas de horizonte); con 241
eventos, cualquier ganadora de esa grilla sería sobreajuste.

**La lección, que es de este proyecto y conviene no volver a pagar:** averiguar si existía el
híbrido costó unos 25 ensayos y la respuesta fue usar la doctrina que el Playbook ya declaraba, que
cuesta cero. Es «ambición en construir es gratis; ambición en buscar es cara y no reembolsable»,
demostrado.

### El hueco que deja la doctrina exigida, declarado

Habilitar la salida sin objetivo fijo tiene una consecuencia que corresponde escribir acá y no
enterrarla en un artefacto de ciclo: **para una intención sin objetivo, el embudo pre-trade queda
sin verificación de viabilidad.**

El embudo veta por riesgo/beneficio mínimo, y ese cociente no existe cuando la salida no tiene
techo. La decisión (2026-09-07, delegada, en el Change #97) es que el veto **no aplica** en ese
caso, así que quedan dos frenos previos a la operación: la ventana de noticias y los límites de
lotaje. No hay verificación de calidad de entrada.

**No es aflojar un gate normativo**: los gates go/no-go del torneo (G1-G9, C1-C2, P1-P3) no
contienen ningún criterio de riesgo/beneficio, y el umbral del embudo es un **default de
configuración**, no una política declarada. Los gates que deciden un GO miden **desempeño** (PF con
costos completos, probabilidad de breach, breach diario) y quedan intactos.

**Y no hay criterio medido con el que construir un sustituto.** Sobre las mismas 241 operaciones,
ninguna cantidad pre-trade separa las buenas de las malas:

| Candidato a freno | Correlación con el resultado | Por cuartiles |
|---|---|---|
| ADX de entrada | −0,009 | no monótono: el cuartil más bajo es el mejor (+0,75 R) |
| Espacio libre al borde del canal | +0,086 | no monótono: el cuartil sin espacio da +0,57 R |

Las señales que entran con menos espacio libre que su propio riesgo (40 % del total) rinden
+0,31 R contra +0,32 R del resto. La hipótesis de que un filtro de asimetría protege de la
«entrada tardía en agotamiento» es plausible y **no aparece en esta medición**; podría aparecer con
un obstáculo de temporalidad mayor, que no se midió.

Consecuencia para el conteo: **construir un freno de reemplazo calibrado con estos datos costaría
ensayos** y no tendría sustento. Se declara el hueco y no se tapa.

Lo que la evidencia sí señala como protección efectiva no es un filtro de entrada: es la
concurrencia. El peor día medido fue de **−10 R** y viene de operaciones simultáneas, no de la
salida. Es el issue #96.

### Dimensiones exigidas que hay que declarar antes de correr, y todavía no tienen valor

Salieron de la misma investigación y **no cuestan ensayos si se declaran como regla**. Cuestan si se
eligen midiendo.

| Dimensión | Por qué hace falta | Estado |
|---|---|---|
| Operaciones simultáneas máximas | Con 1 % por señal, el riesgo del día se acumula: el peor día medido es −10 R | sin declarar |
| Riesgo por operación en climas de shock (R1, R3) | El Playbook ya cierra el trailing a `2,0 × ATR` y recorta el apalancamiento al 50 % para rally de crudo sin confirmación del cobre; el riesgo unitario no está declarado | sin declarar |

### `[DECISIÓN HUMANA]` 2 — el presupuesto de ensayos (D4)

D1 dejó explícito que el ledger **no tiene reset sancionado y el listón solo sube**, así que D4 es
el único freno que existe. Este pre-registro no puede fijarlo: es el techo que el dueño del
proyecto le pone a su propia búsqueda.

Lo que sí puede decir es el piso implícito de lo pre-registrado acá:

| Concepto | Ensayos |
|---|---|
| Elegir cuál de los tres setups se reporta | 3 |
| Por símbolo, si se acepta un subconjunto | 1 cada uno |
| La doctrina de salida | **0** (exigida, ver arriba) |
| Ya gastados el 2026-09-07 y pendientes de anotar | **~30** |

Los ~30 gastados son las cinco salidas del diagnóstico inicial más las ~25 variantes de la
investigación del híbrido. **No están en el ledger porque el ledger no está cableado**, y ése es
justamente el punto de la primera precondición: se gastaron de verdad, el sistema no los cuenta, y
el DSR de la próxima corrida los ignoraría en silencio.

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
| ~~1~~ | ~~La doctrina de salida~~ | ~~decisión~~ | **resuelta el 2026-09-07: exigida** |
| 2 | `[DECISIÓN HUMANA]` el presupuesto de ensayos (D4) | decisión | todo |
| 3 | `[DECISIÓN HUMANA]` concurrencia máxima y riesgo unitario en R1/R3 | decisión | nada, pero sin declararlas el resultado no es interpretable |
| 4 | Cablear `record_trial_completions` y derivar `_N_TRIALS_*` de `GridConfig` | ciclo SDD | el conteo honesto de todo |
| 5 | **Salida por trailing en la capa 3** | ciclo SDD | **H1, H2 y H3, o sea todo** |
| 6 | Historia suficiente para una ventana institucional | capa 1 | las tres a ventanas institucionales |

**Declarar la salida como exigida movió el punto 5 al camino crítico, y conviene ver por qué.**
Mientras la doctrina estaba en discusión, el trailing en la capa 3 solo bloqueaba a H3 y solo si se
decidía compararlas. Ahora el trailing **es** la salida del método: sin él, genesis no puede
representar la estrategia del operador en absoluto, así que no puede evaluar ninguna de las tres
hipótesis. Pasó de condicional a bloqueante.

Y la decisión **descargó** la prelación que este documento traía. El argumento para poner el ledger
antes del trailing era que un eje de selección que el sistema no puede contar es peor que no
tenerlo. Al quedar la salida exigida, el trailing **no agrega ningún eje de búsqueda**: es una
premisa. Así que 4 y 5 pueden ir en paralelo, y el 4 sigue haciendo falta por los otros ejes que sí
son de selección (los setups y los símbolos) y porque `_N_TRIALS_SIGNAL` está clavado en 9.

---

Ver `mem:proposito-real-y-alcance-de-genesis` (bloque B1),
`mem:d1-que-cuenta-como-ensayo`, `mem:d3-holdout-oos-intocable`,
`mem:ledger-de-ensayos-decisiones-de-diseno` y
`mem:corrida-institucional-2026-08-us500-primera-e2e-real`.
