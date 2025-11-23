"""
Unit tests for Risk Management Module.

Tests DailyLossGuard, PositionSizer, TiltProtection, and RiskManager.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.risk_manager import (
    DailyLossGuard,
    PositionSizer,
    TiltProtection,
    RiskManager
)
from bot.config import STRATEGY_CONFIG


class TestDailyLossGuard(unittest.TestCase):
    """Tests for DailyLossGuard class."""

    def setUp(self):
        """Set up test fixtures."""
        self.guard = DailyLossGuard("TEST")

    @patch('bot.risk_manager.mt5')
    def test_reset_daily_equity(self, mock_mt5):
        """Test daily equity reset."""
        # Mock account info
        mock_account = Mock()
        mock_account.equity = 10000.0
        mock_mt5.account_info.return_value = mock_account

        self.guard.reset_daily_equity()

        self.assertEqual(self.guard.daily_start_equity, 10000.0)
        self.assertEqual(self.guard.daily_limit, 450.0)  # 4.5% of 10000
        self.assertFalse(self.guard.trading_disabled)

    @patch('bot.risk_manager.mt5')
    def test_check_daily_limit_safe(self, mock_mt5):
        """Test daily limit check when safe to trade."""
        # Set up initial equity
        self.guard.daily_start_equity = 10000.0
        self.guard.daily_limit = 450.0
        self.guard.last_reset_date = datetime.now().date()

        # Mock current equity (only lost 200)
        mock_account = Mock()
        mock_account.equity = 9800.0
        mock_mt5.account_info.return_value = mock_account

        result = self.guard.check_daily_limit()

        self.assertTrue(result)
        self.assertFalse(self.guard.trading_disabled)

    @patch('bot.risk_manager.mt5')
    def test_check_daily_limit_breached(self, mock_mt5):
        """Test daily limit check when limit is breached."""
        # Set up initial equity
        self.guard.daily_start_equity = 10000.0
        self.guard.daily_limit = 450.0
        self.guard.last_reset_date = datetime.now().date()

        # Mock current equity (lost 500 - exceeds 450 limit)
        mock_account = Mock()
        mock_account.equity = 9500.0
        mock_mt5.account_info.return_value = mock_account

        # Mock positions_get for circuit breaker
        mock_mt5.positions_get.return_value = []

        result = self.guard.check_daily_limit()

        self.assertFalse(result)
        self.assertTrue(self.guard.trading_disabled)

    @patch('bot.risk_manager.mt5')
    def test_check_new_day_reset(self, mock_mt5):
        """Test automatic reset on new day."""
        # Set last reset to yesterday
        self.guard.last_reset_date = datetime.now().date() - timedelta(days=1)

        # Mock account info for reset
        mock_account = Mock()
        mock_account.equity = 10500.0
        mock_mt5.account_info.return_value = mock_account

        self.guard.check_new_day()

        self.assertEqual(self.guard.daily_start_equity, 10500.0)
        self.assertEqual(self.guard.last_reset_date, datetime.now().date())

    def test_is_trading_enabled(self):
        """Test trading enabled status."""
        self.guard.trading_disabled = False
        self.assertTrue(self.guard.is_trading_enabled())

        self.guard.trading_disabled = True
        self.assertFalse(self.guard.is_trading_enabled())


class TestPositionSizer(unittest.TestCase):
    """Tests for PositionSizer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.sizer = PositionSizer("TEST")

    @patch('bot.risk_manager.mt5')
    def test_calculate_lot_size_basic(self, mock_mt5):
        """Test basic lot size calculation."""
        # Mock account info
        mock_account = Mock()
        mock_account.equity = 10000.0
        mock_account.margin_free = 5000.0
        mock_mt5.account_info.return_value = mock_account

        # Mock symbol info
        mock_symbol = Mock()
        mock_symbol.trade_contract_size = 100000
        mock_symbol.digits = 5
        mock_symbol.point = 0.00001
        mock_symbol.trade_tick_value = 1.0
        mock_symbol.trade_tick_size = 0.00001
        mock_symbol.volume_min = 0.01
        mock_symbol.volume_max = 100.0
        mock_symbol.volume_step = 0.01
        mock_mt5.symbol_info.return_value = mock_symbol

        # Mock margin calculation
        mock_mt5.order_calc_margin.return_value = 100.0

        # Calculate lot size for 1% risk with 20 pip SL
        lot_size = self.sizer.calculate_lot_size("EURUSD", 20.0, 1.0)

        # Risk amount = 10000 * 0.01 = 100
        # Pip value for 1 lot = (0.0001 / 0.00001) * 1.0 = 10
        # Lot size = 100 / (20 * 10) = 0.5
        self.assertIsNotNone(lot_size)
        self.assertEqual(lot_size, 0.5)

    @patch('bot.risk_manager.mt5')
    def test_calculate_lot_size_below_minimum(self, mock_mt5):
        """Test lot size calculation when result is below minimum."""
        # Mock account info (small account)
        mock_account = Mock()
        mock_account.equity = 100.0
        mock_account.margin_free = 50.0
        mock_mt5.account_info.return_value = mock_account

        # Mock symbol info
        mock_symbol = Mock()
        mock_symbol.trade_contract_size = 100000
        mock_symbol.digits = 5
        mock_symbol.point = 0.00001
        mock_symbol.trade_tick_value = 1.0
        mock_symbol.trade_tick_size = 0.00001
        mock_symbol.volume_min = 0.01
        mock_symbol.volume_max = 100.0
        mock_symbol.volume_step = 0.01
        mock_mt5.symbol_info.return_value = mock_symbol

        # Calculate lot size - should return None as below minimum
        lot_size = self.sizer.calculate_lot_size("EURUSD", 50.0, 1.0)

        self.assertIsNone(lot_size)

    @patch('bot.risk_manager.mt5')
    def test_calculate_lot_size_insufficient_margin(self, mock_mt5):
        """Test lot size calculation with insufficient margin."""
        # Mock account info
        mock_account = Mock()
        mock_account.equity = 10000.0
        mock_account.margin_free = 10.0  # Very low margin
        mock_mt5.account_info.return_value = mock_account

        # Mock symbol info
        mock_symbol = Mock()
        mock_symbol.trade_contract_size = 100000
        mock_symbol.digits = 5
        mock_symbol.point = 0.00001
        mock_symbol.trade_tick_value = 1.0
        mock_symbol.trade_tick_size = 0.00001
        mock_symbol.volume_min = 0.01
        mock_symbol.volume_max = 100.0
        mock_symbol.volume_step = 0.01
        mock_mt5.symbol_info.return_value = mock_symbol

        # Mock margin calculation (requires more than available)
        mock_mt5.order_calc_margin.return_value = 1000.0

        lot_size = self.sizer.calculate_lot_size("EURUSD", 20.0, 1.0)

        self.assertIsNone(lot_size)


class TestTiltProtection(unittest.TestCase):
    """Tests for TiltProtection class."""

    def setUp(self):
        """Set up test fixtures."""
        self.tilt = TiltProtection("TEST")

    def test_record_win_resets_counter(self):
        """Test that a win resets the consecutive loss counter."""
        self.tilt.consecutive_losses = 2

        self.tilt.record_trade_result(is_win=True)

        self.assertEqual(self.tilt.consecutive_losses, 0)
        self.assertTrue(self.tilt.is_trading_allowed())

    def test_record_loss_increments_counter(self):
        """Test that a loss increments the counter."""
        self.tilt.record_trade_result(is_win=False)

        self.assertEqual(self.tilt.consecutive_losses, 1)
        self.assertTrue(self.tilt.is_trading_allowed())

    def test_consecutive_losses_trigger_pause(self):
        """Test that 3 consecutive losses trigger a pause."""
        self.tilt.record_trade_result(is_win=False)
        self.tilt.record_trade_result(is_win=False)
        self.tilt.record_trade_result(is_win=False)

        self.assertEqual(self.tilt.consecutive_losses, 3)
        self.assertFalse(self.tilt.is_trading_allowed())
        self.assertIsNotNone(self.tilt.paused_until)

    def test_pause_expires(self):
        """Test that pause expires after duration."""
        # Trigger pause
        self.tilt.consecutive_losses = 3
        self.tilt.paused_until = datetime.now() - timedelta(hours=1)

        self.assertTrue(self.tilt.is_trading_allowed())
        self.assertIsNone(self.tilt.paused_until)
        self.assertEqual(self.tilt.consecutive_losses, 0)

    def test_get_pause_remaining(self):
        """Test getting remaining pause duration."""
        # No pause
        self.assertIsNone(self.tilt.get_pause_remaining())

        # Active pause
        self.tilt.paused_until = datetime.now() + timedelta(hours=2)
        remaining = self.tilt.get_pause_remaining()
        self.assertIsNotNone(remaining)
        self.assertGreater(remaining.total_seconds(), 0)


class TestRiskManager(unittest.TestCase):
    """Tests for RiskManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.rm = RiskManager("TEST")

    @patch('bot.risk_manager.mt5')
    def test_can_trade_all_checks_pass(self, mock_mt5):
        """Test can_trade when all checks pass."""
        # Set up daily guard
        self.rm.daily_guard.daily_start_equity = 10000.0
        self.rm.daily_guard.daily_limit = 450.0
        self.rm.daily_guard.last_reset_date = datetime.now().date()

        # Mock account info (safe equity)
        mock_account = Mock()
        mock_account.equity = 9800.0
        mock_mt5.account_info.return_value = mock_account

        result = self.rm.can_trade()

        self.assertTrue(result)

    @patch('bot.risk_manager.mt5')
    def test_can_trade_daily_limit_breached(self, mock_mt5):
        """Test can_trade when daily limit is breached."""
        # Set up daily guard
        self.rm.daily_guard.daily_start_equity = 10000.0
        self.rm.daily_guard.daily_limit = 450.0
        self.rm.daily_guard.last_reset_date = datetime.now().date()

        # Mock account info (breached)
        mock_account = Mock()
        mock_account.equity = 9500.0
        mock_mt5.account_info.return_value = mock_account

        # Mock positions_get for circuit breaker
        mock_mt5.positions_get.return_value = []

        result = self.rm.can_trade()

        self.assertFalse(result)

    @patch('bot.risk_manager.mt5')
    def test_can_trade_tilt_paused(self, mock_mt5):
        """Test can_trade when tilt protection is active."""
        # Set up daily guard
        self.rm.daily_guard.daily_start_equity = 10000.0
        self.rm.daily_guard.daily_limit = 450.0
        self.rm.daily_guard.last_reset_date = datetime.now().date()

        # Mock account info (safe)
        mock_account = Mock()
        mock_account.equity = 9800.0
        mock_mt5.account_info.return_value = mock_account

        # Trigger tilt pause
        self.rm.tilt_protection.paused_until = datetime.now() + timedelta(hours=4)

        result = self.rm.can_trade()

        self.assertFalse(result)

    def test_record_trade_result(self):
        """Test recording trade results."""
        # Record a loss
        self.rm.record_trade_result(-50.0)
        self.assertEqual(self.rm.tilt_protection.consecutive_losses, 1)

        # Record a win
        self.rm.record_trade_result(100.0)
        self.assertEqual(self.rm.tilt_protection.consecutive_losses, 0)

    @patch('bot.risk_manager.mt5')
    def test_get_status(self, mock_mt5):
        """Test getting risk manager status."""
        # Mock account info
        mock_account = Mock()
        mock_account.equity = 9800.0
        mock_mt5.account_info.return_value = mock_account

        # Set up state
        self.rm.daily_guard.daily_start_equity = 10000.0
        self.rm.daily_guard.daily_limit = 450.0

        status = self.rm.get_status()

        self.assertIn('trading_enabled', status)
        self.assertIn('tilt_paused', status)
        self.assertIn('daily_start_equity', status)
        self.assertIn('current_equity', status)
        self.assertIn('daily_loss', status)
        self.assertEqual(status['daily_loss'], 200.0)


if __name__ == '__main__':
    unittest.main()
