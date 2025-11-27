"""
Technical Indicators Module.

Calculates EMA, RSI, and ATR for the Elastic Band strategy.
"""

import numpy as np
from typing import Optional, Dict, Any, List
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


class Indicators:
    """
    Technical indicators calculator for the trading strategy.

    Provides EMA(200), EMA(50), RSI(7), and ATR(14).
    """

    def __init__(self, account_name: str):
        self.logger = setup_logger(f"IND:{account_name}")

        # Indicator periods from config
        self.ema_trend_period = STRATEGY_CONFIG['ema_trend_period']
        self.ema_reversion_period = STRATEGY_CONFIG['ema_reversion_period']
        self.rsi_period = STRATEGY_CONFIG['rsi_period']
        self.atr_period = STRATEGY_CONFIG['atr_period']

        # Cache for indicator values
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_timeframe_constant(self) -> int:
        """Get MT5 timeframe constant based on config."""
        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1
        }
        return timeframe_map.get(STRATEGY_CONFIG['timeframe'], mt5.TIMEFRAME_M15)

    def fetch_candles(self, symbol: str, count: int = 300) -> Optional[np.ndarray]:
        """
        Fetch OHLC data from MT5.

        Args:
            symbol: Trading symbol.
            count: Number of candles to fetch.

        Returns:
            Numpy array with OHLC data.
        """
        timeframe = self.get_timeframe_constant()
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)

        if rates is None or len(rates) == 0:
            self.logger.error(f"Failed to fetch candles for {symbol}")
            return None

        return rates

    def calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate Exponential Moving Average.

        Args:
            data: Price data array.
            period: EMA period.

        Returns:
            EMA values array.
        """
        ema = np.zeros(len(data))
        multiplier = 2 / (period + 1)

        # Start with SMA for first value
        ema[period - 1] = np.mean(data[:period])

        # Calculate EMA
        for i in range(period, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i - 1] * (1 - multiplier))

        return ema

    def calculate_rsi(self, close_prices: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate Relative Strength Index.

        Args:
            close_prices: Close price array.
            period: RSI period.

        Returns:
            RSI values array.
        """
        rsi = np.zeros(len(close_prices))

        # Calculate price changes
        deltas = np.diff(close_prices)

        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Calculate initial averages
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        # First RSI value
        if avg_loss == 0:
            rsi[period] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[period] = 100 - (100 / (1 + rs))

        # Calculate subsequent RSI values using smoothed averages
        for i in range(period, len(close_prices) - 1):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi[i + 1] = 100
            else:
                rs = avg_gain / avg_loss
                rsi[i + 1] = 100 - (100 / (1 + rs))

        return rsi

    def calculate_atr(self, rates: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate Average True Range.

        Args:
            rates: OHLC data array.
            period: ATR period.

        Returns:
            ATR values array.
        """
        high = rates['high']
        low = rates['low']
        close = rates['close']

        atr = np.zeros(len(rates))

        # Calculate True Range
        tr = np.zeros(len(rates))
        tr[0] = high[0] - low[0]

        for i in range(1, len(rates)):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i - 1])
            lc = abs(low[i] - close[i - 1])
            tr[i] = max(hl, hc, lc)

        # Calculate ATR (using EMA method)
        atr[period - 1] = np.mean(tr[:period])

        multiplier = 2 / (period + 1)
        for i in range(period, len(rates)):
            atr[i] = (tr[i] * multiplier) + (atr[i - 1] * (1 - multiplier))

        return atr

    def calculate_macd(self, close_prices: np.ndarray, fast: int = 12, slow: int = 27, signal: int = 9) -> Dict[str, np.ndarray]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            close_prices: Close price array.
            fast: Fast EMA period (default 12).
            slow: Slow EMA period (default 27).
            signal: Signal line period (default 9).

        Returns:
            Dictionary with 'macd', 'signal', and 'histogram' arrays.
        """
        # Calculate fast and slow EMAs
        ema_fast = self.calculate_ema(close_prices, fast)
        ema_slow = self.calculate_ema(close_prices, slow)

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line (EMA of MACD)
        signal_line = self.calculate_ema(macd_line, signal)

        # Histogram
        histogram = macd_line - signal_line

        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }

    def calculate_bollinger_bands(self, close_prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Dict[str, np.ndarray]:
        """
        Calculate Bollinger Bands.

        Args:
            close_prices: Close price array.
            period: Moving average period (default 20).
            std_dev: Standard deviation multiplier (default 2.0).

        Returns:
            Dictionary with 'upper', 'middle', and 'lower' band arrays.
        """
        # Calculate SMA for middle band
        middle_band = np.zeros(len(close_prices))
        upper_band = np.zeros(len(close_prices))
        lower_band = np.zeros(len(close_prices))

        for i in range(period - 1, len(close_prices)):
            window = close_prices[i - period + 1:i + 1]
            middle = np.mean(window)
            std = np.std(window)

            middle_band[i] = middle
            upper_band[i] = middle + (std * std_dev)
            lower_band[i] = middle - (std * std_dev)

        return {
            'upper': upper_band,
            'middle': middle_band,
            'lower': lower_band
        }

    def calculate_mfi(self, rates: np.ndarray, period: int = 14) -> np.ndarray:
        """
        Calculate Money Flow Index.

        Args:
            rates: OHLC data array.
            period: MFI period (default 14).

        Returns:
            MFI values array.
        """
        high = rates['high']
        low = rates['low']
        close = rates['close']
        volume = rates['tick_volume']  # Use tick volume

        mfi = np.zeros(len(rates))

        # Calculate typical price
        typical_price = (high + low + close) / 3

        # Calculate raw money flow
        money_flow = typical_price * volume

        for i in range(period, len(rates)):
            positive_flow = 0
            negative_flow = 0

            for j in range(i - period, i):
                if typical_price[j + 1] > typical_price[j]:
                    positive_flow += money_flow[j + 1]
                elif typical_price[j + 1] < typical_price[j]:
                    negative_flow += money_flow[j + 1]

            if negative_flow == 0:
                mfi[i] = 100
            else:
                money_ratio = positive_flow / negative_flow
                mfi[i] = 100 - (100 / (1 + money_ratio))

        return mfi

    def update(self, symbol: str) -> bool:
        """
        Update all indicators for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            True if update successful.
        """
        # Need enough bars for longest indicator (EMA 200)
        required_bars = self.ema_trend_period + 100
        rates = self.fetch_candles(symbol, required_bars)

        if rates is None:
            return False

        close_prices = rates['close']

        # Calculate indicators
        ema_trend = self.calculate_ema(close_prices, self.ema_trend_period)
        ema_reversion = self.calculate_ema(close_prices, self.ema_reversion_period)
        rsi = self.calculate_rsi(close_prices, self.rsi_period)
        atr = self.calculate_atr(rates, self.atr_period)

        # Store in cache
        self._cache[symbol] = {
            'rates': rates,
            'close': close_prices,
            'high': rates['high'],
            'low': rates['low'],
            'ema_trend': ema_trend,
            'ema_reversion': ema_reversion,
            'rsi': rsi,
            'atr': atr,
            'last_update': rates[-1]['time']
        }

        return True

    def get_current_values(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current indicator values for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Dictionary with current indicator values.
        """
        if symbol not in self._cache:
            if not self.update(symbol):
                return None

        cache = self._cache[symbol]

        return {
            'close': cache['close'][-1],
            'high': cache['high'][-1],
            'low': cache['low'][-1],
            'prev_close': cache['close'][-2],
            'ema_trend': cache['ema_trend'][-1],
            'ema_reversion': cache['ema_reversion'][-1],
            'rsi': cache['rsi'][-1],
            'prev_rsi': cache['rsi'][-2],
            'atr': cache['atr'][-1],
            'atr_pips': self._atr_to_pips(symbol, cache['atr'][-1])
        }

    def get_previous_values(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get previous bar indicator values for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Dictionary with previous bar indicator values.
        """
        if symbol not in self._cache:
            if not self.update(symbol):
                return None

        cache = self._cache[symbol]

        return {
            'close': cache['close'][-2],
            'high': cache['high'][-2],
            'low': cache['low'][-2],
            'ema_trend': cache['ema_trend'][-2],
            'ema_reversion': cache['ema_reversion'][-2],
            'rsi': cache['rsi'][-2],
            'prev_rsi': cache['rsi'][-3] if len(cache['rsi']) > 2 else 0,
            'atr': cache['atr'][-2]
        }

    def _atr_to_pips(self, symbol: str, atr_value: float) -> float:
        """
        Convert ATR value to pips.

        Args:
            symbol: Trading symbol.
            atr_value: ATR in price terms.

        Returns:
            ATR in pips.
        """
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return 0

        # Determine pip size based on digits
        if symbol_info.digits == 3 or symbol_info.digits == 5:
            pip_size = symbol_info.point * 10
        else:
            pip_size = symbol_info.point

        return atr_value / pip_size if pip_size > 0 else 0

    def get_stop_loss_pips(self, symbol: str) -> float:
        """
        Calculate stop loss distance in pips based on ATR.

        Args:
            symbol: Trading symbol.

        Returns:
            Stop loss distance in pips.
        """
        values = self.get_current_values(symbol)
        if values is None:
            return 0

        atr_pips = values['atr_pips']
        sl_multiplier = STRATEGY_CONFIG['atr_sl_multiplier']

        return atr_pips * sl_multiplier

    def is_new_bar(self, symbol: str) -> bool:
        """
        Check if a new bar has formed.

        Args:
            symbol: Trading symbol.

        Returns:
            True if new bar detected.
        """
        timeframe = self.get_timeframe_constant()
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)

        if rates is None or len(rates) == 0:
            return False

        current_time = rates[0]['time']

        if symbol in self._cache:
            last_time = self._cache[symbol]['last_update']
            if current_time > last_time:
                return True

        return False
