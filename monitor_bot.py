"""
Real-Time Bot Monitoring Dashboard.

Displays live performance metrics while the bot is running.
Run this in a separate terminal window alongside the bot.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None


class BotMonitor:
    """Real-time monitoring dashboard for the trading bot."""

    def __init__(self):
        self.symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
        self.start_time = datetime.now()
        self.start_balance = 0
        self.start_equity = 0

    def initialize(self):
        """Initialize MT5 connection."""
        if not MT5_AVAILABLE:
            print("ERROR: MetaTrader5 not installed")
            return False

        if not mt5.initialize():
            print("ERROR: MT5 initialization failed")
            print("Make sure MetaTrader 5 is running")
            return False

        account_info = mt5.account_info()
        if account_info:
            self.start_balance = account_info.balance
            self.start_equity = account_info.equity

        return True

    def get_account_stats(self) -> Dict:
        """Get current account statistics."""
        account_info = mt5.account_info()
        if account_info is None:
            return None

        return {
            'balance': account_info.balance,
            'equity': account_info.equity,
            'margin': account_info.margin,
            'free_margin': account_info.margin_free,
            'margin_level': account_info.margin_level if account_info.margin > 0 else 0,
            'profit': account_info.profit
        }

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        positions = mt5.positions_get()
        if positions is None:
            return []

        return [
            {
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': 'BUY' if pos.type == 0 else 'SELL',
                'volume': pos.volume,
                'open_price': pos.price_open,
                'current_price': pos.price_current,
                'sl': pos.sl,
                'tp': pos.tp,
                'profit': pos.profit,
                'swap': pos.swap,
                'time': datetime.fromtimestamp(pos.time)
            }
            for pos in positions
        ]

    def get_today_deals(self) -> List[Dict]:
        """Get deals from today."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        deals = mt5.history_deals_get(today, datetime.now())
        if deals is None:
            return []

        closed_deals = []
        for deal in deals:
            if deal.entry == 1:  # Exit deal (closed position)
                closed_deals.append({
                    'ticket': deal.ticket,
                    'symbol': deal.symbol,
                    'type': 'BUY' if deal.type == 0 else 'SELL',
                    'volume': deal.volume,
                    'price': deal.price,
                    'profit': deal.profit,
                    'time': datetime.fromtimestamp(deal.time)
                })

        return closed_deals

    def calculate_daily_stats(self, deals: List[Dict]) -> Dict:
        """Calculate daily statistics from closed deals."""
        if not deals:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'gross_profit': 0,
                'gross_loss': 0,
                'net_profit': 0,
                'profit_factor': 0
            }

        winning_trades = [d for d in deals if d['profit'] > 0]
        losing_trades = [d for d in deals if d['profit'] < 0]

        gross_profit = sum(d['profit'] for d in winning_trades)
        gross_loss = abs(sum(d['profit'] for d in losing_trades))
        net_profit = sum(d['profit'] for d in deals)

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        return {
            'total_trades': len(deals),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': (len(winning_trades) / len(deals) * 100) if deals else 0,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'net_profit': net_profit,
            'profit_factor': profit_factor
        }

    def clear_screen(self):
        """Clear terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def display_dashboard(self):
        """Display real-time dashboard."""
        self.clear_screen()

        # Get data
        account = self.get_account_stats()
        positions = self.get_open_positions()
        deals = self.get_today_deals()
        daily_stats = self.calculate_daily_stats(deals)

        if account is None:
            print("ERROR: Could not retrieve account data")
            return

        # Calculate performance
        balance_change = account['balance'] - self.start_balance
        balance_change_pct = (balance_change / self.start_balance * 100) if self.start_balance > 0 else 0

        equity_change = account['equity'] - self.start_equity
        equity_change_pct = (equity_change / self.start_equity * 100) if self.start_equity > 0 else 0

        # Display header
        print("\n" + "="*80)
        print("  ELASTIC BAND BOT - LIVE MONITORING DASHBOARD")
        print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("="*80)

        # Account Overview
        print("\n┌─ ACCOUNT OVERVIEW " + "─"*59)
        print(f"│ Balance:      ${account['balance']:,.2f}  ({balance_change:+.2f} / {balance_change_pct:+.2f}%)")
        print(f"│ Equity:       ${account['equity']:,.2f}  ({equity_change:+.2f} / {equity_change_pct:+.2f}%)")
        print(f"│ Free Margin:  ${account['free_margin']:,.2f}")
        print(f"│ Margin Level: {account['margin_level']:.2f}%")
        print(f"│ Floating P&L: ${account['profit']:+,.2f}")
        print("└" + "─"*79)

        # Daily Performance
        print("\n┌─ TODAY'S PERFORMANCE " + "─"*56)
        print(f"│ Closed Trades:    {daily_stats['total_trades']}")
        print(f"│ Winning Trades:   {daily_stats['winning_trades']}")
        print(f"│ Losing Trades:    {daily_stats['losing_trades']}")
        print(f"│ Win Rate:         {daily_stats['win_rate']:.1f}%")
        print(f"│ Gross Profit:     ${daily_stats['gross_profit']:+,.2f}")
        print(f"│ Gross Loss:       ${daily_stats['gross_loss']:,.2f}")
        print(f"│ Net Profit:       ${daily_stats['net_profit']:+,.2f}")
        print(f"│ Profit Factor:    {daily_stats['profit_factor']:.2f}")

        # Daily DD check
        daily_dd_pct = (daily_stats['net_profit'] / self.start_balance * 100) if self.start_balance > 0 else 0
        if daily_dd_pct < 0:
            print(f"│ Daily Drawdown:   {abs(daily_dd_pct):.2f}%", end="")
            if abs(daily_dd_pct) > 4.0:
                print(" ⚠ WARNING: Approaching limit!")
            else:
                print()
        print("└" + "─"*79)

        # Open Positions
        print("\n┌─ OPEN POSITIONS " + "─"*61)
        if positions:
            print(f"│ {'Symbol':<8} {'Type':<4} {'Volume':<8} {'Entry':<10} {'Current':<10} {'P&L':<12}")
            print("├" + "─"*79)
            for pos in positions:
                pnl_str = f"${pos['profit']:+,.2f}"
                print(f"│ {pos['symbol']:<8} {pos['type']:<4} {pos['volume']:<8.2f} "
                      f"{pos['open_price']:<10.5f} {pos['current_price']:<10.5f} {pnl_str:<12}")
        else:
            print("│ No open positions")
        print("└" + "─"*79)

        # Recent Trades
        print("\n┌─ RECENT CLOSED TRADES (Last 5) " + "─"*45)
        if deals:
            recent_deals = sorted(deals, key=lambda x: x['time'], reverse=True)[:5]
            print(f"│ {'Time':<8} {'Symbol':<8} {'Type':<4} {'Volume':<8} {'Price':<10} {'P&L':<12}")
            print("├" + "─"*79)
            for deal in recent_deals:
                time_str = deal['time'].strftime("%H:%M:%S")
                pnl_str = f"${deal['profit']:+,.2f}"
                print(f"│ {time_str:<8} {deal['symbol']:<8} {deal['type']:<4} "
                      f"{deal['volume']:<8.2f} {deal['price']:<10.5f} {pnl_str:<12}")
        else:
            print("│ No trades today")
        print("└" + "─"*79)

        # Warnings
        warnings = []
        if abs(daily_dd_pct) > 4.0:
            warnings.append("⚠ Daily loss approaching 4.5% limit!")
        if account['margin_level'] < 200 and account['margin_level'] > 0:
            warnings.append("⚠ Low margin level!")
        if len(positions) > 6:
            warnings.append("⚠ High number of open positions!")

        if warnings:
            print("\n┌─ WARNINGS " + "─"*67)
            for warning in warnings:
                print(f"│ {warning}")
            print("└" + "─"*79)

        print("\n" + "─"*80)
        print("  Press Ctrl+C to stop monitoring")
        print("  Refreshing every 5 seconds...")
        print("─"*80 + "\n")

    def run(self):
        """Run monitoring loop."""
        if not self.initialize():
            return

        print("Starting monitoring dashboard...")
        print("Bot must be running in another terminal")
        time.sleep(2)

        try:
            while True:
                self.display_dashboard()
                time.sleep(5)  # Update every 5 seconds
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
        finally:
            mt5.shutdown()


if __name__ == "__main__":
    monitor = BotMonitor()
    monitor.run()
