"""
Symbol translation utilities for broker-specific normalization.
"""

from typing import Dict, Optional


class SymbolTranslator:
    """
    Translates master symbols to slave broker format.

    Handles symbol mapping and suffix appending.
    """

    def __init__(self, symbol_map: Dict[str, str] = None, suffix: str = ""):
        """
        Initialize the translator.

        Args:
            symbol_map: Dictionary mapping master symbols to slave symbols.
            suffix: Broker-specific suffix to append (e.g., ".c", ".pro").
        """
        self.symbol_map = symbol_map or {}
        self.suffix = suffix

    def translate(self, master_symbol: str) -> str:
        """
        Translate a master symbol to slave format.

        Priority:
        1. Check symbol_map for manual override
        2. Append suffix if no mapping found

        Args:
            master_symbol: Symbol from master account.

        Returns:
            Translated symbol for slave broker.
        """
        # Check for explicit mapping first
        if master_symbol in self.symbol_map:
            return self.symbol_map[master_symbol]

        # Otherwise, append suffix
        return f"{master_symbol}{self.suffix}"

    def reverse_translate(self, slave_symbol: str) -> str:
        """
        Reverse translate a slave symbol back to master format.

        Args:
            slave_symbol: Symbol from slave account.

        Returns:
            Original master symbol.
        """
        # Check reverse mapping
        for master, slave in self.symbol_map.items():
            if slave == slave_symbol:
                return master

        # Remove suffix if present
        if self.suffix and slave_symbol.endswith(self.suffix):
            return slave_symbol[:-len(self.suffix)]

        return slave_symbol
