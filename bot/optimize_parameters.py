"""
Parameter Optimization Script.

Tests different parameter combinations to find optimal settings
for each strategy and prop firm phase.
"""

import argparse
import json
import itertools
from datetime import datetime
from typing import Dict, List, Any
import sys
import os

# Suppress MT5 import errors during parameter grid generation
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None
except:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Parameter grids for each strategy
ELASTIC_BAND_PARAMS = {
    'rsi_period': [5, 7, 9, 14],
    'atr_sl_multiplier': [1.0, 1.5, 2.0, 2.5],
    'risk_reward_ratio': [1.0, 1.5, 2.0],
    'ema_touch_tolerance_pips': [1, 2, 3, 5],
    'ema_reversion_period': [20, 30, 50, 100],
}

FVG_PARAMS = {
    'fvg_min_gap_pips': [3, 5, 7, 10],
    'fvg_risk_reward_ratio': [1.0, 1.5, 2.0],
    'atr_sl_multiplier': [1.0, 1.5, 2.0],
}

MACD_RSI_PARAMS = {
    'macd_fast': [8, 12, 16],
    'macd_slow': [21, 27, 33],
    'macd_signal': [7, 9, 11],
    'rsi_period': [5, 7, 9, 14],
    'macd_rsi_atr_sl': [1.5, 2.0, 2.5],
    'macd_rsi_rr_ratio': [1.5, 2.0, 2.5],
}

ELASTIC_BB_PARAMS = {
    'rsi_period': [5, 7, 9, 14],
    'bb_period': [15, 20, 25],
    'bb_std_dev': [1.5, 2.0, 2.5],
    'atr_sl_multiplier': [1.0, 1.5, 2.0],
    'elastic_bb_rr_ratio': [1.0, 1.5, 2.0],
}


def generate_param_combinations(param_grid: Dict[str, List[Any]], max_combinations: int = 100) -> List[Dict[str, Any]]:
    """
    Generate parameter combinations from a grid.

    Args:
        param_grid: Dictionary of parameter names to lists of values.
        max_combinations: Maximum number of combinations to generate.

    Returns:
        List of parameter dictionaries.
    """
    keys = list(param_grid.keys())
    values = [param_grid[k] for k in keys]

    # Generate all combinations
    all_combinations = list(itertools.product(*values))

    # Limit to max_combinations
    if len(all_combinations) > max_combinations:
        # Sample evenly
        step = len(all_combinations) // max_combinations
        all_combinations = all_combinations[::step][:max_combinations]

    # Convert to list of dicts
    return [dict(zip(keys, combo)) for combo in all_combinations]


def print_optimization_plan(strategy_name: str, param_grid: Dict[str, List[Any]]):
    """
    Print the optimization plan for a strategy.

    Args:
        strategy_name: Name of the strategy.
        param_grid: Parameter grid to optimize.
    """
    total_combinations = 1
    for param, values in param_grid.items():
        total_combinations *= len(values)

    print(f"\n{'='*60}")
    print(f"OPTIMIZATION PLAN: {strategy_name}")
    print(f"{'='*60}")
    print(f"\nParameters to optimize:")
    for param, values in param_grid.items():
        print(f"  - {param}: {values} ({len(values)} values)")
    print(f"\nTotal combinations: {total_combinations}")
    print(f"Recommended: Test top 50-100 combinations")
    print(f"{'='*60}\n")


def save_param_combinations(strategy_name: str, combinations: List[Dict[str, Any]], output_file: str):
    """
    Save parameter combinations to a JSON file.

    Args:
        strategy_name: Name of the strategy.
        combinations: List of parameter dictionaries.
        output_file: Output file path.
    """
    output_data = {
        'strategy': strategy_name,
        'timestamp': datetime.now().isoformat(),
        'total_combinations': len(combinations),
        'combinations': combinations
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Saved {len(combinations)} parameter combinations to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Generate parameter optimization grids for trading strategies')
    parser.add_argument(
        '--strategy',
        choices=['elastic_band', 'fvg', 'macd_rsi', 'elastic_bb', 'all'],
        default='all',
        help='Strategy to optimize'
    )
    parser.add_argument(
        '--max-combinations',
        type=int,
        default=100,
        help='Maximum number of parameter combinations to generate (default: 100)'
    )
    parser.add_argument(
        '--output-dir',
        default='tests/parameter_sets',
        help='Output directory for parameter files (default: tests/parameter_sets)'
    )

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    strategies = {
        'elastic_band': ELASTIC_BAND_PARAMS,
        'fvg': FVG_PARAMS,
        'macd_rsi': MACD_RSI_PARAMS,
        'elastic_bb': ELASTIC_BB_PARAMS,
    }

    if args.strategy == 'all':
        selected_strategies = strategies
    else:
        selected_strategies = {args.strategy: strategies[args.strategy]}

    print(f"\n{'#'*60}")
    print(f"PARAMETER OPTIMIZATION GRID GENERATOR")
    print(f"{'#'*60}")

    for strategy_name, param_grid in selected_strategies.items():
        # Print optimization plan
        print_optimization_plan(strategy_name, param_grid)

        # Generate combinations
        combinations = generate_param_combinations(param_grid, args.max_combinations)

        # Save to file
        output_file = os.path.join(args.output_dir, f'{strategy_name}_params.json')
        save_param_combinations(strategy_name, combinations, output_file)

        # Print sample combinations
        print(f"\nSample parameter combinations for {strategy_name}:")
        for i, combo in enumerate(combinations[:3]):
            print(f"\n  Combination {i+1}:")
            for param, value in combo.items():
                print(f"    {param}: {value}")

        print(f"\n{'='*60}\n")

    print(f"\n{'#'*60}")
    print(f"NEXT STEPS:")
    print(f"{'#'*60}")
    print(f"\n1. Review the generated parameter files in: {args.output_dir}/")
    print(f"2. Run backtests using the backtest_runner.py script")
    print(f"3. Example:")
    print(f"   python bot/backtest_runner.py --strategy elastic_band --params bot/optimization/elastic_band_params.json")
    print(f"\n{'#'*60}\n")


if __name__ == '__main__':
    main()
