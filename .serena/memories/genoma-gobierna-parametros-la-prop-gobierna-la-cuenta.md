# Los parámetros son del genoma; la prop gobierna la cuenta, no los parámetros

**Decisión humana del dueño del proyecto, 2026-09-14**, tomada en la fase `propose` del
Change #109. Resuelve la única pregunta de arquitectura que ese change dejó abierta, y fija
una frontera que aplica a todo genoma futuro.

*(Reemplaza a una versión anterior de esta memoria que decía «el genoma acotado por la
ficha, y la cota rechaza». Esa era una lectura errónea del asistente, corregida por el
usuario: **no hay cotas sobre parámetros de estrategia**.)*

## La frontera

| Clase | Ejemplos | Quién lo fija | ¿Cota? |
|---|---|---|---|
| **Parámetro de estrategia** | `atr_multiplier`, `lookback_bars`, `atr_period`, `atr_stop_frac`, `tp_rr_multiple`, `risk_pct` | **el genoma**, cada uno el suyo | **Ninguna.** Sin techo ni piso |
| **Regla de la prop** | `max_loss_limit` y su tipo, `threshold_lock_at`, `daily_loss_limit` si existe, `payout_buffer`, tenencia de fin de semana | **la ficha de la firma** | Es la restricción misma; el genoma nunca la toca |

Un genoma que declare `atr_multiplier: 50.0` es válido y **se corre tal como está**. Si esa
geometría rompe la cuenta, el sistema lo **descubre en la simulación** y lo refleja en el
`p_pass` y en los gates. No se prohíbe de antemano.

**La regla de la prop se aplica sobre la cuenta, no sobre los parámetros.**

## Por qué, y no es permisividad

Es lo que hace que genesis sea un **evaluador de caja negra**. Un techo sobre
`atr_multiplier` sería una constante de política de estrategia metida dentro del evaluador,
y el evaluador dejaría de ser agnóstico al candidato — el mismo error que el SSoT v1.5 evita
en §2.3 al exigir que el criterio de admisión al universo sea intrínseco al activo y no a la
estrategia. **Los gates deciden; un validador de parámetros no.**

## Las cotas del SSoT §7.2 no son una excepción

El spec fija un *piso de operabilidad* y un *techo de canasta* para el sizing. Ninguno es
validación a priori:

- El **piso** se hace cumplir solo por el mecanismo: un sizing por debajo de un contrato
  micro redondea a cero contratos, no genera trades, y el candidato falla **G1** (≥300
  trades OOS). Ya está castigado sin prohibirlo.
- El **techo** *es* el gate **C3**, evaluado sobre resultados.
- El spec mismo dice qué hacer cuando nada cabe: *«la cuenta es demasiado chica para el
  candidato — y eso se reporta, no se fuerza»* (SSoT:1082-1083). Hallazgo del evaluador, no
  prohibición del compilador.

## Criterio para decidir qué validación puede existir: imposible vs. indeseable

Sobreviven las guardas que impiden estados **imposibles**, no valores **indeseables**:
`trailing_atr_mult > 0` y `trailing_lookback >= 1` (`risk_profile.py:47-53`) existen porque
un multiplicador nulo y un lookback vacío no tienen semántica, no porque un valor alto sea
riesgoso.

## Lo que sí hay que garantizar: nada se recorta en silencio

El defecto actual no se arregla con cotas, se arregla haciendo que **el valor declarado sea
el que corre, siempre**. Un *clamp* (recortar al borde de un rango «razonable») sería la
misma enfermedad con otro nombre. Con un arquitecto encendido deja de ser higiene y pasa a
ser correctitud: si el LLM recibe métricas de una configuración distinta de la que propuso,
**aprende de una señal corrupta**.

## Estado medido del código (2026-09-14, `fe5e683`)

- **No existe hoy ninguna cota sobre el ATR.** Única validación: `trailing_atr_mult > 0.0`
  y `trailing_lookback >= 1` (`risk_profile.py:47-53`). Sin techo.
- El schema del genoma valida **solo estructura**, cero rangos numéricos
  (`schema.py:180-193`).
- `GridConfig.atr_stop_frac_levels = (0.5, 1.0, 1.5)` (`window_config.py:68`) **no es una
  cota**: enumera lo que el torneo prueba, no lo que un genoma puede declarar. El techo que
  sí valida (`_MAX_SIGNAL_CONFIGS`) es sobre el *número* de configuraciones, para el
  presupuesto de trials de G4.
- **Defecto vivo:** dentro del mismo bloque `risk_exit.params`, unas claves gobiernan y
  otras se ignoran en silencio. `candidate.py:63-79` lee `atr_stop_frac`, `atr_period` y
  `tp_rr_multiple`; `lookback_bars` y `atr_multiplier` se descartan y el simulador usa los
  del JSON global (`simulator.py:391, 399`). Nada en el YAML distingue unas de otras.
- **Ya no es hipotético:** `candidates/specs/candidate_c1_gold_lob.yaml:35` declara
  `atr_multiplier: 2.5` y hoy correría a 3,0.

Relacionado: `mem:change-103-arquitecto-y-compilador-genomas`,
`mem:mll-duplicado-acopla-simulador-y-p-pass`, `mem:arquitecto-estrategias-y-ledger-ensayos`,
`mem:proposito-real-y-alcance-de-genesis`
