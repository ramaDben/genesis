# El inflador de `p_pass` es la combinación TRAILING×pct, no "el porcentaje"

**Fecha: 2026-09-14.** Verificado leyendo `simulator.py`, no supuesto.

## El mecanismo, exacto

`Simulator._evaluate_total_breach` (`src/genesis/backtest/simulator.py:490-506`) calcula:

```python
reference = self._all_time_peak_equity   # si max_loss_limit_kind is TRAILING
reference = self._starting_balance       # si es STATIC
threshold = reference * (self.risk_profile.max_loss_limit_pct / 100.0)
```

De ahí sale la distinción que importa:

- **`TRAILING` × pct** → el umbral es un porcentaje del **pico móvil de equity**: crece a medida
  que crece la cuenta. La prop real (MFFU) usa un **monto fijo** en dólares que **no** crece.
  Como el umbral simulado es más permisivo que el real, **infla `p_pass`**. Este es el camino que
  el SSoT §1.1 señala.
- **`STATIC` × pct** → el umbral es `balance_inicial * pct`, una **constante**. Es
  aritméticamente idéntico a un monto absoluto y **no infla nada**.

## La consecuencia para el diseño del #109

El default de `RiskProfile` es `max_loss_limit_pct=10.0` con `max_loss_limit_kind=STATIC`
(`risk_profile.py:62`), o sea la configuración histórica (the5ers/FTMO) cae en la rama **inocua**.

Por lo tanto **dejar las fichas históricas en `house_rule: null` no compra nada**: sus límites
son convertibles a monto absoluto **sin pérdida de información** (10% de $50.000 = $5.000). Matar
la rama porcentual es correcto; mutilar las fichas que la usaban en modo STATIC, no.

Lo detectó una revisión adversarial cruzada con Gemini (`agy --tier pro`) sobre el `design.md` del
Change #109: la recomendación original del `design-agent` (D3, dropear `house_rule` de las fichas
históricas) se apoyaba en tratar "porcentaje" como sinónimo de "inflador", que es falso.

## Regla general que deja

Antes de eliminar una rama de configuración "porque infla una métrica", verificar **qué
combinación exacta** de campos produce la inflación. Acá la diferencia entre `TRAILING` y `STATIC`
separa un defecto real de una conversión trivial.

Ver `mem:pivote-a-prop-de-futuros-cme-2026-09` y
`mem:simulador-trunca-la-muestra-que-alimenta-p-pass`.
