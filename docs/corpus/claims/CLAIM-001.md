# CLAIM-001 — Techo de edge bruto en patrones OHLCV intradía de MNQ

| Campo | Valor |
|---|---|
| Fuente | [Mesfin (2026)](../fuentes/mesfin-2026-mnq-falsification.md), arXiv:2605.04004 v3 |
| Concepto | Techo de edge / eficiencia a resolución de barra |
| Mecanismo | `sin mecanismo publicado` como mecanismo de *edge*; el paper lo enuncia como **restricción competitiva**, no como fuente de retorno |
| Estado | registrado |

## Cita textual

> *«MNQ está entre los contratos de futuros más líquidos del mundo. Cualquier patrón OHLCV visible
> para todos los participantes del mercado que prediga de forma confiable la barra siguiente es
> arbitrado. Los participantes con costos más bajos y ejecución más rápida toman el otro lado hasta
> que el retorno bruto esperado iguala aproximadamente el costo de explotación. En barras de cinco
> minutos, ese equilibrio parece situarse cerca de uno a dos puntos brutos.»*

## Predicción falsable

**La fuente predice que** el retorno bruto por operación de cualquier señal direccional construida
sobre características OHLCV públicamente observables de MNQ, a resolución de 5 minutos y horizonte de
barra única, **no supera de forma estable ~1–2 puntos**, es decir queda por debajo del piso de
fricción de 2,0 puntos ($4,00 por contrato micro, ida y vuelta).

Se falsa exhibiendo una señal de esa clase con retorno bruto sostenidamente superior a la fricción y
T ≥ 2,0 sobre retornos netos fuera de muestra.

## Evidencia que la fuente aporta

Once de catorce familias con retorno bruto máximo entre **0,07 y 1,50 puntos**. La dispersión de la
Figura 4 muestra casi todas las variantes agrupadas a la izquierda del umbral de 2,0 puntos.

## Alcance declarado, y por qué importa

El propio autor acota el claim, y la acotación es la parte más útil:

> *«El techo aplica específicamente a predicciones direccionales de barra única a partir de
> características OHLCV públicamente observables, no a todas las estrategias intradía.»*

O sea: **no dice que el intradía en MNQ sea inoperable.** Dice que el intradía *de patrón sobre barra*
lo es. Ver `CLAIM-005`, que es la otra mitad de esa afirmación.

## Qué implica para genesis

1. **La fricción es la variable que domina, no el filtro.** Un pipeline que valida señales sin costos
   completos no está midiendo nada en este dominio. `backtest/costs.py` ya los modela; el número de
   2,0 pts / $4,00 sirve de referencia de sanidad para la casilla B.1.
2. **El umbral de admisión del torneo debería expresarse en múltiplos de fricción**, no en retorno
   absoluto. Una señal con edge bruto de 1,5 puntos es indistinguible de ruido *después* de costos,
   por más que su gráfico de equity en bruto se vea creciente.

## Reservas

El número 1–2 puntos sale de **este** dataset, **esta** ventana (2021-2025), **este** feed
(NinjaTrader, retail, sin ajuste de roll) y **esta** definición de fricción. El propio paper señala
que la fricción está fija en términos nominales mientras MNQ cotizó entre ~11.000 y ~24.000, o sea
entre 1,8 y 0,8 puntos base según el nivel de precio, y que **si el techo escala proporcionalmente
con el precio no está probado**.
