# Elastic Band Trading Bot

A high-win-rate mean reversion trading system designed for passing proprietary trading firm (prop firm) evaluations within strict drawdown limits.

## Core Philosophy

**Risk Management is the primary driver; Trade Signals are secondary.**

The system prioritizes account survival (preventing the 5% daily breach) over profit maximization.

---

## Trading Strategy: "The Elastic Band"

**Type:** Trend-Following Mean Reversion
**Timeframe:** M15 (15-Minute)
**Assets:** EURUSD, GBPUSD, USDJPY

### Indicator Configuration

| Indicator | Period | Purpose |
|-----------|--------|---------|
| EMA | 200 | Trend Filter |
| EMA | 50 | Reversion Zone |
| RSI | 7 | Entry Trigger |
| ATR | 14 | Stop Loss Sizing |

### Entry Logic

#### LONG (BUY) Signal
1. **Trend Condition:** Close Price > EMA(200)
2. **Dip Condition:** Low Price touches EMA(50) ± 2 pips
3. **RSI Trigger:** Previous RSI < 30, Current RSI >= 30 (hooking up from oversold)

#### SHORT (SELL) Signal
1. **Trend Condition:** Close Price < EMA(200)
2. **Rally Condition:** High Price touches EMA(50) ± 2 pips
3. **RSI Trigger:** Previous RSI > 70, Current RSI <= 70 (hooking down from overbought)

### Exit Logic

- **Stop Loss:** Entry Price ± (ATR(14) × 1.5)
- **Take Profit:** 1:1 Risk/Reward ratio
- **Time Exit:** Close profitable trades after 180 minutes (3 hours)

---

## Operational Phases

| Parameter | Phase 1 (Challenge) | Phase 2 (Verification) | Phase 3 (Funded) |
|-----------|---------------------|------------------------|------------------|
| Profit Target | 10% | 8% | N/A (Growth) |
| Max Daily Loss | 5% (Buffer: 4.5%) | 5% (Buffer: 4.5%) | 5% (Buffer: 3.0%) |
| Max Total Loss | 10% | 10% | 10% |
| Risk Per Trade | 1.0% | 0.5% - 0.8% | 0.25% - 0.5% |

---

## Risk Management Module

The Risk Management module operates independently and acts as a "Circuit Breaker" that wraps all trading logic.

### 1. Daily Loss Guard (DLG)

```python
Current_Loss = Daily_Start_Equity - Current_Equity
IF Current_Loss >= Daily_Limit:
    CLOSE_ALL_POSITIONS()
    DISABLE_TRADING(Until="00:00 Next Day")
    SEND_ALERT("CRITICAL: Daily Limit Reached")
```

**Features:**
- Calculates equity snapshot at Server Time 00:00
- Monitors floating P/L continuously
- Hard stop at 4.5% (buffer before 5% limit)
- Automatic position closure when breached

### 2. Dynamic Position Sizing

**Formula:**
```
LotSize = (CurrentEquity × RiskPercentage) / (StopLossPips × PipValue)
```

**Constraints:**
- Validates minimum/maximum lot sizes
- Checks available margin
- Aborts trade if requirements not met

### 3. Tilt Protection

**Logic:**
- Tracks consecutive losses
- Pauses trading for 4 hours after 3 consecutive losses
- Prevents fighting strong trends that invalidate mean reversion

---

## Bot Structure

```
bot/
├── __init__.py
├── config.py           # Phase and strategy configurations
├── risk_manager.py     # Risk management (DLG, Sizer, Tilt)
├── indicators.py       # EMA, RSI, ATR calculations
├── strategy.py         # Signal detection logic
├── news_filter.py      # ForexFactory integration
├── trader.py           # Order execution
├── main.py             # Main bot entry point
├── backtester.py       # Historical backtesting
└── backtest_runner.py  # Backtest CLI tool
```

---

## Usage

### Running the Bot

```bash
python bot/main.py --account YOUR_ACCOUNT --password YOUR_PASSWORD --server YOUR_SERVER --name "Account1"
```

**Arguments:**
- `--account`: MT5 account number
- `--password`: MT5 password
- `--server`: MT5 server name (e.g., "ICMarkets-Demo")
- `--name`: Account name for logging (optional)

### Running Backtests

```bash
# Single symbol, Phase 1, 90 days
python bot/backtest_runner.py --symbols EURUSD --phase 1 --days 90 --balance 10000

# Multiple symbols
python bot/backtest_runner.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 90

# All phases comparison
python bot/backtest_runner.py --symbols EURUSD --phase all --days 180

# Save results to JSON
python bot/backtest_runner.py --symbols EURUSD --phase 1 --output results.json
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_risk_manager.py -v
```

---

## Configuration

### Changing Trading Phase

Edit `bot/config.py`:
```python
ACTIVE_PHASE = TradingPhase.PHASE_1  # or PHASE_2, PHASE_3
```

### Strategy Parameters

All parameters are in `bot/config.py`:

```python
STRATEGY_CONFIG = {
    'timeframe': 'M15',
    'symbols': ['EURUSD', 'GBPUSD', 'USDJPY'],
    'ema_trend_period': 200,
    'ema_reversion_period': 50,
    'rsi_period': 7,
    'atr_period': 14,
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'ema_touch_tolerance_pips': 2,
    'atr_sl_multiplier': 1.5,
    'risk_reward_ratio': 1.0,
    'max_trade_duration_minutes': 180,
    'max_consecutive_losses': 3,
    'tilt_pause_hours': 4,
}
```

---

## Data Flow

```
┌─────────────────┐
│  Start/OnBar    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Check Daily     │────▶│   Halt Trading  │
│ Guard           │ Hit └─────────────────┘
└────────┬────────┘
         │ Safe
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Check News      │────▶│   Halt Trading  │
│ Filter          │ News└─────────────────┘
└────────┬────────┘
         │ Safe
         ▼
┌─────────────────┐
│ Update          │
│ Indicators      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Check Signal    │
│ (EMA + RSI)     │
└────────┬────────┘
         │ Valid
         ▼
┌─────────────────┐
│ Calculate       │
│ Position Size   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Send Order      │
│ to Broker       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Monitor Trade   │
│ (TP/SL/Time)    │
└─────────────────┘
```

---

## Backtesting Metrics

The backtester calculates:

- **Net Profit/Loss:** Total P/L from all trades
- **Win Rate:** Percentage of winning trades
- **Profit Factor:** Gross Profit / Gross Loss
- **Expectancy:** Average profit per trade
- **Max Drawdown:** Maximum peak-to-trough decline
- **Max Consecutive Losses:** Longest losing streak

### Viability Analysis

The system checks prop firm viability:
- ✓ Profit target achieved
- ✓ Drawdown within daily limit
- ✓ Win rate > 40%

---

## News Filter

Integrates with ForexFactory calendar:

- Fetches high-impact (red folder) events
- 30-minute blackout window before/after events
- Filters by currencies: USD, EUR, GBP, JPY
- Auto-refreshes every 4 hours

---

## Next Steps (Roadmap)

### Immediate (Step 4 - Testing)
1. Run comprehensive backtests on 6-12 months of data
2. Validate strategy on all three trading phases
3. Optimize parameters based on results:
   - RSI periods (5, 7, 9, 14)
   - ATR multiplier (1.0, 1.5, 2.0)
   - EMA tolerance (1, 2, 3 pips)
   - Risk/Reward ratio (1:1, 1:1.5, 1:2)

### Short-term
1. Add walk-forward optimization
2. Implement Monte Carlo simulation
3. Add equity curve visualization
4. Create parameter optimization grid search

### Medium-term
1. Add machine learning signal filtering
2. Implement multi-timeframe confirmation
3. Add correlation analysis between pairs
4. Create dashboard for monitoring

### Long-term
1. Deploy to production VPS
2. Add real-time alerting (Telegram/Email)
3. Implement portfolio-level risk management
4. Add automatic parameter adaptation

---

## Deployment

### Recommended Setup

1. **Windows VPS** with:
   - Low latency (<5ms) to broker server
   - 24/7 uptime
   - Minimum 4GB RAM

2. **MT5 Terminal** running continuously

3. **Scheduled restarts** for stability

### Do NOT run on:
- Home laptop/desktop
- Unstable internet connection
- Shared hosting

---

## Disclaimer

This software is for educational purposes only. Trading foreign exchange carries a high level of risk and may not be suitable for all investors. Past performance is not indicative of future results. Use at your own risk.
