"""
Master Node - Signal Generator for trade copying.

Monitors master account positions and broadcasts changes via ZeroMQ.
"""

import sys
import time
import argparse
import MetaTrader5 as mt5
from typing import Dict, Set

import config
from messaging import Publisher
from utils import setup_logger


class MasterNode:
    """
    Master node that monitors positions and publishes trade signals.

    Detects new positions (OPEN) and closed positions (CLOSE) by
    comparing current state against an in-memory cache.
    """

    def __init__(self, name: str, terminal_path: str):
        """
        Initialize the master node.

        Args:
            name: Account identifier.
            terminal_path: Path to terminal64.exe.
        """
        self.name = name
        self.terminal_path = terminal_path
        self.logger = setup_logger(f"MASTER:{name}")
        self.publisher = Publisher()

        # In-memory cache of known open tickets
        self._ticket_cache: Dict[int, dict] = {}
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

    def get_current_positions(self) -> Dict[int, dict]:
        """
        Get all current open positions.

        Returns:
            Dictionary mapping ticket ID to position data.
        """
        positions = mt5.positions_get()
        if positions is None:
            return {}

        return {
            pos.ticket: {
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': pos.type,
                'volume': pos.volume,
                'price': pos.price_open,
                'sl': pos.sl,
                'tp': pos.tp,
                'time': pos.time
            }
            for pos in positions
        }

    def detect_changes(self, current: Dict[int, dict]) -> tuple:
        """
        Detect opened and closed positions.

        Args:
            current: Current positions from MT5.

        Returns:
            Tuple of (opened_tickets, closed_tickets).
        """
        current_tickets = set(current.keys())
        cached_tickets = set(self._ticket_cache.keys())

        opened = current_tickets - cached_tickets
        closed = cached_tickets - current_tickets

        return opened, closed

    def publish_open_signal(self, position: dict):
        """
        Publish an OPEN signal for a new position.

        Args:
            position: Position data dictionary.
        """
        self.publisher.publish_open(
            ticket=position['ticket'],
            symbol=position['symbol'],
            order_type=position['type'],
            volume=position['volume'],
            price=position['price'],
            sl=position['sl'],
            tp=position['tp']
        )
        direction = "BUY" if position['type'] == 0 else "SELL"
        self.logger.info(
            f"OPEN Signal | Ticket: {position['ticket']} | "
            f"{direction} {position['volume']} {position['symbol']} @ {position['price']}"
        )

    def publish_close_signal(self, ticket: int):
        """
        Publish a CLOSE signal for a closed position.

        Args:
            ticket: The closed ticket ID.
        """
        position = self._ticket_cache.get(ticket, {})
        symbol = position.get('symbol', 'UNKNOWN')

        self.publisher.publish_close(ticket=ticket, symbol=symbol)
        self.logger.info(f"CLOSE Signal | Ticket: {ticket} | Symbol: {symbol}")

    def run(self):
        """Main loop to monitor positions and publish signals."""
        if not self.initialize_mt5():
            return

        self.publisher.start()
        self.logger.info(f"Publisher started on {config.ZMQ_PUB_ADDRESS}")

        # Initial cache population
        self._ticket_cache = self.get_current_positions()
        self.logger.info(f"Initial positions loaded: {len(self._ticket_cache)}")

        self._running = True
        poll_interval = config.MASTER_POLL_INTERVAL_MS / 1000.0

        try:
            while self._running:
                current_positions = self.get_current_positions()
                opened, closed = self.detect_changes(current_positions)

                # Process opened positions
                for ticket in opened:
                    position = current_positions[ticket]
                    self.publish_open_signal(position)
                    self._ticket_cache[ticket] = position

                # Process closed positions
                for ticket in closed:
                    self.publish_close_signal(ticket)
                    del self._ticket_cache[ticket]

                time.sleep(poll_interval)

        except KeyboardInterrupt:
            self.logger.info("Shutdown requested")
        finally:
            self.stop()

    def stop(self):
        """Stop the master node and cleanup resources."""
        self._running = False
        self.publisher.stop()
        mt5.shutdown()
        self.logger.info("Master node stopped")


def main():
    """Entry point for master node process."""
    parser = argparse.ArgumentParser(description='Master Node - Signal Generator')
    parser.add_argument('--name', required=True, help='Account name identifier')
    parser.add_argument('--path', required=True, help='Path to terminal64.exe')
    args = parser.parse_args()

    node = MasterNode(name=args.name, terminal_path=args.path)
    node.run()


if __name__ == '__main__':
    main()
