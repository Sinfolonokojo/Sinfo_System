"""
Main Bot Entry Point - The Elastic Band Trading Bot.

Implements the OnTick/OnBar event loop for the prop firm trading system.
"""

import time
import signal
import argparse
from datetime import datetime
from typing import Dict
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
from bot.config import (
    STRATEGY_CONFIG,
    get_active_config,
    ACTIVE_PHASE
)
from bot.risk_manager import RiskManager
from bot.strategy import ElasticBandStrategy, SignalType
from bot.news_filter import NewsFilter
from bot.trader import Trader


class ElasticBandBot:
    """
    Main trading bot orchestrator.

    Implements the data flow:
    OnTick -> Check Guards
    OnBar -> Check Signals -> Execute Trades
    """

    def __init__(self, account_id: int, password: str, server: str, account_name: str = "DEFAULT"):
        self.account_id = account_id
        self.password = password
        self.server = server
        self.account_name = account_name
        self.logger = setup_logger(f"BOT:{account_name}")

        # Components
        self.risk_manager = RiskManager(account_name)
        self.strategy = ElasticBandStrategy(account_name)
        self.news_filter = NewsFilter(account_name)
        self.trader = Trader(account_name)

        # State
        self.running = False
        self.symbols = STRATEGY_CONFIG['symbols']
        self.last_bar_time: Dict[str, int] = {}

        # Performance tracking
        self.trades_today = 0
        self.wins_today = 0
        self.losses_today = 0

    def initialize(self) -> bool:
        """
        Initialize MT5 connection and components.

        Returns:
            True if initialization successful.
        """
        # Initialize MT5
        if not mt5.initialize():
            self.logger.error(f"MT5 initialize failed: {mt5.last_error()}")
            return False

        # Login to account
        if not mt5.login(self.account_id, password=self.password, server=self.server):
            self.logger.error(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        # Get account info
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("Failed to get account info")
            mt5.shutdown()
            return False

        self.logger.info(
            f"Connected to MT5 | Account: {account_info.login} | "
            f"Balance: {account_info.balance:.2f} | "
            f"Server: {account_info.server}"
        )

        # Initialize symbols
        for symbol in self.symbols:
            if not mt5.symbol_select(symbol, True):
                self.logger.warning(f"Failed to select symbol {symbol}")
                self.symbols.remove(symbol)

        if not self.symbols:
            self.logger.error("No valid symbols available")
            mt5.shutdown()
            return False

        # Initialize components
        self.risk_manager.initialize()
        self.news_filter.fetch_calendar()
        self.trader.sync_open_trades()

        # Log configuration
        config = get_active_config()
        self.logger.info(
            f"Phase: {config.name} | Risk/Trade: {config.risk_per_trade_min}-{config.risk_per_trade_max}% | "
            f"Daily Limit: {config.daily_loss_buffer}%"
        )

        return True

    def run(self):
        """Main bot loop."""
        self.running = True
        self.logger.info("Bot started - entering main loop")

        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        tick_interval = 1  # seconds
        last_status_log = datetime.now()
        status_log_interval = 300  # 5 minutes

        try:
            while self.running:
                # OnTick - Check guards on every tick
                self._on_tick()

                # OnBar - Check signals when new bar forms
                self._on_bar()

                # Periodic status log
                if (datetime.now() - last_status_log).seconds >= status_log_interval:
                    self._log_status()
                    last_status_log = datetime.now()

                time.sleep(tick_interval)

        except Exception as e:
            self.logger.error(f"Bot error: {e}")
            raise
        finally:
            self.shutdown()

    def _on_tick(self):
        """
        OnTick event - Run on every tick.

        Checks:
        - Risk guards (daily loss, tilt)
        - Time-based exits for open trades
        """
        # Check risk guards
        if not self.risk_manager.can_trade():
            return

        # Check time exits for open trades
        profits = self.trader.check_time_exits()
        for profit in profits:
            self._record_trade_result(profit)

    def _on_bar(self):
        """
        OnBar event - Run when new bar forms.

        Checks:
        - News filter
        - Entry signals
        - Executes trades
        """
        for symbol in self.symbols:
            # Check if new bar
            if not self._is_new_bar(symbol):
                continue

            self.logger.debug(f"New bar detected for {symbol}")

            # Update indicators
            if not self.strategy.update_indicators(symbol):
                continue

            # Check if we can trade
            if not self._can_trade_symbol(symbol):
                continue

            # Check for signals
            signal = self.strategy.check_signal(symbol)

            if signal != SignalType.NONE:
                self._execute_signal(symbol, signal)

    def _is_new_bar(self, symbol: str) -> bool:
        """Check if a new bar has formed for a symbol."""
        timeframe = self.strategy.indicators.get_timeframe_constant()
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)

        if rates is None or len(rates) == 0:
            return False

        current_bar_time = rates[0]['time']

        if symbol not in self.last_bar_time:
            self.last_bar_time[symbol] = current_bar_time
            return True

        if current_bar_time > self.last_bar_time[symbol]:
            self.last_bar_time[symbol] = current_bar_time
            return True

        return False

    def _can_trade_symbol(self, symbol: str) -> bool:
        """
        Check all conditions before trading a symbol.

        Returns:
            True if all checks pass.
        """
        # Check risk manager
        if not self.risk_manager.can_trade():
            return False

        # Check news filter
        if not self.news_filter.can_trade(symbol):
            return False

        # Check if already have position for this symbol
        if self.trader.has_open_trade(symbol):
            self.logger.debug(f"Already have position for {symbol}")
            return False

        return True

    def _execute_signal(self, symbol: str, signal: SignalType):
        """
        Execute a trading signal.

        Args:
            symbol: Trading symbol.
            signal: BUY or SELL signal.
        """
        # Calculate trade levels
        levels = self.strategy.calculate_trade_levels(symbol, signal)
        if levels is None:
            self.logger.warning(f"Failed to calculate trade levels for {symbol}")
            return

        # Calculate position size
        lot_size = self.risk_manager.calculate_position_size(
            symbol,
            levels['sl_pips']
        )

        if lot_size is None:
            self.logger.warning(f"Position sizing failed for {symbol}")
            return

        # Send order
        ticket = self.trader.send_order(
            symbol=symbol,
            signal=signal,
            volume=lot_size,
            entry=levels['entry'],
            sl=levels['sl'],
            tp=levels['tp']
        )

        if ticket:
            self.trades_today += 1
            self.logger.info(
                f"TRADE EXECUTED | {symbol} | Ticket: {ticket} | "
                f"Lots: {lot_size} | SL: {levels['sl_pips']:.1f} pips"
            )

    def _record_trade_result(self, profit: float):
        """Record a trade result for tracking."""
        self.risk_manager.record_trade_result(profit)

        if profit > 0:
            self.wins_today += 1
        else:
            self.losses_today += 1

        self.logger.info(
            f"Trade closed | Profit: {profit:.2f} | "
            f"Today: {self.wins_today}W / {self.losses_today}L"
        )

    def _log_status(self):
        """Log current bot status."""
        risk_status = self.risk_manager.get_status()
        trader_status = self.trader.get_status()

        self.logger.info(
            f"STATUS | Equity: {risk_status['current_equity']:.2f} | "
            f"Daily Loss: {risk_status['daily_loss']:.2f}/{risk_status['daily_limit']:.2f} | "
            f"Open: {trader_status['open_trades']} | "
            f"Today: {self.trades_today} trades ({self.wins_today}W/{self.losses_today}L)"
        )

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info("Shutdown signal received")
        self.running = False

    def shutdown(self):
        """Clean shutdown of the bot."""
        self.logger.info("Shutting down bot...")

        # Optionally close all positions on shutdown
        # self.trader.close_all_positions("SHUTDOWN")

        mt5.shutdown()
        self.logger.info("Bot shutdown complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Elastic Band Trading Bot")
    parser.add_argument("--account", type=int, required=True, help="MT5 account number")
    parser.add_argument("--password", type=str, required=True, help="MT5 password")
    parser.add_argument("--server", type=str, required=True, help="MT5 server name")
    parser.add_argument("--name", type=str, default="DEFAULT", help="Account name for logging")

    args = parser.parse_args()

    # Create and run bot
    bot = ElasticBandBot(
        account_id=args.account,
        password=args.password,
        server=args.server,
        account_name=args.name
    )

    if bot.initialize():
        bot.run()
    else:
        print("Bot initialization failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
