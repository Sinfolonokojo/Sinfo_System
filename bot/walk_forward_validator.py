"""
Walk-Forward Validation Module.

Implements train/test split validation to detect overfitting.
Parameters are optimized on training data and validated on out-of-sample test data.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.config import TradingPhase

logger = setup_logger("WALK_FORWARD")


class WalkForwardValidator:
    """
    Walk-forward validation for parameter testing.

    Splits historical data into training and testing periods to detect overfitting.
    Rejects parameters that perform significantly worse on out-of-sample data.
    """

    def __init__(
        self,
        train_ratio: float = 0.7,
        min_test_ratio: float = 0.8,
        min_train_trades: int = 20,
        min_test_trades: int = 10
    ):
        """
        Initialize walk-forward validator.

        Args:
            train_ratio: Fraction of data to use for training (0.0-1.0)
            min_test_ratio: Minimum (test_score / train_score) to pass (0.0-1.0)
            min_train_trades: Minimum trades required in training period
            min_test_trades: Minimum trades required in test period
        """
        self.train_ratio = train_ratio
        self.min_test_ratio = min_test_ratio
        self.min_train_trades = min_train_trades
        self.min_test_trades = min_test_trades

        if not 0 < train_ratio < 1:
            raise ValueError("train_ratio must be between 0 and 1")

        if not 0 < min_test_ratio <= 1:
            raise ValueError("min_test_ratio must be between 0 and 1")

    def split_period(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[Tuple[datetime, datetime], Tuple[datetime, datetime]]:
        """
        Split a date range into training and testing periods.

        Args:
            start_date: Overall period start
            end_date: Overall period end

        Returns:
            Tuple of ((train_start, train_end), (test_start, test_end))
        """
        total_days = (end_date - start_date).days
        train_days = int(total_days * self.train_ratio)

        train_start = start_date
        train_end = start_date + timedelta(days=train_days)

        test_start = train_end
        test_end = end_date

        return (train_start, train_end), (test_start, test_end)

    def calculate_score(self, result) -> float:
        """
        Calculate single score from backtest result.

        Uses profit as primary metric, adjusted for win rate and drawdown.

        Args:
            result: Backtest result object

        Returns:
            Composite score for comparison
        """
        # Base score on profit
        score = result.net_profit

        # Adjust for win rate (penalize low win rates)
        if result.win_rate < 50:
            score *= 0.5  # Heavy penalty
        elif result.win_rate < 55:
            score *= 0.8

        # Adjust for drawdown (penalize high drawdown)
        if result.max_drawdown_pct > 15:
            score *= 0.7
        elif result.max_drawdown_pct > 20:
            score *= 0.5

        return score

    def validate(
        self,
        params: Dict[str, Any],
        strategy_class,
        symbol: str,
        phase: TradingPhase,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float = 10000.0
    ) -> Optional[Dict[str, Any]]:
        """
        Perform walk-forward validation on parameters.

        Args:
            params: Parameters to validate
            strategy_class: Strategy class to use
            symbol: Trading symbol
            phase: Trading phase
            start_date: Overall period start
            end_date: Overall period end
            initial_balance: Starting balance

        Returns:
            Validation results dictionary or None if validation failed
        """
        from bot.backtester import Backtester

        # Split into train/test periods
        (train_start, train_end), (test_start, test_end) = self.split_period(
            start_date, end_date
        )

        train_days = (train_end - train_start).days
        test_days = (test_end - test_start).days

        logger.info(f"Walk-Forward Validation for {symbol}:")
        logger.info(f"  Training: {train_start.date()} to {train_end.date()} ({train_days} days)")
        logger.info(f"  Testing:  {test_start.date()} to {test_end.date()} ({test_days} days)")

        # Run training backtest
        train_backtester = Backtester(phase, strategy_class=strategy_class)
        train_result = train_backtester.run(
            symbol, train_start, train_end, initial_balance
        )

        # Run testing backtest (out-of-sample)
        test_backtester = Backtester(phase, strategy_class=strategy_class)
        test_result = test_backtester.run(
            symbol, test_start, test_end, initial_balance
        )

        # Calculate scores
        train_score = self.calculate_score(train_result)
        test_score = self.calculate_score(test_result)

        logger.info(f"  Training Score: {train_score:.2f}")
        logger.info(f"    Profit: ${train_result.net_profit:.2f}, WR: {train_result.win_rate:.1f}%, Trades: {train_result.total_trades}")
        logger.info(f"  Test Score: {test_score:.2f}")
        logger.info(f"    Profit: ${test_result.net_profit:.2f}, WR: {test_result.win_rate:.1f}%, Trades: {test_result.total_trades}")

        # Check minimum trade requirements
        if train_result.total_trades < self.min_train_trades:
            logger.warning(f"  ⚠️  Insufficient training trades: {train_result.total_trades} < {self.min_train_trades}")
            return None

        if test_result.total_trades < self.min_test_trades:
            logger.warning(f"  ⚠️  Insufficient test trades: {test_result.total_trades} < {self.min_test_trades}")
            return None

        # Check for overfitting
        if train_score > 0:
            test_train_ratio = test_score / train_score
        else:
            # If training score is negative or zero, can't validate
            logger.warning("  ⚠️  Training score is not positive, cannot validate")
            return None

        logger.info(f"  Test/Train Ratio: {test_train_ratio:.2%}")

        # Overfitting check
        if test_train_ratio < self.min_test_ratio:
            logger.warning(f"  ❌ OVERFITTED: Test score is {test_train_ratio:.1%} of training (< {self.min_test_ratio:.0%})")
            return None

        logger.info(f"  ✓ Not overfitted ({test_train_ratio:.1%} of training)")

        # Calculate final score (favor out-of-sample performance)
        final_score = train_score * 0.4 + test_score * 0.6

        # Return validation results
        validation_result = {
            'validated': True,
            'overfitted': False,
            'train_score': train_score,
            'test_score': test_score,
            'test_train_ratio': test_train_ratio,
            'final_score': final_score,
            'train_metrics': {
                'net_profit': train_result.net_profit,
                'win_rate': train_result.win_rate,
                'profit_factor': train_result.profit_factor,
                'max_drawdown_pct': train_result.max_drawdown_pct,
                'total_trades': train_result.total_trades,
            },
            'test_metrics': {
                'net_profit': test_result.net_profit,
                'win_rate': test_result.win_rate,
                'profit_factor': test_result.profit_factor,
                'max_drawdown_pct': test_result.max_drawdown_pct,
                'total_trades': test_result.total_trades,
            }
        }

        return validation_result

    def is_overfitted(
        self,
        train_score: float,
        test_score: float
    ) -> bool:
        """
        Determine if parameters are overfitted based on train/test scores.

        Args:
            train_score: Score on training data
            test_score: Score on test data

        Returns:
            True if overfitted, False otherwise
        """
        if train_score <= 0:
            return True  # Can't validate if training isn't profitable

        test_train_ratio = test_score / train_score

        return test_train_ratio < self.min_test_ratio

    def batch_validate(
        self,
        param_sets: list,
        strategy_class,
        symbol: str,
        phase: TradingPhase,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float = 10000.0
    ) -> Dict[str, Any]:
        """
        Validate multiple parameter sets and return only those that pass.

        Args:
            param_sets: List of parameter dictionaries
            strategy_class: Strategy class
            symbol: Trading symbol
            phase: Trading phase
            start_date: Overall period start
            end_date: Overall period end
            initial_balance: Starting balance

        Returns:
            Dictionary with validated and rejected parameter sets
        """
        logger.info(f"\nValidating {len(param_sets)} parameter sets...")

        validated = []
        rejected = []

        for i, params in enumerate(param_sets, 1):
            logger.info(f"\n[{i}/{len(param_sets)}] Validating parameter set...")

            result = self.validate(
                params, strategy_class, symbol, phase,
                start_date, end_date, initial_balance
            )

            if result is not None:
                # Add parameters to result
                result['parameters'] = params
                validated.append(result)
                logger.info("  ✓ VALIDATED")
            else:
                rejected.append({
                    'parameters': params,
                    'reason': 'Overfitted or insufficient trades'
                })
                logger.info("  ✗ REJECTED")

        pass_rate = len(validated) / len(param_sets) * 100 if param_sets else 0

        logger.info(f"\nValidation Summary:")
        logger.info(f"  Total: {len(param_sets)}")
        logger.info(f"  Validated: {len(validated)} ({pass_rate:.1f}%)")
        logger.info(f"  Rejected: {len(rejected)} ({100-pass_rate:.1f}%)")

        return {
            'validated': validated,
            'rejected': rejected,
            'pass_rate': pass_rate,
            'total_tested': len(param_sets)
        }


if __name__ == "__main__":
    # Example usage
    logger.info("Testing WalkForwardValidator...")

    validator = WalkForwardValidator(
        train_ratio=0.7,
        min_test_ratio=0.8,
        min_train_trades=20,
        min_test_trades=10
    )

    # Test date splitting
    start = datetime(2024, 1, 1)
    end = datetime(2024, 12, 31)

    (train_start, train_end), (test_start, test_end) = validator.split_period(start, end)

    logger.info(f"\nDate Split Test:")
    logger.info(f"  Overall: {start.date()} to {end.date()}")
    logger.info(f"  Training: {train_start.date()} to {train_end.date()} ({(train_end-train_start).days} days)")
    logger.info(f"  Testing: {test_start.date()} to {test_end.date()} ({(test_end-test_start).days} days)")

    # Test overfitting detection
    logger.info(f"\nOverfitting Detection:")
    logger.info(f"  Train: 1000, Test: 850, Ratio: 85% → Overfitted: {validator.is_overfitted(1000, 850)}")
    logger.info(f"  Train: 1000, Test: 700, Ratio: 70% → Overfitted: {validator.is_overfitted(1000, 700)}")
    logger.info(f"  Train: 1000, Test: 950, Ratio: 95% → Overfitted: {validator.is_overfitted(1000, 950)}")
