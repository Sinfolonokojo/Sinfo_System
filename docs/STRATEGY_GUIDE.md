# Trading Bot Strategy Guide

## Overview

This trading bot now includes **4 different strategies** optimized for prop firm challenges. Each strategy has been researched and designed with specific market conditions and trading objectives in mind.

---

## Available Strategies

### 1. **Elastic Band** (Original)
**File:** `bot/strategy.py`
**Best For:** Trending markets with clear pullbacks

#### Concept
Price acts like an elastic band - when stretched too far from the mean (EMA50), it snaps back, but only when aligned with the overall trend (EMA200).

#### Entry Rules
**LONG:**
- Price > EMA(200) - Uptrend confirmed
- Low touches EMA(50) ± 2 pips - Pullback to mean
- RSI crosses above 30 from below - Momentum reversal

**SHORT:**
- Price < EMA(200) - Downtrend confirmed
- High touches EMA(50) ± 2 pips - Rally to mean
- RSI crosses below 70 from above - Momentum reversal

#### Exit Rules
- **Stop Loss:** ATR(14) × 1.5
- **Take Profit:** 1:1 Risk/Reward
- **Time Exit:** Close after 180 minutes if profitable

#### Key Parameters
```python
'ema_trend_period': 200,
'ema_reversion_period': 50,
'rsi_period': 7,
'atr_sl_multiplier': 1.5,
'risk_reward_ratio': 1.0,
```

#### Strengths
- Conservative 1:1 RR → High win rate potential
- Trend filter prevents counter-trend losses
- Time exit reduces overnight risk

#### Weaknesses
- Requires clear trending market
- Low RR ratio needs high win rate
- May miss strong momentum moves

---

### 2. **Fair Value Gap (FVG)**
**File:** `bot/strategy_fvg.py`
**Best For:** Volatile markets with price imbalances
**Research Results:** 61% win rate (bearish setups)

#### Concept
Identifies price "gaps" where the market moved so fast that it left inefficiencies. These gaps tend to fill as price returns to find fair value.

#### Entry Rules
**LONG (Bullish FVG):**
- Current bar's low > High from 2 bars ago
- Gap size >= 5 pips (minimum)

**SHORT (Bearish FVG):**
- Current bar's high < Low from 2 bars ago
- Gap size >= 5 pips (minimum)

**Note:** Research shows bearish FVGs perform significantly better (61% vs 42% win rate)

#### Exit Rules
- **Stop Loss:** ATR(14) × 1.5
- **Take Profit:** 1:1.5 Risk/Reward (gap fill distance)
- **Time Exit:** Close after 5 bars (75 minutes on M15)

#### Key Parameters
```python
'fvg_min_gap_pips': 5,
'fvg_risk_reward_ratio': 1.5,
```

#### Strengths
- High win rate (especially shorts)
- Works in ranging and trending markets
- Clear, objective entry signals

#### Weaknesses
- Fewer signals than other strategies
- Requires sufficient volatility
- Gap may not always fill immediately

---

### 3. **MACD + RSI Combination**
**File:** `bot/strategy_macd_rsi.py`
**Best For:** Momentum-driven markets

#### Concept
Combines MACD histogram crossovers (momentum shift) with RSI confirmation (not overbought/oversold) to catch the start of trending moves.

#### Entry Rules
**LONG:**
- MACD histogram crosses above 0 (bullish momentum)
- RSI > 30 (not oversold)

**SHORT:**
- MACD histogram crosses below 0 (bearish momentum)
- RSI < 70 (not overbought)

#### Exit Rules
- **Stop Loss:** ATR(14) × 2.0 (wider for momentum)
- **Take Profit:** 1:2 Risk/Reward (let winners run)
- **Time Exit:** Close after 240 minutes (4 hours)

#### Key Parameters
```python
'macd_fast': 12,
'macd_slow': 27,
'macd_signal': 9,
'rsi_period': 7,
'macd_rsi_atr_sl': 2.0,
'macd_rsi_rr_ratio': 2.0,
```

#### Strengths
- Higher profit potential (2:1 RR)
- Catches trending moves early
- Multi-indicator confirmation reduces false signals

#### Weaknesses
- Lower win rate (momentum strategies typically 40-50%)
- Requires trending conditions
- Wider stops = higher risk per trade

---

### 4. **Enhanced Elastic Band with Bollinger Bands**
**File:** `bot/strategy_elastic_bb.py`
**Best For:** Mean reversion with volatility confirmation

#### Concept
Enhances the original Elastic Band strategy by adding Bollinger Bands confirmation. This ensures we only take mean reversion trades when price has reached extreme volatility levels.

#### Entry Rules
**LONG:**
- All original Elastic Band LONG conditions
- **PLUS:** Low touches or penetrates lower Bollinger Band

**SHORT:**
- All original Elastic Band SHORT conditions
- **PLUS:** High touches or penetrates upper Bollinger Band

#### Exit Rules
- **Stop Loss:** ATR(14) × 1.5
- **Take Profit:** 1:1.5 Risk/Reward
- **Time Exit:** Close after 180 minutes if profitable

#### Key Parameters
```python
'bb_period': 20,
'bb_std_dev': 2.0,
'bb_touch_tolerance_pct': 0.1,
'elastic_bb_rr_ratio': 1.5,
```

#### Strengths
- Fewer but higher quality signals
- Volatility context improves mean reversion timing
- Better RR than original (1.5 vs 1.0)

#### Weaknesses
- Very selective (may have long periods without signals)
- Requires both trend pullback AND volatility extreme
- Miss trades that don't reach BB extremes

---

## How to Switch Strategies

### Method 1: Edit Config File
Open `bot/config.py` and change line 69:

```python
# Choose one:
ACTIVE_STRATEGY = StrategyType.ELASTIC_BAND  # Original
ACTIVE_STRATEGY = StrategyType.FVG           # Fair Value Gap
ACTIVE_STRATEGY = StrategyType.MACD_RSI      # MACD + RSI
ACTIVE_STRATEGY = StrategyType.ELASTIC_BB    # Enhanced Elastic Band
```

### Method 2: Using Strategy Factory
The bot automatically uses the selected strategy via the strategy factory:

```python
from bot.strategy_factory import create_strategy

# Creates the active strategy from config
strategy = create_strategy("account_name")
```

---

## Testing & Optimization

### 1. Generate Parameter Grids
```bash
# Generate optimization parameters for all strategies
python bot/optimize_parameters.py --strategy all --max-combinations 100

# For specific strategy
python bot/optimize_parameters.py --strategy fvg --max-combinations 50
```

This creates JSON files in `bot/optimization/` with parameter combinations to test.

### 2. Run Backtests
```bash
# Test single strategy
python bot/backtest_runner.py --symbols EURUSD,GBPUSD --phase 1 --days 90

# Test with custom parameters (edit config first)
python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 180 --output results.json
```

### 3. Compare All Strategies
```bash
# Run all 4 strategies head-to-head
python bot/compare_strategies.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 90 --output comparison.json
```

This will show:
- Performance table for each strategy
- Rankings by profit, win rate, drawdown
- Recommended strategy for your objectives

---

## Parameter Optimization Ranges

### Elastic Band
| Parameter | Current | Test Range | Impact |
|-----------|---------|------------|--------|
| `rsi_period` | 7 | 5, 7, 9, 14 | Faster = more signals, noisier |
| `atr_sl_multiplier` | 1.5 | 1.0, 1.5, 2.0, 2.5 | Lower = tighter stops, higher win rate |
| `risk_reward_ratio` | 1.0 | 1.0, 1.5, 2.0 | Higher = lower win rate, better PF |
| `ema_reversion_period` | 50 | 20, 30, 50, 100 | Faster = more frequent pullbacks |

### FVG
| Parameter | Current | Test Range | Impact |
|-----------|---------|------------|--------|
| `fvg_min_gap_pips` | 5 | 3, 5, 7, 10 | Lower = more signals, lower quality |
| `fvg_risk_reward_ratio` | 1.5 | 1.0, 1.5, 2.0 | Trade-off: win rate vs profit |

### MACD + RSI
| Parameter | Current | Test Range | Impact |
|-----------|---------|------------|--------|
| `macd_fast` | 12 | 8, 12, 16 | Faster = more responsive |
| `macd_slow` | 27 | 21, 27, 33 | Slower = fewer signals |
| `macd_rsi_rr_ratio` | 2.0 | 1.5, 2.0, 2.5 | Momentum can run farther |

### Elastic BB
| Parameter | Current | Test Range | Impact |
|-----------|---------|------------|--------|
| `bb_period` | 20 | 15, 20, 25 | Standard BB period |
| `bb_std_dev` | 2.0 | 1.5, 2.0, 2.5 | Lower = tighter bands, more signals |
| `elastic_bb_rr_ratio` | 1.5 | 1.0, 1.5, 2.0 | Conservative to aggressive |

---

## Strategy Selection Guide

### For Phase 1 (Challenge - Need 10% Fast)

**Best Choice:** Depends on market conditions

| Market Condition | Recommended Strategy | Why |
|-----------------|---------------------|-----|
| **Strong Trends** | MACD + RSI | Catches momentum moves with 2:1 RR |
| **Ranging/Choppy** | FVG | High win rate (61%) mean reversion |
| **Volatile Swings** | Elastic BB | Quality pullbacks at extremes |
| **Balanced/Unsure** | Elastic Band | Conservative, proven foundation |

### For Phase 2 (Verification - Need 8%)
**Best Choice:** Elastic Band or Elastic BB
- Lower risk per trade (0.5-0.8%)
- Focus on consistency over speed
- High win rate protects drawdown

### For Phase 3 (Funded - Growth Mode)
**Best Choice:** MACD + RSI or FVG
- Can handle lower win rate with 2:1 RR
- Conservative position sizing (0.25-0.5%)
- Long-term profit focus

---

## Next Steps

1. **Run Initial Backtests**
   ```bash
   python bot/compare_strategies.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 180
   ```

2. **Analyze Results**
   - Which strategy has highest profit?
   - Which has best win rate?
   - Which stays under drawdown limits?

3. **Optimize Best 2-3 Strategies**
   ```bash
   python bot/optimize_parameters.py --strategy elastic_band --max-combinations 100
   # Edit config with best parameters
   # Re-run backtests
   ```

4. **Live Test (Paper Trading)**
   - Deploy best strategy on demo account
   - Monitor for 2-4 weeks
   - Validate backtest results

5. **Go Live**
   - Start with funded account (Phase 3 risk)
   - Scale up as confidence grows

---

## Risk Management Notes

**All strategies share the same risk management:**
- Daily Loss Guard (4.5% hard stop)
- Dynamic position sizing (risk % of equity)
- Tilt protection (pause after 3 consecutive losses)
- News filter (avoid high-impact events)

**This cannot be changed per strategy** - it's part of the prop firm protection layer.

---

## Questions?

- Check `docs/ELASTIC_BAND_BOT.md` for overall system architecture
- Check `bot/config.py` for all parameters
- Run `python bot/compare_strategies.py --help` for CLI options
