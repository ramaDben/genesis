> **Briefing de consulta externa — 2026-09-05.** Documento *enviado* a un modelo de otro proveedor
> (Grok) para revisar la decisión D3 (issue #81), a ciegas y sin contexto del repositorio. Se
> versiona porque el briefing es la parte cara: expone deliberadamente el propio encuadre al ataque,
> y esa redacción es lo reutilizable, no el modelo que la responde.
>
> La respuesta está en `CONSULTA_EXTERNA_HOLDOUT_RESPUESTA.md`.

---

# Consulta: ¿reservar un holdout terminal cuando ya hay walk-forward rolling?

Necesito una opinión metodológica acotada. Te doy el contexto mínimo para que sea
respondible, las restricciones numéricas reales, y la pregunta. Al final te digo qué
respuesta me sirve y cuál no — por favor leelo antes de contestar.

## Contexto

Estoy construyendo un pipeline de validación de estrategias de trading. La decisión de
GO / NO-GO la toman 18 gates mecánicos: robustez estadística (walk-forward efficiency,
profit factor, Deflated Sharpe Ratio, PBO, sensibilidad) más una simulación de
supervivencia. Los umbrales están fijados por adelantado y no se relajan.

Hoy hay **un solo candidato ejecutable** y **cero veredictos GO**. La máquina funciona;
todavía no pasó nada por ella.

## La geometría actual, verificada contra el código

- Walk-forward **rolling**, no expandible: IS = 252 días de trading (~12 meses),
  OOS = 126 (~6 meses), paso = 126.
- Paso igual al ancho OOS ⇒ **los tramos OOS de ventanas consecutivas son contiguos, sin
  solape ni hueco**. En cada ventana, los parámetros se eligen en IS y se evalúan en un
  OOS que no participó de esa elección.
- El enumerador de ventanas avanza mientras entren:
  `while k * paso + is_window + oos_window <= n_dias`.
- La sensibilidad reusa exactamente esa misma geometría. El purged K-fold consume el
  ledger de operaciones OOS que produjo el walk-forward, no los datos crudos.
- **No existe ningún holdout terminal declarado.** Queda un residuo al final —los días
  posteriores a la última ventana completa— pero es el resto de una división: nadie lo
  declaró, su tamaño cambia cada vez que se extiende el dataset, y nada impide que la
  próxima corrida se lo consuma.

## Las restricciones numéricas duras

De la única corrida institucional real (índice bursátil, ~3 años de barras de un minuto,
2023-09 a 2026-08, 1.055.530 filas):

| Métrica | Valor | Gate |
|---|---|---|
| Ventanas walk-forward | 5 | — |
| Operaciones OOS totales | 405 | **≥ 300 (gate duro)** |
| Walk-forward efficiency | 0.3496 | ≥ 0.50 |
| Profit factor OOS | 1.0676 | ≥ 1.30 |
| Deflated Sharpe Ratio | 0.0019 | ≥ 0.95 |
| PBO | 0.1667 | ≤ 0.25 |

Veredicto: **NO-GO**. El candidato sobrevive mecánicamente pero no despega en ningún
gate económico.

**Lo que hace cara la decisión:** son ~81 operaciones OOS por ventana. Reservar 6 meses
de holdout cuesta aproximadamente una ventana y deja ~324 operaciones — un margen del 8 %
sobre el gate de 300. Reservar 12 meses probablemente lo rompe. Con este historial, el
holdout se paga en ventanas, y quedarse sin ventanas invalida la corrida entera.

## La pregunta

**¿El OOS rolling del walk-forward ya mide lo que mediría un holdout terminal intocable,
o miden cosas distintas?**

Y si miden cosas distintas: ¿justifica esa diferencia gastar una de cinco ventanas y
dejar el gate de operaciones con 8 % de margen?

Los dos argumentos que están sobre la mesa:

**A favor de NO reservar.** Cada tramo OOS ya es genuinamente fuera de muestra respecto
de la selección de parámetros que lo precede. Un holdout terminal es redundante, y con
tres años de datos su costo es desproporcionado: reduce el poder estadístico de la
evidencia principal para comprar una segunda evidencia más débil (un solo tramo, ~81
operaciones, sin repetición).

**A favor de SÍ reservar.** El OOS rolling responde «¿el procedimiento de selección de
parámetros generaliza hacia adelante?». Un holdout terminal responde otra cosa:
«después de todo lo que se ajustó a lo largo del proyecto, ¿sobrevive algo en datos que
nunca influyeron en ninguna decisión?». Y en este proyecto esas mismas ventanas se usaron
para diseñar el aparato que las juzga: se corrigieron bugs de redondeo de lote mirándolas,
se ajustó el embudo de filtros pre-trade, se corrieron diagnósticos con ventanas
reducidas. Ese sobreajuste **a nivel proyecto** —no a nivel candidato— es invisible para
el walk-forward por construcción, porque el walk-forward es parte de lo que se ajustó.

## Lo que NO estoy preguntando

- Cuánto reservar como fracción genérica del dataset. La restricción que ata es el gate de
  300 operaciones, no un porcentaje.
- Qué hacer con el número una vez que se mira, ni cuántas veces se puede mirar. Ya está
  decidido aparte.
- Si los umbrales de los gates son razonables. No están en discusión.

## Qué respuesta me sirve

**Informativa:** un argumento sobre si el sobreajuste a nivel proyecto —el que viene de
diseñar el pipeline mirando los mismos datos— es capturado o no por un walk-forward
rolling; evidencia o referencias sobre esa distinción específica; o un contraargumento que
muestre que el marco de la pregunta está mal planteado.

**Ruido:** «reservá un 20–30 %, siempre». Ese consejo es correcto en aprendizaje
automático con datos abundantes y acá rompe el gate de operaciones. Si tu respuesta es esa,
decime primero por qué el costo en ventanas no importa.

Si pensás que ambas posiciones fallan en algo, decilo — el encuadre también está en duda.
