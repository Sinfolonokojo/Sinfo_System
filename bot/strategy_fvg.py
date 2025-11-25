"""
Fair Value Gap (FVG) Strategy.

Trades price imbalances (gaps) in the market with high win rate.
Based on research showing 61% win rate for bearish setups.
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


class FVGStrategy:
    """
    Fair Value Gap Strategy.

    Identifies price imbalances where the current bar's low is above
    the high of 2 bars ago (bullish FVG) or the current high is below
    the low of 2 bars ago (bearish FVG).

    Research shows bearish FVGs have 61% win rate with 0.45% avg return.

    Entry Conditions:
    - LONG: Current Low > High from 2 bars ago (bullish gap)
    - SHORT: Current High < Low from 2 bars ago (bearish gap)

    Exit Conditions:
    - Stop Loss: ATR(14) * 1.5
    - Take Profit: 1:1.5 Risk/Reward (better for gap fills)
    - Time Decay: Close after 5 bars (based on research)
    """

    def __init__(self, account_name: str):
        self.logger = setup_logger(f"FVG:{account_name}")
        self.indicators = Indicators(account_name)

        # FVG-specific parameters
        self.lookback_bars = 2
        self.holding_period = 5  # Exit after 5 bars
        self.atr_sl_multiplier = STRATEGY_CONFIG.get('atr_sl_multiplier', 1.5)
        self.rr_ratio = STRATEGY_CONFIG.get('fvg_risk_reward_ratio', 1.5)  # Better RR for FVG

        # Minimum gap size filter (in pips) - avoids tiny gaps
        self.min_gap_pips = STRATEGY_CONFIG.get('fvg_min_gap_pips', 5)

    def update_indicators(self, symbol: str) -> bool:
        """Update indicators for a symbol."""
        return self.indicators.update(symbol)

    def check_signal(self, symbol: str) -> SignalType:
        """
        Check for FVG entry signals.

        Args:
            symbol: Trading symbol.

        Returns:
            SignalType indicating the trade direction.
        """
        # Get historical data
        if symbol not in self.indicators._cache:
            if not self.indicators.update(symbol):
                return SignalType.NONE

        cache = self.indicators._cache[symbol]
        rates = cache['rates']

        if len(rates) < 3:
            return SignalType.NONE

        # Get last 3 bars
        current = rates[-1]
        prev_1 = rates[-2]
        prev_2 = rates[-3]

        # Check for Bullish FVG (current low > high from 2 bars ago)
        if current['low'] > prev_2['high']:
            gap_size = current['low'] - prev_2['high']
            gap_pips = self._price_to_pips(symbol, gap_size)

            # Filter by minimum gap size
            if gap_pips >= self.min_gap_pips:
                self.logger.info(
                    f"BULLISH FVG | {symbol} | "
                    f"Current Low: {current['low']:.5f} > "
                    f"Prev_2 High: {prev_2['high']:.5f} | "
                    f"Gap: {gap_pips:.1f} pips"
                )
                return SignalType.BUY

        # Check for Bearish FVG (current high < low from 2 bars ago)
        if current['high'] < prev_2['low']:
            gap_size = prev_2['low'] - current['high']
            gap_pips = self._price_to_pips(symbol, gap_size)

            # Filter by minimum gap size
            if gap_pips >= self.min_gap_pips:
                self.logger.info(
                    f"BEARISH FVG | {symbol} | "
                    f"Current High: {current['high']:.5f} < "
                    f"Prev_2 Low: {prev_2['low']:.5f} | "
                    f"Gap: {gap_pips:.1f} pips"
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
        sl_pips = self.indicators.get_stop_loss_pips(symbol)
        if sl_pips <= 0:
            self.logger.error(f"Invalid SL pips for {symbol}")
            return None

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

    def _price_to_pips(self, symbol: str, price_distance: float) -> float:
        """Convert price distance to pips."""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return 0

        if symbol_info.digits == 3 or symbol_info.digits == 5:
            pip_size = symbol_info.point * 10
        else:
            pip_size = symbol_info.point

        return price_distance / pip_size if pip_size > 0 else 0

    def is_new_bar(self, symbol: str) -> bool:
        """Check if a new bar has formed."""
        return self.indicators.is_new_bar(symbol)

    def get_indicator_values(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current indicator values for display/logging."""
        return self.indicators.get_current_values(symbol)
