"""
Trader Module - Order Execution and Trade Management.

Handles sending orders to MT5 and monitoring open trades for exits.
"""

from datetime import datetime, timedelta
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
from bot.strategy import SignalType


class Trade:
    """Represents an open trade being monitored."""

    def __init__(
        self,
        ticket: int,
        symbol: str,
        direction: SignalType,
        entry_price: float,
        sl: float,
        tp: float,
        volume: float,
        open_time: datetime
    ):
        self.ticket = ticket
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.sl = sl
        self.tp = tp
        self.volume = volume
        self.open_time = open_time

    def get_duration_minutes(self) -> int:
        """Get trade duration in minutes."""
        return int((datetime.now() - self.open_time).total_seconds() / 60)


class Trader:
    """
    Trader - Order Execution and Trade Management.

    Handles:
    - Sending market orders with SL/TP
    - Monitoring open positions
    - Time-based exit management
    - Trade result recording
    """

    def __init__(self, account_name: str, magic_number: int = 12345):
        self.account_name = account_name
        self.logger = setup_logger(f"TRADE:{account_name}")
        self.magic_number = magic_number

        # Track open trades
        self.open_trades: Dict[int, Trade] = {}

        # Time exit configuration
        self.max_duration = STRATEGY_CONFIG['max_trade_duration_minutes']

    def send_order(
        self,
        symbol: str,
        signal: SignalType,
        volume: float,
        entry: float,
        sl: float,
        tp: float
    ) -> Optional[int]:
        """
        Send a market order to MT5.

        Args:
            symbol: Trading symbol.
            signal: BUY or SELL.
            volume: Lot size.
            entry: Entry price (for reference).
            sl: Stop loss price.
            tp: Take profit price.

        Returns:
            Ticket number if successful, None otherwise.
        """
        # Determine order type
        if signal == SignalType.BUY:
            order_type = mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            price = tick.ask if tick else entry
        else:
            order_type = mt5.ORDER_TYPE_SELL
            tick = mt5.symbol_info_tick(symbol)
            price = tick.bid if tick else entry

        # Build order request
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': order_type,
            'price': price,
            'sl': sl,
            'tp': tp,
            'deviation': 20,
            'magic': self.magic_number,
            'comment': f'ElasticBand:{self.account_name}',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC
        }

        # Send order
        result = mt5.order_send(request)

        if result is None:
            error = mt5.last_error()
            self.logger.error(f"Order send failed: {error}")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(
                f"Order rejected | Code: {result.retcode} | "
                f"Comment: {result.comment}"
            )
            return None

        # Log successful order
        ticket = result.order
        direction = "BUY" if signal == SignalType.BUY else "SELL"
        self.logger.info(
            f"ORDER FILLED | {direction} {volume} {symbol} | "
            f"Ticket: {ticket} | Entry: {result.price:.5f} | "
            f"SL: {sl:.5f} | TP: {tp:.5f}"
        )

        # Track the trade
        trade = Trade(
            ticket=ticket,
            symbol=symbol,
            direction=signal,
            entry_price=result.price,
            sl=sl,
            tp=tp,
            volume=volume,
            open_time=datetime.now()
        )
        self.open_trades[ticket] = trade

        return ticket

    def check_time_exits(self) -> List[float]:
        """
        Check open trades for time-based exits.

        Returns:
            List of profits from closed trades.
        """
        profits = []
        tickets_to_remove = []

        # Get current positions
        positions = mt5.positions_get(magic=self.magic_number)
        if positions is None:
            positions = []

        position_tickets = {pos.ticket for pos in positions}

        for ticket, trade in self.open_trades.items():
            # Check if position still exists
            if ticket not in position_tickets:
                # Position was closed (by SL/TP)
                profit = self._get_closed_trade_profit(ticket)
                profits.append(profit)
                tickets_to_remove.append(ticket)
                continue

            # Check time exit condition
            duration = trade.get_duration_minutes()
            if duration >= self.max_duration:
                # Get current profit
                for pos in positions:
                    if pos.ticket == ticket:
                        if pos.profit > 0:
                            # Profitable and exceeded time - close it
                            profit = self._close_position(pos, "TIME_EXIT")
                            if profit is not None:
                                profits.append(profit)
                                tickets_to_remove.append(ticket)
                            self.logger.info(
                                f"TIME EXIT | {trade.symbol} | "
                                f"Duration: {duration}min | Profit: {profit:.2f}"
                            )
                        else:
                            # Not profitable but exceeded time - let SL/TP handle it
                            self.logger.debug(
                                f"Time exceeded but not profitable | {trade.symbol} | "
                                f"Duration: {duration}min | P/L: {pos.profit:.2f}"
                            )
                        break

        # Clean up closed trades
        for ticket in tickets_to_remove:
            del self.open_trades[ticket]

        return profits

    def _close_position(self, position, reason: str = "") -> Optional[float]:
        """
        Close a position.

        Args:
            position: MT5 position object.
            reason: Reason for closing.

        Returns:
            Profit/loss of closed trade.
        """
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
            'magic': self.magic_number,
            'comment': f'{reason}:{self.account_name}',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC
        }

        result = mt5.order_send(request)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            profit = position.profit
            self.logger.info(f"Position {ticket} closed | Profit: {profit:.2f}")
            return profit
        else:
            self.logger.error(f"Failed to close position {ticket}")
            return None

    def _get_closed_trade_profit(self, ticket: int) -> float:
        """
        Get profit from a closed trade using history.

        Args:
            ticket: Trade ticket number.

        Returns:
            Profit/loss amount.
        """
        # Look in history for the deal
        from_date = datetime.now() - timedelta(days=1)
        to_date = datetime.now() + timedelta(days=1)

        deals = mt5.history_deals_get(from_date, to_date, group="*")
        if deals is None:
            return 0.0

        profit = 0.0
        for deal in deals:
            if deal.position_id == ticket and deal.entry == mt5.DEAL_ENTRY_OUT:
                profit = deal.profit
                break

        return profit

    def sync_open_trades(self):
        """
        Synchronize open trades with MT5 positions.

        Called at startup to recover any existing positions.
        """
        positions = mt5.positions_get(magic=self.magic_number)
        if positions is None:
            return

        for pos in positions:
            if pos.ticket not in self.open_trades:
                # Recover trade from position
                direction = SignalType.BUY if pos.type == mt5.POSITION_TYPE_BUY else SignalType.SELL
                trade = Trade(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    direction=direction,
                    entry_price=pos.price_open,
                    sl=pos.sl,
                    tp=pos.tp,
                    volume=pos.volume,
                    open_time=datetime.fromtimestamp(pos.time)
                )
                self.open_trades[pos.ticket] = trade
                self.logger.info(
                    f"Recovered trade | {pos.symbol} | Ticket: {pos.ticket} | "
                    f"Entry: {pos.price_open:.5f}"
                )

    def get_open_trade_count(self, symbol: str = None) -> int:
        """
        Get count of open trades.

        Args:
            symbol: Optional symbol filter.

        Returns:
            Number of open trades.
        """
        if symbol:
            return sum(1 for t in self.open_trades.values() if t.symbol == symbol)
        return len(self.open_trades)

    def has_open_trade(self, symbol: str) -> bool:
        """
        Check if there's an open trade for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            True if symbol has open trade.
        """
        return any(t.symbol == symbol for t in self.open_trades.values())

    def close_all_positions(self, reason: str = "MANUAL"):
        """
        Close all open positions.

        Args:
            reason: Reason for closing.
        """
        positions = mt5.positions_get(magic=self.magic_number)
        if positions is None:
            return

        for pos in positions:
            self._close_position(pos, reason)

        self.open_trades.clear()
        self.logger.info(f"All positions closed | Reason: {reason}")

    def get_status(self) -> Dict[str, Any]:
        """Get current trader status."""
        return {
            'open_trades': len(self.open_trades),
            'trades': [
                {
                    'ticket': t.ticket,
                    'symbol': t.symbol,
                    'direction': 'BUY' if t.direction == SignalType.BUY else 'SELL',
                    'entry': t.entry_price,
                    'duration_min': t.get_duration_minutes()
                }
                for t in self.open_trades.values()
            ]
        }

    def modify_sl_to_breakeven(self, ticket: int) -> bool:
        """
        Move stop loss to breakeven for a trade.

        Args:
            ticket: Trade ticket.

        Returns:
            True if modification successful.
        """
        if ticket not in self.open_trades:
            return False

        trade = self.open_trades[ticket]
        positions = mt5.positions_get(ticket=ticket)

        if not positions:
            return False

        pos = positions[0]

        # Only if in profit
        if pos.profit <= 0:
            return False

        # Modify SL to entry price
        request = {
            'action': mt5.TRADE_ACTION_SLTP,
            'symbol': trade.symbol,
            'position': ticket,
            'sl': trade.entry_price,
            'tp': trade.tp
        }

        result = mt5.order_send(request)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.info(f"Moved SL to breakeven | Ticket: {ticket}")
            return True

        return False
