# CLAIM-006 — Un retardo de una barra invierte el signo de la señal, no lo degrada

| Campo | Valor |
|---|---|
| Fuente | [Mesfin (2026)](../fuentes/mesfin-2026-mnq-falsification.md), §5.2, Tabla 12 |
| Concepto | Fragilidad temporal / sensibilidad al retardo de ejecución |
| Mecanismo | el movimiento direccional se completa dentro de la primera barra post-transición |
| Estado | registrado |

## Cita textual

> *«El resultado de sensibilidad al retardo merece examinarse con cuidado. Un retardo de una barra
> (15 minutos) invierte T de +4,30 a −2,78; un retardo de dos barras produce T = −2,16.»*

> *«La inversión de signo —no decaimiento hacia cero, sino significativo en la dirección opuesta— es
> consistente con el mecanismo […]: el movimiento direccional que sigue a una transición R0→R2 se
> completa casi enteramente dentro de la primera barra post-transición. Una entrada retrasada captura
> la reversión subsiguiente en vez del movimiento inicial.»*

| Retardo | T-neto | Media neta |
|---|---|---|
| Sin retardo | **+4,30** | +4,09 pts |
| 1 barra (15 min) | **−2,78** | −2,91 pts |
| 2 barras (30 min) | −2,16 | −1,87 pts |

## Predicción falsable

**La fuente predice que** el retorno de la señal London B no decae suavemente con el retardo de
ejecución sino que **cambia de signo con significancia** a una sola barra de retardo, porque el
movimiento se agota dentro de esa barra.

## Qué implica para genesis — y es una prueba que el pipeline debería correr siempre

**Esta es la observación metodológica más reutilizable del paper, y no es sobre una estrategia: es
sobre cómo validar.**

Una señal cuyo T pasa de +4,30 a −2,78 con quince minutos de retardo no es una señal robusta con un
buen número: es una señal que vive enteramente dentro de una frontera de barra. En un entorno de prop
firm con latencia, deslizamiento y rechazos, esa distinción es la diferencia entre una cuenta fondeada
y una cuenta quemada.

**Propuesta concreta para el torneo:** una prueba de sensibilidad al retardo de ejecución (entrada
desplazada 1 y 2 barras) como diagnóstico obligatorio del artefacto de veredicto. No como gate —un
gate nuevo necesita pasar por política, y un gate no declarado que se agrega después de ver resultados
es selección— sino como **número que se reporta siempre**, junto a las métricas prop existentes.

Es barato: el simulador ya es event-driven sobre M1 y el desplazamiento es un parámetro de ejecución,
no una reescritura. Y es exactamente el tipo de diagnóstico que distingue un edge de un artefacto sin
gastar un ensayo adicional, porque **no se selecciona sobre él**: se informa (I3).

El propio autor admite que resolver si esto es artefacto de frontera de barra o edge genuino sensible
al timing **requiere datos tick**, que no tiene. Genesis, si compra tick de CME en B.1, sí los
tendría.

## Reservas

- Es una sola señal, de un control positivo cuya exposición de búsqueda el propio paper declara
  incorregible. El **resultado de fragilidad** no depende de eso —es una propiedad medida de la señal
  tal como está especificada— pero el **nivel base de +4,30** sí.
- Barras de 15 minutos en sesión de Londres. El tamaño del efecto no traslada a otras resoluciones
  sin medirlo.
