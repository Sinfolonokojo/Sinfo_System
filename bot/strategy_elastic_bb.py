"""
Enhanced Elastic Band Strategy with Bollinger Bands Confirmation.

Original Elastic Band strategy enhanced with Bollinger Bands for better
mean reversion signal quality.
"""

from enum import Enum
from typing import Optional, Dict, Any
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None
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


class ElasticBBStrategy:
    """
    Enhanced Elastic Band Strategy with Bollinger Bands.

    Combines original Elastic Band logic with Bollinger Bands for additional
    confirmation of mean reversion opportunities.

    Entry Conditions:
    - LONG: Original elastic band LONG + Price near/touching lower BB
    - SHORT: Original elastic band SHORT + Price near/touching upper BB

    This adds volatility context to the mean reversion trade.

    Exit Conditions:
    - Stop Loss: ATR(14) * 1.5
    - Take Profit: 1:1.5 Risk/Reward
    - Time Decay: Close after 3 hours if profitable
    """

    def __init__(self, account_name: str):
        self.logger = setup_logger(f"ELASTIC_BB:{account_name}")
        self.indicators = Indicators(account_name)

        # Strategy parameters
        self.ema_touch_tolerance = STRATEGY_CONFIG['ema_touch_tolerance_pips']
        self.rsi_oversold = STRATEGY_CONFIG['rsi_oversold']
        self.rsi_overbought = STRATEGY_CONFIG['rsi_overbought']
        self.atr_sl_multiplier = STRATEGY_CONFIG['atr_sl_multiplier']
        self.rr_ratio = STRATEGY_CONFIG.get('elastic_bb_rr_ratio', 1.5)

        # Bollinger Bands parameters
        self.bb_period = STRATEGY_CONFIG.get('bb_period', 20)
        self.bb_std_dev = STRATEGY_CONFIG.get('bb_std_dev', 2.0)
        self.bb_touch_tolerance_pct = STRATEGY_CONFIG.get('bb_touch_tolerance_pct', 0.1)  # 0.1% of price

    def update_indicators(self, symbol: str) -> bool:
        """Update indicators for a symbol."""
        if not self.indicators.update(symbol):
            return False

        # Calculate Bollinger Bands if not already cached
        if symbol in self.indicators._cache:
            cache = self.indicators._cache[symbol]
            close_prices = cache['close']

            # Calculate Bollinger Bands
            bb_data = self.indicators.calculate_bollinger_bands(
                close_prices,
                self.bb_period,
                self.bb_std_dev
            )

            # Add to cache
            cache['bb_upper'] = bb_data['upper']
            cache['bb_middle'] = bb_data['middle']
            cache['bb_lower'] = bb_data['lower']

        return True

    def check_signal(self, symbol: str) -> SignalType:
        """
        Check for enhanced elastic band entry signals.

        Args:
            symbol: Trading symbol.

        Returns:
            SignalType indicating the trade direction.
        """
        if symbol not in self.indicators._cache:
            if not self.update_indicators(symbol):
                return SignalType.NONE

        values = self.indicators.get_current_values(symbol)
        if values is None:
            return SignalType.NONE

        cache = self.indicators._cache[symbol]

        # Get Bollinger Bands values
        bb_upper = cache['bb_upper']
        bb_lower = cache['bb_lower']

        if len(bb_upper) < 1 or len(bb_lower) < 1:
            return SignalType.NONE

        # Current BB values
        curr_bb_upper = bb_upper[-1]
        curr_bb_lower = bb_lower[-1]

        # Get pip tolerance for EMA touch
        pip_tolerance = self._pips_to_price(symbol, self.ema_touch_tolerance)

        # BB touch tolerance (percentage of price)
        bb_tolerance = values['close'] * (self.bb_touch_tolerance_pct / 100)

        # Extract values
        close = values['close']
        high = values['high']
        low = values['low']
        ema_trend = values['ema_trend']
        ema_reversion = values['ema_reversion']
        rsi = values['rsi']
        prev_rsi = values['prev_rsi']

        # Check LONG signal (original + BB confirmation)
        if self._check_long_signal(
            close, low, high,
            ema_trend, ema_reversion,
            rsi, prev_rsi,
            pip_tolerance,
            curr_bb_lower, bb_tolerance
        ):
            self.logger.info(
                f"LONG SIGNAL | {symbol} | "
                f"Close: {close:.5f} | EMA200: {ema_trend:.5f} | "
                f"EMA50: {ema_reversion:.5f} | RSI: {prev_rsi:.1f} -> {rsi:.1f} | "
                f"BB Lower: {curr_bb_lower:.5f}"
            )
            return SignalType.BUY

        # Check SHORT signal (original + BB confirmation)
        if self._check_short_signal(
            close, high, low,
            ema_trend, ema_reversion,
            rsi, prev_rsi,
            pip_tolerance,
            curr_bb_upper, bb_tolerance
        ):
            self.logger.info(
                f"SHORT SIGNAL | {symbol} | "
                f"Close: {close:.5f} | EMA200: {ema_trend:.5f} | "
                f"EMA50: {ema_reversion:.5f} | RSI: {prev_rsi:.1f} -> {rsi:.1f} | "
                f"BB Upper: {curr_bb_upper:.5f}"
            )
            return SignalType.SELL

        return SignalType.NONE

    def _check_long_signal(
        self,
        close: float,
        low: float,
        high: float,
        ema_trend: float,
        ema_reversion: float,
        rsi: float,
        prev_rsi: float,
        ema_tolerance: float,
        bb_lower: float,
        bb_tolerance: float
    ) -> bool:
        """
        Check for LONG (BUY) entry conditions.

        Original elastic band conditions + BB confirmation.
        """
        # Original elastic band conditions
        trend_ok = close > ema_trend
        dip_ok = low <= (ema_reversion + ema_tolerance)
        rsi_trigger = (prev_rsi < self.rsi_oversold) and (rsi >= self.rsi_oversold)

        # Bollinger Bands confirmation: price near lower band
        bb_confirm = low <= (bb_lower + bb_tolerance)

        return trend_ok and dip_ok and rsi_trigger and bb_confirm

    def _check_short_signal(
        self,
        close: float,
        high: float,
        low: float,
        ema_trend: float,
        ema_reversion: float,
        rsi: float,
        prev_rsi: float,
        ema_tolerance: float,
        bb_upper: float,
        bb_tolerance: float
    ) -> bool:
        """
        Check for SHORT (SELL) entry conditions.

        Original elastic band conditions + BB confirmation.
        """
        # Original elastic band conditions
        trend_ok = close < ema_trend
        rally_ok = high >= (ema_reversion - ema_tolerance)
        rsi_trigger = (prev_rsi > self.rsi_overbought) and (rsi <= self.rsi_overbought)

        # Bollinger Bands confirmation: price near upper band
        bb_confirm = high >= (bb_upper - bb_tolerance)

        return trend_ok and rally_ok and rsi_trigger and bb_confirm

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

    def is_new_bar(self, symbol: str) -> bool:
        """Check if a new bar has formed."""
        return self.indicators.is_new_bar(symbol)

    def get_indicator_values(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current indicator values for display/logging."""
        if symbol not in self.indicators._cache:
            return None

        cache = self.indicators._cache[symbol]
        base_values = self.indicators.get_current_values(symbol)

        if base_values and 'bb_upper' in cache:
            base_values['bb_upper'] = cache['bb_upper'][-1]
            base_values['bb_middle'] = cache['bb_middle'][-1]
            base_values['bb_lower'] = cache['bb_lower'][-1]

        return base_values
