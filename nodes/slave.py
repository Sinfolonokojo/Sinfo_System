"""
Slave Node - Execution Engine for trade copying.

Receives signals via ZeroMQ and executes trades on prop firm accounts.
"""

import sys
import time
import argparse
import MetaTrader5 as mt5
from typing import Optional, Dict, Any

import config
from messaging import Subscriber
from db import AccountModel, TradeModel
from utils import setup_logger, SymbolTranslator


class SlaveNode:
    """
    Slave node that receives signals and executes trades.

    Handles symbol translation, slippage protection, and trade lifecycle.
    """

    def __init__(self, name: str, terminal_path: str):
        """
        Initialize the slave node.

        Args:
            name: Account identifier.
            terminal_path: Path to terminal64.exe.
        """
        self.name = name
        self.terminal_path = terminal_path
        self.logger = setup_logger(f"SLAVE:{name}")
        self.subscriber = Subscriber()

        # Load account configuration
        self.account_config = AccountModel.get_by_name(name)
        if not self.account_config:
            raise ValueError(f"Account '{name}' not found in database")

        # Initialize symbol translator
        symbol_map = self.account_config.get('symbol_map', {})
        suffix = self.account_config.get('suffix', '')
        self.translator = SymbolTranslator(symbol_map, suffix)

        # Slippage tolerance in points
        self.slippage_tolerance = self.account_config.get(
            'slippage_tolerance',
            config.DEFAULT_SLIPPAGE_TOLERANCE
        )

        self._running = False

    def initialize_mt5(self) -> bool:
        """
        Initialize MetaTrader 5 connection.

        Returns:
            True if initialization successful.
        """
        if not mt5.initialize(path=self.terminal_path):
            error = mt5.last_error()
            self.logger.error(f"MT5 initialization failed: {error}")
            return False

        account_info = mt5.account_info()
        if account_info:
            self.logger.info(
                f"Connected to account {account_info.login} | "
                f"Balance: {account_info.balance} | "
                f"Server: {account_info.server}"
            )
        return True

    def check_slippage(self, symbol: str, master_price: float, order_type: int) -> bool:
        """
        Check if current price is within slippage tolerance.

        Args:
            symbol: Translated symbol for this broker.
            master_price: Price from master signal.
            order_type: 0 for BUY, 1 for SELL.

        Returns:
            True if slippage is acceptable.
        """
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self.logger.error(f"Failed to get tick for {symbol}")
            return False

        # Use Ask for BUY, Bid for SELL
        current_price = tick.ask if order_type == 0 else tick.bid

        # Get symbol info for point value
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Symbol info not found for {symbol}")
            return False

        # Calculate slippage in points
        price_diff = abs(current_price - master_price)
        slippage_points = price_diff / symbol_info.point

        if slippage_points > self.slippage_tolerance:
            self.logger.warning(
                f"Slippage exceeded | Symbol: {symbol} | "
                f"Master: {master_price} | Current: {current_price} | "
                f"Slippage: {slippage_points:.1f} points > {self.slippage_tolerance}"
            )
            return False

        return True

    def execute_open(self, signal: Dict[str, Any]) -> Optional[int]:
        """
        Execute an OPEN trade.

        Args:
            signal: Trade signal from master.

        Returns:
            Slave ticket ID if successful, None otherwise.
        """
        master_symbol = signal['symbol']
        slave_symbol = self.translator.translate(master_symbol)
        order_type = signal['type']
        volume = signal['volume']
        master_price = signal['price']
        sl = signal['sl']
        tp = signal['tp']

        # Ensure symbol is available
        if not mt5.symbol_select(slave_symbol, True):
            self.logger.error(f"Failed to select symbol {slave_symbol}")
            return None

        # Check slippage
        if not self.check_slippage(slave_symbol, master_price, order_type):
            return None

        # Get current price for execution
        tick = mt5.symbol_info_tick(slave_symbol)
        price = tick.ask if order_type == 0 else tick.bid

        # Determine order type constant
        mt5_order_type = mt5.ORDER_TYPE_BUY if order_type == 0 else mt5.ORDER_TYPE_SELL

        # Build trade request
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': slave_symbol,
            'volume': volume,
            'type': mt5_order_type,
            'price': price,
            'sl': sl,
            'tp': tp,
            'deviation': self.slippage_tolerance,
            'magic': config.DEFAULT_MAGIC_NUMBER,
            'comment': f'Copy:{signal["ticket"]}',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC
        }

        # Execute trade
        result = mt5.order_send(request)

        if result is None:
            self.logger.error(f"Order send failed - no result returned")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(
                f"Order failed | Code: {result.retcode} | "
                f"Comment: {result.comment}"
            )
            return None

        # Log success
        direction = "BUY" if order_type == 0 else "SELL"
        self.logger.info(
            f"EXECUTED | Ticket: {result.order} | "
            f"{direction} {volume} {slave_symbol} @ {result.price}"
        )

        # Store mapping in database
        TradeModel.create_mapping(
            master_ticket=signal['ticket'],
            slave_ticket=result.order,
            slave_name=self.name,
            symbol=slave_symbol,
            direction=direction
        )

        return result.order

    def execute_close(self, signal: Dict[str, Any]) -> bool:
        """
        Execute a CLOSE trade.

        Args:
            signal: Close signal from master.

        Returns:
            True if successful.
        """
        master_ticket = signal['ticket']

        # Get slave ticket from database
        slave_ticket = TradeModel.get_slave_ticket(master_ticket, self.name)
        if slave_ticket is None:
            self.logger.warning(
                f"No mapping found for master ticket {master_ticket}"
            )
            return False

        # Get position details
        position = mt5.positions_get(ticket=slave_ticket)
        if not position:
            self.logger.warning(f"Position {slave_ticket} not found")
            TradeModel.close_trade(master_ticket, self.name)
            return False

        position = position[0]
        symbol = position.symbol
        volume = position.volume

        # Determine close order type (opposite of position)
        if position.type == mt5.POSITION_TYPE_BUY:
            close_type = mt5.ORDER_TYPE_SELL
            tick = mt5.symbol_info_tick(symbol)
            price = tick.bid
        else:
            close_type = mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            price = tick.ask

        # Build close request
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': close_type,
            'position': slave_ticket,
            'price': price,
            'deviation': self.slippage_tolerance,
            'magic': config.DEFAULT_MAGIC_NUMBER,
            'comment': f'Close:{master_ticket}',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC
        }

        # Execute close
        result = mt5.order_send(request)

        if result is None:
            self.logger.error(f"Close order failed - no result returned")
            return False

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(
                f"Close failed | Code: {result.retcode} | "
                f"Comment: {result.comment}"
            )
            return False

        self.logger.info(
            f"CLOSED | Ticket: {slave_ticket} | "
            f"{symbol} @ {result.price}"
        )

        # Update database
        TradeModel.close_trade(master_ticket, self.name)

        return True

    def process_signal(self, signal: Dict[str, Any]):
        """
        Process a received trade signal.

        Args:
            signal: Signal dictionary with action and trade data.
        """
        action = signal.get('action')

        if action == 'OPEN':
            self.execute_open(signal)
        elif action == 'CLOSE':
            self.execute_close(signal)
        else:
            self.logger.warning(f"Unknown action: {action}")

    def run(self):
        """Main loop to receive and process signals."""
        if not self.initialize_mt5():
            return

        self.subscriber.start()
        self.logger.info(f"Subscribed to {config.ZMQ_PUB_ADDRESS}")

        self._running = True
        reconnect_delay = config.SLAVE_RECONNECT_DELAY_S

        try:
            while self._running:
                # Check MT5 connection
                if not mt5.terminal_info():
                    self.logger.warning("MT5 disconnected, attempting reconnect...")
                    time.sleep(reconnect_delay)
                    if not self.initialize_mt5():
                        continue

                # Receive and process signal
                signal = self.subscriber.receive()
                if signal:
                    self.process_signal(signal)

        except KeyboardInterrupt:
            self.logger.info("Shutdown requested")
        finally:
            self.stop()

    def stop(self):
        """Stop the slave node and cleanup resources."""
        self._running = False
        self.subscriber.stop()
        mt5.shutdown()
        self.logger.info("Slave node stopped")


def main():
    """Entry point for slave node process."""
    parser = argparse.ArgumentParser(description='Slave Node - Execution Engine')
    parser.add_argument('--name', required=True, help='Account name identifier')
    parser.add_argument('--path', required=True, help='Path to terminal64.exe')
    args = parser.parse_args()

    node = SlaveNode(name=args.name, terminal_path=args.path)
    node.run()


if __name__ == '__main__':
    main()
