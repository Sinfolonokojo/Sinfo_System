# Complete Automation Guide

## Overview

This guide explains how to use the **fully automated** trading bot optimization system. With these tools, you can test hundreds of parameter combinations across multiple strategies and phases **without any manual editing**.

## 🚀 Quick Start - One Command Does Everything

### The Simplest Way (Recommended)

```bash
# One command to rule them all - tests all strategies, finds the best, and applies it!
python bot/automate_optimization.py --symbols EURUSD,GBPUSD --phase 1 --days 90 --auto-apply
```

**What this does:**
1. ✅ Generates parameters for all 4 strategies
2. ✅ Runs grid searches for each strategy
3. ✅ Analyzes all results
4. ✅ Compares strategies to find the best
5. ✅ **Automatically applies best parameters to bot/config.py**
6. ✅ **Automatically sets the best strategy as active**

**Then you just:**
```bash
python bot/main.py  # Start trading with optimized settings!
```

---

## 📚 The Four Automation Tools

### 1. Config Manager - No More Manual Editing!

**Purpose:** Apply parameters and switch strategies without touching config files.

#### Apply Best Parameters
```bash
# Apply best parameters from a grid search run
python bot/config_manager.py --apply tests/results/elastic_band/run_TIMESTAMP/best_params.json

# Apply specific recommendation type
python bot/config_manager.py --apply tests/results/elastic_band/run_TIMESTAMP/recommended_params.json --param-type risk_adjusted
```

**Available param types:**
- `best` - Overall best by profit
- `risk_adjusted` - Best profit/drawdown ratio (RECOMMENDED)
- `profit` - Maximum profit
- `win_rate` - Highest win rate
- `drawdown` - Lowest drawdown (safest)

#### Switch Active Strategy
```bash
# Switch to FVG strategy
python bot/config_manager.py --set-strategy fvg

# Check current strategy
python bot/config_manager.py --get-strategy

# Test what would change (dry run)
python bot/config_manager.py --set-strategy macd_rsi --dry-run
```

#### Backup Management
```bash
# List all config backups
python bot/config_manager.py --list-backups

# Restore from a backup
python bot/config_manager.py --restore bot/config_backups/config_backup_20251126_192000.py
```

**Note:** Config Manager automatically creates backups before making changes (unless you use `--no-backup`).

---

### 2. Batch Grid Search - Test Multiple Strategies Automatically

**Purpose:** Run grid searches for multiple strategies and phases in one command.

#### Test All Strategies
```bash
# Test all 4 strategies on 2 symbols, Phase 1, 90 days
python bot/batch_grid_search.py --strategies all --symbols EURUSD,GBPUSD --phase 1 --days 90
```

#### Test Specific Strategies
```bash
# Test only FVG and MACD_RSI strategies
python bot/batch_grid_search.py --strategies fvg,macd_rsi --symbols EURUSD --phase 1 --days 90
```

#### Test Multiple Phases
```bash
# Test all strategies across Phase 1, 2, and 3
python bot/batch_grid_search.py --strategies all --symbols EURUSD --phases 1,2,3 --days 90
```

#### Adjust Parameters
```bash
# Quick test with fewer combinations
python bot/batch_grid_search.py --strategies all --symbols EURUSD --phase 1 --days 30 --max-combinations 20

# Thorough overnight test
python bot/batch_grid_search.py --strategies all --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 180 --max-combinations 100
```

**Output:**
- Creates `tests/results/batch_TIMESTAMP/` directory
- Each strategy/phase gets its own run directory
- Saves `batch_metadata.json` with all results

---

### 3. Results Aggregator - Unified Comparison

**Purpose:** Compare results across multiple strategies and phases.

#### Compare Batch Results
```bash
# Compare all results from a batch run
python bot/aggregate_results.py --batch tests/results/batch_2025_11_26_181500
```

#### Compare Specific Runs
```bash
# Compare specific run directories
python bot/aggregate_results.py --runs "tests/results/elastic_band/run_001,tests/results/fvg/run_002"
```

**Output Shows:**
- 🏆 Best overall strategy (risk-adjusted)
- 💰 Top 5 by profit
- 🎯 Top 5 by win rate
- 🛡️ Top 5 by lowest drawdown (safest)
- 📊 Top 5 by risk-adjusted return

**Saves:**
- `comparison_report.json` in the batch directory

---

### 4. Complete Workflow Orchestrator - The Ultimate Tool

**Purpose:** End-to-end automation in ONE command.

#### Full Automation with Auto-Apply
```bash
# Complete workflow: test, compare, and apply best params
python bot/automate_optimization.py \
  --symbols EURUSD,GBPUSD \
  --phase 1 \
  --days 90 \
  --auto-apply
```

#### Test Without Auto-Apply
```bash
# Test everything but don't modify config (review first)
python bot/automate_optimization.py \
  --symbols EURUSD,GBPUSD \
  --phase 1 \
  --days 90
```

#### Test Specific Strategies
```bash
# Only test elastic_band and fvg
python bot/automate_optimization.py \
  --strategies elastic_band,fvg \
  --symbols EURUSD \
  --phase 1 \
  --days 90 \
  --auto-apply
```

#### Choose Which Parameter Set to Apply
```bash
# Apply the safest parameters (lowest drawdown)
python bot/automate_optimization.py \
  --symbols EURUSD \
  --phase 1 \
  --days 90 \
  --auto-apply \
  --apply-type drawdown

# Apply highest win rate parameters
python bot/automate_optimization.py \
  --symbols EURUSD \
  --phase 1 \
  --days 90 \
  --auto-apply \
  --apply-type win_rate
```

**Apply type options:**
- `risk_adjusted` - Best profit/drawdown ratio (DEFAULT, RECOMMENDED)
- `profit` - Maximum profit
- `win_rate` - Highest win rate
- `drawdown` - Lowest drawdown (safest)
- `best` - Overall best by profit

---

## 🎯 Common Workflows

### Workflow 1: Quick Overnight Optimization (Recommended)

```bash
# Before bed: Start complete automation
python bot/automate_optimization.py \
  --symbols EURUSD,GBPUSD \
  --phase 1 \
  --days 90 \
  --auto-apply

# Next morning: Just start the bot!
python bot/main.py
```

### Workflow 2: Conservative Testing (Review Before Applying)

```bash
# Step 1: Run batch testing (no auto-apply)
python bot/automate_optimization.py \
  --symbols EURUSD,GBPUSD \
  --phases 1,2 \
  --days 90

# Step 2: Review the results
# (Script will show you the best strategy and parameters)

# Step 3: Manually apply if you like the results
python bot/config_manager.py --apply tests/results/batch_TIMESTAMP/elastic_band/run_TIMESTAMP/best_params.json
python bot/config_manager.py --set-strategy elastic_band

# Step 4: Start trading
python bot/main.py
```

### Workflow 3: Compare Existing Results

```bash
# Compare multiple existing grid search runs
python bot/aggregate_results.py \
  --runs "tests/results/elastic_band/run_001,tests/results/fvg/run_002,tests/results/macd_rsi/run_003"

# Then apply the winner
python bot/config_manager.py --apply tests/results/fvg/run_002/best_params.json
python bot/config_manager.py --set-strategy fvg
```

### Workflow 4: Strategy-Specific Optimization

```bash
# Optimize just one strategy with many combinations
python bot/optimize_parameters.py --strategy elastic_band --max-combinations 100

python bot/grid_search.py \
  --strategy elastic_band \
  --params tests/parameter_sets/elastic_band_params.json \
  --symbols EURUSD,GBPUSD,USDJPY \
  --phase 1 \
  --days 180

python bot/analyze_results.py --run tests/results/elastic_band/run_TIMESTAMP

# Apply best params
python bot/config_manager.py --apply tests/results/elastic_band/run_TIMESTAMP/best_params.json
```

---

## 📊 Understanding the Results

### Risk-Adjusted Score (Recommended)

The **risk-adjusted score** is calculated as:
```
Risk-Adjusted Score = Profit / Max Drawdown %
```

**Higher is better!** This metric balances profit with risk:
- High profit + low drawdown = Excellent score
- High profit + high drawdown = Lower score (risky)
- Low profit + low drawdown = Lower score (too conservative)

**Example:**
- Strategy A: $1000 profit, 5% drawdown → Score = 200
- Strategy B: $1200 profit, 10% drawdown → Score = 120
- **Strategy A wins!** (Better risk/reward)

### When to Use Each Metric

| Goal | Use This Metric | Why |
|------|----------------|-----|
| Pass challenge fast | `profit` | Maximize gains |
| Minimize stress | `drawdown` | Safest approach |
| Consistency | `win_rate` | Most reliable |
| **Best overall** | **`risk_adjusted`** | **Balanced profit/risk** |

---

## 🛠️ Advanced Tips

### Parallel Testing for Different Phases

```bash
# Test Phase 1 (aggressive)
python bot/batch_grid_search.py --strategies all --symbols EURUSD --phase 1 --days 90 &

# Test Phase 2 (moderate)
python bot/batch_grid_search.py --strategies all --symbols EURUSD --phase 2 --days 90 &

# Test Phase 3 (conservative)
python bot/batch_grid_search.py --strategies all --symbols EURUSD --phase 3 --days 90 &

# Wait for all to complete, then compare
python bot/aggregate_results.py --batch tests/results/batch_TIMESTAMP
```

### Incremental Testing

```bash
# Day 1: Quick test (30 days, 20 combinations)
python bot/automate_optimization.py --symbols EURUSD --phase 1 --days 30 --max-combinations 20

# Day 2: Test top 2 strategies more thoroughly (90 days, 50 combinations)
python bot/batch_grid_search.py --strategies elastic_band,fvg --symbols EURUSD,GBPUSD --phase 1 --days 90 --max-combinations 50

# Day 3: Final validation (180 days)
python bot/grid_search.py --strategy fvg --params tests/parameter_sets/fvg_params.json --symbols EURUSD,GBPUSD --phase 1 --days 180
```

### Backup and Restore Workflow

```bash
# Before testing, backup current config
python bot/config_manager.py --list-backups

# Test new parameters
python bot/config_manager.py --apply tests/results/fvg/run_001/best_params.json

# Run a backtest to verify
python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 90

# If you don't like it, restore previous config
python bot/config_manager.py --restore bot/config_backups/config_backup_TIMESTAMP.py
```

---

## 🚨 Safety Features

### Automatic Backups
- Config Manager **always** creates backups before modifying files
- Backups are timestamped: `config_backup_20251126_192345.py`
- Located in: `bot/config_backups/`
- Use `--no-backup` to skip (not recommended)

### Dry Run Mode
```bash
# Preview changes without actually modifying files
python bot/config_manager.py --apply best_params.json --dry-run
python bot/config_manager.py --set-strategy fvg --dry-run
```

### Validation
- Config Manager validates all parameters before applying
- Strategy names are validated against allowed values
- Parameter files are checked for existence and format

---

## 📁 File Structure After Automation

```
tests/
├── parameter_sets/
│   ├── elastic_band_params.json
│   ├── fvg_params.json
│   ├── macd_rsi_params.json
│   └── elastic_bb_params.json
│
└── results/
    ├── batch_2025_11_26_181500/          # Batch run
    │   ├── batch_metadata.json           # Batch info
    │   └── comparison_report.json        # Unified comparison
    │
    ├── elastic_band/
    │   └── run_2025_11_26_181501/
    │       ├── metadata.json
    │       ├── combo_001.json
    │       ├── combo_002.json
    │       ├── ...
    │       ├── summary.json
    │       ├── best_params.json          # Best overall
    │       └── recommended_params.json   # 4 recommendations
    │
    ├── fvg/
    │   └── run_2025_11_26_182030/
    │       └── ...
    │
    ├── macd_rsi/
    │   └── run_2025_11_26_182530/
    │       └── ...
    │
    └── elastic_bb/
        └── run_2025_11_26_183030/
            └── ...

bot/config_backups/
├── config_backup_20251126_181000.py
├── config_backup_20251126_182000.py
└── config_backup_20251126_183000.py
```

---

## ❓ FAQ

### Q: Can I test just one strategy?
**A:** Yes! Use `--strategies elastic_band` instead of `--strategies all`

### Q: How long does a full batch test take?
**A:**
- 1 strategy, 1 symbol, 50 combos ≈ 15-30 min
- 4 strategies, 2 symbols, 50 combos ≈ 2-4 hours
- Use `--days 30` and `--max-combinations 20` for faster testing

### Q: What if I don't like the auto-applied parameters?
**A:** Restore from backup:
```bash
python bot/config_manager.py --list-backups
python bot/config_manager.py --restore bot/config_backups/config_backup_TIMESTAMP.py
```

### Q: Can I compare results from different days?
**A:** Yes! Use the Results Aggregator:
```bash
python bot/aggregate_results.py --runs "tests/results/elastic_band/run_001,tests/results/elastic_band/run_002"
```

### Q: Which strategy should I use?
**A:** Run the automated workflow and let it decide:
```bash
python bot/automate_optimization.py --symbols EURUSD,GBPUSD --phase 1 --days 90
```
It will show you which strategy performed best.

---

## 🎉 Summary

**Old Way (Manual):**
1. Edit config.py to change parameters
2. Run grid search
3. Manually read results
4. Edit config.py again with best params
5. Repeat for each strategy
6. Manually compare results
7. Edit config.py to set winning strategy

**New Way (Automated):**
```bash
python bot/automate_optimization.py --symbols EURUSD,GBPUSD --phase 1 --days 90 --auto-apply
```

**That's it! Everything is automated! 🚀**

---

## 🔗 Related Documentation

- [GRID_SEARCH_GUIDE.md](GRID_SEARCH_GUIDE.md) - Original grid search documentation
- [docs/STRATEGY_GUIDE.md](docs/STRATEGY_GUIDE.md) - Strategy details
- [README.md](README.md) - Project overview
