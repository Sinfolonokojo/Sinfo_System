"""
Unit tests for Strategy Module.

Tests ElasticBandStrategy signal detection and trade level calculations.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.strategy import ElasticBandStrategy, SignalType
from bot.config import STRATEGY_CONFIG


class TestElasticBandStrategy(unittest.TestCase):
    """Tests for ElasticBandStrategy class."""

    def setUp(self):
        """Set up test fixtures."""
        with patch('bot.strategy.Indicators'):
            self.strategy = ElasticBandStrategy("TEST")

    def test_check_long_signal_valid(self):
        """Test valid LONG signal detection."""
        # Setup: Price > EMA200, Low touches EMA50, RSI hooks up from oversold
        result = self.strategy._check_long_signal(
            close=1.1050,       # Above EMA200
            low=1.1000,         # Touches EMA50 (within tolerance)
            ema_trend=1.1000,   # EMA200
            ema_reversion=1.1000,  # EMA50
            rsi=31.0,           # Current RSI (just crossed above 30)
            prev_rsi=28.0,      # Previous RSI (was oversold)
            tolerance=0.0002    # 2 pip tolerance
        )

        self.assertTrue(result)

    def test_check_long_signal_trend_invalid(self):
        """Test LONG signal rejected when price below EMA200."""
        result = self.strategy._check_long_signal(
            close=1.0950,       # Below EMA200
            low=1.0900,
            ema_trend=1.1000,   # Price below this
            ema_reversion=1.0920,
            rsi=31.0,
            prev_rsi=28.0,
            tolerance=0.0002
        )

        self.assertFalse(result)

    def test_check_long_signal_no_dip(self):
        """Test LONG signal rejected when price doesn't touch EMA50."""
        result = self.strategy._check_long_signal(
            close=1.1100,
            low=1.1080,         # Too far from EMA50
            ema_trend=1.1000,
            ema_reversion=1.1000,  # Low doesn't reach this
            rsi=31.0,
            prev_rsi=28.0,
            tolerance=0.0002
        )

        self.assertFalse(result)

    def test_check_long_signal_rsi_not_oversold(self):
        """Test LONG signal rejected when RSI wasn't oversold."""
        result = self.strategy._check_long_signal(
            close=1.1050,
            low=1.1000,
            ema_trend=1.1000,
            ema_reversion=1.1000,
            rsi=35.0,
            prev_rsi=32.0,      # Was not below 30
            tolerance=0.0002
        )

        self.assertFalse(result)

    def test_check_short_signal_valid(self):
        """Test valid SHORT signal detection."""
        # Setup: Price < EMA200, High touches EMA50, RSI hooks down from overbought
        result = self.strategy._check_short_signal(
            close=1.0950,       # Below EMA200
            high=1.1000,        # Touches EMA50 (within tolerance)
            ema_trend=1.1000,   # EMA200
            ema_reversion=1.1000,  # EMA50
            rsi=69.0,           # Current RSI (just crossed below 70)
            prev_rsi=72.0,      # Previous RSI (was overbought)
            tolerance=0.0002
        )

        self.assertTrue(result)

    def test_check_short_signal_trend_invalid(self):
        """Test SHORT signal rejected when price above EMA200."""
        result = self.strategy._check_short_signal(
            close=1.1050,       # Above EMA200
            high=1.1100,
            ema_trend=1.1000,   # Price above this
            ema_reversion=1.1080,
            rsi=69.0,
            prev_rsi=72.0,
            tolerance=0.0002
        )

        self.assertFalse(result)

    def test_check_short_signal_no_rally(self):
        """Test SHORT signal rejected when price doesn't touch EMA50."""
        result = self.strategy._check_short_signal(
            close=1.0900,
            high=1.0920,        # Too far from EMA50
            ema_trend=1.1000,
            ema_reversion=1.1000,  # High doesn't reach this
            rsi=69.0,
            prev_rsi=72.0,
            tolerance=0.0002
        )

        self.assertFalse(result)

    def test_check_short_signal_rsi_not_overbought(self):
        """Test SHORT signal rejected when RSI wasn't overbought."""
        result = self.strategy._check_short_signal(
            close=1.0950,
            high=1.1000,
            ema_trend=1.1000,
            ema_reversion=1.1000,
            rsi=65.0,
            prev_rsi=68.0,      # Was not above 70
            tolerance=0.0002
        )

        self.assertFalse(result)

    @patch('bot.strategy.mt5')
    def test_pips_to_price_5_digit(self, mock_mt5):
        """Test pip to price conversion for 5-digit pairs."""
        mock_symbol = Mock()
        mock_symbol.digits = 5
        mock_symbol.point = 0.00001
        mock_mt5.symbol_info.return_value = mock_symbol

        result = self.strategy._pips_to_price("EURUSD", 10)

        # 10 pips * 0.0001 = 0.0010
        self.assertAlmostEqual(result, 0.0010, places=5)

    @patch('bot.strategy.mt5')
    def test_pips_to_price_3_digit(self, mock_mt5):
        """Test pip to price conversion for 3-digit pairs (JPY)."""
        mock_symbol = Mock()
        mock_symbol.digits = 3
        mock_symbol.point = 0.001
        mock_mt5.symbol_info.return_value = mock_symbol

        result = self.strategy._pips_to_price("USDJPY", 10)

        # 10 pips * 0.01 = 0.10
        self.assertAlmostEqual(result, 0.10, places=3)

    @patch('bot.strategy.mt5')
    def test_check_signal_with_mock_indicators(self, mock_mt5):
        """Test check_signal with mocked indicator values."""
        # Mock indicator values for a LONG signal
        mock_values = {
            'close': 1.1050,
            'high': 1.1060,
            'low': 1.1000,
            'ema_trend': 1.1000,
            'ema_reversion': 1.1000,
            'rsi': 31.0,
            'prev_rsi': 28.0
        }

        self.strategy.indicators.get_current_values = Mock(return_value=mock_values)

        # Mock symbol info for pip tolerance
        mock_symbol = Mock()
        mock_symbol.digits = 5
        mock_symbol.point = 0.00001
        mock_mt5.symbol_info.return_value = mock_symbol

        signal = self.strategy.check_signal("EURUSD")

        self.assertEqual(signal, SignalType.BUY)

    @patch('bot.strategy.mt5')
    def test_check_signal_no_signal(self, mock_mt5):
        """Test check_signal when no signal conditions met."""
        # Mock indicator values with no signal
        mock_values = {
            'close': 1.1025,    # Middle of range
            'high': 1.1030,
            'low': 1.1020,
            'ema_trend': 1.1000,
            'ema_reversion': 1.1000,
            'rsi': 50.0,        # Neutral RSI
            'prev_rsi': 50.0
        }

        self.strategy.indicators.get_current_values = Mock(return_value=mock_values)

        mock_symbol = Mock()
        mock_symbol.digits = 5
        mock_symbol.point = 0.00001
        mock_mt5.symbol_info.return_value = mock_symbol

        signal = self.strategy.check_signal("EURUSD")

        self.assertEqual(signal, SignalType.NONE)

    @patch('bot.strategy.mt5')
    def test_calculate_trade_levels_buy(self, mock_mt5):
        """Test trade level calculation for BUY signal."""
        # Mock tick
        mock_tick = Mock()
        mock_tick.ask = 1.1050
        mock_tick.bid = 1.1048
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # Mock symbol info
        mock_symbol = Mock()
        mock_symbol.digits = 5
        mock_mt5.symbol_info.return_value = mock_symbol

        # Mock ATR pips
        self.strategy.indicators.get_stop_loss_pips = Mock(return_value=15.0)

        levels = self.strategy.calculate_trade_levels("EURUSD", SignalType.BUY)

        self.assertIsNotNone(levels)
        self.assertEqual(levels['entry'], 1.1050)
        self.assertLess(levels['sl'], levels['entry'])  # SL below entry for BUY
        self.assertGreater(levels['tp'], levels['entry'])  # TP above entry for BUY
        self.assertEqual(levels['sl_pips'], 15.0)

    @patch('bot.strategy.mt5')
    def test_calculate_trade_levels_sell(self, mock_mt5):
        """Test trade level calculation for SELL signal."""
        # Mock tick
        mock_tick = Mock()
        mock_tick.ask = 1.1050
        mock_tick.bid = 1.1048
        mock_mt5.symbol_info_tick.return_value = mock_tick

        # Mock symbol info
        mock_symbol = Mock()
        mock_symbol.digits = 5
        mock_mt5.symbol_info.return_value = mock_symbol

        # Mock ATR pips
        self.strategy.indicators.get_stop_loss_pips = Mock(return_value=15.0)

        levels = self.strategy.calculate_trade_levels("EURUSD", SignalType.SELL)

        self.assertIsNotNone(levels)
        self.assertEqual(levels['entry'], 1.1048)
        self.assertGreater(levels['sl'], levels['entry'])  # SL above entry for SELL
        self.assertLess(levels['tp'], levels['entry'])  # TP below entry for SELL

    def test_calculate_trade_levels_none_signal(self):
        """Test trade level calculation returns None for NONE signal."""
        levels = self.strategy.calculate_trade_levels("EURUSD", SignalType.NONE)

        self.assertIsNone(levels)


class TestSignalType(unittest.TestCase):
    """Tests for SignalType enum."""

    def test_signal_types_exist(self):
        """Test that all signal types are defined."""
        self.assertEqual(SignalType.NONE.value, 0)
        self.assertEqual(SignalType.BUY.value, 1)
        self.assertEqual(SignalType.SELL.value, 2)


if __name__ == '__main__':
    unittest.main()
