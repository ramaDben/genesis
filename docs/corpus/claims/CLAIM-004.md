# CLAIM-004 — El barrido de liquidez no tiene contenido direccional explotable en ninguna dirección

| Campo | Valor |
|---|---|
| Fuente | [Mesfin (2026)](../fuentes/mesfin-2026-mnq-falsification.md), §4.3 |
| Concepto | Barrido de liquidez / *liquidity grab* / *stop hunt* (vocabulario **smart money**) |
| Mecanismo | barrido de liquidez en zonas de stops — **sin mecanismo publicado** que prediga dirección posterior |
| Estado | registrado |

> **Es el primer claim del corpus que adjudica vocabulario retail**, y es el tipo de resultado que
> justifica que el corpus exista.

## Cita textual

> *«Se identificaron 6.442 eventos en los que el precio perforó temporalmente un extremo de sesión
> antes de cerrar de vuelta dentro del rango. Barridos largos: 3.419. Barridos cortos: 3.023.»*

> *«Desvaneciendo la dirección del barrido: media neta −2,20 puntos, T = −14,12 sobre retornos netos.
> Operando con el barrido: media neta −1,80 puntos, T = −13,24. Ambas direcciones fallan. El contenido
> direccional bruto en cualquiera de las dos direcciones es de 0,20 a 0,80 puntos — más chico que la
> fricción en ambos casos. Es el resultado de techo de fricción puro más claro del estudio.»*

## Predicción falsable

**La fuente predice que** el evento «el precio perfora un extremo de sesión y cierra de vuelta dentro
del rango» **no contiene información direccional explotable en ninguna de las dos direcciones**: el
contenido bruto es de 0,20 a 0,80 puntos, por debajo del piso de fricción de 2,0.

Se falsa exhibiendo una regla sobre ese evento con retorno bruto materialmente superior a 0,80 puntos.

## Por qué este claim es distinto de los demás

Los otros claims falsan una hipótesis. **Éste falsa las dos hipótesis opuestas a la vez**, sobre el
mismo evento, con 6.442 observaciones. Desvanecer el barrido pierde; seguirlo pierde. Eso es mucho
más fuerte que un nulo: significa que el evento no divide el espacio de resultados futuros.

Y es justamente lo que el vocabulario *smart money* afirma que hace. «Barrieron los stops y ahora va
para el otro lado» es una predicción direccional condicional sobre exactamente este evento.

## Qué implica para genesis

1. **Entra al catálogo de mecanismos de A.2 con la predicción del lado negativo.** Cuando el
   arquitecto transcriba a un trader que hable de *stop hunt*, *liquidity grab* o *barrido*, Gate 0
   tiene una predicción declarada contra la cual contrastar el `entry_trigger`, en vez de aceptar la
   prosa.
2. **Es el ejemplo canónico de «traducir folclore a mecanismo»** de la casilla A.3, con el resultado
   completo: el concepto **sí** se puede traducir a un evento medible y **sí** se puede contrastar —
   y lo que la medición devuelve es que no hay dirección.
3. **Es barato y es publicable.** Un «no sobrevive» sobre un concepto con enorme circulación retail
   es precisamente el producto que D-A promete.

## Reservas

- Es una definición operativa concreta del barrido (perforar un extremo de **sesión** y cerrar dentro
  del rango, en barras de 5 min de MNQ RTH). Un trader puede razonablemente sostener que su
  definición es otra: otro extremo de referencia, otra resolución, con confluencia adicional.
  **Ese desacuerdo es adjudicable** y es justo lo que el corpus debe registrar como contradicción en
  vez de resolver por autoridad.
- Se hereda toda la reserva de la ficha de la fuente: sin ajuste de roll, feed retail, denominador de
  ensayos desconocido.
