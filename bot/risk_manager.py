"""
Risk Management Module - The Circuit Breaker.

This module operates independently of trading strategy and acts as a safeguard
to prevent account breaches. Risk management is the primary driver.
"""

import time
from datetime import datetime, timedelta
from typing import Optional

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
from bot.config import get_active_config, STRATEGY_CONFIG


class DailyLossGuard:
    """
    Daily Loss Guard - Monitors and enforces daily loss limits.

    Calculates equity at Server Time 00:00 and constantly monitors
    floating P/L to prevent breaching the daily loss limit.
    """

    def __init__(self, account_name: str):
        self.logger = setup_logger(f"DLG:{account_name}")
        self.daily_start_equity: float = 0.0
        self.daily_limit: float = 0.0
        self.last_reset_date: Optional[datetime] = None
        self.trading_disabled: bool = False
        self.disabled_until: Optional[datetime] = None

    def reset_daily_equity(self):
        """Reset daily equity snapshot at 00:00 server time."""
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("Failed to get account info for daily reset")
            return

        self.daily_start_equity = account_info.equity
        config = get_active_config()
        self.daily_limit = self.daily_start_equity * (config.daily_loss_buffer / 100)
        self.last_reset_date = datetime.now().date()
        self.trading_disabled = False
        self.disabled_until = None

        self.logger.info(
            f"Daily Reset | Start Equity: {self.daily_start_equity:.2f} | "
            f"Loss Limit: {self.daily_limit:.2f} ({config.daily_loss_buffer}%)"
        )

    def check_new_day(self):
        """Check if it's a new trading day and reset if needed."""
        current_date = datetime.now().date()
        if self.last_reset_date is None or current_date > self.last_reset_date:
            self.reset_daily_equity()

    def check_daily_limit(self) -> bool:
        """
        Check if daily loss limit has been reached.

        Returns:
            True if safe to trade, False if limit reached.
        """
        # Check for new day first
        self.check_new_day()

        # Check if trading is disabled
        if self.trading_disabled:
            if self.disabled_until and datetime.now() >= self.disabled_until:
                self.logger.info("Trading re-enabled after daily reset")
                self.trading_disabled = False
            else:
                return False

        # Get current equity
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("Failed to get account info")
            return False

        current_equity = account_info.equity
        current_loss = self.daily_start_equity - current_equity

        # Check if limit breached
        if current_loss >= self.daily_limit:
            self.logger.critical(
                f"DAILY LIMIT REACHED | Loss: {current_loss:.2f} | "
                f"Limit: {self.daily_limit:.2f}"
            )
            self._trigger_circuit_breaker()
            return False

        # Log warning if approaching limit
        if current_loss >= self.daily_limit * 0.8:
            self.logger.warning(
                f"Approaching daily limit | Loss: {current_loss:.2f} / {self.daily_limit:.2f} "
                f"({(current_loss/self.daily_limit*100):.1f}%)"
            )

        return True

    def _trigger_circuit_breaker(self):
        """Close all positions and disable trading."""
        self.logger.critical("CIRCUIT BREAKER TRIGGERED - Closing all positions")

        # Close all open positions
        positions = mt5.positions_get()
        if positions:
            for pos in positions:
                self._close_position(pos)

        # Disable trading until next day
        self.trading_disabled = True
        tomorrow = datetime.now().date() + timedelta(days=1)
        self.disabled_until = datetime.combine(tomorrow, datetime.min.time())

        self.logger.critical(
            f"Trading DISABLED until {self.disabled_until.strftime('%Y-%m-%d %H:%M')}"
        )

    def _close_position(self, position):
        """Close a single position."""
        symbol = position.symbol
        ticket = position.ticket
        volume = position.volume

        # Determine close type
        if position.type == mt5.POSITION_TYPE_BUY:
            close_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            close_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask

        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': close_type,
            'position': ticket,
            'price': price,
            'deviation': 20,
            'magic': 0,
            'comment': 'DLG:Emergency Close',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.info(f"Emergency closed position {ticket}")
        else:
            self.logger.error(f"Failed to close position {ticket}")

    def is_trading_enabled(self) -> bool:
        """Check if trading is currently enabled."""
        return not self.trading_disabled


class PositionSizer:
    """
    Dynamic Position Sizing - Risk of Ruin Protection.

    Calculates lot size based on stop loss distance and account equity
    to ensure consistent risk per trade.
    """

    def __init__(self, account_name: str):
        self.logger = setup_logger(f"SIZER:{account_name}")

    def calculate_lot_size(
        self,
        symbol: str,
        stop_loss_pips: float,
        risk_percentage: float
    ) -> Optional[float]:
        """
        Calculate position size based on risk parameters.

        Formula: LotSize = (Equity * Risk%) / (SL_Pips * Pip_Value)

        Args:
            symbol: Trading symbol.
            stop_loss_pips: Stop loss distance in pips.
            risk_percentage: Percentage of equity to risk.

        Returns:
            Calculated lot size, or None if invalid.
        """
        # Get account info
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("Failed to get account info")
            return None

        equity = account_info.equity
        free_margin = account_info.margin_free

        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Failed to get symbol info for {symbol}")
            return None

        # Calculate pip value
        # For most pairs: pip_value = contract_size * pip_size
        contract_size = symbol_info.trade_contract_size

        # Determine pip size based on digits
        if symbol_info.digits == 3 or symbol_info.digits == 5:
            pip_size = symbol_info.point * 10
        else:
            pip_size = symbol_info.point

        # Get tick value (value of 1 point movement for 1 lot)
        tick_value = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size

        # Calculate pip value for 1 lot
        pip_value = (pip_size / tick_size) * tick_value

        # Calculate risk amount
        risk_amount = equity * (risk_percentage / 100)

        # Calculate lot size
        if stop_loss_pips <= 0 or pip_value <= 0:
            self.logger.error(f"Invalid SL or pip value: SL={stop_loss_pips}, PV={pip_value}")
            return None

        lot_size = risk_amount / (stop_loss_pips * pip_value)

        # Apply symbol constraints
        min_lot = symbol_info.volume_min
        max_lot = symbol_info.volume_max
        lot_step = symbol_info.volume_step

        # Round to lot step
        lot_size = round(lot_size / lot_step) * lot_step

        # Constrain to min/max
        if lot_size < min_lot:
            self.logger.warning(f"Lot size {lot_size} below minimum {min_lot}")
            return None

        if lot_size > max_lot:
            self.logger.warning(f"Lot size {lot_size} exceeds maximum {max_lot}, capping")
            lot_size = max_lot

        # Check margin requirement
        margin_required = self._calculate_margin(symbol, lot_size)
        if margin_required and margin_required > free_margin:
            self.logger.warning(
                f"Insufficient margin | Required: {margin_required:.2f} | "
                f"Free: {free_margin:.2f}"
            )
            return None

        self.logger.info(
            f"Position Size | {symbol} | Risk: {risk_amount:.2f} | "
            f"SL: {stop_loss_pips} pips | Lots: {lot_size:.2f}"
        )

        return lot_size

    def _calculate_margin(self, symbol: str, lot_size: float) -> Optional[float]:
        """Calculate margin required for a position."""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return None

        # Use MT5's margin calculation
        margin = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY,
            symbol,
            lot_size,
            symbol_info.ask
        )
        return margin


class TiltProtection:
    """
    Tilt Protection - Consecutive Loss Breaker.

    Prevents the bot from fighting strong trends by pausing
    after consecutive losses.
    """

    def __init__(self, account_name: str):
        self.logger = setup_logger(f"TILT:{account_name}")
        self.consecutive_losses: int = 0
        self.paused_until: Optional[datetime] = None
        self.max_losses = STRATEGY_CONFIG['max_consecutive_losses']
        self.pause_hours = STRATEGY_CONFIG['tilt_pause_hours']

    def record_trade_result(self, is_win: bool):
        """
        Record a trade result.

        Args:
            is_win: True if trade was profitable.
        """
        if is_win:
            if self.consecutive_losses > 0:
                self.logger.info(f"Win recorded, resetting loss counter from {self.consecutive_losses}")
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.logger.warning(f"Loss recorded | Consecutive losses: {self.consecutive_losses}")

            if self.consecutive_losses >= self.max_losses:
                self._trigger_pause()

    def _trigger_pause(self):
        """Pause trading due to consecutive losses."""
        self.paused_until = datetime.now() + timedelta(hours=self.pause_hours)
        self.logger.warning(
            f"TILT PROTECTION | {self.consecutive_losses} consecutive losses | "
            f"Paused until {self.paused_until.strftime('%H:%M')}"
        )

    def is_trading_allowed(self) -> bool:
        """
        Check if trading is allowed.

        Returns:
            True if not paused, False if in tilt pause.
        """
        if self.paused_until is None:
            return True

        if datetime.now() >= self.paused_until:
            self.logger.info("Tilt pause ended, trading resumed")
            self.paused_until = None
            self.consecutive_losses = 0
            return True

        return False

    def get_pause_remaining(self) -> Optional[timedelta]:
        """Get remaining pause duration."""
        if self.paused_until is None:
            return None
        remaining = self.paused_until - datetime.now()
        return remaining if remaining.total_seconds() > 0 else None


class RiskManager:
    """
    Main Risk Manager - Combines all risk controls.

    Acts as the circuit breaker wrapping all trading logic.
    """

    def __init__(self, account_name: str):
        self.account_name = account_name
        self.logger = setup_logger(f"RISK:{account_name}")

        self.daily_guard = DailyLossGuard(account_name)
        self.position_sizer = PositionSizer(account_name)
        self.tilt_protection = TiltProtection(account_name)

    def can_trade(self) -> bool:
        """
        Check all risk conditions before allowing a trade.

        Returns:
            True if all risk checks pass.
        """
        # Check daily loss limit
        if not self.daily_guard.check_daily_limit():
            return False

        # Check tilt protection
        if not self.tilt_protection.is_trading_allowed():
            pause_remaining = self.tilt_protection.get_pause_remaining()
            if pause_remaining:
                self.logger.debug(f"Tilt pause: {pause_remaining.seconds // 60} minutes remaining")
            return False

        return True

    def calculate_position_size(
        self,
        symbol: str,
        stop_loss_pips: float
    ) -> Optional[float]:
        """
        Calculate position size with current risk parameters.

        Args:
            symbol: Trading symbol.
            stop_loss_pips: Stop loss distance in pips.

        Returns:
            Lot size or None if trade should be aborted.
        """
        from bot.config import get_risk_percentage
        risk_pct = get_risk_percentage()

        return self.position_sizer.calculate_lot_size(
            symbol,
            stop_loss_pips,
            risk_pct
        )

    def record_trade_result(self, profit: float):
        """
        Record a closed trade result.

        Args:
            profit: Trade profit/loss amount.
        """
        is_win = profit > 0
        self.tilt_protection.record_trade_result(is_win)

    def initialize(self):
        """Initialize risk manager at startup."""
        self.daily_guard.reset_daily_equity()
        self.logger.info("Risk Manager initialized")

    def get_status(self) -> dict:
        """Get current risk manager status."""
        account_info = mt5.account_info()
        current_equity = account_info.equity if account_info else 0

        return {
            'trading_enabled': self.daily_guard.is_trading_enabled(),
            'tilt_paused': not self.tilt_protection.is_trading_allowed(),
            'consecutive_losses': self.tilt_protection.consecutive_losses,
            'daily_start_equity': self.daily_guard.daily_start_equity,
            'current_equity': current_equity,
            'daily_loss': self.daily_guard.daily_start_equity - current_equity,
            'daily_limit': self.daily_guard.daily_limit
        }
