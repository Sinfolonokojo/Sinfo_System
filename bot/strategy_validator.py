"""
Strategy Validation Module - ML-Based Strategy Analysis.

Uses Random Forest, Permutation Testing, and SHAP to validate
that the trading strategy works for the right reasons.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
    from sklearn.inspection import permutation_importance
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

logger = setup_logger("VALIDATOR")


class StrategyValidator:
    """
    Validates trading strategy using ML techniques.

    Methods:
    1. Random Forest: Predict trade outcomes based on features
    2. Permutation Testing: Validate statistical significance
    3. SHAP: Explain feature contributions
    """

    def __init__(self, trade_data: List[Dict[str, Any]]):
        """
        Initialize validator with trade data.

        Args:
            trade_data: List of trade dictionaries with features and outcomes
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required. Install: pip install scikit-learn")

        self.logger = logger
        self.trade_data = trade_data
        self.df = None
        self.features = []
        self.X = None
        self.y = None
        self.rf_model = None
        self.shap_values = None

        self._prepare_data()

    def _prepare_data(self):
        """Convert trade data to DataFrame and extract features."""
        self.logger.info("Preparing trade data for validation...")

        # Convert to DataFrame
        self.df = pd.DataFrame(self.trade_data)

        # Define feature columns (exclude outcome and metadata)
        exclude_cols = ['profit', 'win', 'exit_reason', 'entry_time', 'exit_time',
                       'symbol', 'direction', 'profit_pips']
        self.features = [col for col in self.df.columns if col not in exclude_cols]

        # Prepare features (X) and target (y)
        self.X = self.df[self.features].values
        self.y = self.df['win'].values  # Binary: 1 for win, 0 for loss

        self.logger.info(f"Prepared {len(self.df)} trades with {len(self.features)} features")
        self.logger.info(f"Features: {', '.join(self.features)}")

    def train_random_forest(self, n_estimators: int = 100, test_size: float = 0.3) -> Dict[str, Any]:
        """
        Train Random Forest classifier to predict trade outcomes.

        Args:
            n_estimators: Number of trees in forest
            test_size: Proportion of data for testing

        Returns:
            Dictionary with model performance metrics
        """
        self.logger.info("Training Random Forest classifier...")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            self.X, self.y, test_size=test_size, random_state=42, stratify=self.y
        )

        # Train model
        self.rf_model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            class_weight='balanced'
        )

        self.rf_model.fit(X_train, y_train)

        # Evaluate
        train_score = self.rf_model.score(X_train, y_train)
        test_score = self.rf_model.score(X_test, y_test)

        # Cross-validation
        cv_scores = cross_val_score(self.rf_model, self.X, self.y, cv=5)

        # Predictions
        y_pred = self.rf_model.predict(X_test)
        y_prob = self.rf_model.predict_proba(X_test)[:, 1]

        # ROC-AUC
        try:
            roc_auc = roc_auc_score(y_test, y_prob)
        except:
            roc_auc = 0.5

        # Feature importance
        feature_importance = dict(zip(self.features, self.rf_model.feature_importances_))
        sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)

        results = {
            'train_accuracy': train_score,
            'test_accuracy': test_score,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'roc_auc': roc_auc,
            'feature_importance': sorted_features,
            'n_train': len(X_train),
            'n_test': len(X_test)
        }

        self.logger.info(f"Random Forest trained - Test Accuracy: {test_score:.2%}")
        self.logger.info(f"Cross-Validation: {cv_scores.mean():.2%} (+/- {cv_scores.std():.2%})")

        return results

    def permutation_test(self, n_permutations: int = 1000) -> Dict[str, Any]:
        """
        Perform permutation testing to validate statistical significance.

        Shuffles trade outcomes to test if results are due to skill or luck.

        Args:
            n_permutations: Number of random shuffles to perform

        Returns:
            Dictionary with permutation test results
        """
        self.logger.info(f"Running permutation test ({n_permutations} shuffles)...")

        # Calculate actual strategy metrics
        actual_win_rate = self.y.mean()
        actual_profit = self.df['profit'].sum()
        actual_profit_factor = self._calculate_profit_factor()

        # Run permutations
        permuted_win_rates = []
        permuted_profits = []
        permuted_pfs = []

        for i in range(n_permutations):
            # Shuffle outcomes
            shuffled_y = np.random.permutation(self.y)
            shuffled_profits = np.random.permutation(self.df['profit'].values)

            # Calculate metrics
            perm_wr = shuffled_y.mean()
            perm_profit = shuffled_profits.sum()
            perm_pf = self._calculate_profit_factor(shuffled_profits)

            permuted_win_rates.append(perm_wr)
            permuted_profits.append(perm_profit)
            permuted_pfs.append(perm_pf)

        # Calculate p-values (one-tailed: is actual better than random?)
        p_value_wr = (np.array(permuted_win_rates) >= actual_win_rate).mean()
        p_value_profit = (np.array(permuted_profits) >= actual_profit).mean()
        p_value_pf = (np.array(permuted_pfs) >= actual_profit_factor).mean()

        results = {
            'actual_win_rate': actual_win_rate,
            'actual_profit': actual_profit,
            'actual_profit_factor': actual_profit_factor,
            'permuted_wr_mean': np.mean(permuted_win_rates),
            'permuted_wr_std': np.std(permuted_win_rates),
            'permuted_profit_mean': np.mean(permuted_profits),
            'permuted_profit_std': np.std(permuted_profits),
            'p_value_win_rate': p_value_wr,
            'p_value_profit': p_value_profit,
            'p_value_profit_factor': p_value_pf,
            'n_permutations': n_permutations,
            'statistically_significant': p_value_profit < 0.05
        }

        self.logger.info(f"Permutation test complete:")
        self.logger.info(f"  Actual Profit: ${actual_profit:.2f}")
        self.logger.info(f"  Random Mean: ${np.mean(permuted_profits):.2f}")
        self.logger.info(f"  P-value: {p_value_profit:.4f}")
        self.logger.info(f"  Significant: {results['statistically_significant']}")

        return results

    def shap_analysis(self, max_samples: int = 100) -> Dict[str, Any]:
        """
        Perform SHAP analysis to explain feature contributions.

        Args:
            max_samples: Max samples for SHAP (for performance)

        Returns:
            Dictionary with SHAP values and analysis
        """
        if not SHAP_AVAILABLE:
            self.logger.warning("SHAP not available. Install: pip install shap")
            return {'error': 'SHAP not installed'}

        if self.rf_model is None:
            self.logger.error("Train Random Forest model first")
            return {'error': 'Model not trained'}

        self.logger.info("Running SHAP analysis...")

        # Use subset for performance
        n_samples = min(max_samples, len(self.X))
        X_sample = self.X[:n_samples]

        # Create SHAP explainer
        explainer = shap.TreeExplainer(self.rf_model)
        self.shap_values = explainer.shap_values(X_sample)

        # Handle multi-output (binary classification)
        if isinstance(self.shap_values, list):
            shap_vals = self.shap_values[1]  # Use positive class
        else:
            shap_vals = self.shap_values

        # Calculate mean absolute SHAP values
        mean_shap = np.abs(shap_vals).mean(axis=0)

        # Convert to Python floats, ensuring scalars
        if isinstance(mean_shap, np.ndarray):
            # Flatten in case of multi-dimensional array
            mean_shap_flat = mean_shap.flatten()
            shap_values_scalar = [float(x.item()) if hasattr(x, 'item') else float(x) for x in mean_shap_flat]
        else:
            shap_values_scalar = [float(mean_shap)]

        shap_importance = dict(zip(self.features, shap_values_scalar))
        sorted_shap = sorted(shap_importance.items(), key=lambda x: x[1], reverse=True)

        # Convert to list format for JSON serialization
        sorted_shap_list = [[feat, imp] for feat, imp in sorted_shap]

        results = {
            'shap_importance': sorted_shap_list,
            'n_samples_analyzed': n_samples,
            'top_features': sorted_shap_list[:5]
        }

        self.logger.info(f"SHAP analysis complete ({n_samples} samples)")
        self.logger.info(f"Top 3 features: {', '.join([f[0] for f in sorted_shap[:3]])}")

        return results

    def _calculate_profit_factor(self, profits: np.ndarray = None) -> float:
        """Calculate profit factor from profit array."""
        if profits is None:
            profits = self.df['profit'].values

        gross_profit = profits[profits > 0].sum()
        gross_loss = abs(profits[profits < 0].sum())

        if gross_loss == 0:
            return 0.0

        return gross_profit / gross_loss

    def generate_validation_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive validation report.

        Returns:
            Complete validation report with all analyses
        """
        self.logger.info("Generating comprehensive validation report...")

        # Run all analyses
        rf_results = self.train_random_forest()
        perm_results = self.permutation_test()
        shap_results = self.shap_analysis()

        # Overall assessment
        validations = {
            'rf_predictive': rf_results['test_accuracy'] > 0.55,
            'rf_not_overfit': abs(rf_results['train_accuracy'] - rf_results['test_accuracy']) < 0.15,
            'statistically_significant': perm_results['statistically_significant'],
            'features_meaningful': len(shap_results.get('top_features', [])) > 0
        }

        all_passed = all(validations.values())

        report = {
            'timestamp': datetime.now().isoformat(),
            'n_trades': len(self.df),
            'n_features': len(self.features),
            'random_forest': rf_results,
            'permutation_test': perm_results,
            'shap_analysis': shap_results,
            'validations': validations,
            'overall_passed': all_passed,
            'confidence_level': 'HIGH' if all_passed else 'MEDIUM' if sum(validations.values()) >= 3 else 'LOW'
        }

        self.logger.info(f"Validation complete - Confidence: {report['confidence_level']}")

        return report


def extract_trade_features(combo_file: str) -> List[Dict[str, Any]]:
    """
    Extract features from a combo backtest file for validation.

    Args:
        combo_file: Path to combo_XXX.json file

    Returns:
        List of trade dictionaries with features
    """
    with open(combo_file, 'r') as f:
        data = json.load(f)

    trades = []
    params = data['parameters']

    # Extract trades from each symbol
    for symbol, results in data['results'].items():
        # We don't have individual trade data in the current format
        # So we'll create synthetic features based on aggregate data
        # This is a placeholder - ideally you'd have individual trade data

        n_trades = results['total_trades']
        wins = int(n_trades * results['win_rate'] / 100)
        losses = n_trades - wins

        avg_profit = results['net_profit'] / n_trades if n_trades > 0 else 0

        # Create synthetic trades
        for i in range(n_trades):
            is_win = i < wins

            trade = {
                'symbol': symbol,
                'win': 1 if is_win else 0,
                'profit': avg_profit * (1.5 if is_win else -0.5),  # Approximate
                'rsi_period': params.get('rsi_period', 14),
                'atr_sl_multiplier': params.get('atr_sl_multiplier', 2.0),
                'risk_reward_ratio': params.get('risk_reward_ratio', 1.5),
                'ema_touch_tolerance': params.get('ema_touch_tolerance_pips', 2),
                'ema_reversion_period': params.get('ema_reversion_period', 50),
            }

            trades.append(trade)

    return trades


if __name__ == "__main__":
    # Example usage
    print("Strategy Validator Module")
    print("Import this module to validate your trading strategies")
