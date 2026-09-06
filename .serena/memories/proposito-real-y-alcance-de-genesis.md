*(2026-09-05 — entrevista de estatutos: bloque A y B1 respondidos. B2–G pendientes y
**reservados** por decisión explícita — ver `mem:reserva-de-gobernanza-2026-09`.)*

# El propósito real de genesis, y lo que cuesta

Revelado en la entrevista de `docs/ENTREVISTA_POLITICA.md`. **Cambia el marco del proyecto entero**:
genesis no es un proyecto de trading, es **la base de evidencia de un negocio regulado**.

> **Objetivo declarado por el usuario**: entrar al **RPSF de la CMF** (Chile) y ofrecer asesoría de
> inversión basada en un modelo probado. Y si se logra algo robusto, **buscar inversionistas**, no
> solo prop firms.

Consecuencia inmediata: los gates dejan de ser gestión de riesgo personal y pasan a ser la
sustentación de afirmaciones hechas a clientes y a un regulador. La reproducibilidad y la
procedencia dejan de ser elegancia de ingeniería y pasan a ser rastro de auditoría.

## A1 — el alcance, en la forma que aguanta

El alcance se movió **tres veces en veinte minutos** durante la entrevista (prop firms de futuros
tipo Apex → más swing y CFDs → multi-venue con cripto e inversionistas). Por eso se escribió
separando lo fijo de lo móvil:

- **Propósito (fijo)**: producir y validar modelos de trading con evidencia suficiente para
  sustentar decisiones de terceros — prop firms, clientes de asesoría o inversionistas.
- **Destino (declarado)**: evaluador agnóstico al mandato y al universo, capaz de buscar dónde hay
  edge — CFDs, futuros, cripto.
- **Fase actual**: prop firms, intradía, CFDs e índices. Todo lo demás es destino, no requisito.

El usuario declaró **tiempo abundante** y preferencia por lo ambicioso.

## A2 — lo que el proyecto NO es

> «No es una máquina de hacer perder dinero, no crea estrategias por suerte ni estrategias que
> hagan perder dinero. No es una casa de apuestas.»

Cláusula concreta que aceptó rechazar aunque venga bien argumentada:
**desplegar capital real sin haber pasado los gates.**

Traducción operativa (derivada con él, para `POLITICA.md`):

1. No se despliega nada que no haya pasado los gates.
2. No se afloja un gate para que un candidato pase.
3. El conteo de ensayos no se relaja — es la versión mecánica de «no por suerte», y coincide con D1.
4. No se afirma más de lo que el artefacto sustenta.

**Derivación que restringe algo grande**: el arquitecto (búsqueda automatizada) es literalmente una
máquina de probar muchas cosas; lo único que lo separa de una casa de apuestas es la contabilidad
honesta de ensayos. Con A2 escrita, **el arquitecto queda condicionado a que el ledger funcione.**

## A3 — el hito de tres meses, reformulado

El usuario fijó tres meses y aceptó la reformulación: a los tres meses la pregunta **no** es
«¿encontramos edge?» sino **«¿aprendimos si acá hay edge que encontrar?»**.

Razón: la velocidad de la IA acelera implementar y probar, pero **no** cuántos datos existen ni si
hay edge en ellos — y **acelera el agotamiento del presupuesto estadístico**. Cincuenta candidatos
en una semana llevan el denominador del DSR a cincuenta en una semana.

Regla que sale de ahí: **ambición en construir es gratis; ambición en buscar es cara y no
reembolsable.**

Ruta barata para ese hito, ya recomendada por el RFC §9 regla 1: correr las reglas canónicas
(Bollinger 20/2, MACD 12/26/9 con parámetros publicados) — un ensayo cada una, cero grados de
libertad. Si lo canónico muere con costos reales, es enormemente informativo y costó 2 ensayos.

## B1 — el reencuadre que cambia qué se prueba primero

No hay capital comprometido; lo invertido es tiempo y sesiones. Pero la respuesta trajo el objetivo
real, y es más chico y más barato que todo lo anterior:

> **Verificar si lo estudiado mirando velas japonesas, estructura de precio y ahora regímenes se
> puede validar o invalidar.**

**El primer trabajo de genesis no es buscar edge genéricamente: es arbitrar las hipótesis
discrecionales que el operador ya acumuló.** Consecuencias:

- **Es el caso más barato bajo D1.** Una hipótesis formada antes de tocar los datos y especificada
  por adelantado es un ensayo con cero grados de libertad — misma categoría que una regla canónica
  con parámetros publicados. El objetivo real resultó ser lo estadísticamente más barato.
- **Corrige la ruta barata del hito de tres meses.** El RFC §9 regla 1 recomienda arrancar por lo
  canónico; para este operador es menos informativo, porque que Bollinger muera con costos reales no
  dice nada sobre si su lectura de estructura es válida. Sus hipótesis cuestan lo mismo en ensayos y
  responden su pregunta.
- **La trampa:** las hipótesis nacieron mirando estos mismos gráficos. Testearlas sobre el mismo
  período no es fuera de muestra. Es la versión humana del problema de anticipación.
- **Los regímenes son una dimensión de selección.** Cada definición de régimen probada y descartada
  es un ensayo bajo D1.

**Acción derivada, gratis y todavía no hecha:** pre-registrar las hipótesis por escrito antes de
correr nada (RFC §9 regla 2). Escritas después de la primera corrida dejan de ser un ensayo limpio.

**Corrección a A3:** la condición de salida es **epistémica, no temporal** — se para cuando hay
respuesta, no cuando se acaba la paciencia. El tiempo invertido no es evidencia de que algo funcione.

## Lo que el alcance cuesta — verificado en el código el 2026-08-30

- **«Swing» no es alcance, es núcleo.** El cierre forzado de sesión **no es opcional**:
  `simulator.py:347` llama a `_enforce_session_close_and_guard` en cada barra y liquida todo al
  llegar a `session_close_utc`. **Hoy la capa 3 no puede representar una posición que sobreviva la
  noche.** Habilitarlo es un cambio de comportamiento en `src/genesis/backtest/**` ⇒ ciclo SDD
  completo. Y arrastra a `prop_sim`, que agrupa el P&L **por día** para el límite de pérdida diaria
  — un gate, no un reporte.
- **El costo de swap está modelado pero nunca se ejecuta.** `costs.py` calcula swap con
  `days_held`, y como ninguna posición cruza la noche, ese término hoy siempre vale cero. G3 exige
  «costos completos, swap incluido»: con swing se activaría por primera vez.
- **El drawdown trailing YA está construido** — `MaxLossLimitKind.TRAILING` en `risk_profile.py`, y
  `prop_sim.py` lo evalúa contra `attempt_peak_balance`. Es el mecanismo que define a las firmas de
  futuros tipo Apex, y está parametrizado junto con la regla de consistencia, el límite de contratos
  y las fases. **Genesis está más cerca del objetivo real que del título de su propio spec.**
- **Futuros intradía es barato; futuros swing no.** Con estrategia intradía nunca se sostiene una
  posición a través de un roll, así que la convención de empalme deja de alterar resultados. Con
  swing vuelve.
- Lo que falta para futuros: capa 1 (datos, fichas de contrato, tabla de sesiones) y capa 3
  (comisión por contrato más fees de bolsa/clearing en vez del modelo por lote).

## Sin verificar, y es requisito de diseño

- **Requisitos del RPSF/CMF**: capital, gobierno, retención de registros, deberes de información,
  y qué se puede afirmar sobre desempeño pasado. **Asesorar y administrar capital de terceros son
  figuras regulatorias distintas** — el salto a inversionistas no es una extensión de la asesoría.
  Si hay obligaciones de trazabilidad o retención, son requisitos de arquitectura y descubrirlos
  tarde significa rehacer.
- **¿Las firmas objetivo permiten mantener posiciones de un día para otro?** Si no, «swing en prop
  firm de futuros» es contradictorio y el costo del núcleo no compra nada.
- **Riesgo de concentración señalado una vez**: el valor del producto dependería de reglas de un
  tercero que las cambia cuando quiere.

Ver `mem:politica-de-decision-y-compuerta-humana`, `mem:d1-que-cuenta-como-ensayo`,
`mem:d3-holdout-oos-intocable`, `mem:cripto-encaje-por-capa`.
