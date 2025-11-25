# Bot Optimization Quick Start Guide

## What We Built

Your trading bot now has **4 strategies** ready to test:

1. **Elastic Band** - Original trend-following mean reversion (1:1 RR, conservative)
2. **Fair Value Gap (FVG)** - Gap trading (61% win rate from research, 1:1.5 RR)
3. **MACD + RSI** - Momentum combination (2:1 RR, aggressive)
4. **Enhanced Elastic Band + BB** - Mean reversion with volatility confirmation (1:1.5 RR)

All strategies share the same robust risk management:
- Daily Loss Guard (stops at 4.5% loss)
- Position sizing based on ATR
- Tilt protection (pause after 3 losses)
- News filter (ForexFactory integration)

---

## Quick Start: 3 Simple Steps

### Step 1: Compare All Strategies (10 minutes)

Run this command to test all 4 strategies head-to-head:

```bash
python bot/compare_strategies.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 90
```

**What this does:**
- Tests all 4 strategies on 3 currency pairs
- Uses last 90 days of data
- Phase 1 settings (Challenge mode - 10% target)
- Shows you which strategy performs best

**Output Example:**
```
STRATEGY PERFORMANCE SUMMARY
Strategy          Total Trades    Win Rate    Total P/L        Max DD%
Elastic_Band      45              52.3        $450.25          3.2
FVG               28              61.2        $520.80          2.8
MACD_RSI          52              45.1        $680.50          4.1
Elastic_BB        18              66.7        $390.20          2.1

RECOMMENDATION
Best Overall Profit: MACD_RSI ($680.50)
Highest Win Rate: Elastic_BB (66.7%)
```

### Step 2: Optimize Your Best Strategy (30 minutes)

Based on Step 1 results, let's say **FVG** performed best. Now optimize its parameters:

```bash
# Generate parameter combinations
python bot/optimize_parameters.py --strategy fvg --max-combinations 50

# This creates: bot/optimization/fvg_params.json with 50 parameter sets to test
```

**Then edit `bot/config.py` and test each combination:**

```python
# Example: Test different gap sizes
'fvg_min_gap_pips': 3,  # Try 3, 5, 7, 10
'fvg_risk_reward_ratio': 1.5,  # Try 1.0, 1.5, 2.0
```

After each change, run:
```bash
python bot/backtest_runner.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 90 --output results_fvg_gap3.json
```

### Step 3: Deploy Your Winning Strategy

Once you find the best parameters:

1. **Update config:**
```python
# bot/config.py line 69
ACTIVE_STRATEGY = StrategyType.FVG  # Or whichever won

# Update parameters with your optimized values
'fvg_min_gap_pips': 5,  # Your best value
'fvg_risk_reward_ratio': 1.5,  # Your best value
```

2. **Test on demo account:**
```bash
python bot/main.py  # Runs with your selected strategy
```

3. **Monitor for 1-2 weeks, then go live!**

---

## Detailed Workflow: Finding the Best Strategy

### Phase 1: Initial Comparison (1 hour)

**Goal:** Find top 2-3 strategies for your market conditions

```bash
# Test all strategies - 30 days (quick)
python bot/compare_strategies.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 30

# Test all strategies - 90 days (thorough)
python bot/compare_strategies.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 90 --output comparison_90d.json

# Test all strategies - 180 days (comprehensive)
python bot/compare_strategies.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 180 --output comparison_180d.json
```

**Look for:**
- ✓ Profit > 10% (Phase 1 target)
- ✓ Max drawdown < 4% (under 4.5% buffer)
- ✓ Win rate > 45%
- ✓ Profit factor > 1.5

**Pick top 2 strategies that meet these criteria.**

---

### Phase 2: Parameter Optimization (2-4 hours)

**Goal:** Fine-tune the top 2 strategies

#### Example: Optimizing Elastic Band

```bash
# Generate parameter grid
python bot/optimize_parameters.py --strategy elastic_band --max-combinations 100
```

This creates `bot/optimization/elastic_band_params.json` with combinations like:

```json
{
  "combinations": [
    {"rsi_period": 5, "atr_sl_multiplier": 1.0, "risk_reward_ratio": 1.0},
    {"rsi_period": 5, "atr_sl_multiplier": 1.5, "risk_reward_ratio": 1.5},
    ...
  ]
}
```

**Manual Testing (Recommended for Beginners):**

Pick 5-10 interesting combinations and test manually:

```python
# bot/config.py - Try combination 1
'rsi_period': 5,
'atr_sl_multiplier': 1.0,
'risk_reward_ratio': 1.0,
```

```bash
python bot/backtest_runner.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 90 --output elastic_combo1.json
```

Repeat for each combination. Record results in a spreadsheet.

**Automated Testing (Advanced):**

```bash
# Coming soon: automated grid search
python bot/grid_search.py --strategy elastic_band --params bot/optimization/elastic_band_params.json
```

---

### Phase 3: Validation (1 week)

**Goal:** Confirm optimized strategy works on unseen data

1. **Out-of-Sample Test:**
```bash
# If you optimized on last 90 days, test on prior 90 days
python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 180
# Check if days 91-180 perform similarly to days 1-90
```

2. **Different Timeframes:**
```python
# bot/config.py
'timeframe': 'M30',  # Try M5, M30, H1
```

```bash
python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 90
```

3. **Different Symbols:**
```bash
# Add AUDUSD, USDCAD, XAUUSD
python bot/backtest_runner.py --symbols AUDUSD,USDCAD --phase 1 --days 90
```

**If performance is similar:** Your strategy is robust! ✓
**If performance degrades:** You may have overfit. Go back to Phase 2 with less aggressive parameters.

---

## Understanding the Results

### Key Metrics Explained

| Metric | What It Means | Good Target |
|--------|---------------|-------------|
| **Net Profit** | Total $ gained | >10% of balance for Phase 1 |
| **Total Trades** | Number of signals | 30-100 for 90 days (not too few, not excessive) |
| **Win Rate** | % of winning trades | >45% (higher is safer) |
| **Profit Factor** | Gross Profit / Gross Loss | >1.5 (1.0 = breakeven) |
| **Max Drawdown %** | Worst peak-to-valley loss | <4% (must stay under 4.5% buffer) |
| **Expectancy** | Average profit per trade | >$5 per trade |
| **Avg Win / Avg Loss** | Quality of trades | >1.0 for balanced RR |

### Example Good Result (Phase 1 - Challenge)

```
Symbol: EURUSD
Phase: Challenge
Timeframe: M15
Period: 90 days

Total Trades: 48
Win Rate: 56.2%
Net Profit: $1,250 (12.5% on $10k account)
Profit Factor: 1.82
Max Drawdown: 3.2%
Expectancy: $26.04

✓ VIABLE for Phase 1 Challenge
  - Profit target met (12.5% > 10%)
  - Drawdown safe (3.2% < 4.5%)
  - Win rate acceptable (56% > 45%)
```

### Example Bad Result

```
Symbol: GBPUSD
Phase: Challenge
Period: 90 days

Total Trades: 15  ⚠ Too few
Win Rate: 33.3%   ⚠ Too low
Net Profit: $450 (4.5%)  ⚠ Below target
Max Drawdown: 5.2%  ⚠ OVER LIMIT
Profit Factor: 0.95  ⚠ Losing strategy

✗ NOT VIABLE for Phase 1 Challenge
  - Profit target NOT met (4.5% < 10%)
  - Drawdown EXCEEDED limit (5.2% > 4.5%)
  - Win rate unacceptable (33% < 45%)
```

---

## Tips for Best Results

### 1. Data Quality
- Use at least **90 days** of data (preferably 180)
- Avoid holiday periods (low volume, unusual behavior)
- Test across different market conditions (trending, ranging)

### 2. Avoid Overfitting
- Don't optimize on the same data you test on
- Use walk-forward testing (optimize 60%, test on 40%)
- Simpler is better (fewer parameters = more robust)

### 3. Market Conditions
- **Trending markets:** MACD+RSI, Elastic Band
- **Ranging markets:** FVG, Elastic BB
- **Volatile markets:** FVG, strategies with wider stops
- **Quiet markets:** Elastic BB (fewer but quality signals)

### 4. Correlation Awareness
- EURUSD and GBPUSD are correlated (80%+)
- Don't run both simultaneously (doubles risk)
- Test portfolio effect (all symbols together)

### 5. Prop Firm Mindset
- **Phase 1:** Aggressive (1% risk, 10% target, 30-60 days)
- **Phase 2:** Balanced (0.5-0.8% risk, 8% target)
- **Phase 3:** Conservative (0.25-0.5% risk, steady growth)

---

## Command Reference

### Compare Strategies
```bash
python bot/compare_strategies.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 90 --output comparison.json
```

### Generate Parameters
```bash
python bot/optimize_parameters.py --strategy all --max-combinations 100 --output-dir bot/optimization
```

### Run Backtest
```bash
python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 90 --output results.json
```

### Test Specific Strategy
```python
# Edit bot/config.py first
ACTIVE_STRATEGY = StrategyType.FVG
```
```bash
python bot/backtest_runner.py --symbols EURUSD,GBPUSD --phase 1 --days 90
```

---

## What's Next?

### Immediate Actions:
1. ✓ Run strategy comparison (Step 1 above)
2. ✓ Pick your top 2 strategies
3. ✓ Optimize parameters
4. ✓ Validate on different timeframes/symbols

### Advanced Enhancements (Coming Soon):
- ✓ Trailing stops (move SL to breakeven after 0.5R)
- ✓ Partial exits (close 50% at 1R, let 50% run)
- ✓ Correlation filter (prevent correlated pair trading)
- ✓ Time-of-day filter (avoid low liquidity hours)
- ✓ Multi-timeframe confirmation (H1 + M15)

### Final Goal:
**Pass Phase 1 challenge in 30-45 days with <3% max drawdown**

---

## Need Help?

1. Check `docs/STRATEGY_GUIDE.md` for strategy details
2. Check `docs/ELASTIC_BAND_BOT.md` for system architecture
3. Review `bot/config.py` for all parameters
4. Run scripts with `--help` flag for options

**Good luck with your optimization! 🚀**
