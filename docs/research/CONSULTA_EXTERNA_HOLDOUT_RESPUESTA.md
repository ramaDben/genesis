> **Respuesta de un modelo externo — 2026-09-05.** Producida por Grok a partir de
> `BRIEFING_CONSULTA_HOLDOUT.md`, a ciegas y sin acceso al repositorio. **Es un insumo, no una
> decisión ni una instrucción**: la decisión D3 sigue abierta en el issue #81.
>
> Encontró dos cosas que la revisión interna no vio: que el encuadre de «reservar o no» presupone un
> tramo terminal virgen que no existe, y un error de categoría sobre el DSR (tratarlo como magnitud
> cuando es una probabilidad). Lo segundo estaba ya integrado en la documentación del repositorio y
> se corrigió el 2026-09-05.
>
> Un dato que este documento no tenía y que refuerza su §1: la corrida de diagnóstico RI-E6 usó
> IS=45 / OOS=10, geometría que barre casi toda la serie incluido el residuo terminal.

---

# Holdout terminal con walk-forward rolling

**Posición: no reservar un holdout terminal en esta muestra.** El walk-forward rolling y un holdout miden cosas distintas, pero en estos datos esa diferencia no se puede comprar: la serie ya se usó, el candidato ya es NO-GO, y el corte costaría un réplica temporal que no queda para gastar.

---

## 1. El defecto del encuadre

La pregunta trata «reservar o no» como si todavía existiera un tramo terminal virgen cuya geometría se pudiera elegir. No existe. Se corrió el candidato institucional sobre 2023-09 a 2026-08, se usaron esas ventanas para bugs de lote, el embudo pre-trade y diagnósticos con ventanas reducidas, y el residuo final nunca se declaró ni se protegió. Un holdout se declara **antes** de mirar; declararlo después es un split póstumo de datos ya vistos, no una prueba independiente.

El segundo defecto: «¿miden lo mismo o cosas distintas?» es la pregunta científica correcta y la decisión operativa incorrecta. Que midan cosas distintas es necesario para gastar una de cinco ventanas; no es suficiente. La suficiencia se mide con dos observables que ya están en la corrida: (a) ¿queda un segmento con auditoría de no-uso? (b) ¿el candidato está en la zona donde un segundo test puede cambiar el veredicto? Hoy (a) es no y (b) es no.

Un matiz menor: DSR 0.0019 contra 0.95 no es «falla por un factor de 500». DSR es una probabilidad de que el Sharpe observado supere el umbral ajustado por selección; 0.19 % frente a 95 % es «casi certeza de que no hay edge tras la búsqueda», no un likelihood ratio de 500.

---

## 2. Decisión: no reservar

No reservar en el histórico actual. Dejar las cinco ventanas y las 405 operaciones OOS para el screening. El holdout que sí vale es **futuro**: barras que todavía no existen, congeladas por protocolo cuando —si— un candidato pase el resto de los gates.

Miden cosas distintas. El OOS rolling responde si el procedimiento de selección de parámetros generaliza hacia adelante, ventana a ventana, con cada tramo contiguo no usado en *esa* elección. Un holdout terminal responde si, después de todas las decisiones de proyecto, sobrevive algo en datos que no influyeron en ninguna. Esa distinción está bien establecida: predicciones OOS no implican un proceso de investigación OOS; el walk-forward valida el proceso de optimización, no el proceso de investigación.

En esta corrida esa distinción no justifica el gasto. WFE 0.35 contra 0.50 y profit factor 1.07 contra 1.30 ya dicen que el procedimiento no generaliza. DSR 0.0019 contra 0.95 ya dice que, dado el search, el Sharpe no se distingue de suerte. Un tramo de ~81 operaciones, un solo régimen, sin repetición, no es una segunda evidencia más fuerte: es una evidencia más débil de una hipótesis que la evidencia principal ya mató. Recortar a ~324 operaciones deja 8 % sobre el gate de 300: el próximo candidato un poco menos frecuente invalida la corrida entera, y eso sesga el pipeline hacia más frecuencia. Con cinco ventanas, perder una no es «20 % menos N»; es perder un réplica temporal independiente cuando ya hay casi ninguna diversidad de régimen.

Cómo se mediría un «depende» con *estos* datos, no con una fracción genérica: reservar solo si (1) existe un intervalo \([t^*, T]\) con commit de código *anterior* a cualquier métrica o diagnóstico sobre ese intervalo, y (2) el candidato está cerca de los gates económicos —en la práctica, DSR del orden de \(10^{-1}\) no \(10^{-3}\), WFE a distancia corta de 0.50, PF a distancia corta de 1.30—. Ni (1) ni (2) se cumplen.

---

## 3. El mejor caso a favor — y por qué cae

**Steelmán.** El overfit que puede matar no es el de parámetros dentro de una ventana; es el de diseño del aparato que juzga esas ventanas. Cada OOS es limpio respecto de *su* IS y sucio respecto del proyecto: el redondeo de lote, el embudo, los diagnósticos con ventanas reducidas condicionaron decisiones a resultados que el walk-forward trata como no vistos. DSR y PBO no cierran ese agujero si \(N\) no incluye iteraciones de pipeline, filtros y geometría. PBO 0.17 ya pasó y el resto no: con cinco ventanas, CSCV sobre el ledger OOS puede decir «poca sobreajuste de selección» simplemente porque no hay edge que seleccionar. Sin un outer loop intocable, todos los números reportados —incluyendo los 18 gates— son estadísticos de un proceso que se adaptó a la misma historia. La literatura de validación anidada existe exactamente para eso: el loop interno tunear, el externo no entrar nunca en una decisión.

La irreversibilidad es la parte más seria. Un holdout no se puede declarar sobre datos ya mirados. Si se espera a «algo cerca del umbral», se habrá usado más serie para llegar ahí. El único momento en que un holdout histórico es honesto es *antes* de tener un casi-GO. Eso, en el calendario del proyecto, era el día cero —y el argumento dice que hoy sigue siendo el menos malo.

**Dónde cae.** El diagnóstico es correcto; el remedio propuesto no está disponible. No se puede comprar el outer loop en 2023-09–2026-08 porque ese outer loop ya fue inner. Congelar ahora los últimos 126 días, después de haber computado 405 trades, WFE, DSR y PBO sobre el stitch completo, es teatro: ya se conoce el veredicto agregado, y el pipeline se ajustó con diagnósticos que los incluyen. Un test de ~81 trades no tiene potencia para el fenómeno descrito (contaminación de muchas decisiones de proyecto); fallaría o pasaría por ruido de muestreo. DSR ya es la corrección por cuántas cosas se probaron; a 0.0019 no se está en la región donde un segundo test cambia el GO/NO-GO.

La irreversibilidad se sostiene para barras **no vistas**. Se aplica mal a un recorte retrospectivo. El movimiento correcto no es esperar ni escarbar el pasado: es precomprometer que, en el primer candidato que pase los gates no-holdout, el período *posterior* —paper o live, datos que aún no existen— es el holdout, con reglas de muerte fijadas antes de verlo.

---

## 4. Qué evidencia haría cambiar de opinión

Tres cosas verificables, no una intuición.

1. Un commit (git, changelog, o hash de config) con fecha anterior a cualquier corrida, que congele un \(t^*\) y prohíba métricas, plots y diagnósticos en \((t^*, T]\). Si ese artefacto existe, se retracta «esta muestra no tiene holdout» y se reevalúa el costo en ventanas sobre el prefijo.
2. Una corrida del mismo aparato con \(\geq 8\) ventanas OOS y \(\geq 600\) operaciones OOS *después* de sacar seis meses, de modo que perder un tramo no deje el gate de 300 al 8 % ni reduzca los réplicas temporales a cuatro.
3. Un candidato con DSR \(\geq 0.80\), WFE a no más de ~0.05 del umbral 0.50, y profit factor a no más de ~0.10 del umbral 1.30, *antes* de tocar el tramo congelado. Ahí un test independiente tiene trabajo. Con DSR 0.0019 no.

Si no se puede producir el commit, no hay holdout. Si no se pueden producir los otros dos, no hay un candidato que merezca gastarlo.

---

## 5. Modo de falla

Si se sigue este consejo, el modo de falla es el jardín de senderos que se bifurcan sobre las mismas cinco ventanas hasta que algo pase 18 gates. DSR y PBO subcontarán el search real (candidatos descartados, filtros, geometría). El primer GO será un falso positivo. El único OOS verdadero será capital. Ese es el costo de no reservar en el histórico.

Mitigación, no holdout retrospectivo: congelar ya geometría, gates y umbrales (si se dijo que no se relajan, el modo de falla es que se relajen igual); registrar cada candidato y cada iteración de pipeline en el \(N\) de DSR; el primer tramo live/paper *después* de un GO es el holdout, con tamaño y kill rules escritos antes de ver una barra.

---

## 6. La pregunta que el briefing no hace

¿Tiene sentido gastar poder estadístico en un holdout ahora, con DSR 0.0019 contra umbral 0.95, o es optimizar el rigor de la validación para una estrategia que ni se acerca? El contraargumento: la decisión es irreversible en una sola dirección —un holdout no se puede declarar sobre datos ya mirados— así que «esperemos a tener algo cerca del umbral» podría ser precisamente la trampa.

No gastar poder estadístico de *esta* muestra en un holdout. El contraargumento de irreversibilidad **se sostiene para el futuro y no se sostiene para el pasado**. «Esperemos a tener algo cerca» es una trampa si durante la espera se siguen mirando las barras que se querían reservar. No es una trampa que se resuelva recortando una serie ya inspeccionada. No se está preguntando si preservar una opción; se está preguntando si destruir una de cinco réplicas para etiquetar de holdout un tramo que ya no lo es.

No hay base para afirmar cuánto del 0.0019 viene de \(N\) inflado versus Sharpe miserable: no se dio el conteo de trials ni el Sharpe crudo. Tampoco se puede afirmar, ventana por ventana, cuánto aportó el último OOS al NO-GO. Ninguna de las dos lagunas cambia la decisión sobre *esta* muestra.
