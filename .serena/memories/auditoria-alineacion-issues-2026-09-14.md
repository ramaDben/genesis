# Auditoría de alineación de los issues abiertos (2026-09-14)

Contraste de los issues abiertos **no diferidos** contra el árbol en `fe5e683` y el SSoT v1.5.
Todo verificado en código, no en memorias. Las cuatro correcciones quedaron comentadas en
GitHub (#105, #107, #96, #57).

## Lo que se encontró

### Dos esquemas de metadata de genoma conviven en el árbol

- `candidates/specs/candidate_b1_orb.yaml` — `metadata` con `id`/`author`/`paper_ref`/
  `economic_rationale`/`fidelity`. **Sin bloque `sources:` en absoluto.** Arranca con BOM UTF-8.
- `candidates/specs/candidate_c1_gold_lob.yaml` — los mismos campos **más** `sources.academic`
  y `sources.institutional` completos. **Sin trackear.**

O sea: el Gate 0 de `docs/PROTOCOLO_ADMISION_ESTRATEGIAS.md` no tiene ejecutor mecánico, y c1
entraría al repo con un esquema que nada valida. Es exactamente lo que pide #105.

### #105 y R8 de la spec de #109 son el mismo mecanismo

Rechazo ruidoso de claves que no gobiernan nada, sobre dos bloques del mismo YAML:
#105 sobre `metadata.sources`, R8 sobre `risk_exit.params` (caso vivo:
`candidate_c1_gold_lob.yaml:35`, `atr_multiplier: 2.5`, hoy descartado en silencio porque
`simulator.py:399` lee `trailing_atr_mult` del JSON global). Implementarlos por separado deja
dos caminos de validación dentro del mismo compilador.

Las rutas que cita #105 quedaron viejas por #103: `strategy/genome.py` es hoy el paquete
`strategy/genome/`, y `tests/strategy/test_genome.py` es `tests/strategy/genome/test_compiler.py`.

### El defecto de #107 se replicó

`candidate_c1_gold_lob.yaml` también declara `fidelity: canonical` citando a Lou, Polk & Skouras
(2019) *A Tug of War: Overnight vs Intraday Expected Returns* mientras implementa
`opening_range_breakout` de 60 min con salida Chandelier. Mismo modo de falla que b1: misma
familia, regla distinta. Su DoD cubre a los dos; el título nombra a uno.

### #96 tiene la premisa vencida por el pivote

Mide contra «un límite diario del 4 % o 5 %» que **MFFU Rapid EOD no tiene**. Su peor día medido
(−10 R al 1 % = −$5.000) es **2,5× el MLL real** de $2.000 trailing EOD, y sin reset diario el
argumento de la barrera de absorción cambia de naturaleza: un mal día no se sobrevive para
empezar de cero, consume colchón hasta que el ancla vuelva a subir. Su universo (cobre, crudo,
dólar, «los cinco activos del Playbook») es CFD pre-pivote.

Y **bloquea trabajo en curso**: la spec de #109 declaró el presupuesto de contratos
(3 mini / 30 micro) fuera de alcance por depender de esta decisión.

### D2 del RFC #57 se resolvió por elusión, sin gate

`src/genesis/strategy/contract.py:63` sigue siendo `CANDIDATE_REGISTRY: dict[str, ...]` indexado
por letra con fail-fast ante colisión. El camino de genomas de #103
(`src/genesis/strategy/genome/candidate.py`) **no lo toca**: un genoma compilado nunca entra al
registry. El registry por letra no se cambió ni se decidió — se eludió. Es un cambio de contrato
de capa 2 tomado de hecho, mismo patrón que el precedente del PR #69 que documenta el `CLAUDE.md`.

Conviene declarar D2 («el registry por letra queda para los candidatos manuscritos; los genomas
compilados viven fuera de él») en vez de dejarla abierta mientras el código ya opera de otra forma.

## Deriva en el propio `CLAUDE.md` — CORREGIDA el 2026-09-14

Dice que la búsqueda automatizada está «condicionada a un ledger de ensayos persistente (#53)» y
que «el ledger va antes que el arquitecto». Pero:

- #53 cerró **COMPLETED el 2026-08-11**;
- `src/genesis/validation/trial_ledger.py` existe y está cableado en `verdict.py:913`
  (`ledger.read_summary()` → `ledger_extra_trials`);
- el arquitecto Fase 1 (#103) mergeó el 2026-09-10.

El archivo que todo agente lee al arrancar declaraba pendiente un prerrequisito satisfecho y
anunciaba un orden que ya se ejecuto. **Corregido el 2026-09-14**: el parrafo de "Vision de largo
plazo" ahora dice que los dos prerrequisitos estan construidos, cita el cableado real
(`trial_ledger.py` -> `verdict.py` -> `ledger_extra_trials`) y redirige lo pendiente a los
controles (Gate 0 sin ejecutor, D2 del RFC resuelta por elusion). Queda **sin commitear** junto con
el resto del working tree de la rama `docs/spec-v1-5-futuros-cme`.

## El compilador no tiene gramática — abierto como #110 el 2026-09-14

Hallazgo posterior a esta auditoría, verificado en el árbol: **ningún `kind` del genoma ramifica**.
`GenomeAlpha.entry_trigger` y `regime_filter` son `Mapping[str, Any]` opacos (`schema.py:52-53`) y
el parser sólo valida que sean mappings (`schema.py:167-173`) — la clave `kind` que escribe el YAML
de b1 **ni siquiera es un campo del esquema**. El único `kind` tipado es el de `GenomeRiskExit`, y
es un `str` libre (`schema.py:60`). En el compilador, `candidate.py:57` dice literal
`# 1. Trigger config (ORB)`, y `candidate.py:274` es un booleano
(`is_chandelier = kind == "chandelier_trailing"`), no un dispatch.

Consecuencia: un genoma con `entry_trigger.kind: "mean_reversion"` compila sin quejarse y se
ejecuta como ruptura de rango de apertura. Por eso b1 y c1 son la misma familia — no es alcance, es
que no hay forma de expresar otra cosa. El #103 probó que la tubería declarativa no degrada nada;
**no** probó expresividad.

Abierto como [#110](https://github.com/ramaDben/genesis/issues/110), que depende del #109 porque su
R8 es el mismo mecanismo de rechazo ruidoso.

## Orden recomendado

1. Terminar #109 (en `design`, esperando el gate humano).
2. Fundir **#105 + #107** en un solo change de Gate 0, coordinando el rechazo de claves con R8 de #109.
2b. **#110** después de #109: la gramática con dispatch. Complementa al Gate 0 — #105/#107 validan
   la *procedencia* del genoma, #110 valida su *gramática*. Sin los dos, un genoma puede citar el
   paper correcto y ejecutar otra cosa, que es hoy el estado de `candidate_c1_gold_lob.yaml`.
3. Reescribir la premisa de #96 contra el MLL trailing EOD y el universo CME antes de decidirlo.
4. #88 en cualquier momento: no depende de nada y no toca código.
5. #57: refrescar a v1.5 o dejar constancia del estado real de D1/D2/D3.

Relacionadas: `mem:pivote-a-prop-de-futuros-cme-2026-09`,
`mem:mffu-rapid-eod-50k-reglas-confirmadas`, `mem:change-103-arquitecto-y-compilador-genomas`,
`mem:change-103-no-paso-por-el-engine`, `mem:d1-que-cuenta-como-ensayo`,
`mem:arquitecto-estrategias-y-ledger-ensayos`.
