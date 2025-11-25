"""
Strategy Comparison Tool.

Runs backtests on all available strategies and compares performance.
"""

import argparse
from datetime import datetime, timedelta
from typing import List, Dict
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.config import TradingPhase, StrategyType, STRATEGY_CONFIG

logger = setup_logger("STRATEGY_COMPARE")


def compare_all_strategies(
    symbols: List[str],
    phase: TradingPhase,
    start_date: datetime,
    end_date: datetime,
    initial_balance: float
) -> Dict[str, List]:
    """
    Run backtests for all strategies and compare results.

    NOTE: Currently all strategies use Elastic Band backtest logic.
    Full strategy-specific backtesting will be added in future update.
    This comparison helps test parameter variations.

    Args:
        symbols: List of trading symbols.
        phase: Trading phase to test.
        start_date: Backtest start date.
        end_date: Backtest end date.
        initial_balance: Initial account balance.

    Returns:
        Dictionary of strategy results.
    """
    import MetaTrader5 as mt5
    from bot.backtester import Backtester
    from bot.config import STRATEGY_CONFIG

    # Import all strategy classes
    from bot.strategy import ElasticBandStrategy
    from bot.strategy_fvg import FVGStrategy
    from bot.strategy_macd_rsi import MACDRSIStrategy
    from bot.strategy_elastic_bb import ElasticBBStrategy

    # For now, we'll test with different parameter sets
    # TODO: Implement full strategy-specific backtesting
    strategies_to_test = {
        'Elastic_Band': {
            'class': ElasticBandStrategy,
            'params': {
                'rsi_period': 7,
                'atr_sl_multiplier': 1.5,
                'risk_reward_ratio': 1.0
            }
        },
        'Elastic_Band_Aggressive': {
            'class': ElasticBandStrategy,
            'params': {
                'rsi_period': 5,
                'atr_sl_multiplier': 2.0,
                'risk_reward_ratio': 2.0
            }
        },
        'Elastic_Band_Conservative': {
            'class': ElasticBandStrategy,
            'params': {
                'rsi_period': 14,
                'atr_sl_multiplier': 1.0,
                'risk_reward_ratio': 1.0
            }
        },
    }

    logger.warning("NOTE: All backtests currently use Elastic Band logic with different parameters")
    logger.warning("Full strategy-specific backtesting coming in next update")

    all_results = {}

    for strategy_name, strategy_info in strategies_to_test.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {strategy_name}")
        logger.info(f"Parameters: {strategy_info['params']}")
        logger.info(f"{'='*60}")

        # Temporarily modify config for this test
        original_params = {}
        for key, value in strategy_info['params'].items():
            if key in STRATEGY_CONFIG:
                original_params[key] = STRATEGY_CONFIG[key]
                STRATEGY_CONFIG[key] = value

        strategy_results = []

        for symbol in symbols:
            logger.info(f"Running backtest for {symbol}...")

            # Create backtester with this strategy
            backtester = Backtester(phase, strategy_class=strategy_info['class'])
            result = backtester.run(symbol, start_date, end_date, initial_balance)
            strategy_results.append(result)

        # Restore original parameters
        for key, value in original_params.items():
            STRATEGY_CONFIG[key] = value

        all_results[strategy_name] = strategy_results

    return all_results


def generate_comparison_report(all_results: Dict[str, List], output_file: str = None):
    """
    Generate a comprehensive comparison report.

    Args:
        all_results: Dictionary of strategy name to results list.
        output_file: Optional output JSON file.
    """
    print("\n" + "=" * 100)
    print("STRATEGY COMPARISON REPORT")
    print("=" * 100)

    # Header
    print(f"{'Strategy':<15} {'Symbol':<10} {'Trades':<8} {'Win%':<8} {'Net P/L':<12} {'PF':<6} {'MaxDD%':<8} {'Expect':<8}")
    print("-" * 100)

    # Aggregated metrics per strategy
    strategy_totals = {}

    for strategy_name, results in all_results.items():
        for r in results:
            net_pct = r.net_profit / r.initial_balance * 100 if r.initial_balance > 0 else 0
            print(
                f"{strategy_name:<15} {r.symbol:<10} {r.total_trades:<8} "
                f"{r.win_rate:<8.1f} ${r.net_profit:<11.2f} "
                f"{r.profit_factor:<6.2f} {r.max_drawdown_pct:<8.1f} "
                f"{r.expectancy:<8.2f}"
            )

            # Aggregate
            if strategy_name not in strategy_totals:
                strategy_totals[strategy_name] = {
                    'total_trades': 0,
                    'net_profit': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'max_dd': 0
                }

            strategy_totals[strategy_name]['total_trades'] += r.total_trades
            strategy_totals[strategy_name]['net_profit'] += r.net_profit
            strategy_totals[strategy_name]['winning_trades'] += r.winning_trades
            strategy_totals[strategy_name]['losing_trades'] += r.losing_trades
            strategy_totals[strategy_name]['max_dd'] = max(strategy_totals[strategy_name]['max_dd'], r.max_drawdown_pct)

    print("-" * 100)

    # Print strategy summaries
    print("\n" + "=" * 100)
    print("STRATEGY PERFORMANCE SUMMARY")
    print("=" * 100)
    print(f"{'Strategy':<15} {'Total Trades':<15} {'Win Rate':<12} {'Total P/L':<15} {'Max DD%':<10}")
    print("-" * 100)

    for strategy_name, totals in strategy_totals.items():
        total_trades = totals['total_trades']
        win_rate = (totals['winning_trades'] / total_trades * 100) if total_trades > 0 else 0
        print(
            f"{strategy_name:<15} {total_trades:<15} {win_rate:<12.1f} "
            f"${totals['net_profit']:<14.2f} {totals['max_dd']:<10.1f}"
        )

    print("=" * 100)

    # Rank strategies
    print("\n" + "=" * 100)
    print("STRATEGY RANKINGS")
    print("=" * 100)

    # Rank by total profit
    sorted_by_profit = sorted(strategy_totals.items(), key=lambda x: x[1]['net_profit'], reverse=True)
    print("\nRanked by Total Profit:")
    for i, (strategy, totals) in enumerate(sorted_by_profit, 1):
        print(f"  {i}. {strategy}: ${totals['net_profit']:.2f}")

    # Rank by win rate
    sorted_by_winrate = sorted(
        strategy_totals.items(),
        key=lambda x: (x[1]['winning_trades'] / x[1]['total_trades'] * 100) if x[1]['total_trades'] > 0 else 0,
        reverse=True
    )
    print("\nRanked by Win Rate:")
    for i, (strategy, totals) in enumerate(sorted_by_winrate, 1):
        win_rate = (totals['winning_trades'] / totals['total_trades'] * 100) if totals['total_trades'] > 0 else 0
        print(f"  {i}. {strategy}: {win_rate:.1f}%")

    # Rank by max drawdown (lower is better)
    sorted_by_dd = sorted(strategy_totals.items(), key=lambda x: x[1]['max_dd'])
    print("\nRanked by Max Drawdown (lower is better):")
    for i, (strategy, totals) in enumerate(sorted_by_dd, 1):
        print(f"  {i}. {strategy}: {totals['max_dd']:.1f}%")

    print("=" * 100)

    # Recommendation
    print("\n" + "=" * 100)
    print("RECOMMENDATION")
    print("=" * 100)

    best_strategy = sorted_by_profit[0][0]
    best_profit = sorted_by_profit[0][1]['net_profit']
    best_winrate_strategy = sorted_by_winrate[0][0]
    best_winrate = (sorted_by_winrate[0][1]['winning_trades'] / sorted_by_winrate[0][1]['total_trades'] * 100)

    print(f"\nBest Overall Profit: {best_strategy} (${best_profit:.2f})")
    print(f"Highest Win Rate: {best_winrate_strategy} ({best_winrate:.1f}%)")

    if best_strategy == best_winrate_strategy:
        print(f"\n✓ RECOMMENDED STRATEGY: {best_strategy}")
        print(f"  This strategy has both the highest profit AND highest win rate.")
    else:
        print(f"\n⚠ MIXED RESULTS:")
        print(f"  - For maximum profit: {best_strategy}")
        print(f"  - For consistency: {best_winrate_strategy}")

    print("=" * 100)

    # Save to JSON if requested
    if output_file:
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'strategies': {}
        }

        for strategy_name, results in all_results.items():
            report_data['strategies'][strategy_name] = []
            for r in results:
                report_data['strategies'][strategy_name].append({
                    'symbol': r.symbol,
                    'phase': r.phase,
                    'total_trades': r.total_trades,
                    'win_rate': r.win_rate,
                    'net_profit': r.net_profit,
                    'profit_factor': r.profit_factor,
                    'max_drawdown_pct': r.max_drawdown_pct,
                    'expectancy': r.expectancy,
                })

        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Comparison report saved to {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Compare all trading strategies")
    parser.add_argument("--symbols", type=str, default="EURUSD,GBPUSD,USDJPY",
                       help="Comma-separated list of symbols")
    parser.add_argument("--phase", type=str, choices=['1', '2', '3'], default='1',
                       help="Trading phase (1, 2, or 3)")
    parser.add_argument("--days", type=int, default=90,
                       help="Number of days to backtest")
    parser.add_argument("--balance", type=float, default=10000.0,
                       help="Initial balance")
    parser.add_argument("--output", type=str, default=None,
                       help="Output JSON file for comparison report")

    args = parser.parse_args()

    # Initialize MT5
    import MetaTrader5 as mt5
    if not mt5.initialize():
        logger.error(f"MT5 initialize failed: {mt5.last_error()}")
        sys.exit(1)

    try:
        # Parse arguments
        symbols = [s.strip() for s in args.symbols.split(',')]
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)

        phase_map = {'1': TradingPhase.PHASE_1, '2': TradingPhase.PHASE_2, '3': TradingPhase.PHASE_3}
        phase = phase_map[args.phase]

        logger.info(f"Comparing all strategies on {symbols} for {args.days} days")

        # Run comparison
        all_results = compare_all_strategies(
            symbols=symbols,
            phase=phase,
            start_date=start_date,
            end_date=end_date,
            initial_balance=args.balance
        )

        # Generate report
        generate_comparison_report(all_results, args.output)

    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
