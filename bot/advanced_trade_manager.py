"""
Advanced Trade Management Module.

Implements advanced exit strategies:
- Trailing stops
- Partial exits
- Breakeven management
"""

from datetime import datetime
from typing import Optional, Dict, Any
import MetaTrader5 as mt5

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.config import STRATEGY_CONFIG
from bot.strategy import SignalType


class AdvancedTradeManager:
    """
    Advanced trade management with trailing stops and partial exits.

    Features:
    - Move SL to breakeven after 0.5R profit
    - Partial exit: Close 50% at 1R, let 50% run to 2R
    - Trailing stop: Lock in profits as trade moves favorably
    """

    def __init__(self, account_name: str):
        self.account_name = account_name
        self.logger = setup_logger(f"ADV_TM:{account_name}")

        # Advanced management settings
        self.enable_breakeven = STRATEGY_CONFIG.get('enable_breakeven', True)
        self.breakeven_trigger_r = STRATEGY_CONFIG.get('breakeven_trigger_r', 0.5)  # 0.5R

        self.enable_partial_exits = STRATEGY_CONFIG.get('enable_partial_exits', False)
        self.partial_exit_r = STRATEGY_CONFIG.get('partial_exit_r', 1.0)  # 1R
        self.partial_exit_percent = STRATEGY_CONFIG.get('partial_exit_percent', 0.5)  # 50%

        self.enable_trailing_stop = STRATEGY_CONFIG.get('enable_trailing_stop', False)
        self.trailing_start_r = STRATEGY_CONFIG.get('trailing_start_r', 1.0)  # Start at 1R
        self.trailing_distance_r = STRATEGY_CONFIG.get('trailing_distance_r', 0.5)  # Trail by 0.5R

        # Track which trades have been managed
        self.breakeven_set: set = set()
        self.partial_exited: set = set()

    def manage_trade(
        self,
        ticket: int,
        symbol: str,
        direction: SignalType,
        entry_price: float,
        current_price: float,
        sl: float,
        tp: float,
        sl_distance_pips: float
    ) -> Dict[str, Any]:
        """
        Apply advanced management to a trade.

        Args:
            ticket: Trade ticket.
            symbol: Trading symbol.
            direction: BUY or SELL.
            entry_price: Entry price.
            current_price: Current market price.
            sl: Current stop loss.
            tp: Take profit.
            sl_distance_pips: Original SL distance in pips.

        Returns:
            Dictionary with actions taken.
        """
        actions = {
            'breakeven_set': False,
            'partial_exit': False,
            'trailing_adjusted': False
        }

        # Calculate R (risk amount) in pips
        pip_size = self._get_pip_size(symbol)
        if pip_size == 0:
            return actions

        sl_distance_price = abs(entry_price - sl)
        r_value = sl_distance_price  # 1R = original SL distance

        # Calculate current profit in R
        if direction == SignalType.BUY:
            profit_price = current_price - entry_price
        else:  # SELL
            profit_price = entry_price - current_price

        profit_r = profit_price / r_value if r_value > 0 else 0

        # 1. Breakeven Management
        if self.enable_breakeven and ticket not in self.breakeven_set:
            if profit_r >= self.breakeven_trigger_r:
                if self._move_sl_to_breakeven(ticket, symbol, entry_price, tp):
                    self.breakeven_set.add(ticket)
                    actions['breakeven_set'] = True
                    self.logger.info(
                        f"Breakeven set | {symbol} | Ticket: {ticket} | "
                        f"Profit: {profit_r:.2f}R"
                    )

        # 2. Partial Exits
        if self.enable_partial_exits and ticket not in self.partial_exited:
            if profit_r >= self.partial_exit_r:
                if self._partial_close(ticket, symbol, self.partial_exit_percent):
                    self.partial_exited.add(ticket)
                    actions['partial_exit'] = True
                    self.logger.info(
                        f"Partial exit | {symbol} | Ticket: {ticket} | "
                        f"Closed: {self.partial_exit_percent*100:.0f}% at {profit_r:.2f}R"
                    )

        # 3. Trailing Stop
        if self.enable_trailing_stop and ticket in self.breakeven_set:
            if profit_r >= self.trailing_start_r:
                new_sl = self._calculate_trailing_sl(
                    direction,
                    entry_price,
                    current_price,
                    sl,
                    r_value
                )
                if new_sl and new_sl != sl:
                    if self._modify_sl(ticket, symbol, new_sl, tp):
                        actions['trailing_adjusted'] = True
                        self.logger.info(
                            f"Trailing stop adjusted | {symbol} | Ticket: {ticket} | "
                            f"New SL: {new_sl:.5f}"
                        )

        return actions

    def _move_sl_to_breakeven(
        self,
        ticket: int,
        symbol: str,
        entry_price: float,
        tp: float
    ) -> bool:
        """Move stop loss to breakeven (entry price)."""
        request = {
            'action': mt5.TRADE_ACTION_SLTP,
            'symbol': symbol,
            'position': ticket,
            'sl': entry_price,
            'tp': tp
        }

        result = mt5.order_send(request)
        return result and result.retcode == mt5.TRADE_RETCODE_DONE

    def _partial_close(
        self,
        ticket: int,
        symbol: str,
        close_percent: float
    ) -> bool:
        """
        Close a percentage of the position.

        Args:
            ticket: Trade ticket.
            symbol: Trading symbol.
            close_percent: Percentage to close (0.0 - 1.0).

        Returns:
            True if successful.
        """
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False

        pos = positions[0]
        close_volume = round(pos.volume * close_percent, 2)

        # Minimum volume check
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info and close_volume < symbol_info.volume_min:
            self.logger.warning(f"Partial close volume too small: {close_volume}")
            return False

        # Determine close order type
        if pos.type == mt5.POSITION_TYPE_BUY:
            close_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            close_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask

        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': close_volume,
            'type': close_type,
            'position': ticket,
            'price': price,
            'deviation': 20,
            'comment': f'PartialExit:{self.account_name}',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC
        }

        result = mt5.order_send(request)
        return result and result.retcode == mt5.TRADE_RETCODE_DONE

    def _calculate_trailing_sl(
        self,
        direction: SignalType,
        entry_price: float,
        current_price: float,
        current_sl: float,
        r_value: float
    ) -> Optional[float]:
        """
        Calculate new trailing stop loss.

        Args:
            direction: BUY or SELL.
            entry_price: Entry price.
            current_price: Current market price.
            current_sl: Current stop loss.
            r_value: 1R value (original SL distance).

        Returns:
            New SL price, or None if no change.
        """
        trailing_distance = r_value * self.trailing_distance_r

        if direction == SignalType.BUY:
            # For longs, trail below current price
            new_sl = current_price - trailing_distance
            # Only move SL up, never down
            if new_sl > current_sl:
                return new_sl
        else:  # SELL
            # For shorts, trail above current price
            new_sl = current_price + trailing_distance
            # Only move SL down, never up
            if new_sl < current_sl:
                return new_sl

        return None

    def _modify_sl(
        self,
        ticket: int,
        symbol: str,
        new_sl: float,
        tp: float
    ) -> bool:
        """Modify stop loss for a position."""
        request = {
            'action': mt5.TRADE_ACTION_SLTP,
            'symbol': symbol,
            'position': ticket,
            'sl': new_sl,
            'tp': tp
        }

        result = mt5.order_send(request)
        return result and result.retcode == mt5.TRADE_RETCODE_DONE

    def _get_pip_size(self, symbol: str) -> float:
        """Get pip size for a symbol."""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return 0

        if symbol_info.digits == 3 or symbol_info.digits == 5:
            return symbol_info.point * 10
        else:
            return symbol_info.point

    def reset_tracking(self, ticket: int):
        """Reset tracking for a closed trade."""
        self.breakeven_set.discard(ticket)
        self.partial_exited.discard(ticket)

    def get_status(self) -> Dict[str, Any]:
        """Get current status of advanced management."""
        return {
            'breakeven_enabled': self.enable_breakeven,
            'partial_exits_enabled': self.enable_partial_exits,
            'trailing_stop_enabled': self.enable_trailing_stop,
            'trades_at_breakeven': len(self.breakeven_set),
            'trades_partially_exited': len(self.partial_exited)
        }
