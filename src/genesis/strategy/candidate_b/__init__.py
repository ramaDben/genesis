"""Superficie pública curada de `genesis.strategy.candidate_b` (R48).

`CandidateB` no se re-exporta en `genesis.strategy.__init__.__all__` (agnóstico de
capa 2, §2.2 del design): se importa por ruta explícita `genesis.strategy.
candidate_b`, coherente con que el Candidato C dejó `candidate_*` fuera de esa
superficie.
"""

from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.candidate_b.config import CandidateBConfig, load_candidate_b_config

__all__ = ["CandidateB", "CandidateBConfig", "load_candidate_b_config"]
