"""
Backtest Runner - Execute and Compare Backtests.

Run backtests on multiple symbols and phases, generate reports.
"""

import argparse
from datetime import datetime, timedelta
from typing import List
import MetaTrader5 as mt5
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.config import TradingPhase, STRATEGY_CONFIG
from bot.backtester import Backtester, BacktestResult


logger = setup_logger("BT_RUNNER")


def run_single_backtest(
    symbol: str,
    phase: TradingPhase,
    start_date: datetime,
    end_date: datetime,
    initial_balance: float
) -> BacktestResult:
    """Run a single backtest."""
    backtester = Backtester(phase)
    return backtester.run(symbol, start_date, end_date, initial_balance)


def run_multi_symbol_backtest(
    symbols: List[str],
    phase: TradingPhase,
    start_date: datetime,
    end_date: datetime,
    initial_balance: float
) -> List[BacktestResult]:
    """Run backtests on multiple symbols."""
    results = []

    for symbol in symbols:
        logger.info(f"Running backtest for {symbol}...")
        result = run_single_backtest(symbol, phase, start_date, end_date, initial_balance)
        results.append(result)

    return results


def run_phase_comparison(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    initial_balance: float
) -> List[BacktestResult]:
    """Run backtests for all phases on a symbol."""
    results = []

    for phase in TradingPhase:
        logger.info(f"Running backtest for {symbol} - {phase.value}...")
        result = run_single_backtest(symbol, phase, start_date, end_date, initial_balance)
        results.append(result)

    return results


def generate_report(results: List[BacktestResult], output_file: str = None):
    """Generate a summary report of backtest results."""
    if not results:
        logger.warning("No results to report")
        return

    # Console report
    print("\n" + "=" * 80)
    print("BACKTEST SUMMARY REPORT")
    print("=" * 80)

    # Header
    print(f"{'Symbol':<10} {'Phase':<15} {'Trades':<8} {'Win%':<8} {'Net P/L':<12} {'PF':<6} {'MaxDD%':<8}")
    print("-" * 80)

    # Results
    total_net = 0
    total_trades = 0

    for r in results:
        net_pct = r.net_profit / r.initial_balance * 100 if r.initial_balance > 0 else 0
        print(
            f"{r.symbol:<10} {r.phase:<15} {r.total_trades:<8} "
            f"{r.win_rate:<8.1f} ${r.net_profit:<11.2f} "
            f"{r.profit_factor:<6.2f} {r.max_drawdown_pct:<8.1f}"
        )
        total_net += r.net_profit
        total_trades += r.total_trades

    print("-" * 80)
    print(f"{'TOTAL':<10} {'':<15} {total_trades:<8} {'':<8} ${total_net:<11.2f}")
    print("=" * 80)

    # Detailed trade breakdown by exit reason
    print("\nEXIT REASON BREAKDOWN:")
    print("-" * 40)

    for r in results:
        if r.total_trades == 0:
            continue

        tp_exits = sum(1 for t in r.trades if t.exit_reason == 'TP')
        sl_exits = sum(1 for t in r.trades if t.exit_reason == 'SL')
        time_exits = sum(1 for t in r.trades if t.exit_reason == 'TIME')

        print(f"{r.symbol} ({r.phase}):")
        print(f"  TP: {tp_exits} | SL: {sl_exits} | TIME: {time_exits}")

    # Save to JSON if output file specified
    if output_file:
        report_data = []
        for r in results:
            report_data.append({
                'symbol': r.symbol,
                'phase': r.phase,
                'start_date': r.start_date.isoformat(),
                'end_date': r.end_date.isoformat(),
                'initial_balance': r.initial_balance,
                'final_balance': r.final_balance,
                'net_profit': r.net_profit,
                'total_trades': r.total_trades,
                'winning_trades': r.winning_trades,
                'losing_trades': r.losing_trades,
                'win_rate': r.win_rate,
                'profit_factor': r.profit_factor,
                'max_drawdown': r.max_drawdown,
                'max_drawdown_pct': r.max_drawdown_pct,
                'max_consecutive_losses': r.max_consecutive_losses,
                'average_win': r.average_win,
                'average_loss': r.average_loss,
                'expectancy': r.expectancy,
                'trades': [
                    {
                        'entry_time': t.entry_time.isoformat(),
                        'exit_time': t.exit_time.isoformat(),
                        'direction': t.direction,
                        'entry_price': t.entry_price,
                        'exit_price': t.exit_price,
                        'profit': t.profit,
                        'profit_pips': t.profit_pips,
                        'exit_reason': t.exit_reason
                    }
                    for t in r.trades
                ]
            })

        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Report saved to {output_file}")


def check_phase_viability(results: List[BacktestResult]) -> dict:
    """
    Check if strategy is viable for prop firm challenge.

    Criteria:
    - Must achieve profit target
    - Max drawdown must stay under daily limit
    - Win rate should be reasonable (>40%)
    """
    from bot.config import PHASE_CONFIGS

    analysis = {}

    for r in results:
        phase_config = None
        for phase, config in PHASE_CONFIGS.items():
            if config.name == r.phase:
                phase_config = config
                break

        if phase_config is None:
            continue

        key = f"{r.symbol}_{r.phase}"

        profit_pct = r.net_profit / r.initial_balance * 100
        target_met = profit_pct >= phase_config.profit_target if phase_config.profit_target > 0 else True
        dd_ok = r.max_drawdown_pct < phase_config.daily_loss_buffer
        win_rate_ok = r.win_rate >= 40

        analysis[key] = {
            'viable': target_met and dd_ok and win_rate_ok,
            'profit_pct': profit_pct,
            'target': phase_config.profit_target,
            'target_met': target_met,
            'max_dd_pct': r.max_drawdown_pct,
            'dd_limit': phase_config.daily_loss_buffer,
            'dd_ok': dd_ok,
            'win_rate': r.win_rate,
            'win_rate_ok': win_rate_ok
        }

    # Print analysis
    print("\n" + "=" * 80)
    print("PROP FIRM VIABILITY ANALYSIS")
    print("=" * 80)

    for key, a in analysis.items():
        status = "✓ VIABLE" if a['viable'] else "✗ NOT VIABLE"
        print(f"\n{key}: {status}")
        print(f"  Profit: {a['profit_pct']:.1f}% / {a['target']}% target {'✓' if a['target_met'] else '✗'}")
        print(f"  MaxDD: {a['max_dd_pct']:.1f}% / {a['dd_limit']}% limit {'✓' if a['dd_ok'] else '✗'}")
        print(f"  Win Rate: {a['win_rate']:.1f}% {'✓' if a['win_rate_ok'] else '✗'}")

    return analysis


def main():
    """Main entry point for backtest runner."""
    parser = argparse.ArgumentParser(description="Backtest Runner for Elastic Band Strategy")
    parser.add_argument("--symbols", type=str, default="EURUSD,GBPUSD,USDJPY",
                       help="Comma-separated list of symbols")
    parser.add_argument("--phase", type=str, choices=['1', '2', '3', 'all'], default='1',
                       help="Trading phase (1, 2, 3, or all)")
    parser.add_argument("--days", type=int, default=90,
                       help="Number of days to backtest")
    parser.add_argument("--balance", type=float, default=10000.0,
                       help="Initial balance")
    parser.add_argument("--output", type=str, default=None,
                       help="Output JSON file for report")

    args = parser.parse_args()

    # Initialize MT5
    if not mt5.initialize():
        logger.error(f"MT5 initialize failed: {mt5.last_error()}")
        sys.exit(1)

    try:
        # Parse arguments
        symbols = [s.strip() for s in args.symbols.split(',')]
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)

        # Select phase(s)
        if args.phase == 'all':
            phases = list(TradingPhase)
        else:
            phase_map = {'1': TradingPhase.PHASE_1, '2': TradingPhase.PHASE_2, '3': TradingPhase.PHASE_3}
            phases = [phase_map[args.phase]]

        # Run backtests
        all_results = []

        for phase in phases:
            results = run_multi_symbol_backtest(
                symbols=symbols,
                phase=phase,
                start_date=start_date,
                end_date=end_date,
                initial_balance=args.balance
            )
            all_results.extend(results)

        # Generate report
        generate_report(all_results, args.output)

        # Check viability
        check_phase_viability(all_results)

    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
