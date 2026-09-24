# CLAIM-005 — Lo que escapa al techo usa detección de régimen y holds largos, no predicción de barra única

| Campo | Valor |
|---|---|
| Fuente | [Mesfin (2026)](../fuentes/mesfin-2026-mnq-falsification.md), §5, §6.2, Apéndice A |
| Concepto | Clasificación de régimen / arquitectura de señal |
| Mecanismo | transición de régimen menos observable que un patrón OHLCV crudo + acumulación de retorno sobre hold largo |
| Estado | registrado — **con la reserva más grande del corpus** |

## Cita textual

> *«Los dos controles positivos existen fuera de este techo porque usan clasificación de régimen por
> GMM y sostienen posiciones durante 60 a 75 minutos. Las transiciones de régimen derivadas de
> modelos de mezcla gaussiana multivariados son menos transparentemente observables que los patrones
> OHLCV crudos, y el período de tenencia más largo acumula suficiente retorno neto para superar la
> fricción antes de que el edge revierta.»*

## Predicción falsable

**La fuente predice que** la arquitectura que supera el techo de `CLAIM-001` tiene dos propiedades
conjuntas: **(a)** el estado de entrada se deriva de una clasificación de régimen multivariada, no de
un patrón visible sobre las últimas barras, y **(b)** el horizonte de tenencia es de 60–75 minutos,
no de una barra.

Se falsa exhibiendo señales que superen el techo sin ninguna de las dos propiedades, o exhibiendo que
señales con las dos propiedades tampoco lo superan.

## Evidencia que la fuente aporta

| Señal | N (OOS) | Neto | T-neto | p | Arquitectura |
|---|---|---|---|---|---|
| RTH Confluence | 196 | +11,82 | 3,11 | < 0,001 | GMM 3 componentes, 4 features, hold hasta barra 13 |
| London Signal B | 247 | +4,09 | **4,30** | 0,000025 | GMM 3 componentes, 5 features, hold 60 min |

Referencias incondicionales que descartan deriva pasiva: largo incondicional 09:30→barra 13 sobre
2022-2024 da media neta **−2,60 pts, T = −0,75** sobre 759 operaciones; el equivalente de Londres da
**−0,47 pts, T = −0,22** sobre 639 sesiones.

## Qué implica para genesis

1. **Es el insumo directo de la casilla A.4 (primitivas de ejecución).** Si esto es cierto, la
   primitiva que hace falta no es otro patrón de ruptura: es **un clasificador de régimen con estado
   incremental**. Y eso choca de frente con la restricción forward-only — un GMM reajustado por
   pliegue es un objeto con estado de entrenamiento, no un estimador online. Cómo se expresa eso en
   la gramática de A.1 sin romper el invariante anti-anticipación **es una pregunta de diseño abierta
   que este claim pone sobre la mesa antes de A.4, que es donde sirve tenerla.**
2. **Corrobora la decisión de horizonte del CLAIM-002.** Los dos controles positivos tienen holds de
   60–75 min; el ORB largo sólo atraviesa la fricción en bruto a bar+15 (75 min). El horizonte de
   salida aparece dos veces como la variable que decide si hay algo que medir.

## La reserva, que es grande y va antes que el claim

**Los dos controles positivos son los sobrevivientes de la misma búsqueda que produjo los catorce
fracasos.** No son validación independiente. El propio paper lo declara:

- RTH Confluence: **«53 o más combinaciones de parámetros a través de siete parámetros fueron
  evaluadas antes de fijar la especificación final»**, con exposición de multiplicidad que *«no puede
  corregirse post hoc»*. El autor cita el DSR de Bailey & López de Prado (2014) y el PBO de Bailey et
  al. (2017) y dice que aplicar cualquiera de los dos **reduciría** la confianza en T = 3,11. **No los
  aplica.**
- El pliegue W1 está contaminado: el GMM se ajustó sobre todo 2022 y prueba sobre 2022 H2.
- La línea base de ATR se computó sobre todo el período in-sample y se fijó globalmente — *«un leve
  look-ahead relativo a la estructura walk-forward»*.
- Una versión anterior del manuscrito reportaba como resultado primario un backtest estático de
  muestra completa (T = 5,15), después superado por las cifras walk-forward.

**Bajo los gates de genesis, ninguno de los dos controles positivos pasaría G4.** Este claim se
registra por su valor de **hipótesis arquitectónica**, no como evidencia de que esas dos señales
funcionen. Y su fragilidad está medida aparte: ver `CLAIM-006`.
