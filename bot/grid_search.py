"""
Grid Search Runner - Automated Parameter Testing.

Tests all parameter combinations automatically and saves results.
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.config import TradingPhase, STRATEGY_CONFIG

logger = setup_logger("GRID_SEARCH")


class GridSearchRunner:
    """
    Automated grid search for parameter optimization.

    Tests all parameter combinations and saves results for analysis.
    """

    def __init__(
        self,
        strategy_name: str,
        param_combinations: List[Dict[str, Any]],
        symbols: List[str],
        phase: TradingPhase,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float,
        output_dir: str
    ):
        self.strategy_name = strategy_name
        self.param_combinations = param_combinations
        self.symbols = symbols
        self.phase = phase
        self.start_date = start_date
        self.end_date = end_date
        self.initial_balance = initial_balance
        self.output_dir = output_dir

        # Create run directory
        run_id = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        self.run_dir = os.path.join(output_dir, strategy_name, f"run_{run_id}")
        os.makedirs(self.run_dir, exist_ok=True)

        # Save run metadata
        self._save_metadata()

        # Track progress
        self.completed_combos = 0
        self.total_combos = len(param_combinations)
        self.start_time = None

        # Best results tracking
        self.best_combo = None
        self.best_profit = float('-inf')

    def _save_metadata(self):
        """Save run metadata."""
        metadata = {
            'run_id': os.path.basename(self.run_dir),
            'strategy': self.strategy_name,
            'symbols': self.symbols,
            'phase': self.phase.value,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_balance': self.initial_balance,
            'total_combinations': len(self.param_combinations),
            'created_at': datetime.now().isoformat()
        }

        with open(os.path.join(self.run_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)

    def run(self, resume_from: int = 0):
        """
        Run grid search.

        Args:
            resume_from: Combination index to resume from (0-based).
        """
        try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None
        from bot.backtester import Backtester

        # Initialize MT5
        if not mt5.initialize():
            logger.error(f"MT5 initialize failed: {mt5.last_error()}")
            return

        try:
            self.start_time = time.time()

            logger.info(f"\n{'='*80}")
            logger.info(f"GRID SEARCH: {self.strategy_name}")
            logger.info(f"{'='*80}")
            logger.info(f"Testing {self.total_combos} parameter combinations")
            logger.info(f"Symbols: {', '.join(self.symbols)}")
            logger.info(f"Total backtests: {self.total_combos * len(self.symbols)}")
            logger.info(f"Results: {self.run_dir}")
            logger.info(f"{'='*80}\n")

            # Test each combination
            for i, params in enumerate(self.param_combinations[resume_from:], start=resume_from):
                combo_id = f"{i+1:03d}"

                logger.info(f"\n{'─'*80}")
                logger.info(f"Testing Combination {combo_id}/{self.total_combos}")
                logger.info(f"Parameters: {params}")
                logger.info(f"{'─'*80}")

                # Backup original config
                original_params = {}
                for key, value in params.items():
                    if key in STRATEGY_CONFIG:
                        original_params[key] = STRATEGY_CONFIG[key]
                        STRATEGY_CONFIG[key] = value

                # Run backtests for all symbols
                combo_results = {
                    'combo_id': combo_id,
                    'parameters': params,
                    'results': {},
                    'aggregate': {}
                }

                total_profit = 0
                total_trades = 0
                total_wins = 0

                for symbol in self.symbols:
                    logger.info(f"  Testing {symbol}...")

                    backtester = Backtester(self.phase)
                    result = backtester.run(
                        symbol,
                        self.start_date,
                        self.end_date,
                        self.initial_balance
                    )

                    # Store results
                    combo_results['results'][symbol] = {
                        'net_profit': result.net_profit,
                        'total_trades': result.total_trades,
                        'win_rate': result.win_rate,
                        'profit_factor': result.profit_factor,
                        'max_drawdown_pct': result.max_drawdown_pct,
                        'expectancy': result.expectancy
                    }

                    total_profit += result.net_profit
                    total_trades += result.total_trades
                    total_wins += result.winning_trades

                # Calculate aggregates
                avg_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
                combo_results['aggregate'] = {
                    'total_profit': total_profit,
                    'total_trades': total_trades,
                    'avg_win_rate': avg_win_rate
                }

                # Save combination results
                combo_file = os.path.join(self.run_dir, f'combo_{combo_id}.json')
                with open(combo_file, 'w') as f:
                    json.dump(combo_results, f, indent=2)

                # Restore original config
                for key, value in original_params.items():
                    STRATEGY_CONFIG[key] = value

                # Update progress
                self.completed_combos += 1

                # Track best
                if total_profit > self.best_profit:
                    self.best_profit = total_profit
                    self.best_combo = combo_id

                # Print progress
                self._print_progress(combo_id, params, total_profit, avg_win_rate)

            # Generate summary
            self._generate_summary()

            logger.info(f"\n{'='*80}")
            logger.info(f"GRID SEARCH COMPLETE!")
            logger.info(f"{'='*80}")
            logger.info(f"Results saved to: {self.run_dir}")
            logger.info(f"Best combination: {self.best_combo}")
            logger.info(f"Best profit: ${self.best_profit:.2f}")
            logger.info(f"{'='*80}\n")

        finally:
            mt5.shutdown()

    def _print_progress(self, combo_id: str, params: Dict, profit: float, win_rate: float):
        """Print progress update."""
        elapsed = time.time() - self.start_time
        avg_time = elapsed / self.completed_combos
        remaining = avg_time * (self.total_combos - self.completed_combos)

        pct = (self.completed_combos / self.total_combos) * 100
        bar_length = 50
        filled = int(bar_length * self.completed_combos / self.total_combos)
        bar = '█' * filled + '░' * (bar_length - filled)

        logger.info(f"\n  Progress: [{bar}] {self.completed_combos}/{self.total_combos} ({pct:.1f}%)")
        logger.info(f"  ETA: {int(remaining/60)}m {int(remaining%60)}s")
        logger.info(f"  Combo {combo_id}: Profit: ${profit:.2f} | Win Rate: {win_rate:.1f}%")
        logger.info(f"  Best so far: Combo {self.best_combo} - ${self.best_profit:.2f}")

    def _generate_summary(self):
        """Generate summary report of all results."""
        all_results = []

        # Load all combo results
        for i in range(1, self.total_combos + 1):
            combo_id = f"{i:03d}"
            combo_file = os.path.join(self.run_dir, f'combo_{combo_id}.json')

            if os.path.exists(combo_file):
                with open(combo_file, 'r') as f:
                    all_results.append(json.load(f))

        # Sort by total profit
        all_results.sort(key=lambda x: x['aggregate']['total_profit'], reverse=True)

        # Create summary
        summary = {
            'run_directory': self.run_dir,
            'strategy': self.strategy_name,
            'total_combinations_tested': len(all_results),
            'symbols': self.symbols,
            'top_10_by_profit': [],
            'best_parameters': {}
        }

        # Top 10
        for i, result in enumerate(all_results[:10], 1):
            summary['top_10_by_profit'].append({
                'rank': i,
                'combo_id': result['combo_id'],
                'parameters': result['parameters'],
                'total_profit': result['aggregate']['total_profit'],
                'avg_win_rate': result['aggregate']['avg_win_rate'],
                'total_trades': result['aggregate']['total_trades']
            })

        # Best parameters (top result)
        if all_results:
            summary['best_parameters'] = all_results[0]['parameters']

            # Save best parameters separately
            best_params_file = os.path.join(self.run_dir, 'best_params.json')
            with open(best_params_file, 'w') as f:
                json.dump(all_results[0]['parameters'], f, indent=2)

        # Save summary
        summary_file = os.path.join(self.run_dir, 'summary.json')
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        # Print summary
        logger.info(f"\n{'='*80}")
        logger.info("TOP 10 COMBINATIONS BY PROFIT")
        logger.info(f"{'='*80}")
        logger.info(f"{'Rank':<6} {'Combo':<8} {'Profit':<12} {'WinRate':<10} {'Trades':<8} Parameters")
        logger.info(f"{'-'*80}")

        for entry in summary['top_10_by_profit']:
            params_str = ', '.join([f"{k}:{v}" for k, v in list(entry['parameters'].items())[:3]])
            logger.info(
                f"{entry['rank']:<6} {entry['combo_id']:<8} "
                f"${entry['total_profit']:<11.2f} {entry['avg_win_rate']:<9.1f}% "
                f"{entry['total_trades']:<8} {params_str}"
            )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Automated Grid Search for Parameter Optimization")
    parser.add_argument("--strategy", type=str, required=True,
                       help="Strategy name (elastic_band, fvg, macd_rsi, elastic_bb)")
    parser.add_argument("--params", type=str, required=True,
                       help="Path to parameter combinations JSON file")
    parser.add_argument("--symbols", type=str, default="EURUSD,GBPUSD",
                       help="Comma-separated list of symbols")
    parser.add_argument("--phase", type=str, choices=['1', '2', '3'], default='1',
                       help="Trading phase")
    parser.add_argument("--days", type=int, default=90,
                       help="Number of days to backtest")
    parser.add_argument("--balance", type=float, default=10000.0,
                       help="Initial balance")
    parser.add_argument("--output", type=str, default="tests/results",
                       help="Output directory for results")
    parser.add_argument("--resume", type=int, default=0,
                       help="Resume from combination number (0-based)")

    args = parser.parse_args()

    # Load parameter combinations
    if not os.path.exists(args.params):
        logger.error(f"Parameter file not found: {args.params}")
        sys.exit(1)

    with open(args.params, 'r') as f:
        param_data = json.load(f)
        combinations = param_data.get('combinations', [])

    if not combinations:
        logger.error("No parameter combinations found in file")
        sys.exit(1)

    # Parse arguments
    symbols = [s.strip() for s in args.symbols.split(',')]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)

    phase_map = {'1': TradingPhase.PHASE_1, '2': TradingPhase.PHASE_2, '3': TradingPhase.PHASE_3}
    phase = phase_map[args.phase]

    # Create and run grid search
    grid_search = GridSearchRunner(
        strategy_name=args.strategy,
        param_combinations=combinations,
        symbols=symbols,
        phase=phase,
        start_date=start_date,
        end_date=end_date,
        initial_balance=args.balance,
        output_dir=args.output
    )

    grid_search.run(resume_from=args.resume)


if __name__ == "__main__":
    main()
