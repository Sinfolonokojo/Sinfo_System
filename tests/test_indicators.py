"""
Unit tests for Indicators Module.

Tests EMA, RSI, and ATR calculations.
"""

import unittest
from unittest.mock import Mock, patch
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.indicators import Indicators
from bot.config import STRATEGY_CONFIG


class TestIndicators(unittest.TestCase):
    """Tests for Indicators class."""

    def setUp(self):
        """Set up test fixtures."""
        self.indicators = Indicators("TEST")

    def test_calculate_ema_basic(self):
        """Test basic EMA calculation."""
        # Simple test data
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        period = 3

        ema = self.indicators.calculate_ema(data, period)

        # First EMA value should be SMA of first 3 values
        expected_first = (1.0 + 2.0 + 3.0) / 3
        self.assertAlmostEqual(ema[2], expected_first, places=5)

        # EMA should be calculated for all values after period
        self.assertGreater(ema[-1], 0)

    def test_calculate_ema_trending_up(self):
        """Test EMA responds to uptrend."""
        # Uptrending data
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0,
                        11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0])
        period = 5

        ema = self.indicators.calculate_ema(data, period)

        # EMA should be increasing
        self.assertLess(ema[10], ema[15])
        self.assertLess(ema[15], ema[19])

    def test_calculate_ema_trending_down(self):
        """Test EMA responds to downtrend."""
        # Downtrending data
        data = np.array([20.0, 19.0, 18.0, 17.0, 16.0, 15.0, 14.0, 13.0, 12.0, 11.0,
                        10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0])
        period = 5

        ema = self.indicators.calculate_ema(data, period)

        # EMA should be decreasing
        self.assertGreater(ema[10], ema[15])
        self.assertGreater(ema[15], ema[19])

    def test_calculate_rsi_oversold(self):
        """Test RSI calculation for oversold condition."""
        # Simulate price drops (5 losses in a row)
        data = np.array([100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90])
        period = 7

        rsi = self.indicators.calculate_rsi(data, period)

        # RSI should be low (oversold territory)
        # After continuous drops, RSI should be 0 or near 0
        self.assertLess(rsi[-1], 30)

    def test_calculate_rsi_overbought(self):
        """Test RSI calculation for overbought condition."""
        # Simulate price rises (continuous gains)
        data = np.array([90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100])
        period = 7

        rsi = self.indicators.calculate_rsi(data, period)

        # RSI should be high (overbought territory)
        # After continuous gains, RSI should be 100 or near 100
        self.assertGreater(rsi[-1], 70)

    def test_calculate_rsi_neutral(self):
        """Test RSI calculation for neutral market."""
        # Oscillating price (equal ups and downs)
        data = np.array([100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100])
        period = 7

        rsi = self.indicators.calculate_rsi(data, period)

        # RSI should be around 50 for neutral market
        self.assertGreater(rsi[-1], 30)
        self.assertLess(rsi[-1], 70)

    def test_calculate_rsi_range(self):
        """Test RSI stays within 0-100 range."""
        # Random data
        np.random.seed(42)
        data = 100 + np.cumsum(np.random.randn(100) * 0.5)
        period = 7

        rsi = self.indicators.calculate_rsi(data, period)

        # All RSI values should be between 0 and 100
        valid_rsi = rsi[period:]  # Skip initial zeros
        self.assertTrue(all(0 <= r <= 100 for r in valid_rsi))

    def test_calculate_atr_basic(self):
        """Test basic ATR calculation."""
        # Create structured numpy array
        dtype = [('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
                 ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
                 ('spread', '<i4'), ('real_volume', '<i8')]

        # Simple data with constant range
        data = []
        for i in range(20):
            data.append((i, 100.0, 102.0, 98.0, 101.0, 1000, 1, 1000))

        rates = np.array(data, dtype=dtype)
        period = 14

        atr = self.indicators.calculate_atr(rates, period)

        # ATR should be close to 4.0 (high - low = 4.0 for all bars)
        self.assertAlmostEqual(atr[-1], 4.0, places=1)

    def test_calculate_atr_increasing_volatility(self):
        """Test ATR increases with volatility."""
        dtype = [('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
                 ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
                 ('spread', '<i4'), ('real_volume', '<i8')]

        data = []
        # Low volatility period
        for i in range(15):
            data.append((i, 100.0, 101.0, 99.0, 100.0, 1000, 1, 1000))
        # High volatility period
        for i in range(15, 30):
            data.append((i, 100.0, 105.0, 95.0, 100.0, 1000, 1, 1000))

        rates = np.array(data, dtype=dtype)
        period = 7

        atr = self.indicators.calculate_atr(rates, period)

        # ATR should be higher at the end (high volatility)
        self.assertGreater(atr[-1], atr[14])

    @patch('bot.indicators.mt5')
    def test_atr_to_pips_5_digit(self, mock_mt5):
        """Test ATR to pips conversion for 5-digit pairs."""
        mock_symbol = Mock()
        mock_symbol.digits = 5
        mock_symbol.point = 0.00001
        mock_mt5.symbol_info.return_value = mock_symbol

        result = self.indicators._atr_to_pips("EURUSD", 0.0015)

        # 0.0015 / 0.0001 = 15 pips
        self.assertAlmostEqual(result, 15.0, places=1)

    @patch('bot.indicators.mt5')
    def test_atr_to_pips_3_digit(self, mock_mt5):
        """Test ATR to pips conversion for 3-digit pairs (JPY)."""
        mock_symbol = Mock()
        mock_symbol.digits = 3
        mock_symbol.point = 0.001
        mock_mt5.symbol_info.return_value = mock_symbol

        result = self.indicators._atr_to_pips("USDJPY", 0.15)

        # 0.15 / 0.01 = 15 pips
        self.assertAlmostEqual(result, 15.0, places=1)

    @patch('bot.indicators.mt5')
    def test_get_timeframe_constant(self, mock_mt5):
        """Test timeframe constant mapping."""
        mock_mt5.TIMEFRAME_M15 = 15

        result = self.indicators.get_timeframe_constant()

        self.assertEqual(result, 15)

    @patch('bot.indicators.mt5')
    def test_update_symbol(self, mock_mt5):
        """Test updating indicators for a symbol."""
        # Create mock rates data
        dtype = [('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
                 ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
                 ('spread', '<i4'), ('real_volume', '<i8')]

        data = []
        for i in range(300):
            price = 1.1000 + 0.0001 * np.sin(i * 0.1)
            data.append((i * 900, price, price + 0.001, price - 0.001, price, 1000, 1, 1000))

        rates = np.array(data, dtype=dtype)
        mock_mt5.copy_rates_from_pos.return_value = rates
        mock_mt5.TIMEFRAME_M15 = 15

        result = self.indicators.update("EURUSD")

        self.assertTrue(result)
        self.assertIn("EURUSD", self.indicators._cache)

    @patch('bot.indicators.mt5')
    def test_get_current_values(self, mock_mt5):
        """Test getting current indicator values."""
        # Set up cache
        self.indicators._cache["EURUSD"] = {
            'rates': None,
            'close': np.array([1.1000, 1.1010, 1.1020]),
            'high': np.array([1.1005, 1.1015, 1.1025]),
            'low': np.array([1.0995, 1.1005, 1.1015]),
            'ema_trend': np.array([1.0990, 1.0995, 1.1000]),
            'ema_reversion': np.array([1.1000, 1.1005, 1.1010]),
            'rsi': np.array([45.0, 50.0, 55.0]),
            'atr': np.array([0.0010, 0.0012, 0.0015]),
            'last_update': 1000
        }

        # Mock symbol info for ATR to pips
        mock_symbol = Mock()
        mock_symbol.digits = 5
        mock_symbol.point = 0.00001
        mock_mt5.symbol_info.return_value = mock_symbol

        values = self.indicators.get_current_values("EURUSD")

        self.assertIsNotNone(values)
        self.assertEqual(values['close'], 1.1020)
        self.assertEqual(values['rsi'], 55.0)
        self.assertEqual(values['prev_rsi'], 50.0)
        self.assertEqual(values['ema_trend'], 1.1000)

    @patch('bot.indicators.mt5')
    def test_get_stop_loss_pips(self, mock_mt5):
        """Test stop loss calculation in pips."""
        # Set up cache with ATR
        self.indicators._cache["EURUSD"] = {
            'rates': None,
            'close': np.array([1.1000]),
            'high': np.array([1.1005]),
            'low': np.array([1.0995]),
            'ema_trend': np.array([1.0990]),
            'ema_reversion': np.array([1.1000]),
            'rsi': np.array([50.0]),
            'atr': np.array([0.0010]),  # 10 pips ATR
            'last_update': 1000
        }

        # Mock symbol info
        mock_symbol = Mock()
        mock_symbol.digits = 5
        mock_symbol.point = 0.00001
        mock_mt5.symbol_info.return_value = mock_symbol

        sl_pips = self.indicators.get_stop_loss_pips("EURUSD")

        # SL = ATR * 1.5 = 10 * 1.5 = 15 pips
        self.assertAlmostEqual(sl_pips, 15.0, places=1)


class TestIndicatorEdgeCases(unittest.TestCase):
    """Test edge cases for indicator calculations."""

    def setUp(self):
        """Set up test fixtures."""
        self.indicators = Indicators("TEST")

    def test_ema_single_period(self):
        """Test EMA with minimum data."""
        data = np.array([1.0, 2.0, 3.0])
        period = 3

        ema = self.indicators.calculate_ema(data, period)

        # Should have at least one valid EMA value
        self.assertGreater(ema[-1], 0)

    def test_rsi_all_gains(self):
        """Test RSI with all gains (should be 100)."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        period = 7

        rsi = self.indicators.calculate_rsi(data, period)

        # RSI should be 100 for continuous gains
        self.assertEqual(rsi[-1], 100)

    def test_rsi_all_losses(self):
        """Test RSI with all losses (should be 0)."""
        data = np.array([10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0])
        period = 7

        rsi = self.indicators.calculate_rsi(data, period)

        # RSI should be 0 for continuous losses
        self.assertEqual(rsi[-1], 0)


if __name__ == '__main__':
    unittest.main()
