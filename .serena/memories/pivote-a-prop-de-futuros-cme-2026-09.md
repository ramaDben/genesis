*(2026-09-11 — decisión de rumbo del dueño del proyecto + relevamiento verificado. NO es todavía un cambio de spec.)*

# Pivote: de CFDs MT5 a futuros CME en prop de futuros

## Qué decidió el usuario

El destino operativo de genesis deja de ser el torneo sobre **índices CFD en MT5 con prop firms tipo
FTMO/The5ers** y pasa a ser **futuros de CME operados en una prop firm de futuros**: oro, Nasdaq,
Russell, S&P, Dow (GC/MGC, NQ/MNQ, RTY/M2K, ES/MES, YM/MYM).

Firma elegida: **MyFundedFutures (MFFU)**, plan Rapid EOD, cuenta de 50K. Ver
`mem:mffu-rapid-eod-50k-reglas-confirmadas`.

**CERRADO el 2026-09-12 por el change #106**: el SSoT pasó a
`docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md`, que describe el régimen de futuros CME. El
v1.4 queda como histórico. Durante un tiempo el spec siguió describiendo el mundo CFD/MT5 mientras el
rumbo real ya era otro — ese desalineamiento entre SSoT y rumbo es exactamente la deriva que costó los
precedentes #68/#69, y es la razón por la que el pivote se tradujo a un change de spec antes de
construir capa 1 o capa 3 nuevas.

**IRREVERSIBLE desde el 2026-09-14.** El dueño del proyecto lo declaró sin ambigüedad: *"mi
objetivo ahora es ir por futuros, al menos este proyecto no volverá a CFDs ni a 5ers ni a FTMO"*.
No es una prioridad de orden: es **alcance cerrado**. El resto de esta memoria —en particular la
sección *"The5ers: por qué duele que quede fuera"*— fue escrito cuando todavía se leía como una
elección con la puerta entornada; leerlo así hoy es un error.

Consecuencia práctica, porque cambia decisiones concretas: todo lo que quede de la era CFD deja de
estar "en pausa" y pasa a ser **código muerto**. Eso incluye `data/profiles/the5ers.json`, la
denominación de límites en porcentajes (que el #109 ya elimina) y los **2.036 sidecars
`.meta.json`** de `data/raw/` sin `tick_size` (US500.cash, GER40.cash, US30.cash, US100.cash,
XAUUSD, EURUSD, GBPUSD, USDJPY — contra 161 que sí lo traen, todos de SP500/BTCUSDT). Mantener vivo
ese universo no tiene valor y sí tiene costo: ver
`mem:back-fill-de-tick-size-es-deuda-con-el-signo-invertido`.

## El hallazgo que ordena todo: la mitad del sector prohíbe automatizar

Relevamiento hecho el 2026-09-11 leyendo **las páginas oficiales de cada firma**, no agregadores
(los blogs que salen primero en búsqueda decían que Apex permite automatización y que Take Profit
Trader es "algo-friendly": las dos cosas son falsas según las propias firmas).

| Firma | ¿Automatización? | Cita oficial |
|---|---|---|
| **Apex Trader Funding** | ❌ | *"No Automation or Algorithm Usage allowed"* |
| **Take Profit Trader** | ❌ | UTP #1 *"No Trading Bots or Algos"*; PRO: *"All trades must be manually executed"* |
| **The5ers Futures** | ❌ | *"No. These practices are strictly forbidden."* + *"High-frequency trading, algorithmic trading, and hedging are not supported"* |
| **MyFundedFutures** | ✅ | *"Traders may make use of automated trading strategies tailored to their own specific settings…"* (sin HFT) |
| **Topstep** | ✅ | API oficial de pago (TopstepX/ProjectX, US$14,50/mes con código `topstep`). **Prohíbe VPS/VPN/servidores remotos** |
| **Tradeify** | ✅ | Con verificación: propiedad exclusiva demostrable, **video en vivo activando el código**, no usarlo en otra firma, sin HFT |

**Tres de seis prohíben automatizar.** Eso no es un detalle de una firma: es una característica del
sector, y significa que la premisa de genesis —un pipeline que valida sistemas mecánicos— solo es
compatible con una minoría de la industria. **Debe quedar escrito en el spec cuando se haga el
change.**

## El segundo eje: la regla de hedging varía muchísimo, y decide si el portafolio es viable

| Firma | Alcance de la prohibición |
|---|---|
| Apex | Instrumentos **correlacionados** (largo ES / corto YM = cierre de cuenta). El más amplio |
| Tradeify | Mismo instrumento o mismo **Product Group**, incluso entre cuentas propias |
| Take Profit Trader | *"same or closely related products"* bajo control común, justificado en reglas CME de wash trades |
| The5ers | Prohibido, y además prohíbe *"bulk trading"* = múltiples trades abiertos simultáneamente |
| **MFFU** | **Solo el mismo subyacente** (NQ vs MNQ). *"Hedging through different unrelated assets is permitted"* |

**MFFU es la única que permite las dos cosas a la vez**: automatizar, y tomar direcciones opuestas
en instrumentos distintos. Por eso gana, no solo por reputación.

## The5ers: por qué duele que quede fuera

Era la mejor encajada en todo lo demás y **genesis ya tiene su perfil** (`profiles/the5ers.json` —
que es el perfil **CFD**, no sirve de base para futuros). Su producto de futuros ofrece: drawdown
EOD, **denominación en porcentajes** (objetivo 6% eval / 4% fondeada, max loss 4%) que no obligaba
a rediseñar la capa 3, consistencia 40% **por posición**, news trading permitido, y —único en el
sector— un **plan Swing con tenencia overnight** (hasta 1 mini / 10 micros), que era la única
puerta a candidatos no puramente intradía.

Nota de matiz: la página general de prácticas prohibidas de The5ers **sí** permite EAs si el trader
**posee el código fuente** — pero eso aplica al producto CFD. El producto **Futuros** los prohíbe.
Dos regímenes distintos en la misma firma.

## Reputación: Apex vs MFFU (Trustpilot, 2026-09-11)

| | Apex | MFFU |
|---|---|---|
| Puntaje | 4,2 | 4,9 |
| Reseñas | 20.997 | 21.659 |
| Últimos 12 meses | 5.828 | 11.465 |
| ★☆☆☆☆ | **9%** | **2%** |
| Responde a negativas | Sí | **No** |

El dato que manda es el 9% vs 2% de una estrella (4,5×): en una prop firm esa reseña casi siempre
dice "no me pagaron". Las dos pagan suscripción a Trustpilot y las dos invitan a reseñar, así que
el nivel absoluto vale poco pero la comparación entre ellas sí.

Apex fundada 2021 (Darrell Martin); su página dice *"since 2008"* pero eso es **Apex Investing**, el
sitio educativo previo — conflación de marketing. MFFU fundada 2023.

**Corroboración estructural del historial de payouts de Apex:** reescribieron el producto entero.
Todo lo anterior está etiquetado "Legacy" y los productos nuevos traen concesiones (consistencia
"Not Applied" en evaluación, 100% de payout split, marketing de *"no more payout denials"*). Una
firma no hace eso si no había un problema. Las denuncias específicas (denegaciones por "erratic
trading", pedidos de video, cierres masivos) vienen de fuentes secundarias y **no están verificadas
contra fuente primaria**.

**Riesgo derivado, específico de genesis:** si la firma reescribe su rulebook, la validación
**caduca** — el `trial_id`, el hash del perfil y el `p_pass` quedan describiendo un contrato que ya
no existe. Apex acaba de demostrar que lo hace. Es un riesgo de plataforma a registrar en el perfil.

## Orden recomendado (no ejecutado)

1. **Change de spec.** Es lo único que debe preceder a todo. Acá el gate humano protege algo real.
2. **Perfil de firma confirmado** (ver `mem:mffu-rapid-eod-50k-reglas-confirmadas`). Barato y decisivo.
3. **Capa 3**: `TRAILING_EOD`, denominación en dólares, congelamiento del umbral, DLL opcional y con
   semántica de pausa, balance inicial $0 con saldo negativo permitido.
4. **Capa 1**: exportador CME (no hay MT5), empalme de continuos, sesiones CME, registro de fichas.
   El más caro; va último porque hasta el punto 3 se puede trabajar con los datos actuales.

## Decisiones abiertas

- **Una cuenta multi-activo vs. multi-cuenta.** Sin resolver. Ver
  `mem:correlacion-indices-y-oro-apuestas-efectivas`: la medición sugiere que el multi-activo entre
  índices no diversifica, y MFFU permite 3 cuentas fondeadas en Rapid EOD.
- **Régimen D1**: ¿el universo nuevo entra como **exigencia** (no suma ensayos) o como **selección**
  (cada universo suma al denominador del DSR)? Hay que declararlo **antes** de la primera campaña.
  Ver `mem:d1-que-cuenta-como-ensayo`.

Relacionadas: `mem:cripto-encaje-por-capa` (el mismo análisis por capa, hecho para cripto en
2026-08; buena parte del mapeo aplica igual), `mem:proposito-real-y-alcance-de-genesis`.
