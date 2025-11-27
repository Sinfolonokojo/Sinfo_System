# Testing Guide for Automation Tools

## ✅ Tests That Work WITHOUT MT5

These tests will work in any environment (including without MT5 terminal):

### 1. Config Manager Tests

```bash
# Get current strategy
python bot/config_manager.py --get-strategy

# Test strategy switching (dry run)
python bot/config_manager.py --set-strategy fvg --dry-run

# Test parameter application (dry run)
python bot/config_manager.py --apply tests/results/elastic_band/run_2025_11_26_181201/best_params.json --dry-run

# List backups
python bot/config_manager.py --list-backups

# Test all help commands
python bot/config_manager.py --help
python bot/batch_grid_search.py --help
python bot/aggregate_results.py --help
python bot/automate_optimization.py --help
```

### 2. Parameter Generation

```bash
# Generate test parameters
python bot/optimize_parameters.py --strategy elastic_band --max-combinations 5

# Generate for all strategies
python bot/optimize_parameters.py --strategy all --max-combinations 10

# Check generated files
dir tests\parameter_sets
```

### 3. Results Analysis

```bash
# Analyze existing results (if you have any from previous runs)
python bot/analyze_results.py --run tests/results/elastic_band/run_2025_11_26_181201
```

---

## ⚠️ Tests That REQUIRE MT5 Terminal

These will fail without MT5 terminal running:

```bash
# Grid search - REQUIRES MT5
python bot/grid_search.py --strategy elastic_band --params tests/parameter_sets/elastic_band_params.json --symbols EURUSD --phase 1 --days 30

# Batch grid search - REQUIRES MT5
python bot/batch_grid_search.py --strategies elastic_band --symbols EURUSD --phase 1 --days 30 --max-combinations 5

# Complete automation - REQUIRES MT5
python bot/automate_optimization.py --symbols EURUSD --phase 1 --days 30 --max-combinations 5

# Backtesting - REQUIRES MT5
python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 30
```

---

## 🧪 Full Testing Workflow (When MT5 is Available)

### Phase 1: Quick Smoke Test (5 minutes)

```bash
# Step 1: Generate minimal parameters
python bot/optimize_parameters.py --strategy elastic_band --max-combinations 2

# Step 2: Run quick grid search
python bot/grid_search.py \
  --strategy elastic_band \
  --params tests/parameter_sets/elastic_band_params.json \
  --symbols EURUSD \
  --phase 1 \
  --days 7

# Step 3: Analyze results
python bot/analyze_results.py --run tests/results/elastic_band/run_TIMESTAMP

# Step 4: Test config application (dry run)
python bot/config_manager.py --apply tests/results/elastic_band/run_TIMESTAMP/best_params.json --dry-run
```

### Phase 2: Test Batch Processing (15 minutes)

```bash
# Test 2 strategies with minimal combos
python bot/batch_grid_search.py \
  --strategies elastic_band,fvg \
  --symbols EURUSD \
  --phase 1 \
  --days 7 \
  --max-combinations 3

# Compare results
python bot/aggregate_results.py --batch tests/results/batch_TIMESTAMP
```

### Phase 3: Test Complete Automation (20 minutes)

```bash
# Full workflow with auto-apply
python bot/automate_optimization.py \
  --strategies elastic_band,fvg \
  --symbols EURUSD \
  --phase 1 \
  --days 7 \
  --max-combinations 3 \
  --auto-apply

# Verify config was updated
python bot/config_manager.py --get-strategy

# Check backups were created
python bot/config_manager.py --list-backups

# Run a backtest to verify
python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 7
```

### Phase 4: Restore Test

```bash
# Restore previous config
python bot/config_manager.py --list-backups
python bot/config_manager.py --restore bot/config_backups/config_backup_TIMESTAMP.py

# Verify restoration
python bot/config_manager.py --get-strategy
```

---

## 📊 Expected Output Examples

### Config Manager - Get Strategy
```
Current active strategy: elastic_band
```

### Config Manager - Dry Run Apply
```
2025-11-26 XX:XX:XX | INFO | CONFIG_MGR | Loaded parameters from: tests/results/elastic_band/run_TIMESTAMP/best_params.json
2025-11-26 XX:XX:XX | INFO | CONFIG_MGR | Applying 5 parameters to config
2025-11-26 XX:XX:XX | INFO | CONFIG_MGR | Updated rsi_period: 14 -> 5
2025-11-26 XX:XX:XX | INFO | CONFIG_MGR | Updated atr_sl_multiplier: 2.0 -> 2.0
...
2025-11-26 XX:XX:XX | INFO | CONFIG_MGR | DRY RUN - No changes were made
```

### Parameter Generation Success
```
============================================================
OPTIMIZATION PLAN: elastic_band
============================================================

Parameters to optimize:
  - rsi_period: [5, 7, 9, 14] (4 values)
  ...

Total combinations: 768
Recommended: Test top 50-100 combinations
============================================================

Saved 5 parameter combinations to: tests/parameter_sets\elastic_band_params.json
```

---

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'MetaTrader5'"

**This is EXPECTED** if you don't have MT5 terminal running. The automation tools (config_manager, optimize_parameters) should still work. Only grid_search and batch_grid_search will fail.

**Solution:**
- For testing automation tools: No action needed, they work without MT5
- For running backtests: Install and run MT5 terminal

### Error: "Run directory not found"

**Cause:** Trying to analyze results that don't exist yet.

**Solution:** Run a grid search first to generate results, or use existing results from previous runs.

### Error: "Config file not found"

**Cause:** Running from wrong directory.

**Solution:** Make sure you're in the project root directory:
```bash
cd C:\Users\Admin\Projects\Sinfo_System
```

---

## ✨ Quick Test Summary

Run these commands to verify everything works:

```bash
# 1. Test config manager (should work)
python bot/config_manager.py --get-strategy

# 2. Test parameter generation (should work)
python bot/optimize_parameters.py --strategy elastic_band --max-combinations 3

# 3. Test dry run (should work)
python bot/config_manager.py --set-strategy fvg --dry-run

# 4. Check generated files (should work)
dir tests\parameter_sets

# 5. View help (should work)
python bot/automate_optimization.py --help
```

All 5 commands should complete without errors!

---

## 🎯 When You Have MT5 Available

```bash
# The ultimate test - complete automation!
python bot/automate_optimization.py \
  --symbols EURUSD \
  --phase 1 \
  --days 7 \
  --max-combinations 3 \
  --auto-apply

# Then just run the bot
python bot/main.py
```

---

## 📝 Test Checklist

- [ ] Config manager gets current strategy
- [ ] Config manager dry run works
- [ ] Parameter generation creates JSON files
- [ ] All help commands work
- [ ] (MT5 required) Grid search runs
- [ ] (MT5 required) Batch grid search runs
- [ ] (MT5 required) Results aggregator works
- [ ] (MT5 required) Complete automation works
- [ ] (MT5 required) Config auto-apply works
- [ ] (MT5 required) Backup/restore works
