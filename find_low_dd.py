"""Find parameter combinations with max drawdown <= 5%."""
import json
import os
from pathlib import Path

def find_low_drawdown_combos(run_dir, max_dd=5.0, min_profit=0, min_win_rate=55, min_pf=1.3):
    """Find combos meeting strict drawdown requirement."""
    results = []

    # Load all combo files
    for combo_file in sorted(Path(run_dir).glob("combo_*.json")):
        with open(combo_file, 'r') as f:
            data = json.load(f)

        # Get max drawdown across all symbols
        dd_values = [r['max_drawdown_pct'] for r in data['results'].values()]
        max_drawdown = max(dd_values) if dd_values else 999

        # Check if meets criteria
        if max_drawdown <= max_dd:
            # Calculate average profit factor
            pf_values = [r['profit_factor'] for r in data['results'].values() if r['profit_factor'] > 0]
            avg_pf = sum(pf_values) / len(pf_values) if pf_values else 0

            total_profit = data['aggregate']['total_profit']
            avg_win_rate = data['aggregate']['avg_win_rate']

            # Apply additional filters
            if total_profit >= min_profit and avg_win_rate >= min_win_rate and avg_pf >= min_pf:
                results.append({
                    'combo_id': data['combo_id'],
                    'parameters': data['parameters'],
                    'profit': total_profit,
                    'win_rate': avg_win_rate,
                    'profit_factor': avg_pf,
                    'max_dd': max_drawdown,
                    'trades': data['aggregate']['total_trades']
                })

    # Sort by profit
    results.sort(key=lambda x: x['profit'], reverse=True)
    return results

# Search all strategy runs
strategies = {
    'ELASTIC_BAND': 'tests/results/elastic_band/run_2025_11_29_153643',
    'FVG': 'tests/results/fvg/run_2025_11_29_153719',
    'MACD_RSI': 'tests/results/macd_rsi/run_2025_11_29_153802',
    'ELASTIC_BB': 'tests/results/elastic_bb/run_2025_11_29_153838'
}

print("\n" + "="*80)
print("SEARCHING FOR PARAMETERS WITH MAX DRAWDOWN <= 5%")
print("="*80)
print("\nQuality Gate Requirements:")
print("  - Win Rate >= 55%")
print("  - Profit Factor >= 1.3")
print("  - Max Drawdown <= 5.0%")
print("  - Minimum Trades >= 30")
print("="*80)

all_results = []

for strategy_name, run_dir in strategies.items():
    if not os.path.exists(run_dir):
        continue

    print(f"\n{strategy_name}:")
    print("-" * 80)

    results = find_low_drawdown_combos(run_dir, max_dd=5.0, min_win_rate=55, min_pf=1.3)

    if results:
        print(f"  Found {len(results)} combinations meeting ALL quality gates!")
        for i, r in enumerate(results[:3], 1):  # Show top 3
            print(f"\n  [{i}] Combo {r['combo_id']}:")
            print(f"      Profit: ${r['profit']:.2f}")
            print(f"      Win Rate: {r['win_rate']:.2f}%")
            print(f"      Profit Factor: {r['profit_factor']:.2f}")
            print(f"      Max DD: {r['max_dd']:.2f}%")
            print(f"      Trades: {r['trades']}")
            print(f"      Parameters: {r['parameters']}")
        all_results.extend([(strategy_name, r) for r in results])
    else:
        print(f"  [X] NO combinations found meeting 5% DD requirement")

        # Show closest
        loose_results = find_low_drawdown_combos(run_dir, max_dd=10.0, min_win_rate=55, min_pf=1.0, min_profit=0)
        if loose_results:
            best = loose_results[0]
            print(f"  Closest: Combo {best['combo_id']} with {best['max_dd']:.2f}% DD")

print("\n" + "="*80)
if all_results:
    print(f"\nTOTAL: {len(all_results)} parameter combinations pass ALL gates with <= 5% DD")

    # Show overall best
    best_strategy, best_result = max(all_results, key=lambda x: x[1]['profit'])
    print(f"\nBEST OVERALL: {best_strategy} - Combo {best_result['combo_id']}")
    print(f"  Profit: ${best_result['profit']:.2f}")
    print(f"  Win Rate: {best_result['win_rate']:.2f}%")
    print(f"  Profit Factor: {best_result['profit_factor']:.2f}")
    print(f"  Max DD: {best_result['max_dd']:.2f}%")
    print(f"  Parameters: {best_result['parameters']}")
else:
    print("\n[!] WARNING: NO PARAMETERS MEET THE 5% MAX DRAWDOWN REQUIREMENT!")
    print("\nThis is an EXTREMELY strict requirement for forex trading.")
    print("Consider:")
    print("  1. Relaxing to 7-10% max drawdown")
    print("  2. Using smaller position sizes")
    print("  3. Running optimization with more conservative parameter ranges")
print("="*80 + "\n")
