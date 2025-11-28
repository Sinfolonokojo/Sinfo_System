"""
Multi-Period Testing Module.

Tests parameters across multiple historical time periods to ensure robustness
and prevent overfitting to recent market conditions.
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.config import TradingPhase

logger = setup_logger("MULTI_PERIOD")


# Default testing periods configuration
TESTING_PERIODS = [
    {
        'name': 'recent',
        'days_ago_start': 0,
        'days_ago_end': 180,      # Last 6 months
        'weight': 0.50,           # Most weight on recent performance
        'description': 'Recent 6 months (current market conditions)'
    },
    {
        'name': 'medium',
        'days_ago_start': 180,
        'days_ago_end': 365,      # 6-12 months ago
        'weight': 0.30,
        'description': 'Medium period (6-12 months ago)'
    },
    {
        'name': 'older',
        'days_ago_start': 365,
        'days_ago_end': 730,      # 1-2 years ago
        'weight': 0.20,
        'description': 'Older period (1-2 years ago)'
    },
]


class MultiPeriodTester:
    """
    Test parameters across multiple historical time periods.

    Ensures parameters work across different market conditions and
    penalizes overfitting to a single time period.
    """

    def __init__(
        self,
        periods: Optional[List[Dict]] = None,
        num_periods: int = 3
    ):
        """
        Initialize multi-period tester.

        Args:
            periods: Custom period configuration (uses defaults if None)
            num_periods: Number of periods to test (uses first N from config)
        """
        self.periods = periods or TESTING_PERIODS
        self.periods = self.periods[:num_periods]  # Limit to requested count

        # Validate periods
        self._validate_periods()

    def _validate_periods(self):
        """Validate period configuration."""
        if not self.periods:
            raise ValueError("At least one testing period must be defined")

        # Check that weights sum to 1.0
        total_weight = sum(p.get('weight', 0) for p in self.periods)
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Period weights sum to {total_weight}, normalizing to 1.0")
            for period in self.periods:
                period['weight'] /= total_weight

        # Check for overlaps
        for i, p1 in enumerate(self.periods):
            for p2 in self.periods[i+1:]:
                if not (p1['days_ago_end'] <= p2['days_ago_start'] or
                        p2['days_ago_end'] <= p1['days_ago_start']):
                    logger.warning(f"Periods '{p1['name']}' and '{p2['name']}' overlap")

    def get_period_dates(
        self,
        period: Dict,
        reference_date: Optional[datetime] = None
    ) -> Tuple[datetime, datetime]:
        """
        Calculate start and end dates for a period.

        Args:
            period: Period configuration dictionary
            reference_date: Reference date (uses now() if None)

        Returns:
            Tuple of (start_date, end_date)
        """
        if reference_date is None:
            reference_date = datetime.now()

        end_date = reference_date - timedelta(days=period['days_ago_start'])
        start_date = reference_date - timedelta(days=period['days_ago_end'])

        return start_date, end_date

    def test_across_periods(
        self,
        params: Dict[str, Any],
        strategy_class,
        symbol: str,
        phase: TradingPhase,
        initial_balance: float = 10000.0
    ) -> Dict[str, Any]:
        """
        Test parameters across all configured time periods.

        Args:
            params: Parameter dictionary to test
            strategy_class: Strategy class to use
            symbol: Trading symbol
            phase: Trading phase
            initial_balance: Starting balance

        Returns:
            Dictionary with period results and aggregated metrics
        """
        from bot.backtester import Backtester

        logger.info(f"Testing {len(self.periods)} time periods for {symbol}...")

        period_results = []

        for period in self.periods:
            start_date, end_date = self.get_period_dates(period)

            logger.info(f"  Period '{period['name']}': {start_date.date()} to {end_date.date()}")

            # Run backtest for this period
            backtester = Backtester(phase, strategy_class=strategy_class)
            result = backtester.run(symbol, start_date, end_date, initial_balance)

            # Store result with period info
            period_result = {
                'period_name': period['name'],
                'period_weight': period['weight'],
                'start_date': start_date,
                'end_date': end_date,
                'net_profit': result.net_profit,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor,
                'max_drawdown_pct': result.max_drawdown_pct,
                'total_trades': result.total_trades,
                'expectancy': result.expectancy,
            }

            period_results.append(period_result)

            logger.info(f"    Profit: ${result.net_profit:.2f}, WR: {result.win_rate:.1f}%, Trades: {result.total_trades}")

        # Calculate aggregate metrics
        aggregated = self.aggregate_period_results(period_results)

        # Calculate consistency score
        consistency = self.calculate_consistency_score(period_results)
        aggregated['consistency_score'] = consistency

        logger.info(f"  Consistency Score: {consistency:.2f} (0.0=poor, 1.0=excellent)")

        return aggregated

    def aggregate_period_results(
        self,
        period_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate results across periods using weighted average.

        Args:
            period_results: List of results from each period

        Returns:
            Dictionary with weighted aggregate metrics
        """
        if not period_results:
            return {}

        # Weighted sums
        total_profit = sum(r['net_profit'] * r['period_weight'] for r in period_results)
        avg_win_rate = sum(r['win_rate'] * r['period_weight'] for r in period_results)
        avg_pf = sum(r['profit_factor'] * r['period_weight'] for r in period_results if r['profit_factor'] > 0)
        avg_dd = sum(r['max_drawdown_pct'] * r['period_weight'] for r in period_results)
        total_trades = sum(r['total_trades'] for r in period_results)

        aggregated = {
            'net_profit': total_profit,
            'win_rate': avg_win_rate,
            'profit_factor': avg_pf if avg_pf > 0 else 0,
            'max_drawdown_pct': avg_dd,
            'total_trades': total_trades,
            'period_results': period_results,
            'periods_tested': len(period_results),
        }

        return aggregated

    def calculate_consistency_score(
        self,
        period_results: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate consistency score across periods.

        Measures how stable the parameters perform across different
        market conditions. Lower variance = higher score.

        Returns:
            Score from 0.0 (inconsistent) to 1.0 (very consistent)
        """
        if len(period_results) < 2:
            return 1.0  # Can't measure consistency with <2 periods

        # Extract metrics
        profits = [r['net_profit'] for r in period_results]
        win_rates = [r['win_rate'] for r in period_results]

        # Calculate Coefficient of Variation (CV) for each metric
        # CV = std_dev / mean (normalized measure of dispersion)

        # Profit CV
        profit_mean = np.mean(profits)
        if profit_mean > 0:
            profit_cv = np.std(profits) / profit_mean
        else:
            # If mean profit is 0 or negative, use high penalty
            profit_cv = 999

        # Win Rate CV
        wr_mean = np.mean(win_rates)
        if wr_mean > 0:
            wr_cv = np.std(win_rates) / wr_mean
        else:
            wr_cv = 999

        # Combined CV (average)
        combined_cv = (profit_cv + wr_cv) / 2

        # Convert CV to consistency score (0-1 scale)
        # Lower CV = higher consistency
        # CV of 0.5 = moderate consistency
        # CV > 1.0 = poor consistency
        consistency = max(0, min(1, 1 - (combined_cv / 2)))

        # Additional penalty if any period is losing
        losing_periods = sum(1 for p in profits if p < 0)
        if losing_periods > 0:
            consistency *= (1 - losing_periods / len(profits) * 0.5)

        return consistency

    def is_robust(
        self,
        period_results: List[Dict[str, Any]],
        min_consistency: float = 0.5
    ) -> bool:
        """
        Check if parameters are robust across periods.

        Args:
            period_results: Results from each period
            min_consistency: Minimum consistency score required

        Returns:
            True if parameters are robust, False otherwise
        """
        consistency = self.calculate_consistency_score(period_results)

        # Check that no period is significantly losing
        all_positive = all(r['net_profit'] > 0 for r in period_results)

        # Check that win rate is consistent
        win_rates = [r['win_rate'] for r in period_results]
        min_wr = min(win_rates)
        max_wr = max(win_rates)
        wr_range = max_wr - min_wr

        # Robust if:
        # 1. Consistency score above threshold
        # 2. All periods profitable (or at least breakeven)
        # 3. Win rate doesn't vary wildly (within 15%)
        is_robust = (
            consistency >= min_consistency and
            all_positive and
            wr_range <= 15.0
        )

        return is_robust

    def compare_periods(
        self,
        period_results: List[Dict[str, Any]]
    ) -> str:
        """
        Generate human-readable comparison of period results.

        Args:
            period_results: Results from each period

        Returns:
            Formatted string comparing periods
        """
        lines = []
        lines.append("\nMulti-Period Performance:")
        lines.append("-" * 80)
        lines.append(f"{'Period':<15} {'Profit':>12} {'Win Rate':>10} {'PF':>8} {'DD':>8} {'Trades':>8}")
        lines.append("-" * 80)

        for result in period_results:
            lines.append(
                f"{result['period_name']:<15} "
                f"${result['net_profit']:>11.2f} "
                f"{result['win_rate']:>9.1f}% "
                f"{result['profit_factor']:>7.2f} "
                f"{result['max_drawdown_pct']:>7.1f}% "
                f"{result['total_trades']:>8}"
            )

        lines.append("-" * 80)

        # Add consistency metrics
        consistency = self.calculate_consistency_score(period_results)
        lines.append(f"Consistency Score: {consistency:.2f} (0.0=poor, 1.0=excellent)")

        # Profit variance
        profits = [r['net_profit'] for r in period_results]
        profit_range = max(profits) - min(profits)
        lines.append(f"Profit Range: ${profit_range:.2f}")

        # Win rate variance
        win_rates = [r['win_rate'] for r in period_results]
        wr_range = max(win_rates) - min(win_rates)
        lines.append(f"Win Rate Range: {wr_range:.1f}%")

        return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    logger.info("Testing MultiPeriodTester...")

    tester = MultiPeriodTester(num_periods=3)

    # Display configured periods
    logger.info(f"\nConfigured {len(tester.periods)} testing periods:")
    for period in tester.periods:
        start, end = tester.get_period_dates(period)
        logger.info(f"  {period['name']}: {start.date()} to {end.date()} (weight: {period['weight']})")

    # Simulate period results
    test_results = [
        {'period_name': 'recent', 'period_weight': 0.5, 'net_profit': 1234, 'win_rate': 63.1, 'profit_factor': 2.52, 'max_drawdown_pct': 7.2, 'total_trades': 89},
        {'period_name': 'medium', 'period_weight': 0.3, 'net_profit': 891, 'win_rate': 61.8, 'profit_factor': 2.34, 'max_drawdown_pct': 8.5, 'total_trades': 76},
        {'period_name': 'older', 'period_weight': 0.2, 'net_profit': 722, 'win_rate': 62.0, 'profit_factor': 2.37, 'max_drawdown_pct': 9.1, 'total_trades': 68},
    ]

    # Calculate consistency
    consistency = tester.calculate_consistency_score(test_results)
    logger.info(f"\nConsistency Score: {consistency:.2f}")

    # Aggregate results
    aggregated = tester.aggregate_period_results(test_results)
    logger.info(f"\nAggregated Metrics:")
    logger.info(f"  Total Profit: ${aggregated['net_profit']:.2f}")
    logger.info(f"  Avg Win Rate: {aggregated['win_rate']:.1f}%")
    logger.info(f"  Avg Profit Factor: {aggregated['profit_factor']:.2f}")

    # Check robustness
    is_robust = tester.is_robust(test_results, min_consistency=0.7)
    logger.info(f"\nRobust Parameters: {is_robust}")

    # Compare periods
    comparison = tester.compare_periods(test_results)
    logger.info(comparison)
