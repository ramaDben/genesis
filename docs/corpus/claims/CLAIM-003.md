# CLAIM-003 — La expansión de rango en sesión asiática predice reversión, no continuación

| Campo | Valor |
|---|---|
| Fuente | [Mesfin (2026)](../fuentes/mesfin-2026-mnq-falsification.md), §4.2, Tabla 5, Figura 3 |
| Concepto | Expansión de rango / continuación direccional |
| Mecanismo | agotamiento intrabarra del movimiento direccional |
| Estado | registrado |

## Cita textual

> *«T = −11,52 en bar+1. Eso no es un resultado nulo. La señal está activamente equivocada en la
> dirección de continuación, y el estadístico T es el hallazgo direccional más fuerte de todo el
> estudio.»*

> *«El mecanismo es el timing. Las ráfagas de expansión son reales —el movimiento direccional
> existe— pero se consume enteramente dentro de la barra de ruptura. Para cuando la barra cierra, la
> señal dispara y la entrada de la barra siguiente ejecuta, el momentum ya se agotó. Lo que la
> estrategia captura es la reversión post-agotamiento.»*

## Predicción falsable

**La fuente predice que** una barra de 5 minutos de la sesión asiática (20:00–02:00 ET) cuyo rango
excede 1,5× el rango verdadero medio de 20 barras **va seguida de movimiento contrario**, no de
continuación, y que ese efecto es fuertemente significativo (T = −11,52 sobre N = 1.955).

## Resultados

| Umbral | Horizonte | N | Bruto | Neto | T-neto |
|---|---|---|---|---|---|
| 1,5× | b+1 | 1.955 | −0,27 | −2,27 | **−11,52** |
| 1,5× | b+6 | 1.955 | −0,08 | −2,08 | −4,86 |
| 2,0× | b+1 | 778 | −0,35 | −2,35 | −7,42 |
| 2,5× | b+6 | 340 | +1,06 | −0,94 | −0,90 |

Medición de anatomía intrabarra citada del trabajo compañero: el retorno medio de **apertura de barra
a apertura de la siguiente** es **+32,24 puntos** en la dirección de expansión, mientras que el de
**cierre de barra a apertura de la siguiente** es **−0,17 puntos**.

## Qué implica para genesis

1. **Es el claim más directamente accionable del paper, y no por su signo sino por su mecanismo.**
   Dice que hay movimiento real que una estrategia que opera *al cierre de barra* no puede capturar
   nunca. La restricción **forward-only** de genesis y su convención de ejecución (señal al cierre,
   entrada a la apertura siguiente) caen exactamente del lado que no lo captura.
2. **Marca una clase de claim que el arquitecto va a encontrar mucho y que el corpus debe saber
   rechazar**: el que es verdadero sobre el mercado y falso sobre lo que se puede operar. Un trader
   que muestra la expansión y dice «mirá el movimiento» no miente — es inaccesible a resolución de
   barra, que es otra cosa.
3. **Contradicción a registrar cuando aparezca la contraparte.** Todo claim de «ruptura de volatilidad
   = continuación» —vocabulario habitual— contradice a este. Ese es el tipo de par adjudicable que
   A.3 busca.

## Reservas

- Es la sesión asiática (20:00–02:00 ET), no RTH. No traslada automáticamente a la apertura de Nueva
  York.
- El dato de anatomía intrabarra viene de un manuscrito del mismo autor, no publicado y no
  verificable desde acá. **No se registra como evidencia, se registra como cita.**
- El paper admite que distinguir «artefacto de frontera de barra» de «edge genuino sensible al
  timing» **requiere datos tick**, que no tiene.
