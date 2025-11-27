"""
Complete Workflow Orchestrator - One-Command Full Automation.

End-to-end automated optimization: generate params, test, analyze, compare, apply.
"""

import argparse
import subprocess
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger

logger = setup_logger("AUTOMATE")


class WorkflowOrchestrator:
    """Orchestrates complete end-to-end optimization workflow."""

    def __init__(
        self,
        strategies: List[str],
        symbols: List[str],
        phases: List[int],
        days: int,
        max_combinations: int = 50,
        auto_apply: bool = False,
        apply_type: str = 'risk_adjusted'
    ):
        self.strategies = strategies
        self.symbols = symbols
        self.phases = phases
        self.days = days
        self.max_combinations = max_combinations
        self.auto_apply = auto_apply
        self.apply_type = apply_type

        self.batch_dir = None
        self.best_result = None

    def run(self):
        """Execute complete workflow."""
        logger.info("=" * 100)
        logger.info("🚀 AUTOMATED OPTIMIZATION WORKFLOW STARTED")
        logger.info("=" * 100)
        logger.info(f"Strategies: {', '.join(self.strategies)}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Phases: {', '.join(map(str, self.phases))}")
        logger.info(f"Days: {self.days}")
        logger.info(f"Max Combinations: {self.max_combinations}")
        logger.info(f"Auto-Apply Best Params: {'Yes' if self.auto_apply else 'No'}")
        if self.auto_apply:
            logger.info(f"Apply Type: {self.apply_type}")
        logger.info("=" * 100)

        # Step 1: Run batch grid search
        logger.info("")
        logger.info("┌" + "─" * 98 + "┐")
        logger.info("│ STEP 1/4: Running batch grid search for all strategies...".ljust(99) + "│")
        logger.info("└" + "─" * 98 + "┘")

        self._run_batch_grid_search()

        # Step 2: Aggregate and compare results
        logger.info("")
        logger.info("┌" + "─" * 98 + "┐")
        logger.info("│ STEP 2/4: Aggregating and comparing results...".ljust(99) + "│")
        logger.info("└" + "─" * 98 + "┘")

        comparison = self._aggregate_results()

        # Step 3: Display best result
        logger.info("")
        logger.info("┌" + "─" * 98 + "┐")
        logger.info("│ STEP 3/4: Identifying best strategy and parameters...".ljust(99) + "│")
        logger.info("└" + "─" * 98 + "┘")

        self._display_best_result(comparison)

        # Step 4: Optionally apply best parameters
        if self.auto_apply:
            logger.info("")
            logger.info("┌" + "─" * 98 + "┐")
            logger.info("│ STEP 4/4: Applying best parameters to config...".ljust(99) + "│")
            logger.info("└" + "─" * 98 + "┘")

            self._apply_best_parameters()
        else:
            logger.info("")
            logger.info("┌" + "─" * 98 + "┐")
            logger.info("│ STEP 4/4: Skipping auto-apply (use --auto-apply to enable)".ljust(99) + "│")
            logger.info("└" + "─" * 98 + "┘")

        # Final summary
        self._print_final_summary()

    def _run_batch_grid_search(self):
        """Run batch grid search."""
        cmd = [
            'python', 'bot/batch_grid_search.py',
            '--strategies', ','.join(self.strategies),
            '--symbols', ','.join(self.symbols),
            '--phases', ','.join(map(str, self.phases)),
            '--days', str(self.days),
            '--max-combinations', str(self.max_combinations)
        ]

        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(cmd)

        if result.returncode != 0:
            logger.error("Batch grid search failed")
            sys.exit(1)

        # Find the most recent batch directory
        batch_dirs = sorted(Path("tests/results").glob("batch_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not batch_dirs:
            logger.error("No batch results found")
            sys.exit(1)

        self.batch_dir = batch_dirs[0]
        logger.info(f"✓ Batch grid search completed: {self.batch_dir}")

    def _aggregate_results(self) -> dict:
        """Aggregate and compare results."""
        cmd = [
            'python', 'bot/aggregate_results.py',
            '--batch', str(self.batch_dir)
        ]

        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(cmd)

        if result.returncode != 0:
            logger.warning("Results aggregation had issues, but continuing...")

        # Load comparison report
        comparison_file = self.batch_dir / "comparison_report.json"
        if not comparison_file.exists():
            logger.error("Comparison report not found")
            sys.exit(1)

        with open(comparison_file, 'r') as f:
            comparison = json.load(f)

        logger.info(f"✓ Results aggregated and compared")
        return comparison

    def _display_best_result(self, comparison: dict):
        """Display best overall result."""
        best = comparison.get('best_overall', {})

        if not best:
            logger.error("No best result found")
            sys.exit(1)

        self.best_result = best

        logger.info("")
        logger.info("=" * 100)
        logger.info("🏆 BEST OVERALL STRATEGY (Risk-Adjusted)")
        logger.info("=" * 100)
        logger.info(f"Strategy:          {best['strategy'].upper()}")
        logger.info(f"Phase:             {best['phase']}")
        logger.info(f"Profit:            ${best['profit']:.2f}")
        logger.info(f"Win Rate:          {best['win_rate']:.1f}%")
        logger.info(f"Max Drawdown:      {best['max_drawdown_pct']:.2f}%")
        logger.info(f"Risk-Adj Score:    {best['risk_adjusted_score']:.2f}")
        logger.info(f"Total Trades:      {best['total_trades']}")
        logger.info("─" * 100)
        logger.info("Best Parameters:")
        for param, value in best['parameters'].items():
            logger.info(f"  {param}: {value}")
        logger.info("=" * 100)

    def _apply_best_parameters(self):
        """Apply best parameters to config."""
        if not self.best_result:
            logger.error("No best result available")
            return

        # Find the run directory
        run_dir = Path(self.best_result['run_dir'])

        # Determine which params file to use based on apply_type
        if self.apply_type == 'best':
            params_file = run_dir / "best_params.json"
        else:
            params_file = run_dir / "recommended_params.json"

        if not params_file.exists():
            logger.error(f"Parameters file not found: {params_file}")
            return

        # Apply parameters using config manager
        cmd = [
            'python', 'bot/config_manager.py',
            '--apply', str(params_file)
        ]

        if self.apply_type != 'best':
            cmd.extend(['--param-type', self.apply_type])

        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(cmd)

        if result.returncode != 0:
            logger.error("Failed to apply parameters")
            return

        # Set active strategy
        cmd = [
            'python', 'bot/config_manager.py',
            '--set-strategy', self.best_result['strategy']
        ]

        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(cmd)

        if result.returncode != 0:
            logger.error("Failed to set active strategy")
            return

        logger.info("✓ Best parameters and strategy applied to config")

    def _print_final_summary(self):
        """Print final summary and next steps."""
        logger.info("")
        logger.info("=" * 100)
        logger.info("✅ AUTOMATED OPTIMIZATION WORKFLOW COMPLETED")
        logger.info("=" * 100)
        logger.info(f"Batch Results:     {self.batch_dir}")
        if self.best_result:
            logger.info(f"Best Strategy:     {self.best_result['strategy'].upper()} (Phase {self.best_result['phase']})")
            logger.info(f"Expected Profit:   ${self.best_result['profit']:.2f}")
            logger.info(f"Win Rate:          {self.best_result['win_rate']:.1f}%")

        logger.info("─" * 100)
        logger.info("NEXT STEPS:")
        logger.info("─" * 100)

        if self.auto_apply:
            logger.info("✓ Config has been updated with best parameters")
            logger.info("")
            logger.info("1. Review config:  bot/config.py")
            logger.info("2. Run backtest:   python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 90")
            logger.info("3. Start bot:      python bot/main.py")
        else:
            logger.info("1. Review results: python bot/aggregate_results.py --batch " + str(self.batch_dir))
            logger.info("2. Apply params:   python bot/config_manager.py --apply <params_file>")
            logger.info("3. Run backtest:   python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 90")
            logger.info("4. Start bot:      python bot/main.py")

        logger.info("")
        logger.info("MANUAL COMMANDS (if needed):")
        logger.info("─" * 100)
        if self.best_result:
            logger.info(f"Apply best params: python bot/config_manager.py --apply {self.best_result['run_dir']}/best_params.json")
            logger.info(f"Set strategy:      python bot/config_manager.py --set-strategy {self.best_result['strategy']}")

        logger.info("=" * 100)


def main():
    parser = argparse.ArgumentParser(
        description='Complete automated optimization workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Test all strategies on EURUSD for Phase 1 (90 days)
  python bot/automate_optimization.py --symbols EURUSD --phase 1 --days 90

  # Test specific strategies and auto-apply best params
  python bot/automate_optimization.py \\
    --strategies elastic_band,fvg \\
    --symbols EURUSD,GBPUSD \\
    --phases 1,2 \\
    --days 90 \\
    --auto-apply

  # Quick test with fewer combinations
  python bot/automate_optimization.py \\
    --strategies all \\
    --symbols EURUSD \\
    --phase 1 \\
    --days 30 \\
    --max-combinations 20 \\
    --auto-apply
        """
    )
    parser.add_argument(
        '--strategies',
        type=str,
        default='all',
        help='Comma-separated list of strategies or "all" (default: all)'
    )
    parser.add_argument(
        '--symbols',
        type=str,
        required=True,
        help='Comma-separated list of symbols (e.g., EURUSD,GBPUSD)'
    )
    parser.add_argument(
        '--phases',
        type=str,
        default='1',
        help='Comma-separated list of phases to test (default: 1)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=90,
        help='Number of days to backtest (default: 90)'
    )
    parser.add_argument(
        '--max-combinations',
        type=int,
        default=50,
        help='Maximum parameter combinations per strategy (default: 50)'
    )
    parser.add_argument(
        '--auto-apply',
        action='store_true',
        help='Automatically apply best parameters to config (default: False)'
    )
    parser.add_argument(
        '--apply-type',
        choices=['best', 'profit', 'win_rate', 'drawdown', 'risk_adjusted'],
        default='risk_adjusted',
        help='Which parameter set to apply (default: risk_adjusted)'
    )

    args = parser.parse_args()

    # Parse strategies
    all_strategies = ['elastic_band', 'fvg', 'macd_rsi', 'elastic_bb']
    if args.strategies.lower() == 'all':
        strategies = all_strategies
    else:
        strategies = [s.strip() for s in args.strategies.split(',')]
        invalid = [s for s in strategies if s not in all_strategies]
        if invalid:
            logger.error(f"Invalid strategies: {invalid}")
            logger.error(f"Valid strategies: {all_strategies}")
            sys.exit(1)

    # Parse symbols
    symbols = [s.strip() for s in args.symbols.split(',')]

    # Parse phases
    phases = [int(p.strip()) for p in args.phases.split(',')]
    if any(p not in [1, 2, 3] for p in phases):
        logger.error("Phases must be 1, 2, or 3")
        sys.exit(1)

    # Create and run orchestrator
    orchestrator = WorkflowOrchestrator(
        strategies=strategies,
        symbols=symbols,
        phases=phases,
        days=args.days,
        max_combinations=args.max_combinations,
        auto_apply=args.auto_apply,
        apply_type=args.apply_type
    )

    orchestrator.run()


if __name__ == '__main__':
    main()
