"""
Results Analyzer - Analyze Grid Search Results.

Analyzes grid search results and ranks parameter combinations.
"""

import argparse
import json
import os
from typing import List, Dict, Any
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger

logger = setup_logger("ANALYZE")


class ResultsAnalyzer:
    """Analyze and rank grid search results."""

    def __init__(self, run_directory: str):
        self.run_dir = run_directory
        self.results = []
        self.metadata = {}

    def load_results(self):
        """Load all results from the run directory."""
        # Load metadata
        metadata_file = os.path.join(self.run_dir, 'metadata.json')
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                self.metadata = json.load(f)

        # Load all combo results
        combo_files = [f for f in os.listdir(self.run_dir) if f.startswith('combo_') and f.endswith('.json')]

        for combo_file in sorted(combo_files):
            file_path = os.path.join(self.run_dir, combo_file)
            with open(file_path, 'r') as f:
                self.results.append(json.load(f))

        logger.info(f"Loaded {len(self.results)} combinations from {self.run_dir}")

    def analyze(self):
        """Analyze and display results."""
        if not self.results:
            logger.error("No results to analyze")
            return

        # Print run info
        logger.info(f"\n{'='*100}")
        logger.info(f"GRID SEARCH RESULTS ANALYSIS")
        logger.info(f"{'='*100}")
        logger.info(f"Run: {os.path.basename(self.run_dir)}")
        logger.info(f"Strategy: {self.metadata.get('strategy', 'Unknown')}")
        logger.info(f"Symbols: {', '.join(self.metadata.get('symbols', []))}")
        logger.info(f"Total Combinations: {len(self.results)}")
        logger.info(f"{'='*100}\n")

        # Rankings by different metrics
        self._rank_by_profit()
        self._rank_by_win_rate()
        self._rank_by_profit_factor()
        self._rank_by_drawdown()
        self._rank_by_sharpe()

        # Overall recommendation
        self._generate_recommendation()

    def _rank_by_profit(self):
        """Rank combinations by total profit."""
        sorted_results = sorted(
            self.results,
            key=lambda x: x['aggregate']['total_profit'],
            reverse=True
        )

        logger.info(f"\n{'─'*100}")
        logger.info("RANKED BY TOTAL PROFIT")
        logger.info(f"{'─'*100}")
        logger.info(f"{'Rank':<6} {'Combo':<8} {'Profit':<14} {'Win Rate':<12} {'Trades':<10} Parameters")
        logger.info(f"{'-'*100}")

        for i, result in enumerate(sorted_results[:10], 1):
            params_str = ', '.join([f"{k}={v}" for k, v in list(result['parameters'].items())[:4]])
            logger.info(
                f"{i:<6} {result['combo_id']:<8} "
                f"${result['aggregate']['total_profit']:<13.2f} "
                f"{result['aggregate']['avg_win_rate']:<11.1f}% "
                f"{result['aggregate']['total_trades']:<10} "
                f"{params_str}"
            )

    def _rank_by_win_rate(self):
        """Rank combinations by win rate."""
        sorted_results = sorted(
            self.results,
            key=lambda x: x['aggregate']['avg_win_rate'],
            reverse=True
        )

        logger.info(f"\n{'─'*100}")
        logger.info("RANKED BY WIN RATE")
        logger.info(f"{'─'*100}")
        logger.info(f"{'Rank':<6} {'Combo':<8} {'Win Rate':<12} {'Profit':<14} {'Trades':<10} Parameters")
        logger.info(f"{'-'*100}")

        for i, result in enumerate(sorted_results[:10], 1):
            params_str = ', '.join([f"{k}={v}" for k, v in list(result['parameters'].items())[:4]])
            logger.info(
                f"{i:<6} {result['combo_id']:<8} "
                f"{result['aggregate']['avg_win_rate']:<11.1f}% "
                f"${result['aggregate']['total_profit']:<13.2f} "
                f"{result['aggregate']['total_trades']:<10} "
                f"{params_str}"
            )

    def _rank_by_profit_factor(self):
        """Rank combinations by average profit factor."""
        # Calculate average profit factor across symbols
        for result in self.results:
            pf_values = [r['profit_factor'] for r in result['results'].values() if r['profit_factor'] > 0]
            result['avg_profit_factor'] = sum(pf_values) / len(pf_values) if pf_values else 0

        sorted_results = sorted(
            self.results,
            key=lambda x: x.get('avg_profit_factor', 0),
            reverse=True
        )

        logger.info(f"\n{'─'*100}")
        logger.info("RANKED BY PROFIT FACTOR")
        logger.info(f"{'─'*100}")
        logger.info(f"{'Rank':<6} {'Combo':<8} {'PF':<8} {'Profit':<14} {'Win Rate':<12} Parameters")
        logger.info(f"{'-'*100}")

        for i, result in enumerate(sorted_results[:10], 1):
            params_str = ', '.join([f"{k}={v}" for k, v in list(result['parameters'].items())[:4]])
            logger.info(
                f"{i:<6} {result['combo_id']:<8} "
                f"{result.get('avg_profit_factor', 0):<7.2f} "
                f"${result['aggregate']['total_profit']:<13.2f} "
                f"{result['aggregate']['avg_win_rate']:<11.1f}% "
                f"{params_str}"
            )

    def _rank_by_drawdown(self):
        """Rank combinations by lowest max drawdown."""
        # Calculate max drawdown across symbols
        for result in self.results:
            dd_values = [r['max_drawdown_pct'] for r in result['results'].values()]
            result['max_drawdown'] = max(dd_values) if dd_values else 100

        sorted_results = sorted(
            self.results,
            key=lambda x: x.get('max_drawdown', 100)
        )

        logger.info(f"\n{'─'*100}")
        logger.info("RANKED BY LOWEST DRAWDOWN (Safest)")
        logger.info(f"{'─'*100}")
        logger.info(f"{'Rank':<6} {'Combo':<8} {'MaxDD':<10} {'Profit':<14} {'Win Rate':<12} Parameters")
        logger.info(f"{'-'*100}")

        for i, result in enumerate(sorted_results[:10], 1):
            params_str = ', '.join([f"{k}={v}" for k, v in list(result['parameters'].items())[:4]])
            logger.info(
                f"{i:<6} {result['combo_id']:<8} "
                f"{result.get('max_drawdown', 0):<9.1f}% "
                f"${result['aggregate']['total_profit']:<13.2f} "
                f"{result['aggregate']['avg_win_rate']:<11.1f}% "
                f"{params_str}"
            )

    def _rank_by_sharpe(self):
        """Rank combinations by risk-adjusted returns (Sharpe-like metric)."""
        # Simple Sharpe approximation: Profit / MaxDD
        for result in self.results:
            profit = result['aggregate']['total_profit']
            max_dd = result.get('max_drawdown', 1)
            result['sharpe_proxy'] = profit / max_dd if max_dd > 0 else 0

        sorted_results = sorted(
            self.results,
            key=lambda x: x.get('sharpe_proxy', 0),
            reverse=True
        )

        logger.info(f"\n{'─'*100}")
        logger.info("RANKED BY RISK-ADJUSTED RETURNS (Profit/DD ratio)")
        logger.info(f"{'─'*100}")
        logger.info(f"{'Rank':<6} {'Combo':<8} {'P/DD':<10} {'Profit':<14} {'MaxDD':<10} Parameters")
        logger.info(f"{'-'*100}")

        for i, result in enumerate(sorted_results[:10], 1):
            params_str = ', '.join([f"{k}={v}" for k, v in list(result['parameters'].items())[:4]])
            logger.info(
                f"{i:<6} {result['combo_id']:<8} "
                f"{result.get('sharpe_proxy', 0):<9.1f} "
                f"${result['aggregate']['total_profit']:<13.2f} "
                f"{result.get('max_drawdown', 0):<9.1f}% "
                f"{params_str}"
            )

    def _generate_recommendation(self):
        """Generate overall recommendation."""
        # Best by profit
        best_profit = max(self.results, key=lambda x: x['aggregate']['total_profit'])

        # Best by win rate
        best_wr = max(self.results, key=lambda x: x['aggregate']['avg_win_rate'])

        # Best by drawdown (lowest)
        best_dd = min(self.results, key=lambda x: x.get('max_drawdown', 100))

        # Best risk-adjusted
        best_sharpe = max(self.results, key=lambda x: x.get('sharpe_proxy', 0))

        logger.info(f"\n{'='*100}")
        logger.info("RECOMMENDATION SUMMARY")
        logger.info(f"{'='*100}\n")

        logger.info(f"BEST FOR MAXIMUM PROFIT:")
        logger.info(f"  Combo: {best_profit['combo_id']}")
        logger.info(f"  Parameters: {best_profit['parameters']}")
        logger.info(f"  Profit: ${best_profit['aggregate']['total_profit']:.2f}")
        logger.info(f"  Win Rate: {best_profit['aggregate']['avg_win_rate']:.1f}%")

        logger.info(f"\nBEST FOR CONSISTENCY (Highest Win Rate):")
        logger.info(f"  Combo: {best_wr['combo_id']}")
        logger.info(f"  Parameters: {best_wr['parameters']}")
        logger.info(f"  Win Rate: {best_wr['aggregate']['avg_win_rate']:.1f}%")
        logger.info(f"  Profit: ${best_wr['aggregate']['total_profit']:.2f}")

        logger.info(f"\nBEST FOR SAFETY (Lowest Drawdown):")
        logger.info(f"  Combo: {best_dd['combo_id']}")
        logger.info(f"  Parameters: {best_dd['parameters']}")
        logger.info(f"  Max Drawdown: {best_dd.get('max_drawdown', 0):.1f}%")
        logger.info(f"  Profit: ${best_dd['aggregate']['total_profit']:.2f}")

        logger.info(f"\nBEST RISK-ADJUSTED (Recommended):")
        logger.info(f"  Combo: {best_sharpe['combo_id']}")
        logger.info(f"  Parameters: {best_sharpe['parameters']}")
        logger.info(f"  Profit/DD Ratio: {best_sharpe.get('sharpe_proxy', 0):.1f}")
        logger.info(f"  Profit: ${best_sharpe['aggregate']['total_profit']:.2f}")
        logger.info(f"  Max Drawdown: {best_sharpe.get('max_drawdown', 0):.1f}%")

        # Save recommended parameters
        rec_file = os.path.join(self.run_dir, 'recommended_params.json')
        with open(rec_file, 'w') as f:
            json.dump({
                'best_profit': best_profit['parameters'],
                'best_win_rate': best_wr['parameters'],
                'best_drawdown': best_dd['parameters'],
                'best_risk_adjusted': best_sharpe['parameters']
            }, f, indent=2)

        logger.info(f"\nRecommended parameters saved to: {rec_file}")
        logger.info(f"{'='*100}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze Grid Search Results")
    parser.add_argument("--run", type=str, required=True,
                       help="Path to grid search run directory")

    args = parser.parse_args()

    if not os.path.exists(args.run):
        logger.error(f"Run directory not found: {args.run}")
        sys.exit(1)

    analyzer = ResultsAnalyzer(args.run)
    analyzer.load_results()
    analyzer.analyze()


if __name__ == "__main__":
    main()
