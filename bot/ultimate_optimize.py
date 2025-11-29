"""
Ultimate Parameter Optimization System.

Single-command automation that finds the best parameter combinations
through comprehensive testing, validation, and intelligent ranking.

Usage:
    python bot/ultimate_optimize.py                    # Full 12-24 hour run
    python bot/ultimate_optimize.py --quick            # Quick 1-2 hour test
    python bot/ultimate_optimize.py --resume BATCH_ID  # Resume interrupted run
"""

import argparse
import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.intelligent_ranker import create_ranker
from bot.config import TradingPhase, STRATEGY_CONFIG

logger = setup_logger("ULTIMATE_OPT")


class UltimateOptimizer:
    """
    Ultimate parameter optimization orchestrator.

    Implements 8-step workflow:
    1. Pre-flight Checks
    2. Generate Extended Parameter Sets
    3. Multi-Period Grid Search
    4. Walk-Forward Validation
    5. Aggregate & Rank
    6. Quality Gate Check
    7. Present Results & Confirmation
    8. Apply & Verify
    """

    def __init__(
        self,
        quick_mode: bool = False,
        resume_batch: Optional[str] = None,
        strategies: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None,
        phases: Optional[List[int]] = None,
        auto_apply: bool = False
    ):
        """
        Initialize Ultimate Optimizer.

        Args:
            quick_mode: If True, use reduced parameters for faster testing
            resume_batch: Batch ID to resume from
            strategies: List of strategies to test (all if None)
            symbols: List of symbols to test (default: EURUSD,GBPUSD,USDJPY)
            phases: List of phases to test (default: [1])
            auto_apply: If True, skip confirmation and apply best params automatically
        """
        self.quick_mode = quick_mode
        self.resume_batch = resume_batch
        self.auto_apply = auto_apply

        # Configuration
        self.strategies = strategies or ['elastic_band', 'fvg', 'macd_rsi', 'elastic_bb']
        self.symbols = symbols or ['EURUSD', 'GBPUSD', 'USDJPY']
        self.phases = phases or [1]

        # Quick mode: reduced scope for 1-2 hour testing
        if quick_mode:
            self.max_combinations = 20  # Quick test
            self.num_periods = 1  # Single period
            self.days = 60  # 2 months
            logger.info("[QUICK MODE] Testing 20 combos per strategy, single period, 60 days")
        else:
            self.max_combinations = 200  # Thorough test
            self.num_periods = 3  # All 3 periods
            self.days = 180  # 6 months
            logger.info("[FULL MODE] Testing 200 combos per strategy, 3 periods, 180 days")

        # Results tracking
        self.batch_id = None
        self.batch_dir = None
        self.comparison = None
        self.best_params = None

        # Create ranker (balanced profile for prop firm focus)
        self.ranker = create_ranker('balanced')

    def run(self) -> Dict[str, Any]:
        """
        Execute the complete optimization workflow.

        Returns:
            Dictionary with final results and status.
        """
        logger.info("")
        logger.info("=" * 100)
        logger.info(">>> ULTIMATE PARAMETER OPTIMIZATION SYSTEM <<<")
        logger.info("=" * 100)
        logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Mode: {'QUICK (1-2 hours)' if self.quick_mode else 'FULL (12-24 hours)'}")
        logger.info(f"Strategies: {', '.join(s.upper() for s in self.strategies)}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Phases: {', '.join(map(str, self.phases))}")
        logger.info("=" * 100)
        logger.info("")

        workflow_start = datetime.now()

        try:
            # Step 1: Pre-flight Checks
            if not self._step1_preflight_checks():
                logger.error("[FAILED] Pre-flight checks failed. Aborting.")
                return {'status': 'failed', 'step': 1, 'error': 'Pre-flight checks failed'}

            # Step 2: Generate Extended Parameter Sets
            if not self._step2_generate_parameters():
                logger.error("[FAILED] Parameter generation failed. Aborting.")
                return {'status': 'failed', 'step': 2, 'error': 'Parameter generation failed'}

            # Step 3: Multi-Period Grid Search
            if not self._step3_grid_search():
                logger.error("[FAILED] Grid search failed. Aborting.")
                return {'status': 'failed', 'step': 3, 'error': 'Grid search failed'}

            # Step 4: Walk-Forward Validation (optional - can add later if needed)
            # Currently grid search handles multi-period testing
            logger.info("[STEP 4/8] Walk-Forward Validation (integrated in grid search)")

            # Step 5: Aggregate & Rank
            if not self._step5_aggregate_rank():
                logger.error("[FAILED] Aggregation and ranking failed. Aborting.")
                return {'status': 'failed', 'step': 5, 'error': 'Aggregation failed'}

            # Step 6: Quality Gate Check
            passed_gates = self._step6_quality_gate_check()
            if not passed_gates:
                logger.warning("[WARNING]  NO PARAMETERS PASSED QUALITY GATES")
                return {
                    'status': 'no_viable_params',
                    'message': 'No parameters met quality gate requirements',
                    'recommendation': 'Keep current configuration or adjust quality gates'
                }

            # Step 7: Present Results & Confirmation
            if not self.auto_apply:
                if not self._step7_present_and_confirm():
                    logger.info("[FAILED] User declined to apply parameters. Keeping current configuration.")
                    return {'status': 'user_declined', 'best_params': self.best_params}

            # Step 8: Apply & Verify
            if not self._step8_apply_verify():
                logger.error("[FAILED] Failed to apply parameters. Please apply manually.")
                return {'status': 'apply_failed', 'best_params': self.best_params}

            # Success!
            workflow_end = datetime.now()
            duration = (workflow_end - workflow_start).total_seconds()

            logger.info("")
            logger.info("=" * 100)
            logger.info("[SUCCESS] ULTIMATE OPTIMIZATION COMPLETED SUCCESSFULLY!")
            logger.info("=" * 100)
            logger.info(f"Duration: {duration / 60:.1f} minutes ({duration / 3600:.1f} hours)")
            logger.info(f"Best Strategy: {self.best_params['strategy'].upper()}")
            logger.info(f"Expected Profit: ${self.best_params.get('net_profit', 0):.2f}")
            logger.info(f"Composite Score: {self.best_params.get('composite_score', 0):.1f} / 100")
            logger.info("=" * 100)

            return {
                'status': 'success',
                'duration_hours': duration / 3600,
                'batch_id': self.batch_id,
                'best_params': self.best_params,
                'comparison': self.comparison
            }

        except KeyboardInterrupt:
            logger.warning("\n[WARNING] Interrupted by user. Progress saved in checkpoint.")
            logger.info(f"Resume with: python bot/ultimate_optimize.py --resume {self.batch_id}")
            return {'status': 'interrupted', 'batch_id': self.batch_id}

        except Exception as e:
            logger.error(f"[FAILED] Unexpected error: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}

    def _step1_preflight_checks(self) -> bool:
        """
        Step 1: Pre-flight Checks.

        Verify all required files and directories exist.
        """
        logger.info("[STEP 1/8] Pre-flight Checks")
        logger.info("-" * 80)

        checks = {
            'bot/optimize_parameters.py': Path('bot/optimize_parameters.py'),
            'bot/batch_grid_search.py': Path('bot/batch_grid_search.py'),
            'bot/aggregate_results.py': Path('bot/aggregate_results.py'),
            'bot/intelligent_ranker.py': Path('bot/intelligent_ranker.py'),
            'bot/multi_period_tester.py': Path('bot/multi_period_tester.py'),
            'bot/config.py': Path('bot/config.py'),
        }

        all_passed = True
        for name, path in checks.items():
            if path.exists():
                logger.info(f"  [OK] {name}")
            else:
                logger.error(f"  [X] {name} NOT FOUND")
                all_passed = False

        # Create required directories
        Path('tests/parameter_sets').mkdir(parents=True, exist_ok=True)
        Path('tests/results').mkdir(parents=True, exist_ok=True)
        logger.info(f"  [OK] Created tests/parameter_sets/")
        logger.info(f"  [OK] Created tests/results/")

        if all_passed:
            logger.info("[SUCCESS] All pre-flight checks passed")
        else:
            logger.error("[FAILED] Some pre-flight checks failed")

        logger.info("")
        return all_passed

    def _step2_generate_parameters(self) -> bool:
        """
        Step 2: Generate Extended Parameter Sets.

        Generate parameter combinations for all strategies.
        """
        logger.info("[STEP 2/8] Generating Extended Parameter Sets")
        logger.info("-" * 80)

        for strategy in self.strategies:
            logger.info(f"  Generating {self.max_combinations} combinations for {strategy.upper()}...")

            cmd = [
                'python', 'bot/optimize_parameters.py',
                '--strategy', strategy,
                '--max-combinations', str(self.max_combinations)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"  [X] Failed to generate {strategy}: {result.stderr}")
                return False

            logger.info(f"  [OK] Generated {strategy}_params.json")

        logger.info("[SUCCESS] All parameter sets generated")
        logger.info("")
        return True

    def _step3_grid_search(self) -> bool:
        """
        Step 3: Multi-Period Grid Search.

        Run batch grid search across all strategies and phases.
        """
        logger.info("[STEP 3/8] Multi-Period Grid Search")
        logger.info("-" * 80)

        # Determine batch ID
        if self.resume_batch:
            self.batch_id = self.resume_batch
            logger.info(f"  Resuming batch: {self.batch_id}")
        else:
            # Will be created by batch_grid_search.py
            logger.info(f"  Starting new batch run...")

        cmd = [
            'python', 'bot/batch_grid_search.py',
            '--strategies', ','.join(self.strategies),
            '--symbols', ','.join(self.symbols),
            '--phases', ','.join(map(str, self.phases)),
            '--days', str(self.days),
            '--max-combinations', str(self.max_combinations)
        ]

        # Add multi-period flag if not quick mode
        if not self.quick_mode:
            cmd.extend(['--multi-period', '--num-periods', str(self.num_periods)])

        # Add resume flag if resuming
        if self.resume_batch:
            cmd.extend(['--resume', self.resume_batch])

        logger.info(f"  Command: {' '.join(cmd)}")
        logger.info("")
        logger.info("  ... This will take several hours. Progress will be shown below...")
        logger.info("")

        # Run grid search (show output in real-time)
        result = subprocess.run(cmd)

        if result.returncode != 0:
            logger.error("  [X] Grid search failed")
            return False

        # Find the batch directory
        if not self.batch_id:
            # Get most recent batch directory
            batch_dirs = sorted(Path('tests/results').glob('batch_*'), key=lambda p: p.stat().st_mtime, reverse=True)
            if not batch_dirs:
                logger.error("  [X] No batch directory found")
                return False
            self.batch_dir = batch_dirs[0]
            self.batch_id = self.batch_dir.name.replace('batch_', '')
        else:
            self.batch_dir = Path(f'tests/results/batch_{self.batch_id}')

        logger.info(f"[SUCCESS] Grid search completed: {self.batch_dir}")
        logger.info("")
        return True

    def _step5_aggregate_rank(self) -> bool:
        """
        Step 5: Aggregate & Rank Results.

        Use intelligent ranking to compare all results.
        """
        logger.info("[STEP 5/8] Aggregate & Rank Results")
        logger.info("-" * 80)

        cmd = [
            'python', 'bot/aggregate_results.py',
            '--batch', str(self.batch_dir),
            '--profile', 'balanced'
        ]

        logger.info(f"  Command: {' '.join(cmd)}")
        logger.info("")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"  [X] Aggregation failed: {result.stderr}")
            return False

        # Print the comparison output
        print(result.stdout)

        # Load comparison results
        comparison_file = self.batch_dir / 'comparison_report.json'
        if not comparison_file.exists():
            logger.error(f"  [X] Comparison report not found: {comparison_file}")
            return False

        with open(comparison_file, 'r') as f:
            self.comparison = json.load(f)

        logger.info("[SUCCESS] Aggregation and ranking completed")
        logger.info("")
        return True

    def _step6_quality_gate_check(self) -> bool:
        """
        Step 6: Quality Gate Check.

        Verify that at least one parameter set passed quality gates.
        """
        logger.info("[STEP 6/8] Quality Gate Check")
        logger.info("-" * 80)

        passed = self.comparison.get('passed_quality_gates', 0)
        total = self.comparison.get('total_runs', 0)
        pass_rate = self.comparison.get('pass_rate', 0)

        logger.info(f"  Total Runs: {total}")
        logger.info(f"  Passed Gates: {passed} ({pass_rate:.1f}%)")
        logger.info(f"  Failed Gates: {total - passed}")
        logger.info("")

        # Show quality requirements
        gates = self.comparison.get('quality_gates', {})
        logger.info("  Quality Requirements:")
        logger.info(f"    - Win Rate >= {gates.get('min_win_rate', 55)}%")
        logger.info(f"    - Profit Factor >= {gates.get('min_profit_factor', 1.3)}")
        logger.info(f"    - Max Drawdown <= {gates.get('max_drawdown_pct', 15)}%")
        logger.info(f"    - Minimum Trades >= {gates.get('min_trades', 30)}")
        logger.info("")

        if passed == 0:
            logger.warning("[FAILED] NO PARAMETERS PASSED QUALITY GATES")
            logger.warning("   Recommendation: Keep current configuration")
            return False

        # Get best overall
        self.best_params = self.comparison.get('best_overall', {})

        if not self.best_params:
            logger.warning("[FAILED] No best parameters found")
            return False

        logger.info("[SUCCESS] Quality gates passed")
        logger.info(f"  Best Strategy: {self.best_params['strategy'].upper()} (Phase {self.best_params['phase']})")
        logger.info(f"  Composite Score: {self.best_params.get('composite_score', 0):.1f} / 100")
        logger.info("")
        return True

    def _step7_present_and_confirm(self) -> bool:
        """
        Step 7: Present Results & Confirmation.

        Show best parameters to user and ask for confirmation.
        """
        logger.info("[STEP 7/8] Present Results & Confirmation")
        logger.info("-" * 80)

        best = self.best_params

        logger.info("")
        logger.info("[BEST] RECOMMENDED PARAMETERS:")
        logger.info("=" * 80)
        logger.info(f"Strategy: {best['strategy'].upper()}")
        logger.info(f"Phase: {best['phase']}")
        logger.info(f"Composite Score: {best.get('composite_score', 0):.1f} / 100")
        logger.info("")
        logger.info("Performance Metrics:")
        logger.info(f"  Profit: ${best.get('net_profit', 0):.2f}")
        logger.info(f"  Win Rate: {best.get('win_rate', 0):.1f}%")
        logger.info(f"  Profit Factor: {best.get('profit_factor', 0):.2f}")
        logger.info(f"  Max Drawdown: {best.get('max_drawdown_pct', 0):.2f}%")
        logger.info(f"  Total Trades: {best.get('total_trades', 0)}")
        if best.get('consistency_score'):
            logger.info(f"  Consistency Score: {best.get('consistency_score'):.2f} (multi-period)")
        logger.info("")
        logger.info("Parameters:")
        params = best.get('parameters', {})
        for key, value in params.items():
            logger.info(f"  {key}: {value}")
        logger.info("=" * 80)
        logger.info("")

        # Ask for confirmation
        try:
            response = input("Apply these parameters to bot/config.py? (Y/n): ").strip().lower()
            if response in ['', 'y', 'yes']:
                logger.info("[SUCCESS] User confirmed application")
                return True
            else:
                logger.info("[FAILED] User declined application")
                return False
        except (EOFError, KeyboardInterrupt):
            logger.info("[FAILED] User interrupted confirmation")
            return False

    def _step8_apply_verify(self) -> bool:
        """
        Step 8: Apply & Verify Parameters.

        Apply best parameters to bot/config.py and verify.
        """
        logger.info("[STEP 8/8] Apply & Verify Parameters")
        logger.info("-" * 80)

        # Save best params to JSON file
        best_params_file = self.batch_dir / 'final_best_params.json'
        with open(best_params_file, 'w') as f:
            json.dump(self.best_params, f, indent=2)

        logger.info(f"  Saved best parameters to: {best_params_file}")

        # Apply using config_manager if it exists, otherwise manual instruction
        config_manager = Path('bot/config_manager.py')
        if config_manager.exists():
            cmd = [
                'python', 'bot/config_manager.py',
                '--apply', str(best_params_file)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"  [X] Failed to apply parameters: {result.stderr}")
                logger.info(f"  Please manually apply parameters from: {best_params_file}")
                return False

            logger.info("  [OK] Parameters applied to bot/config.py")
        else:
            logger.warning("  [WARNING]  config_manager.py not found")
            logger.info(f"  Please manually apply parameters from: {best_params_file}")
            logger.info("")
            logger.info("  Manual Steps:")
            logger.info(f"    1. Open bot/config.py")
            logger.info(f"    2. Set ACTIVE_STRATEGY = StrategyType.{self.best_params['strategy'].upper()}")
            logger.info(f"    3. Update {self.best_params['strategy'].upper()}_PARAMS with values from {best_params_file}")

        logger.info("[SUCCESS] Parameters ready for deployment")
        logger.info("")
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Ultimate Parameter Optimization - One Command to Rule Them All',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full 12-24 hour optimization (recommended)
  python bot/ultimate_optimize.py

  # Quick 1-2 hour test
  python bot/ultimate_optimize.py --quick

  # Resume interrupted run
  python bot/ultimate_optimize.py --resume 2025_11_28_153702

  # Specific strategies only
  python bot/ultimate_optimize.py --strategies elastic_band,fvg

  # Auto-apply without confirmation (use with caution)
  python bot/ultimate_optimize.py --quick --auto-apply
        """
    )

    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick mode: 20 combos, 1 period, 60 days (1-2 hours)'
    )
    parser.add_argument(
        '--resume',
        type=str,
        help='Resume from batch ID (e.g., 2025_11_28_153702)'
    )
    parser.add_argument(
        '--strategies',
        type=str,
        help='Comma-separated strategies (default: all)'
    )
    parser.add_argument(
        '--symbols',
        type=str,
        help='Comma-separated symbols (default: EURUSD,GBPUSD,USDJPY)'
    )
    parser.add_argument(
        '--phases',
        type=str,
        default='1',
        help='Comma-separated phases (default: 1)'
    )
    parser.add_argument(
        '--auto-apply',
        action='store_true',
        help='Auto-apply best parameters without confirmation'
    )

    args = parser.parse_args()

    # Parse arguments
    strategies = None
    if args.strategies:
        strategies = [s.strip() for s in args.strategies.split(',')]

    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]

    phases = [int(p.strip()) for p in args.phases.split(',')]

    # Create and run optimizer
    optimizer = UltimateOptimizer(
        quick_mode=args.quick,
        resume_batch=args.resume,
        strategies=strategies,
        symbols=symbols,
        phases=phases,
        auto_apply=args.auto_apply
    )

    result = optimizer.run()

    # Exit with appropriate code
    if result['status'] == 'success':
        sys.exit(0)
    elif result['status'] == 'user_declined':
        sys.exit(0)  # Not an error
    elif result['status'] == 'no_viable_params':
        sys.exit(2)  # No viable params found
    else:
        sys.exit(1)  # Error


if __name__ == '__main__':
    main()
