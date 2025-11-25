"""
MACD + RSI Combination Strategy.

Combines MACD momentum with RSI overbought/oversold for high-probability entries.
Multi-indicator confirmation reduces false signals.
"""

from enum import Enum
from typing import Optional, Dict, Any
import MetaTrader5 as mt5
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.config import STRATEGY_CONFIG
from bot.indicators import Indicators


class SignalType(Enum):
    """Trading signal types."""
    NONE = 0
    BUY = 1
    SELL = 2


class MACDRSIStrategy:
    """
    MACD + RSI Combination Strategy.

    Uses MACD histogram crossovers confirmed by RSI for entry signals.

    Entry Conditions:
    - LONG: MACD histogram crosses above 0 + RSI > 30 (leaving oversold)
    - SHORT: MACD histogram crosses below 0 + RSI < 70 (leaving overbought)

    Exit Conditions:
    - Stop Loss: ATR(14) * 2.0 (wider for momentum trades)
    - Take Profit: 1:2 Risk/Reward (momentum can run)
    - Time Decay: Close after 4 hours
    """

    def __init__(self, account_name: str):
        self.logger = setup_logger(f"MACD_RSI:{account_name}")
        self.indicators = Indicators(account_name)

        # MACD parameters
        self.macd_fast = STRATEGY_CONFIG.get('macd_fast', 12)
        self.macd_slow = STRATEGY_CONFIG.get('macd_slow', 27)
        self.macd_signal = STRATEGY_CONFIG.get('macd_signal', 9)

        # RSI parameters
        self.rsi_period = STRATEGY_CONFIG.get('rsi_period', 7)
        self.rsi_oversold = STRATEGY_CONFIG.get('rsi_oversold', 30)
        self.rsi_overbought = STRATEGY_CONFIG.get('rsi_overbought', 70)

        # Exit parameters
        self.atr_sl_multiplier = STRATEGY_CONFIG.get('macd_rsi_atr_sl', 2.0)
        self.rr_ratio = STRATEGY_CONFIG.get('macd_rsi_rr_ratio', 2.0)
        self.max_trade_duration = STRATEGY_CONFIG.get('macd_rsi_max_duration', 240)  # 4 hours

    def update_indicators(self, symbol: str) -> bool:
        """Update indicators for a symbol."""
        if not self.indicators.update(symbol):
            return False

        # Calculate MACD if not already cached
        if symbol in self.indicators._cache:
            cache = self.indicators._cache[symbol]
            close_prices = cache['close']

            # Calculate MACD
            macd_data = self.indicators.calculate_macd(
                close_prices,
                self.macd_fast,
                self.macd_slow,
                self.macd_signal
            )

            # Add to cache
            cache['macd'] = macd_data['macd']
            cache['macd_signal'] = macd_data['signal']
            cache['macd_histogram'] = macd_data['histogram']

        return True

    def check_signal(self, symbol: str) -> SignalType:
        """
        Check for MACD + RSI entry signals.

        Args:
            symbol: Trading symbol.

        Returns:
            SignalType indicating the trade direction.
        """
        if symbol not in self.indicators._cache:
            if not self.update_indicators(symbol):
                return SignalType.NONE

        cache = self.indicators._cache[symbol]

        # Get MACD histogram values
        histogram = cache['macd_histogram']
        rsi = cache['rsi']

        if len(histogram) < 2 or len(rsi) < 2:
            return SignalType.NONE

        # Current and previous values
        curr_hist = histogram[-1]
        prev_hist = histogram[-2]
        curr_rsi = rsi[-1]
        prev_rsi = rsi[-2]

        # Check for LONG signal
        # MACD histogram crosses above 0 + RSI leaving oversold zone
        if prev_hist <= 0 and curr_hist > 0 and curr_rsi > self.rsi_oversold:
            self.logger.info(
                f"LONG SIGNAL | {symbol} | "
                f"MACD Histogram: {prev_hist:.6f} -> {curr_hist:.6f} | "
                f"RSI: {curr_rsi:.1f}"
            )
            return SignalType.BUY

        # Check for SHORT signal
        # MACD histogram crosses below 0 + RSI leaving overbought zone
        if prev_hist >= 0 and curr_hist < 0 and curr_rsi < self.rsi_overbought:
            self.logger.info(
                f"SHORT SIGNAL | {symbol} | "
                f"MACD Histogram: {prev_hist:.6f} -> {curr_hist:.6f} | "
                f"RSI: {curr_rsi:.1f}"
            )
            return SignalType.SELL

        return SignalType.NONE

    def calculate_trade_levels(
        self,
        symbol: str,
        signal: SignalType
    ) -> Optional[Dict[str, float]]:
        """
        Calculate entry, stop loss, and take profit levels.

        Args:
            symbol: Trading symbol.
            signal: Signal type (BUY or SELL).

        Returns:
            Dictionary with entry, sl, tp prices and sl_pips.
        """
        if signal == SignalType.NONE:
            return None

        # Get current tick for entry price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self.logger.error(f"Failed to get tick for {symbol}")
            return None

        # Get ATR for stop loss calculation
        values = self.indicators.get_current_values(symbol)
        if values is None:
            return None

        atr_pips = values['atr_pips']
        sl_pips = atr_pips * self.atr_sl_multiplier

        # Convert pips to price
        sl_distance = self._pips_to_price(symbol, sl_pips)
        tp_distance = sl_distance * self.rr_ratio

        if signal == SignalType.BUY:
            entry = tick.ask
            sl = entry - sl_distance
            tp = entry + tp_distance
        else:  # SELL
            entry = tick.bid
            sl = entry + sl_distance
            tp = entry - tp_distance

        # Get symbol digits for rounding
        symbol_info = mt5.symbol_info(symbol)
        digits = symbol_info.digits if symbol_info else 5

        return {
            'entry': round(entry, digits),
            'sl': round(sl, digits),
            'tp': round(tp, digits),
            'sl_pips': sl_pips
        }

    def _pips_to_price(self, symbol: str, pips: float) -> float:
        """Convert pips to price distance."""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return 0

        if symbol_info.digits == 3 or symbol_info.digits == 5:
            pip_size = symbol_info.point * 10
        else:
            pip_size = symbol_info.point

        return pips * pip_size

    def is_new_bar(self, symbol: str) -> bool:
        """Check if a new bar has formed."""
        return self.indicators.is_new_bar(symbol)

    def get_indicator_values(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current indicator values for display/logging."""
        if symbol not in self.indicators._cache:
            return None

        cache = self.indicators._cache[symbol]
        base_values = self.indicators.get_current_values(symbol)

        if base_values and 'macd_histogram' in cache:
            base_values['macd_histogram'] = cache['macd_histogram'][-1]
            base_values['macd'] = cache['macd'][-1]
            base_values['macd_signal'] = cache['macd_signal'][-1]

        return base_values
