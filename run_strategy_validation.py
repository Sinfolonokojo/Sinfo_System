"""
Run Strategy Validation - Comprehensive ML-Based Analysis.

Validates the conservative 5% DD strategy using:
- Random Forest classification
- Permutation testing
- SHAP feature importance
"""

import sys
import json
from pathlib import Path
from bot.strategy_validator import StrategyValidator, extract_trade_features
from utils import setup_logger

logger = setup_logger("VALIDATION_RUN")


def load_trade_data_from_files():
    """Load real trade data from backtest JSON files."""
    logger.info("Loading trade data from validation_data folder...")

    all_trades = []
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY']

    for symbol in symbols:
        trade_file = f'tests/validation_data/{symbol}_trades.json'
        if not Path(trade_file).exists():
            logger.warning(f"Trade file not found: {trade_file}")
            continue

        with open(trade_file, 'r') as f:
            trades = json.load(f)

        logger.info(f"  {symbol}: {len(trades)} trades")

        # The trades already have all the features we need from the backtester
        all_trades.extend(trades)

    logger.info(f"Total trades loaded: {len(all_trades)}")
    return all_trades


def print_validation_report(report: dict):
    """Print formatted validation report."""
    print("\n" + "="*80)
    print("STRATEGY VALIDATION REPORT - ML ANALYSIS")
    print("="*80)
    print(f"Timestamp: {report['timestamp']}")
    print(f"Total Trades Analyzed: {report['n_trades']}")
    print(f"Features Used: {report['n_features']}")
    print(f"\nOVERALL CONFIDENCE: {report['confidence_level']}")
    print("="*80)

    # Random Forest Results
    print("\n" + "-"*80)
    print("[1] RANDOM FOREST CLASSIFICATION")
    print("-"*80)
    rf = report['random_forest']
    print(f"Training Accuracy:   {rf['train_accuracy']:.2%}")
    print(f"Testing Accuracy:    {rf['test_accuracy']:.2%}")
    print(f"Cross-Validation:    {rf['cv_mean']:.2%} (+/- {rf['cv_std']:.2%})")
    print(f"ROC-AUC Score:       {rf['roc_auc']:.3f}")
    print(f"\nOverfitting Check:   {abs(rf['train_accuracy'] - rf['test_accuracy']):.2%}")
    print(f"Status: {'PASS' if abs(rf['train_accuracy'] - rf['test_accuracy']) < 0.15 else 'FAIL'}")

    print(f"\nTop 5 Important Features:")
    for i, (feature, importance) in enumerate(rf['feature_importance'][:5], 1):
        print(f"  {i}. {feature:<30} {importance:.4f}")

    # Permutation Test
    print("\n" + "-"*80)
    print("[2] PERMUTATION TEST (Statistical Significance)")
    print("-"*80)
    perm = report['permutation_test']
    print(f"Actual Win Rate:     {perm['actual_win_rate']:.2%}")
    print(f"Random Mean:         {perm['permuted_wr_mean']:.2%}")
    print(f"Actual Profit:       ${perm['actual_profit']:.2f}")
    print(f"Random Mean:         ${perm['permuted_profit_mean']:.2f}")
    print(f"\nP-Value (Profit):    {perm['p_value_profit']:.4f}")
    print(f"P-Value (Win Rate):  {perm['p_value_win_rate']:.4f}")
    print(f"Permutations:        {perm['n_permutations']}")
    print(f"\nStatistically Significant: {perm['statistically_significant']}")
    print(f"Status: {'PASS' if perm['statistically_significant'] else 'FAIL'} (p < 0.05)")

    # SHAP Analysis
    print("\n" + "-"*80)
    print("[3] SHAP ANALYSIS (Feature Explanations)")
    print("-"*80)
    if 'error' not in report['shap_analysis']:
        shap = report['shap_analysis']
        print(f"Samples Analyzed:    {shap['n_samples_analyzed']}")
        print(f"\nTop 5 Features by SHAP Importance:")
        for i, item in enumerate(shap['top_features'], 1):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                feature, importance = item
                print(f"  {i}. {feature:<30} {importance:.6f}")
            else:
                print(f"  {i}. {item}")
    else:
        print(f"SHAP Error: {report['shap_analysis']['error']}")

    # Overall Validations
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    val = report['validations']
    print(f"  RF Predictive Power:       {val['rf_predictive']}")
    print(f"  No Overfitting:            {val['rf_not_overfit']}")
    print(f"  Statistically Significant: {val['statistically_significant']}")
    print(f"  Meaningful Features:       {val['features_meaningful']}")
    print(f"\nOVERALL: {'PASSED' if report['overall_passed'] else 'FAILED'}")
    print("="*80 + "\n")


def main():
    """Run validation on conservative 5% DD strategy with REAL trade data."""
    logger.info("="*80)
    logger.info("STARTING STRATEGY VALIDATION WITH REAL TRADE DATA")
    logger.info("="*80)
    logger.info(f"Strategy: Conservative FVG (5% Max DD)")
    logger.info(f"Source: tests/validation_data/ (Real backtest trades)")
    logger.info("")

    # Check for required packages
    try:
        import sklearn
        import shap
        logger.info("All required packages installed")
    except ImportError as e:
        logger.error("Missing required packages!")
        logger.error("Install with: pip install scikit-learn shap")
        return

    # Load real trade data from backtests
    trades = load_trade_data_from_files()

    if not trades:
        logger.error("No trade data found!")
        logger.error("Please run: python run_backtest_for_validation.py first")
        return

    if len(trades) < 30:
        logger.warning(f"Only {len(trades)} trades available for validation")
        logger.warning("More trades = more reliable results, but proceeding...")

    # Initialize validator
    validator = StrategyValidator(trades)

    # Run full validation
    report = validator.generate_validation_report()

    # Print formatted report
    print_validation_report(report)

    # Note: JSON saving disabled due to complex objects in report
    # The full report is displayed above
    logger.info(f"\nValidation report complete!")

    # Recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    if report['overall_passed']:
        print("[PASS] Strategy validation PASSED all checks!")
        print("[PASS] The strategy is statistically valid and not curve-fitted")
        print("[PASS] Safe to proceed with live/demo trading")
    else:
        print("[WARNING] Some validation checks failed")
        failed = [k for k, v in report['validations'].items() if not v]
        for check in failed:
            print(f"  - {check}")
        print("\nRecommendations:")
        print("  1. Review failed checks above")
        print("  2. Consider collecting more trade data")
        print("  3. Re-optimize with different parameter ranges")

    print("="*80 + "\n")


if __name__ == "__main__":
    main()
