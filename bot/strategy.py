"""
Elastic Band Strategy - Trend-Following Mean Reversion.

Entry logic state machine for the prop firm trading strategy.
"""

from enum import Enum
from typing import Optional, Dict, Any
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None

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


class ElasticBandStrategy:
    """
    The Elastic Band Strategy - Trend-Following Mean Reversion.

    Entry Conditions:
    - LONG: Price > EMA(200), Low touches EMA(50), RSI hooks up from oversold
    - SHORT: Price < EMA(200), High touches EMA(50), RSI hooks down from overbought

    Exit Conditions:
    - Stop Loss: ATR(14) * 1.5
    - Take Profit: 1:1 Risk/Reward
    - Time Decay: Close after 3 hours if profitable
    """

    def __init__(self, account_name: str):
        self.logger = setup_logger(f"STRAT:{account_name}")
        self.indicators = Indicators(account_name)

        # Strategy parameters
        self.ema_touch_tolerance = STRATEGY_CONFIG['ema_touch_tolerance_pips']
        self.rsi_oversold = STRATEGY_CONFIG['rsi_oversold']
        self.rsi_overbought = STRATEGY_CONFIG['rsi_overbought']
        self.atr_sl_multiplier = STRATEGY_CONFIG['atr_sl_multiplier']
        self.rr_ratio = STRATEGY_CONFIG['risk_reward_ratio']

    def update_indicators(self, symbol: str) -> bool:
        """
        Update indicators for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            True if update successful.
        """
        return self.indicators.update(symbol)

    def check_signal(self, symbol: str) -> SignalType:
        """
        Check for entry signals on a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            SignalType indicating the trade direction.
        """
        values = self.indicators.get_current_values(symbol)
        if values is None:
            return SignalType.NONE

        # Get pip tolerance for EMA touch
        pip_tolerance = self._pips_to_price(symbol, self.ema_touch_tolerance)

        # Extract values
        close = values['close']
        high = values['high']
        low = values['low']
        ema_trend = values['ema_trend']
        ema_reversion = values['ema_reversion']
        rsi = values['rsi']
        prev_rsi = values['prev_rsi']

        # Check LONG signal
        if self._check_long_signal(close, low, ema_trend, ema_reversion,
                                    rsi, prev_rsi, pip_tolerance):
            self.logger.info(
                f"LONG SIGNAL | {symbol} | Close: {close:.5f} | "
                f"EMA200: {ema_trend:.5f} | EMA50: {ema_reversion:.5f} | "
                f"RSI: {prev_rsi:.1f} -> {rsi:.1f}"
            )
            return SignalType.BUY

        # Check SHORT signal
        if self._check_short_signal(close, high, ema_trend, ema_reversion,
                                     rsi, prev_rsi, pip_tolerance):
            self.logger.info(
                f"SHORT SIGNAL | {symbol} | Close: {close:.5f} | "
                f"EMA200: {ema_trend:.5f} | EMA50: {ema_reversion:.5f} | "
                f"RSI: {prev_rsi:.1f} -> {rsi:.1f}"
            )
            return SignalType.SELL

        return SignalType.NONE

    def _check_long_signal(
        self,
        close: float,
        low: float,
        ema_trend: float,
        ema_reversion: float,
        rsi: float,
        prev_rsi: float,
        tolerance: float
    ) -> bool:
        """
        Check for LONG (BUY) entry conditions.

        Conditions:
        1. Trend: Close > EMA(200)
        2. Dip: Low touches or nears EMA(50)
        3. RSI: Hooks up from oversold (prev < 30, current >= 30)
        """
        # Trend condition: Price above trend line
        trend_ok = close > ema_trend

        # Dip condition: Price touched or came close to reversion line
        dip_ok = low <= (ema_reversion + tolerance)

        # RSI trigger: Was oversold, now hooking up
        rsi_trigger = (prev_rsi < self.rsi_oversold) and (rsi >= self.rsi_oversold)

        return trend_ok and dip_ok and rsi_trigger

    def _check_short_signal(
        self,
        close: float,
        high: float,
        ema_trend: float,
        ema_reversion: float,
        rsi: float,
        prev_rsi: float,
        tolerance: float
    ) -> bool:
        """
        Check for SHORT (SELL) entry conditions.

        Conditions:
        1. Trend: Close < EMA(200)
        2. Rally: High touches or nears EMA(50)
        3. RSI: Hooks down from overbought (prev > 70, current <= 70)
        """
        # Trend condition: Price below trend line
        trend_ok = close < ema_trend

        # Rally condition: Price touched or came close to reversion line
        rally_ok = high >= (ema_reversion - tolerance)

        # RSI trigger: Was overbought, now hooking down
        rsi_trigger = (prev_rsi > self.rsi_overbought) and (rsi <= self.rsi_overbought)

        return trend_ok and rally_ok and rsi_trigger

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
        """
        Convert pips to price distance.

        Args:
            symbol: Trading symbol.
            pips: Number of pips.

        Returns:
            Price distance.
        """
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return 0

        # Determine pip size based on digits
        if symbol_info.digits == 3 or symbol_info.digits == 5:
            pip_size = symbol_info.point * 10
        else:
            pip_size = symbol_info.point

        return pips * pip_size

    def is_new_bar(self, symbol: str) -> bool:
        """
        Check if a new bar has formed.

        Args:
            symbol: Trading symbol.

        Returns:
            True if new bar detected.
        """
        return self.indicators.is_new_bar(symbol)

    def get_indicator_values(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current indicator values for display/logging.

        Args:
            symbol: Trading symbol.

        Returns:
            Dictionary with indicator values.
        """
        return self.indicators.get_current_values(symbol)
