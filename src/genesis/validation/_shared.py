"""Helpers idénticos compartidos por los módulos de `genesis/validation/` (Change #46).

Existe para que `montecarlo.py`, `purged_cv.py` y `prop_sim.py` dejen de llevar cada uno su
copia byte-idéntica de `clip`. La regla que empujó a duplicarlos —no importar símbolos
privados de un módulo ya cerrado (ADR-I1/ADR-I2 de `.pulse/specs/validation/spec.md`)— se
respeta igual con un módulo interno compartido: `_shared` lleva prefijo `_` y no se exporta
en `genesis/validation/__init__.py`, así que no amplía la superficie pública de la capa.

**Solo entra aquí lo que sea idéntico en todas sus copias.** Es la parte importante de la
regla: `_default_block_size` tiene una variante distinta en
`strategy/candidate_a/diagnostics.py` (sin piso de 5, con guarda `n <= 0`), y
`_first_fill_record` difiere en firma y en el tipo de excepción entre `montecarlo.py` y
`purged_cv.py`. Unificar cualquiera de esos dos cambiaría resultados numéricos, que es
exactamente lo que este Change prohíbe.
"""


def clip(value: int, low: int, high: int) -> int:
    """Acota `value` al intervalo cerrado `[low, high]`."""
    return max(low, min(high, value))
