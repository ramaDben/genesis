# La revisión cruzada con otro modelo atrapa inferencias falsas que ningún test atraparía

**Fecha: 2026-09-14.** Medido sobre la fase design del Change #109, no supuesto.

## Qué se hizo

Dos rondas de revisión adversarial del `design.md` con Gemini (`agy-delegate --tier pro`, plugin
`antigravity`), cada hallazgo reconciliado después contra el código real antes de aceptarlo.

| Ronda | Hallazgos | Sobrevivieron | Qué cambió |
|---|---|---|---|
| 1ª | 5 | 3 | Revirtió DH-1, disolvió DH-2, destapó defaults silenciosos en `RiskProfile` |
| 2ª | 8 | 5 | Revirtió `house_rule` obligatorio, destapó el hueco `account_size`↔`--starting-balance` y dos evals faltantes |

## Por qué importa: los dos errores caros eran inferencias plausibles y falsas

Ninguno de los dos lo habría agarrado un test, un linter ni un type checker — no eran bugs de
código, eran **premisas equivocadas dentro de un documento de diseño**, que es justamente lo que
después se convierte en código correcto respecto de una premisa incorrecta:

1. **"porcentaje = inflador de `p_pass`"** → falso. El inflador es la combinación `TRAILING × pct`
   (ver `mem:inflador-de-p-pass-es-trailing-por-pct-no-el-porcentaje`). Iba a mutilar tres fichas.
2. **"la rama `None` de `house_rule` no tiene caso real"** → falso. `binance_futures.json` es un
   **exchange**, no una prop firm; volver el campo obligatorio obligaba a inventarle tres reglas
   que no existen en ningún contrato. Contradecía el principio que el mismo documento enunciaba
   dos secciones más abajo.

Los dos errores los cometió un modelo escribiendo el diseño, y los dos los encontró **otro modelo
leyendo el mismo código**.

## Cómo hacerlo, en concreto

- `agy` **sólo funciona desde Git Bash en Windows**, no desde WSL: el shim
  `/mnt/c/Users/<u>/bin/agy` tiene un `exec` a una ruta `/c/...` que WSL no resuelve.
- El wrapper pasa el prompt **por argv**, así que un dossier grande revienta el límite de línea de
  comandos de Windows (`Argument list too long`, exit 126). La vía que funciona es
  `agy-delegate --tier pro --dir <dir> "leé el archivo X"` con el material en un archivo.
- `--continue` reusa la conversación: para una segunda ronda ahorra remandar el código.
- **Reconciliar siempre.** Las citas `archivo:línea` de la respuesta son **offsets del dossier**,
  no de los archivos reales — hay que mapearlas a mano. De 13 hallazgos, 5 eran falsos positivos,
  y uno de ellos fusionaba tres objetos distintos del dominio en dos.
- Decirle explícitamente qué está **fuera de discusión** y qué hallazgos previos ya se rechazaron
  y por qué: sin eso, la segunda ronda vuelve a plantear lo mismo.

## Cuándo repetirlo

Vale la pena en un design que toca contrato público o gates. En el #109 fueron ~300K tokens de
Gemini y dos vueltas de reescritura, contra el costo de descubrir en `review` que el diseño
eliminaba fichas por una premisa falsa.

Ver `mem:pulse-engine-prefijo-de-tools-en-subagentes` para la trampa de nombres de tools que
apareció en el mismo ciclo.
