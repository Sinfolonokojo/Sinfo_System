"""
Intelligent Parameter Ranking System.

Multi-objective optimization with quality gates for parameter selection.
Provides composite scoring that balances profit, risk, and consistency.
"""

import numpy as np
from typing import Dict, List, Optional, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import setup_logger

logger = setup_logger("RANKER")


class QualityGates:
    """Quality gate thresholds for parameter filtering."""

    def __init__(
        self,
        min_win_rate: float = 55.0,
        min_profit_factor: float = 1.3,
        max_drawdown_pct: float = 15.0,
        min_trades: int = 30
    ):
        self.min_win_rate = min_win_rate
        self.min_profit_factor = min_profit_factor
        self.max_drawdown_pct = max_drawdown_pct
        self.min_trades = min_trades

    def passes(self, result: Dict[str, Any]) -> bool:
        """
        Check if a result passes all quality gates.

        Args:
            result: Backtest result dictionary

        Returns:
            True if all gates passed, False otherwise
        """
        checks = {
            'win_rate': result.get('win_rate', 0) >= self.min_win_rate,
            'profit_factor': result.get('profit_factor', 0) >= self.min_profit_factor,
            'max_drawdown': result.get('max_drawdown_pct', 999) <= self.max_drawdown_pct,
            'trades': result.get('total_trades', 0) >= self.min_trades,
        }

        return all(checks.values())

    def get_failed_gates(self, result: Dict[str, Any]) -> List[str]:
        """Get list of failed quality gates for a result."""
        failed = []

        if result.get('win_rate', 0) < self.min_win_rate:
            failed.append(f"Win Rate: {result.get('win_rate', 0):.1f}% < {self.min_win_rate}%")

        if result.get('profit_factor', 0) < self.min_profit_factor:
            failed.append(f"Profit Factor: {result.get('profit_factor', 0):.2f} < {self.min_profit_factor}")

        if result.get('max_drawdown_pct', 999) > self.max_drawdown_pct:
            failed.append(f"Max Drawdown: {result.get('max_drawdown_pct', 999):.1f}% > {self.max_drawdown_pct}%")

        if result.get('total_trades', 0) < self.min_trades:
            failed.append(f"Total Trades: {result.get('total_trades', 0)} < {self.min_trades}")

        return failed


class IntelligentRanker:
    """
    Multi-objective parameter ranking system.

    Combines multiple metrics into a composite score with configurable weights.
    Applies quality gates to filter out unacceptable parameters.
    """

    def __init__(
        self,
        quality_gates: Optional[QualityGates] = None,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize ranker.

        Args:
            quality_gates: Quality gate thresholds (uses defaults if None)
            weights: Metric weights for composite scoring (uses balanced if None)
        """
        self.quality_gates = quality_gates or QualityGates()

        # Default balanced weights (risk-adjusted focus)
        self.weights = weights or {
            'profit': 0.30,      # 30% - Absolute returns
            'win_rate': 0.20,    # 20% - Consistency
            'profit_factor': 0.15,  # 15% - Quality of wins
            'drawdown': 0.25,    # 25% - Risk (most important for prop firms)
            'trades': 0.10,      # 10% - Sample size confidence
        }

        # Ensure weights sum to 1.0
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Weights sum to {total_weight}, normalizing to 1.0")
            for key in self.weights:
                self.weights[key] /= total_weight

    def normalize(
        self,
        value: float,
        min_val: float,
        max_val: float,
        invert: bool = False
    ) -> float:
        """
        Normalize a value to 0-100 scale.

        Args:
            value: Value to normalize
            min_val: Minimum expected value
            max_val: Maximum expected value
            invert: If True, higher input = lower output (for drawdown)

        Returns:
            Normalized value between 0-100
        """
        if max_val == min_val:
            return 50.0  # Neutral score if no range

        # Clamp to range
        value = max(min_val, min(value, max_val))

        # Normalize to 0-100
        normalized = ((value - min_val) / (max_val - min_val)) * 100

        if invert:
            normalized = 100 - normalized

        return normalized

    def calculate_composite_score(self, result: Dict[str, Any]) -> Optional[float]:
        """
        Calculate composite score for a result.

        Returns None if quality gates not met (auto-reject).

        Args:
            result: Backtest result dictionary with metrics

        Returns:
            Composite score (0-100) or None if rejected
        """
        # Apply quality gates first
        if not self.quality_gates.passes(result):
            return None

        # Extract metrics
        profit = result.get('net_profit', 0)
        win_rate = result.get('win_rate', 0)
        profit_factor = result.get('profit_factor', 0)
        max_dd = result.get('max_drawdown_pct', 0)
        total_trades = result.get('total_trades', 0)

        # Normalize each metric to 0-100 scale
        # Ranges based on typical prop firm trading results
        profit_score = self.normalize(profit, 0, 10000)  # $0 to $10k
        wr_score = self.normalize(win_rate, 50, 80)      # 50% to 80%
        pf_score = self.normalize(profit_factor, 1.0, 3.0)  # 1.0 to 3.0
        dd_score = self.normalize(max_dd, 0, 20, invert=True)  # 0% to 20% (lower better)
        trades_score = self.normalize(total_trades, 30, 200)  # 30 to 200 trades

        # Weighted combination
        composite = (
            profit_score * self.weights['profit'] +
            wr_score * self.weights['win_rate'] +
            pf_score * self.weights['profit_factor'] +
            dd_score * self.weights['drawdown'] +
            trades_score * self.weights['trades']
        )

        # Apply robustness bonus if consistency score available
        if result.get('consistency_score') is not None:
            # Reward low variance across time periods (up to 20% bonus)
            consistency = result['consistency_score']
            composite *= (1.0 + consistency * 0.2)

        return composite

    def apply_quality_gates(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter results by quality gates.

        Args:
            results: List of backtest results

        Returns:
            List of results that passed quality gates
        """
        passed = []

        for result in results:
            if self.quality_gates.passes(result):
                passed.append(result)

        if len(passed) == 0:
            logger.warning("⚠️  NO PARAMETERS PASSED QUALITY GATES!")
            logger.warning("   Quality Requirements:")
            logger.warning(f"   - Win Rate >= {self.quality_gates.min_win_rate}%")
            logger.warning(f"   - Profit Factor >= {self.quality_gates.min_profit_factor}")
            logger.warning(f"   - Max Drawdown <= {self.quality_gates.max_drawdown_pct}%")
            logger.warning(f"   - Minimum Trades >= {self.quality_gates.min_trades}")
        else:
            logger.info(f"✓ {len(passed)} / {len(results)} parameters passed quality gates ({len(passed)/len(results)*100:.1f}%)")

        return passed

    def rank_results(
        self,
        results: List[Dict[str, Any]],
        apply_gates: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Rank results by composite score.

        Args:
            results: List of backtest results
            apply_gates: If True, filter by quality gates first

        Returns:
            Sorted list of results (best first) with composite_score added
        """
        # Apply quality gates if requested
        if apply_gates:
            results = self.apply_quality_gates(results)

        if not results:
            return []

        # Calculate composite score for each result
        for result in results:
            score = self.calculate_composite_score(result)
            result['composite_score'] = score if score is not None else 0

        # Sort by composite score (highest first)
        ranked = sorted(
            results,
            key=lambda x: x.get('composite_score', 0),
            reverse=True
        )

        return ranked

    def generate_recommendations(
        self,
        results: List[Dict[str, Any]],
        top_n: int = 10
    ) -> Dict[str, Any]:
        """
        Generate top N recommendations with detailed analysis.

        Args:
            results: List of backtest results
            top_n: Number of top results to return

        Returns:
            Dictionary with top recommendations and summary stats
        """
        # Rank results
        ranked = self.rank_results(results, apply_gates=True)

        if not ranked:
            return {
                'passed_gates': False,
                'total_tested': len(results),
                'total_passed': 0,
                'top_recommendations': [],
                'summary': 'No parameters met quality gate requirements'
            }

        # Get top N
        top_results = ranked[:top_n]

        # Calculate summary statistics
        summary = {
            'passed_gates': True,
            'total_tested': len(results),
            'total_passed': len(ranked),
            'pass_rate': len(ranked) / len(results) * 100,
            'top_recommendations': top_results,
            'best_composite_score': top_results[0].get('composite_score', 0),
            'best_profit': top_results[0].get('net_profit', 0),
            'best_win_rate': top_results[0].get('win_rate', 0),
            'best_strategy': top_results[0].get('strategy', 'Unknown'),
            'best_phase': top_results[0].get('phase', 'Unknown'),
        }

        return summary


# Preset ranking profiles for different user goals
RANKING_PROFILES = {
    'balanced': {
        'weights': {
            'profit': 0.30,
            'win_rate': 0.20,
            'profit_factor': 0.15,
            'drawdown': 0.25,
            'trades': 0.10,
        },
        'description': 'Risk-adjusted returns (DEFAULT)'
    },
    'aggressive': {
        'weights': {
            'profit': 0.50,
            'win_rate': 0.10,
            'profit_factor': 0.15,
            'drawdown': 0.15,
            'trades': 0.10,
        },
        'description': 'Maximum profit, higher risk tolerance'
    },
    'conservative': {
        'weights': {
            'profit': 0.15,
            'win_rate': 0.25,
            'profit_factor': 0.10,
            'drawdown': 0.40,
            'trades': 0.10,
        },
        'description': 'Capital preservation, minimum drawdown'
    },
    'challenge': {
        'weights': {
            'profit': 0.45,
            'win_rate': 0.15,
            'profit_factor': 0.05,
            'drawdown': 0.30,
            'trades': 0.05,
        },
        'description': 'Optimized for passing 10% prop firm challenge'
    }
}


def create_ranker(profile: str = 'balanced', **kwargs) -> IntelligentRanker:
    """
    Create an IntelligentRanker with a preset profile.

    Args:
        profile: Profile name ('balanced', 'aggressive', 'conservative', 'challenge')
        **kwargs: Override quality gate thresholds

    Returns:
        Configured IntelligentRanker instance
    """
    if profile not in RANKING_PROFILES:
        logger.warning(f"Unknown profile '{profile}', using 'balanced'")
        profile = 'balanced'

    weights = RANKING_PROFILES[profile]['weights']
    quality_gates = QualityGates(**kwargs) if kwargs else QualityGates()

    return IntelligentRanker(quality_gates=quality_gates, weights=weights)


if __name__ == "__main__":
    # Example usage
    logger.info("Testing IntelligentRanker...")

    # Sample results
    test_results = [
        {
            'strategy': 'FVG',
            'phase': 'Phase 1',
            'net_profit': 2847,
            'win_rate': 62.3,
            'profit_factor': 2.41,
            'max_drawdown_pct': 8.2,
            'total_trades': 178,
            'consistency_score': 0.89,
        },
        {
            'strategy': 'Elastic Band',
            'phase': 'Phase 1',
            'net_profit': 2341,
            'win_rate': 58.7,
            'profit_factor': 1.98,
            'max_drawdown_pct': 11.4,
            'total_trades': 156,
            'consistency_score': 0.82,
        },
        {
            'strategy': 'Bad Strategy',
            'phase': 'Phase 1',
            'net_profit': 500,
            'win_rate': 48.0,  # Fails win rate gate
            'profit_factor': 1.1,  # Fails PF gate
            'max_drawdown_pct': 22.0,  # Fails DD gate
            'total_trades': 15,  # Fails trade count
        }
    ]

    # Test ranker
    ranker = create_ranker('balanced')
    recommendations = ranker.generate_recommendations(test_results, top_n=5)

    logger.info(f"\nResults:")
    logger.info(f"  Passed Gates: {recommendations['passed_gates']}")
    logger.info(f"  Total Tested: {recommendations['total_tested']}")
    logger.info(f"  Total Passed: {recommendations['total_passed']}")
    logger.info(f"  Pass Rate: {recommendations['pass_rate']:.1f}%")
    logger.info(f"\nTop Recommendation:")
    if recommendations['top_recommendations']:
        top = recommendations['top_recommendations'][0]
        logger.info(f"  Strategy: {top['strategy']}")
        logger.info(f"  Composite Score: {top['composite_score']:.1f}")
        logger.info(f"  Profit: ${top['net_profit']:.2f}")
        logger.info(f"  Win Rate: {top['win_rate']:.1f}%")
