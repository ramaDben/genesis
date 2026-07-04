"""Tests unitarios de `common/zones.py` — clasificación PRO/MID/CT (R32-R37)."""

import pytest

from genesis.strategy.common.zones import Zone, classify_zone

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "zscore,expected",
    [
        (0.0, Zone.PRO),
        (0.5, Zone.PRO),
        (-0.5, Zone.PRO),  # simetría por abs(zscore)
        (0.999, Zone.PRO),
        (1.0, Zone.MID),  # frontera exacta: >= va a MID
        (-1.0, Zone.MID),
        (1.5, Zone.MID),
        (1.999, Zone.MID),
        (2.0, Zone.CT),  # frontera exacta: >= va a CT
        (-2.0, Zone.CT),
        (3.0, Zone.CT),
        (100.0, Zone.CT),
    ],
)
def test_classify_zone_tabla_golden_defaults(zscore: float, expected: Zone) -> None:
    assert classify_zone(zscore) == expected


def test_classify_zone_override_umbrales() -> None:
    assert classify_zone(1.5, pro_zscore_max=1.6, ct_zscore_min=3.0) == Zone.PRO
    assert classify_zone(1.6, pro_zscore_max=1.6, ct_zscore_min=3.0) == Zone.MID
    assert classify_zone(3.0, pro_zscore_max=1.6, ct_zscore_min=3.0) == Zone.CT


def test_classify_zone_umbrales_invertidos_lanza_value_error() -> None:
    with pytest.raises(ValueError, match=r"2\.0.*2\.0"):
        classify_zone(1.0, pro_zscore_max=2.0, ct_zscore_min=2.0)


def test_classify_zone_umbrales_estrictamente_invertidos_lanza_value_error() -> None:
    with pytest.raises(ValueError, match=r"3\.0.*1\.0"):
        classify_zone(1.0, pro_zscore_max=3.0, ct_zscore_min=1.0)
