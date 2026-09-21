# CLAIM-002 — El ORB largo en MNQ RTH no alcanza significancia sobre 447 operaciones OOS

| Campo | Valor |
|---|---|
| Fuente | [Mesfin (2026)](../fuentes/mesfin-2026-mnq-falsification.md), §4.1, Tabla 4 |
| Concepto | Opening Range Breakout (ORB) |
| Mecanismo | momentum intradía / continuación direccional tras el rango de apertura |
| Estado | registrado |

> **Este es el claim que toca al candidato prioritario del torneo.** El Candidato B/B.1 de genesis es
> un ORB intradía. Esta fuente lo prueba sobre el instrumento exacto del destino.

## Cita textual

> *«La ruptura del rango de apertura es la señal intradía más citada en el trading retail de futuros.
> El precio rompe el máximo o el mínimo de las primeras barras de la sesión; la hipótesis es
> continuación direccional.»*

> *«El ORB largo a bar+15 produce T = 0,88 sobre 447 operaciones OOS, media neta +2,82 puntos. El
> patrón anual —+2,43 en 2023, +7,04 en 2024, +15,05 en 2025 parcial— podría reflejar una mejora
> genuina de desempeño o un artefacto de un único régimen macro en un año parcial. T = 0,88 no te
> permite distinguirlo.»*

## Definición exacta de lo probado

| Parámetro | Valor |
|---|---|
| Rango de apertura | **09:30–09:55 ET**, las primeras seis barras de 5 minutos |
| Sesión | **RTH únicamente** (09:30–16:00 ET) |
| Entrada | ruptura del máximo/mínimo del rango; señal al cierre de barra, entrada a la apertura de la siguiente |
| Salidas probadas | bar+1 (5 min) y bar+15 (**hold de 75 minutos**) |
| Fricción | 2,0 pts ida y vuelta |

## Resultados

| Variante | N (OOS) | Bruto | Neto | T-neto | 2023 | 2024 | 2025p | Veredicto |
|---|---|---|---|---|---|---|---|---|
| ORB Largo — bar+1 | 447 | — | −0,82 | −0,82 | −2,11 | −1,54 | +6,11 | FALLA |
| ORB Largo — bar+15 | 447 | +4,82 | **+2,82** | **+0,88** | +2,43 | +7,04 | +15,05 | FALLA |
| ORB Corto — bar+1 | 428 | — | −3,45 | −3,16 | −2,73 | −4,74 | −0,15 | FALLA |
| ORB Corto — bar+15 | 428 | — | −2,16 | −0,58 | −2,06 | −1,04 | −0,59 | FALLA |
| ORB Pullback | 83 | — | −4,44 | −1,27 | +2,97 | −6,05 | −1,55 | FALLA |

## Predicción falsable

**La fuente predice que** el ORB largo sobre MNQ RTH con rango de 25 minutos y hold de 75 minutos
tiene retorno neto positivo pero **estadísticamente indistinguible de cero** (T = 0,88) sobre ~450
operaciones fuera de muestra, y que ninguna de sus variantes direccionales o de pullback alcanza
T ≥ 2,0.

## El hallazgo secundario, que es el más informativo

> *«La entrada de pullback es directamente mala: una tasa de stop-out del 80,7% con un stop de 20
> puntos significa que la señal está identificando predominantemente **reversiones** de intentos de
> ruptura, no continuaciones.»*

Eso no es un nulo. Es una afirmación **direccionalmente opuesta** a la hipótesis del ORB, y es
contrastable.

## Qué implica para genesis

1. **Prior fuerte y negativo sobre el Candidato B/B.1.** No lo mata —esta fuente no tiene autoridad
   para eso, ver las reservas de su ficha— pero sí obliga a que el candidato entre al torneo con la
   expectativa declarada de no sobrevivir, y eso es exactamente lo que I7 pide escribir **antes** del
   resultado, no después.
2. **Refuerza el diagnóstico del [#107](https://github.com/ramaDben/genesis/issues/107).** El #107 ya
   había verificado que Gao et al. (2018) documenta *primera media hora → última media hora*, no un
   ORB. Ahora hay una fuente que prueba el ORB propiamente dicho, sobre MNQ, y le da T = 0,88. Las
   dos cosas juntas dicen que B.1 tiene un problema de procedencia **y** un prior desfavorable sobre
   la regla que efectivamente implementa.
3. **La geometría importa y está medida.** bar+1 pierde (−0,82), bar+15 gana en bruto (+4,82). El
   horizonte de salida no es un parámetro cosmético del genoma: es la diferencia entre atravesar la
   fricción y no. B.1 sale por Chandelier, que no es ninguno de los dos horizontes probados — o sea
   que **este claim no mide a B.1, mide a su familia.**

## Reservas específicas de este claim

- Ventana 2023-2025 con 2025 parcial. El patrón anual de bar+15 es **monótonamente creciente**, lo
  que es compatible tanto con un edge real que mejora como con un artefacto de régimen.
- La Tabla 13 del paper marca esta familia como *year-unstable*, pero sus tres años OOS son positivos
  y crecientes. Por los criterios del propio paper falla **sólo** por T. Es un error del paper, no un
  hallazgo adicional.
- Rango de apertura de **25 minutos**; B.1 usa 30. No son el mismo genoma.
