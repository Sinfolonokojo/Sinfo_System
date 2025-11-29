"""
Batch Grid Search Runner - Multi-Strategy Automated Testing.

Runs grid searches for multiple strategies/phases without manual intervention.
"""

import argparse
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger

logger = setup_logger("BATCH_GS")


class BatchGridSearchRunner:
    """Orchestrates grid searches across multiple strategies and phases."""

    def __init__(
        self,
        strategies: List[str],
        symbols: List[str],
        phases: List[int],
        days: int,
        max_combinations: int = 50,
        multi_period: bool = False,
        num_periods: int = 1,
        resume_from: Optional[str] = None
    ):
        self.strategies = strategies
        self.symbols = symbols
        self.phases = phases
        self.days = days
        self.max_combinations = max_combinations
        self.multi_period = multi_period
        self.num_periods = num_periods

        # Resume from existing batch or create new
        if resume_from:
            self.batch_id = resume_from
            self.batch_dir = Path(f"tests/results/batch_{self.batch_id}")
            if not self.batch_dir.exists():
                raise ValueError(f"Batch directory not found: {self.batch_dir}")
            logger.info(f"Resuming batch: {self.batch_id}")
            self._load_checkpoint()
        else:
            # Create new batch run directory
            self.batch_id = datetime.now().strftime("%Y_%m_%d_%H%M%S")
            self.batch_dir = Path(f"tests/results/batch_{self.batch_id}")
            self.batch_dir.mkdir(parents=True, exist_ok=True)
            self.results = {}
            self.completed_runs = set()

        self.checkpoint_file = self.batch_dir / "checkpoint.json"
        self.start_time = None
        self.end_time = None

    def _load_checkpoint(self):
        """Load checkpoint data for resuming."""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                self.results = checkpoint.get('results', {})
                self.completed_runs = set(checkpoint.get('completed_runs', []))
                logger.info(f"Loaded checkpoint: {len(self.completed_runs)} runs already completed")
        else:
            self.results = {}
            self.completed_runs = set()

    def _save_checkpoint(self):
        """Save checkpoint for resume capability."""
        checkpoint = {
            'batch_id': self.batch_id,
            'timestamp': datetime.now().isoformat(),
            'completed_runs': list(self.completed_runs),
            'results': self.results,
            'strategies': self.strategies,
            'symbols': self.symbols,
            'phases': self.phases,
            'days': self.days,
            'max_combinations': self.max_combinations,
            'multi_period': self.multi_period,
            'num_periods': self.num_periods,
        }

        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def run(self) -> Dict[str, Any]:
        """
        Run batch grid search for all strategies and phases.

        Returns:
            Dictionary with batch results.
        """
        self.start_time = datetime.now()

        logger.info("=" * 80)
        logger.info("BATCH GRID SEARCH STARTED")
        logger.info("=" * 80)
        logger.info(f"Batch ID: {self.batch_id}")
        logger.info(f"Strategies: {', '.join(self.strategies)}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Phases: {', '.join(map(str, self.phases))}")
        logger.info(f"Days: {self.days}")
        logger.info(f"Max Combinations: {self.max_combinations}")
        if self.multi_period:
            logger.info(f"Multi-Period: Yes ({self.num_periods} periods)")
        logger.info(f"Results Directory: {self.batch_dir}")
        logger.info("=" * 80)

        total_runs = len(self.strategies) * len(self.phases)
        current_run = 0

        # Run grid search for each strategy and phase combination
        for strategy in self.strategies:
            for phase in self.phases:
                current_run += 1
                run_key = f"{strategy}_phase{phase}"

                # Skip if already completed (resume capability)
                if run_key in self.completed_runs:
                    logger.info(f"[SKIP]  Skipping {run_key} (already completed)")
                    continue

                logger.info("")
                logger.info("-" * 80)
                logger.info(f"RUN {current_run}/{total_runs}: {strategy.upper()} - Phase {phase}")
                logger.info("-" * 80)

                try:
                    # Step 1: Generate parameters
                    logger.info(f"[1/3] Generating parameters for {strategy}...")
                    self._generate_parameters(strategy)

                    # Step 2: Run grid search
                    logger.info(f"[2/3] Running grid search for {strategy} (Phase {phase})...")
                    run_dir = self._run_grid_search(strategy, phase)

                    # Step 3: Analyze results
                    logger.info(f"[3/3] Analyzing results for {strategy} (Phase {phase})...")
                    analysis_result = self._analyze_results(run_dir)

                    # Store results
                    self.results[run_key] = {
                        'strategy': strategy,
                        'phase': phase,
                        'run_dir': str(run_dir),
                        'status': 'success',
                        'analysis': analysis_result
                    }

                    # Mark as completed
                    self.completed_runs.add(run_key)

                    # Save checkpoint after each successful run
                    self._save_checkpoint()

                    logger.info(f"[OK] Completed {strategy} - Phase {phase}")

                except Exception as e:
                    logger.error(f"[X] Failed {strategy} - Phase {phase}: {e}")
                    self.results[run_key] = {
                        'strategy': strategy,
                        'phase': phase,
                        'status': 'failed',
                        'error': str(e)
                    }

                    # Save checkpoint even after failures
                    self._save_checkpoint()

        self.end_time = datetime.now()

        # Save batch metadata
        self._save_batch_metadata()

        # Print summary
        self._print_summary()

        return self.results

    def _generate_parameters(self, strategy: str):
        """Generate parameter combinations for a strategy."""
        cmd = [
            sys.executable, 'bot/optimize_parameters.py',
            '--strategy', strategy,
            '--max-combinations', str(self.max_combinations)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to generate parameters: {result.stderr}")

    def _run_grid_search(self, strategy: str, phase: int) -> Path:
        """Run grid search for a strategy and phase."""
        params_file = f"tests/parameter_sets/{strategy}_params.json"

        cmd = [
            sys.executable, 'bot/grid_search.py',
            '--strategy', strategy,
            '--params', params_file,
            '--symbols', ','.join(self.symbols),
            '--phase', str(phase),
            '--days', str(self.days)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Grid search failed: {result.stderr}")

        # Parse run directory from output
        # The grid search creates: tests/results/{strategy}/run_TIMESTAMP
        # We need to find the most recent run directory
        strategy_results_dir = Path(f"tests/results/{strategy}")
        if not strategy_results_dir.exists():
            raise RuntimeError(f"Results directory not found: {strategy_results_dir}")

        run_dirs = sorted(strategy_results_dir.glob("run_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not run_dirs:
            raise RuntimeError(f"No run directories found in {strategy_results_dir}")

        return run_dirs[0]

    def _analyze_results(self, run_dir: Path) -> Optional[Dict[str, Any]]:
        """Analyze grid search results."""
        cmd = [
            sys.executable, 'bot/analyze_results.py',
            '--run', str(run_dir)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.warning(f"Analysis failed: {result.stderr}")
            return None

        # Load best params from analysis
        best_params_file = run_dir / "best_params.json"
        recommended_params_file = run_dir / "recommended_params.json"

        analysis = {}

        if best_params_file.exists():
            with open(best_params_file, 'r') as f:
                analysis['best_params'] = json.load(f)

        if recommended_params_file.exists():
            with open(recommended_params_file, 'r') as f:
                analysis['recommended_params'] = json.load(f)

        return analysis

    def _save_batch_metadata(self):
        """Save batch run metadata."""
        metadata = {
            'batch_id': self.batch_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_seconds': (self.end_time - self.start_time).total_seconds(),
            'strategies': self.strategies,
            'symbols': self.symbols,
            'phases': self.phases,
            'days': self.days,
            'max_combinations': self.max_combinations,
            'total_runs': len(self.strategies) * len(self.phases),
            'successful_runs': sum(1 for r in self.results.values() if r['status'] == 'success'),
            'failed_runs': sum(1 for r in self.results.values() if r['status'] == 'failed'),
            'results': self.results
        }

        metadata_file = self.batch_dir / "batch_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Saved batch metadata to: {metadata_file}")

    def _print_summary(self):
        """Print batch run summary."""
        duration = (self.end_time - self.start_time).total_seconds()
        successful = sum(1 for r in self.results.values() if r['status'] == 'success')
        failed = sum(1 for r in self.results.values() if r['status'] == 'failed')

        logger.info("")
        logger.info("=" * 80)
        logger.info("BATCH GRID SEARCH COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Batch ID: {self.batch_id}")
        logger.info(f"Duration: {duration/60:.1f} minutes")
        logger.info(f"Total Runs: {len(self.results)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info("-" * 80)

        if successful > 0:
            logger.info("SUCCESSFUL RUNS:")
            for key, result in self.results.items():
                if result['status'] == 'success':
                    analysis = result.get('analysis', {})
                    best_params = analysis.get('best_params', {})

                    profit = best_params.get('profit', 'N/A')
                    win_rate = best_params.get('win_rate', 'N/A')

                    logger.info(f"  [OK] {result['strategy'].upper()} (Phase {result['phase']})")
                    logger.info(f"    Profit: {profit} | Win Rate: {win_rate}")
                    logger.info(f"    Results: {result['run_dir']}")

        if failed > 0:
            logger.info("")
            logger.info("FAILED RUNS:")
            for key, result in self.results.items():
                if result['status'] == 'failed':
                    logger.info(f"  [X] {result['strategy'].upper()} (Phase {result['phase']})")
                    logger.info(f"    Error: {result.get('error', 'Unknown')}")

        logger.info("=" * 80)
        logger.info(f"Batch results saved to: {self.batch_dir}")
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info(f"  1. Compare results: python bot/aggregate_results.py --batch {self.batch_dir}")
        logger.info(f"  2. Apply best params: python bot/config_manager.py --apply <best_params.json>")
        logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Run grid searches for multiple strategies and phases automatically'
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
        '--multi-period',
        action='store_true',
        help='Enable multi-period testing across 3 time windows'
    )
    parser.add_argument(
        '--num-periods',
        type=int,
        default=1,
        help='Number of time periods to test (1-3, default: 1)'
    )
    parser.add_argument(
        '--resume',
        type=str,
        default=None,
        help='Resume from existing batch ID (e.g., 2025_11_28_153702)'
    )

    args = parser.parse_args()

    # Show resume info if applicable
    if args.resume:
        logger.info(f"Resume mode: Continuing batch {args.resume}")

    # Parse strategies
    all_strategies = ['elastic_band', 'fvg', 'macd_rsi', 'elastic_bb']
    if args.strategies.lower() == 'all':
        strategies = all_strategies
    else:
        strategies = [s.strip() for s in args.strategies.split(',')]
        # Validate strategies
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

    # Validate num_periods
    if args.num_periods < 1 or args.num_periods > 3:
        logger.error("--num-periods must be between 1 and 3")
        sys.exit(1)

    # Create and run batch grid search
    runner = BatchGridSearchRunner(
        strategies=strategies,
        symbols=symbols,
        phases=phases,
        days=args.days,
        max_combinations=args.max_combinations,
        multi_period=args.multi_period,
        num_periods=args.num_periods,
        resume_from=args.resume
    )

    results = runner.run()

    # Exit with error code if any runs failed
    if any(r['status'] == 'failed' for r in results.values()):
        sys.exit(1)


if __name__ == '__main__':
    main()
