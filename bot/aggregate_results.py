"""
Results Aggregator - Unified Multi-Strategy Comparison.

Aggregates and compares results across multiple strategies and phases.
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.intelligent_ranker import IntelligentRanker, QualityGates, create_ranker

logger = setup_logger("AGGREGATOR")


class ResultsAggregator:
    """Aggregates and compares results from multiple grid search runs."""

    def __init__(
        self,
        batch_dir: Optional[str] = None,
        run_dirs: Optional[List[str]] = None,
        ranking_profile: str = 'balanced',
        quality_gates: Optional[QualityGates] = None
    ):
        """
        Initialize aggregator.

        Args:
            batch_dir: Directory containing batch_metadata.json from batch run.
            run_dirs: List of individual run directories to compare.
            ranking_profile: Ranking profile ('balanced', 'aggressive', 'conservative', 'challenge')
            quality_gates: Custom quality gates (uses defaults if None)
        """
        self.results = []
        self.batch_dir = Path(batch_dir) if batch_dir else None
        self.run_dirs = [Path(d) for d in run_dirs] if run_dirs else []

        # Create intelligent ranker
        if quality_gates:
            self.ranker = IntelligentRanker(quality_gates=quality_gates)
        else:
            self.ranker = create_ranker(ranking_profile)

    def load_results(self):
        """Load results from batch or individual runs."""
        if self.batch_dir:
            self._load_batch_results()
        elif self.run_dirs:
            self._load_individual_results()
        else:
            raise ValueError("Must provide either batch_dir or run_dirs")

    def _load_batch_results(self):
        """Load results from a batch run."""
        metadata_file = self.batch_dir / "batch_metadata.json"

        if not metadata_file.exists():
            raise FileNotFoundError(f"Batch metadata not found: {metadata_file}")

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        logger.info(f"Loading batch results: {metadata['batch_id']}")

        for run_key, run_data in metadata['results'].items():
            if run_data['status'] != 'success':
                logger.warning(f"Skipping failed run: {run_key}")
                continue

            run_dir = Path(run_data['run_dir'])
            self._load_run_result(run_dir, run_data['strategy'], run_data['phase'])

    def _load_individual_results(self):
        """Load results from individual run directories."""
        for run_dir in self.run_dirs:
            # Try to determine strategy and phase from metadata
            metadata_file = run_dir / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    strategy = metadata.get('strategy', 'unknown')
                    phase = metadata.get('phase', 1)
            else:
                # Try to parse from directory name
                strategy = run_dir.parent.name
                phase = 1

            self._load_run_result(run_dir, strategy, phase)

    def _load_run_result(self, run_dir: Path, strategy: str, phase: int):
        """Load a single run result."""
        best_params_file = run_dir / "best_params.json"
        recommended_params_file = run_dir / "recommended_params.json"
        metadata_file = run_dir / "metadata.json"

        if not best_params_file.exists():
            logger.warning(f"best_params.json not found in {run_dir}")
            return

        with open(best_params_file, 'r') as f:
            best_params = json.load(f)

        recommended_params = None
        if recommended_params_file.exists():
            with open(recommended_params_file, 'r') as f:
                recommended_params = json.load(f)

        metadata = None
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

        result = {
            'run_dir': str(run_dir),
            'strategy': strategy,
            'phase': phase,
            'best_params': best_params,
            'recommended_params': recommended_params,
            'metadata': metadata
        }

        self.results.append(result)

    def generate_comparison(self) -> Dict[str, Any]:
        """
        Generate unified comparison across all loaded results.

        Uses IntelligentRanker for composite scoring and quality gates.

        Returns:
            Dictionary with comparison data.
        """
        if not self.results:
            logger.error("No results loaded")
            return {}

        logger.info(f"Comparing {len(self.results)} grid search runs")

        # Prepare data for intelligent ranker
        all_result_data = []
        # Known metric fields to exclude from parameters
        metric_fields = {'profit', 'win_rate', 'profit_factor', 'max_drawdown_pct',
                        'total_trades', 'consistency_score', 'composite_score'}

        for result in self.results:
            best = result['best_params']

            # Extract parameters (exclude metric fields)
            parameters = {k: v for k, v in best.items() if k not in metric_fields}

            result_data = {
                'strategy': result['strategy'],
                'phase': result['phase'],
                'run_dir': result['run_dir'],
                'net_profit': best.get('profit', 0),
                'win_rate': best.get('win_rate', 0),
                'profit_factor': best.get('profit_factor', 0),
                'max_drawdown_pct': best.get('max_drawdown_pct', 0),
                'total_trades': best.get('total_trades', 0),
                'consistency_score': best.get('consistency_score'),  # If available from multi-period
                'parameters': parameters
            }
            all_result_data.append(result_data)

        # Apply intelligent ranking
        logger.info("Applying quality gates and composite scoring...")
        ranked_results = self.ranker.rank_results(all_result_data, apply_gates=True)

        # Generate comparison report
        comparison = {
            'total_runs': len(self.results),
            'passed_quality_gates': len(ranked_results),
            'failed_quality_gates': len(self.results) - len(ranked_results),
            'pass_rate': (len(ranked_results) / len(self.results) * 100) if self.results else 0,
            'rankings': {
                'by_composite_score': ranked_results,  # Already sorted by composite score
                'by_profit': self._rank_by_metric('profit'),
                'by_win_rate': self._rank_by_metric('win_rate'),
                'by_profit_factor': self._rank_by_metric('profit_factor'),
                'by_lowest_drawdown': self._rank_by_metric('max_drawdown_pct', reverse=True),
                'by_risk_adjusted': self._rank_by_risk_adjusted()
            },
            'best_overall': ranked_results[0] if ranked_results else {},
            'quality_gates': {
                'min_win_rate': self.ranker.quality_gates.min_win_rate,
                'min_profit_factor': self.ranker.quality_gates.min_profit_factor,
                'max_drawdown_pct': self.ranker.quality_gates.max_drawdown_pct,
                'min_trades': self.ranker.quality_gates.min_trades,
            },
            'timestamp': datetime.now().isoformat()
        }

        return comparison

    def _rank_by_metric(self, metric: str, reverse: bool = False) -> List[Dict[str, Any]]:
        """Rank results by a specific metric."""
        ranked = []

        for result in self.results:
            best = result['best_params']
            value = best.get(metric, 0 if not reverse else float('inf'))

            ranked.append({
                'strategy': result['strategy'],
                'phase': result['phase'],
                'run_dir': result['run_dir'],
                'value': value,
                'profit': best.get('profit', 0),
                'win_rate': best.get('win_rate', 0),
                'total_trades': best.get('total_trades', 0),
                'max_drawdown_pct': best.get('max_drawdown_pct', 0),
                'parameters': best.get('parameters', {})
            })

        # Sort by value (descending for most metrics, ascending for drawdown)
        ranked.sort(key=lambda x: x['value'], reverse=not reverse)

        return ranked

    def _rank_by_risk_adjusted(self) -> List[Dict[str, Any]]:
        """Rank by risk-adjusted returns (profit / max_drawdown)."""
        ranked = []

        for result in self.results:
            best = result['best_params']
            profit = best.get('profit', 0)
            max_dd = best.get('max_drawdown_pct', 0.01)  # Avoid division by zero

            # Calculate risk-adjusted return (higher is better)
            risk_adjusted = profit / max_dd if max_dd > 0 else 0

            ranked.append({
                'strategy': result['strategy'],
                'phase': result['phase'],
                'run_dir': result['run_dir'],
                'value': risk_adjusted,
                'profit': profit,
                'win_rate': best.get('win_rate', 0),
                'max_drawdown_pct': max_dd,
                'total_trades': best.get('total_trades', 0),
                'parameters': best.get('parameters', {})
            })

        ranked.sort(key=lambda x: x['value'], reverse=True)

        return ranked

    def _determine_best_overall(self) -> Dict[str, Any]:
        """Determine best overall strategy/phase combination."""
        # Use risk-adjusted return as the primary metric
        risk_adjusted_ranking = self._rank_by_risk_adjusted()

        if not risk_adjusted_ranking:
            return {}

        best = risk_adjusted_ranking[0]

        return {
            'strategy': best['strategy'],
            'phase': best['phase'],
            'profit': best['profit'],
            'win_rate': best['win_rate'],
            'max_drawdown_pct': best['max_drawdown_pct'],
            'risk_adjusted_score': best['value'],
            'total_trades': best['total_trades'],
            'parameters': best['parameters'],
            'run_dir': best['run_dir']
        }

    def print_comparison(self, comparison: Dict[str, Any]):
        """Print comparison report to console."""
        logger.info("")
        logger.info("=" * 100)
        logger.info("MULTI-STRATEGY COMPARISON REPORT (Intelligent Ranking)")
        logger.info("=" * 100)
        logger.info(f"Total Runs Compared: {comparison['total_runs']}")
        logger.info(f"Passed Quality Gates: {comparison['passed_quality_gates']} ({comparison['pass_rate']:.1f}%)")
        logger.info(f"Failed Quality Gates: {comparison['failed_quality_gates']}")
        logger.info("")
        logger.info("Quality Gate Requirements:")
        gates = comparison['quality_gates']
        logger.info(f"  - Win Rate >= {gates['min_win_rate']}%")
        logger.info(f"  - Profit Factor >= {gates['min_profit_factor']}")
        logger.info(f"  - Max Drawdown <= {gates['max_drawdown_pct']}%")
        logger.info(f"  - Minimum Trades >= {gates['min_trades']}")
        logger.info("=" * 100)

        # Best Overall
        logger.info("")
        logger.info("-" * 100)
        logger.info("[BEST] BEST OVERALL (Composite Score)")
        logger.info("-" * 100)
        best = comparison['best_overall']
        if best:
            logger.info(f"Strategy: {best['strategy'].upper()} (Phase {best['phase']})")
            logger.info(f"Composite Score: {best.get('composite_score', 0):.2f} / 100")
            logger.info(f"Profit: ${best.get('net_profit', 0):.2f}")
            logger.info(f"Win Rate: {best.get('win_rate', 0):.1f}%")
            logger.info(f"Profit Factor: {best.get('profit_factor', 0):.2f}")
            logger.info(f"Max Drawdown: {best.get('max_drawdown_pct', 0):.2f}%")
            logger.info(f"Total Trades: {best.get('total_trades', 0)}")
            if best.get('consistency_score') is not None:
                logger.info(f"Consistency Score: {best.get('consistency_score'):.2f} (multi-period)")
            logger.info(f"Parameters: {json.dumps(best.get('parameters', {}), indent=2)}")
            logger.info(f"Results: {best.get('run_dir', '')}")
        else:
            logger.warning("[FAILED] NO PARAMETERS PASSED QUALITY GATES!")

        # Top 5 by Composite Score
        logger.info("")
        logger.info("-" * 100)
        logger.info("[TOP 5] BY COMPOSITE SCORE (Recommended)")
        logger.info("-" * 100)
        logger.info(f"{'Rank':<6} {'Strategy':<20} {'Phase':<7} {'Score':<12} {'Profit':<10} {'Win Rate':<10} {'Max DD':<10}")
        logger.info("-" * 100)

        composite_ranking = comparison['rankings'].get('by_composite_score', [])
        for i, item in enumerate(composite_ranking[:5], 1):
            logger.info(
                f"{i:<6} {item['strategy'].upper():<20} {item['phase']:<7} "
                f"{item.get('composite_score', 0):<11.1f} ${item.get('net_profit', 0):<9.2f} "
                f"{item.get('win_rate', 0):<9.1f}% {item.get('max_drawdown_pct', 0):<9.2f}%"
            )

        # Top 5 by Profit
        logger.info("")
        logger.info("-" * 100)
        logger.info("[TOP 5] BY PROFIT")
        logger.info("-" * 100)
        logger.info(f"{'Rank':<6} {'Strategy':<20} {'Phase':<7} {'Profit':<12} {'Win Rate':<10} {'Trades':<8}")
        logger.info("-" * 100)

        for i, item in enumerate(comparison['rankings']['by_profit'][:5], 1):
            logger.info(
                f"{i:<6} {item['strategy'].upper():<20} {item['phase']:<7} "
                f"${item['profit']:<11.2f} {item['win_rate']:<9.1f}% {item['total_trades']:<8}"
            )

        # Top 5 by Win Rate
        logger.info("")
        logger.info("-" * 100)
        logger.info("[TOP 5] BY WIN RATE")
        logger.info("-" * 100)
        logger.info(f"{'Rank':<6} {'Strategy':<20} {'Phase':<7} {'Win Rate':<12} {'Profit':<10} {'Trades':<8}")
        logger.info("-" * 100)

        for i, item in enumerate(comparison['rankings']['by_win_rate'][:5], 1):
            logger.info(
                f"{i:<6} {item['strategy'].upper():<20} {item['phase']:<7} "
                f"{item['win_rate']:<11.1f}% ${item['profit']:<9.2f} {item['total_trades']:<8}"
            )

        # Top 5 by Lowest Drawdown (Safest)
        logger.info("")
        logger.info("-" * 100)
        logger.info("[TOP 5] BY LOWEST DRAWDOWN (Safest)")
        logger.info("-" * 100)
        logger.info(f"{'Rank':<6} {'Strategy':<20} {'Phase':<7} {'Max DD':<12} {'Profit':<10} {'Win Rate':<10}")
        logger.info("-" * 100)

        for i, item in enumerate(comparison['rankings']['by_lowest_drawdown'][:5], 1):
            logger.info(
                f"{i:<6} {item['strategy'].upper():<20} {item['phase']:<7} "
                f"{item['max_drawdown_pct']:<11.2f}% ${item['profit']:<9.2f} {item['win_rate']:<9.1f}%"
            )

        # Top 5 by Risk-Adjusted
        logger.info("")
        logger.info("-" * 100)
        logger.info("[TOP 5] BY RISK-ADJUSTED RETURN (Recommended)")
        logger.info("-" * 100)
        logger.info(f"{'Rank':<6} {'Strategy':<20} {'Phase':<7} {'Score':<12} {'Profit':<10} {'Max DD':<10}")
        logger.info("-" * 100)

        for i, item in enumerate(comparison['rankings']['by_risk_adjusted'][:5], 1):
            logger.info(
                f"{i:<6} {item['strategy'].upper():<20} {item['phase']:<7} "
                f"{item['value']:<11.2f} ${item['profit']:<9.2f} {item['max_drawdown_pct']:<9.2f}%"
            )

        logger.info("")
        logger.info("=" * 100)

    def save_comparison(self, comparison: Dict[str, Any], output_file: str):
        """Save comparison to JSON file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(comparison, f, indent=2)

        logger.info(f"Saved comparison report to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Aggregate and compare results from multiple grid search runs with intelligent ranking'
    )
    parser.add_argument(
        '--batch',
        type=str,
        help='Batch directory containing batch_metadata.json'
    )
    parser.add_argument(
        '--runs',
        type=str,
        help='Comma-separated list of run directories to compare'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for comparison JSON (optional)'
    )
    parser.add_argument(
        '--profile',
        type=str,
        choices=['balanced', 'aggressive', 'conservative', 'challenge'],
        default='balanced',
        help='Ranking profile (default: balanced)'
    )

    args = parser.parse_args()

    if not args.batch and not args.runs:
        parser.error("Must provide either --batch or --runs")

    logger.info(f"Using ranking profile: {args.profile}")

    # Create aggregator
    if args.batch:
        aggregator = ResultsAggregator(batch_dir=args.batch, ranking_profile=args.profile)
    else:
        run_dirs = [d.strip() for d in args.runs.split(',')]
        aggregator = ResultsAggregator(run_dirs=run_dirs, ranking_profile=args.profile)

    # Load and compare results
    aggregator.load_results()
    comparison = aggregator.generate_comparison()

    # Print comparison
    aggregator.print_comparison(comparison)

    # Save to file if requested
    if args.output:
        aggregator.save_comparison(comparison, args.output)
    elif args.batch:
        # Auto-save to batch directory
        output_file = Path(args.batch) / "comparison_report.json"
        aggregator.save_comparison(comparison, str(output_file))


if __name__ == '__main__':
    main()
