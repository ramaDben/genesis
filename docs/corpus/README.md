# Corpus — registro de claims con procedencia

Sembrado el 2026-09-20 por la casilla **0.1** de `docs/ROADMAP_ARQUITECTO.md`.

> **El formato de este directorio es provisional.** La casilla **A.3** del roadmap es la que lo
> diseña. Lo que hay acá es la forma mínima que la casilla 0.1 necesitaba para dejar su resultado
> registrado en vez de suelto, y va a cambiar cuando A.3 lo formalice. No se construya nada encima
> todavía.

## Qué es

El registro de lo que **dice el mundo** sobre cómo operar: papers, traders publicados, notas
institucionales. Es la entrada del arquitecto.

**La unidad es el claim, no el autor ni el concepto.** Un archivo = una afirmación testeable. Autores
y tópicos son índices sobre claims, no la unidad de registro. La razón: las contradicciones existen
entre claims. «Fulano contra Mengano» es una pelea de opiniones; «el claim 004 contradice al 009
sobre si el barrido de liquidez tiene contenido direccional» es una proposición adjudicable que se
compila a dos genomas que difieren en una sola cosa.

## Invariante I2 (no negociable)

**El corpus registra lo que dice el mundo, jamás lo que dijo el evaluador.** Ningún veredicto del
pipeline entra acá. Son dos rutas distintas y auditables por separado; si se mezclan, el arquitecto
deja de ser feed-forward y la máquina pierde la propiedad que la hace segura.

Corolario operativo: **ninguna métrica derivada de contar nodos puede alimentar una decisión de
admisión.** Nada de «score de confianza» por volumen de menciones. Un grafo hace que la copia se vea
como corroboración, y esa falla va en dirección permisiva.

## Estructura

```
docs/corpus/
├── README.md              este archivo
├── fuentes/               una ficha por fuente, con su procedencia y su evaluación crítica
└── claims/                un archivo por afirmación testeable
```

### Ficha de fuente (`fuentes/`)

Procedencia completa + **evaluación crítica de la fuente como fuente**: qué tan buscada fue la
evidencia, qué se declara sobre el número de ensayos, qué defectos tiene. Una fuente honesta sobre
sus propios defectos vale más, no menos.

### Claim (`claims/`)

| Campo | Qué va |
|---|---|
| `id` | `CLAIM-NNN` |
| `fuente` | archivo de `fuentes/` |
| `concepto` | el tópico al que pertenece (ORB, barrido de liquidez, momentum intradía…) |
| `cita` | **textual**, de la fuente, sin parafrasear |
| `predicción falsable` | «la fuente predice que X ocurre» — si no se puede escribir, el claim no entra |
| `mecanismo` | ID del catálogo de mecanismos de A.2, o **`sin mecanismo publicado`** |
| `estado` | `registrado` · `compilado a genoma` · `rechazado en Gate 0` |

**`sin mecanismo publicado` no es una falla del corpus: es su producto más barato.** Es Gate 0
diciendo que no hay un *porqué* antes de gastar un ensayo. Se espera que la mayor parte del
vocabulario retail termine así.

## Índice de claims

| ID | Concepto | Predicción, en una línea | Estado |
|---|---|---|---|
| [001](claims/CLAIM-001.md) | Techo de edge OHLCV | El edge bruto de patrones OHLCV de 5 min en MNQ no supera ~1–2 pts, por debajo de la fricción | registrado |
| [002](claims/CLAIM-002.md) | ORB | El ORB largo en MNQ RTH no alcanza significancia estadística sobre 447 operaciones OOS | registrado |
| [003](claims/CLAIM-003.md) | Expansión de rango / sesión asiática | La expansión de rango predice **reversión**, no continuación | registrado |
| [004](claims/CLAIM-004.md) | Barrido de liquidez | El barrido de extremos de sesión no tiene contenido direccional explotable en **ninguna** dirección | registrado |
| [005](claims/CLAIM-005.md) | Clasificación de régimen | Lo que escapa al techo usa detección de régimen y holds de 60–75 min, no predicción de barra única | registrado |
| [006](claims/CLAIM-006.md) | Fragilidad temporal | Un retardo de una barra **invierte el signo** de una señal de régimen, no lo degrada | registrado |

## Índice de fuentes

| Fuente | Tipo | Evaluación |
|---|---|---|
| [Mesfin (2026), falsación OHLCV en MNQ](fuentes/mesfin-2026-mnq-falsification.md) | preprint arXiv, sin revisión de pares | útil con reservas grandes; honesta sobre sus defectos |
