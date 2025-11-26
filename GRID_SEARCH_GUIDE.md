# Automated Grid Search Guide

## Overview

The automated grid search system allows you to test 50-100 parameter combinations **overnight** without any manual intervention. Just start it and come back to see which parameters work best!

---

## Complete Workflow

### Step 1: Generate Parameter Grid (1 minute)

```bash
# Generate 50 combinations for Elastic Band strategy
python bot/optimize_parameters.py --strategy elastic_band --max-combinations 50

# Output saved to: tests/parameter_sets/elastic_band_params.json
```

**What this creates:**
```json
{
  "strategy": "elastic_band",
  "total_combinations": 50,
  "combinations": [
    {"rsi_period": 5, "atr_sl_multiplier": 1.0, "risk_reward_ratio": 1.0},
    {"rsi_period": 5, "atr_sl_multiplier": 1.0, "risk_reward_ratio": 1.5},
    ...
  ]
}
```

---

### Step 2: Run Automated Grid Search (30-60 minutes)

```bash
# Test all 50 combinations on 2 symbols (100 backtests total)
python bot/grid_search.py \
  --strategy elastic_band \
  --params tests/parameter_sets/elastic_band_params.json \
  --symbols EURUSD,GBPUSD \
  --phase 1 \
  --days 90
```

**What happens:**
- Tests combo 001, 002, 003... automatically
- Saves each result to `tests/results/elastic_band/run_TIMESTAMP/`
- Shows progress bar and ETA
- Tracks best combination in real-time
- **Runs completely unattended!**

**Example Output:**
```
================================================================================
GRID SEARCH: elastic_band
================================================================================
Testing 50 parameter combinations
Symbols: EURUSD, GBPUSD
Total backtests: 100
Results: tests/results/elastic_band/run_2025_01_25_143022
================================================================================

────────────────────────────────────────────────────────────────────────────────
Testing Combination 001/050
Parameters: {'rsi_period': 5, 'atr_sl_multiplier': 1.0, 'risk_reward_ratio': 1.0}
────────────────────────────────────────────────────────────────────────────────
  Testing EURUSD...
  Testing GBPUSD...

  Progress: [██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 1/50 (2.0%)
  ETA: 45m 30s
  Combo 001: Profit: $450.25 | Win Rate: 52.3%
  Best so far: Combo 001 - $450.25

────────────────────────────────────────────────────────────────────────────────
Testing Combination 002/050
Parameters: {'rsi_period': 5, 'atr_sl_multiplier': 1.5, 'risk_reward_ratio': 1.0}
────────────────────────────────────────────────────────────────────────────────
...
```

**Resume if Interrupted:**
```bash
# If test stops at combo 023, resume from there
python bot/grid_search.py \
  --strategy elastic_band \
  --params tests/parameter_sets/elastic_band_params.json \
  --symbols EURUSD,GBPUSD \
  --phase 1 \
  --days 90 \
  --resume 23
```

---

### Step 3: Analyze Results (1 minute)

```bash
# Analyze the completed run
python bot/analyze_results.py --run tests/results/elastic_band/run_2025_01_25_143022
```

**What you get:**
```
================================================================================
GRID SEARCH RESULTS ANALYSIS
================================================================================
Run: run_2025_01_25_143022
Strategy: elastic_band
Symbols: EURUSD, GBPUSD
Total Combinations: 50
================================================================================

────────────────────────────────────────────────────────────────────────────────
RANKED BY TOTAL PROFIT
────────────────────────────────────────────────────────────────────────────────
Rank   Combo    Profit         Win Rate     Trades     Parameters
────────────────────────────────────────────────────────────────────────────────
1      015      $1,245.80      58.2%        88         rsi_period=9, atr_sl_multiplier=1.5
2      032      $1,180.50      55.3%        92         rsi_period=7, atr_sl_multiplier=2.0
3      008      $1,125.30      52.1%        85         rsi_period=14, atr_sl_multiplier=1.0
...

────────────────────────────────────────────────────────────────────────────────
RANKED BY WIN RATE
────────────────────────────────────────────────────────────────────────────────
Rank   Combo    Win Rate     Profit         Trades     Parameters
────────────────────────────────────────────────────────────────────────────────
1      018      63.5%        $980.20        78         rsi_period=14, atr_sl_multiplier=1.0
2      015      58.2%        $1,245.80      88         rsi_period=9, atr_sl_multiplier=1.5
...

────────────────────────────────────────────────────────────────────────────────
RANKED BY LOWEST DRAWDOWN (Safest)
────────────────────────────────────────────────────────────────────────────────
Rank   Combo    MaxDD      Profit         Win Rate     Parameters
────────────────────────────────────────────────────────────────────────────────
1      025      2.1%       $890.50        54.2%        rsi_period=14, atr_sl_multiplier=1.0
2      018      2.3%       $980.20        63.5%        rsi_period=14, atr_sl_multiplier=1.0
...

================================================================================
RECOMMENDATION SUMMARY
================================================================================

BEST FOR MAXIMUM PROFIT:
  Combo: 015
  Parameters: {'rsi_period': 9, 'atr_sl_multiplier': 1.5, 'risk_reward_ratio': 1.5}
  Profit: $1,245.80
  Win Rate: 58.2%

BEST FOR CONSISTENCY (Highest Win Rate):
  Combo: 018
  Parameters: {'rsi_period': 14, 'atr_sl_multiplier': 1.0, 'risk_reward_ratio': 1.0}
  Win Rate: 63.5%
  Profit: $980.20

BEST FOR SAFETY (Lowest Drawdown):
  Combo: 025
  Parameters: {'rsi_period': 14, 'atr_sl_multiplier': 1.0, 'risk_reward_ratio': 1.0}
  Max Drawdown: 2.1%
  Profit: $890.50

BEST RISK-ADJUSTED (Recommended):
  Combo: 015
  Parameters: {'rsi_period': 9, 'atr_sl_multiplier': 1.5, 'risk_reward_ratio': 1.5}
  Profit/DD Ratio: 429.6
  Profit: $1,245.80
  Max Drawdown: 2.9%

Recommended parameters saved to: tests/results/elastic_band/run_2025_01_25_143022/recommended_params.json
================================================================================
```

---

### Step 4: Apply Best Parameters

```python
# Edit bot/config.py with the best parameters
STRATEGY_CONFIG = {
    # ... other params ...

    # Apply best parameters from grid search
    'rsi_period': 9,                  # Was: 7
    'atr_sl_multiplier': 1.5,         # Was: 1.5 (no change)
    'risk_reward_ratio': 1.5,         # Was: 1.0 (improved!)
}
```

Or copy from the JSON file:
```bash
# The analyzer saved the best params to:
# tests/results/elastic_band/run_2025_01_25_143022/best_params.json
```

---

## Full Example: Finding Best Parameters Overnight

```bash
# Before bed: Generate and start grid search
python bot/optimize_parameters.py --strategy elastic_band --max-combinations 100

python bot/grid_search.py \
  --strategy elastic_band \
  --params tests/parameter_sets/elastic_band_params.json \
  --symbols EURUSD,GBPUSD,USDJPY \
  --phase 1 \
  --days 180

# Go to sleep 😴
# Wake up, analyze results:

python bot/analyze_results.py --run tests/results/elastic_band/run_2025_01_25_220030

# Copy best params to config, done! ✅
```

---

## Directory Structure

After running grid search, you'll have:

```
tests/
├── parameter_sets/
│   ├── elastic_band_params.json      # Parameter combinations to test
│   ├── fvg_params.json
│   └── macd_rsi_params.json
│
└── results/
    ├── elastic_band/
    │   ├── run_2025_01_25_143022/
    │   │   ├── metadata.json          # Run info
    │   │   ├── combo_001.json         # Result for combo 1
    │   │   ├── combo_002.json         # Result for combo 2
    │   │   ├── ...
    │   │   ├── combo_050.json         # Result for combo 50
    │   │   ├── summary.json           # Top 10 summary
    │   │   ├── best_params.json       # Best overall params
    │   │   └── recommended_params.json # Recommended by goal
    │   │
    │   └── run_2025_01_26_080015/    # Another run
    │
    ├── fvg/
    └── macd_rsi/
```

---

## Advanced Usage

### Test Multiple Strategies

```bash
# Generate params for all strategies
python bot/optimize_parameters.py --strategy all --max-combinations 50

# Run grid search for each
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD,GBPUSD --phase 1 --days 90

python bot/grid_search.py --strategy fvg --params tests/parameter_sets/fvg_params.json --symbols EURUSD,GBPUSD --phase 1 --days 90

python bot/grid_search.py --strategy macd_rsi --params tests/parameter_sets/macd_rsi_params.json --symbols EURUSD,GBPUSD --phase 1 --days 90

# Compare which strategy performs best!
```

### Test Different Phases

```bash
# Phase 1 (Challenge - aggressive)
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD --phase 1 --days 90

# Phase 2 (Verification - moderate)
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD --phase 2 --days 90

# Phase 3 (Funded - conservative)
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD --phase 3 --days 90

# Find best params for each phase!
```

### Test Different Timeframes

```bash
# Test 30 days (quick validation)
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD --phase 1 --days 30

# Test 90 days (standard)
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD --phase 1 --days 90

# Test 180 days (thorough)
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD --phase 1 --days 180
```

---

## Tips for Best Results

### 1. Start Small
```bash
# First run: Test 20 combinations on 1 symbol
python bot/optimize_parameters.py --strategy elastic_band --max-combinations 20
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD --phase 1 --days 90

# Once comfortable: Scale to 100 combinations on 3 symbols
```

### 2. Test Incrementally
- Day 1: Test 30 days of data (fast)
- Day 2: Best 10 combos on 90 days (medium)
- Day 3: Best 3 combos on 180 days (thorough)

### 3. Consider Your Goal
- **Fast challenge pass:** Use "BEST FOR MAXIMUM PROFIT"
- **Low stress/drawdown:** Use "BEST FOR SAFETY"
- **Balanced approach:** Use "BEST RISK-ADJUSTED" (recommended)

### 4. Validate Results
After finding best params:
```bash
# Test on different time period (out-of-sample)
python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 365
```

---

## Troubleshooting

### Grid search stops/crashes
```bash
# Resume from where it stopped (e.g., combo 23)
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD --phase 1 --days 90 --resume 23
```

### Want to test specific params only
Edit the JSON file manually:
```json
{
  "combinations": [
    {"rsi_period": 9, "atr_sl_multiplier": 1.5, "risk_reward_ratio": 1.5},
    {"rsi_period": 9, "atr_sl_multiplier": 2.0, "risk_reward_ratio": 2.0}
  ]
}
```

### Results analyzer shows no data
Make sure the grid search completed and created combo_XXX.json files.

---

## Quick Reference

```bash
# 1. Generate parameters
python bot/optimize_parameters.py --strategy elastic_band --max-combinations 50

# 2. Run grid search
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD,GBPUSD --phase 1 --days 90

# 3. Analyze results
python bot/analyze_results.py --run tests/results/elastic_band/run_TIMESTAMP

# 4. Apply best params to bot/config.py
```

**That's it! Let the computer find your best parameters! 🚀**
