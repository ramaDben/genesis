"""Jerarquía de excepciones de dominio para utilidades comunes de estrategia."""

from genesis.strategy.errors import GenesisStrategyError


class StrategyCommonError(GenesisStrategyError):
    """Raíz de excepciones para componentes comunes de `genesis.strategy.common`."""


class IncrementalAtrStateError(StrategyCommonError):
    """Se consulta el valor de un IncrementalAtr antes de su calentamiento o en estado inválido."""
