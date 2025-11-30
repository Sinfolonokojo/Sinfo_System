# 🚀 Quick Start Guide - Demo Trading

Complete guide to launch your Elastic Band Trading Bot on demo.

---

## ✅ Step 1: Test Connection (REQUIRED)

**Run the connection test first:**

```bash
python test_connection.py
```

**What it checks:**
- ✓ MT5 is installed and running
- ✓ Account connection working
- ✓ Trading symbols available (EURUSD, GBPUSD, USDJPY)
- ✓ M15 historical data accessible
- ✓ All Python packages installed
- ✓ Bot configuration valid

**If test fails:**
- Make sure MetaTrader 5 is open and logged in
- Check that you're logged into a demo account
- Verify EURUSD, GBPUSD, USDJPY are in Market Watch

---

## 🔧 Step 2: Configure Launch Script

**Edit `run_demo.bat`:**

1. Open `run_demo.bat` in a text editor
2. Replace these lines:
   ```batch
   set MT5_ACCOUNT=YOUR_ACCOUNT_NUMBER
   set MT5_PASSWORD=YOUR_PASSWORD
   set MT5_SERVER=YOUR_SERVER_NAME
   ```

3. With your MT5 demo credentials:
   ```batch
   set MT5_ACCOUNT=12345678
   set MT5_PASSWORD=YourPassword123
   set MT5_SERVER=MetaQuotes-Demo
   ```

4. Save the file

---

## 🤖 Step 3: Launch the Bot

**Run the bot:**

```bash
.\run_demo.bat
```

**Or manually:**

```bash
cd bot
python main.py --account 12345678 --password YourPassword --server MetaQuotes-Demo --name "FVG_DEMO"
```

**What you should see:**

```
============================================================
BOT:FVG_DEMO | Connected to MT5
BOT:FVG_DEMO | Account: 12345678 | Balance: $10,000.00
BOT:FVG_DEMO | Phase: Challenge (10% target, 5% max DD)
BOT:FVG_DEMO | Active Strategy: FVG
BOT:FVG_DEMO | Monitoring 3 symbols on M15
BOT:FVG_DEMO | Starting main loop...
============================================================
```

---

## 📊 Step 4: Start Monitoring Dashboard

**Open a NEW terminal window** and run:

```bash
python monitor_bot.py
```

**This displays real-time:**
- Account balance and equity
- Open positions
- Daily performance stats
- Recent closed trades
- Warnings and alerts

**Dashboard updates every 5 seconds**

---

## 📱 Step 5: Setup Telegram Notifications (OPTIONAL)

**Get Telegram credentials:**

1. **Create a bot:**
   - Open Telegram and message `@BotFather`
   - Send `/newbot`
   - Follow instructions
   - Copy the bot token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Get your chat ID:**
   - Message `@userinfobot` on Telegram
   - Copy your chat ID (looks like: `987654321`)

3. **Configure notifications:**
   - Edit `bot/notifier.py`
   - Replace these lines:
     ```python
     TELEGRAM_BOT_TOKEN = None
     TELEGRAM_CHAT_ID = None
     ```
   - With your credentials:
     ```python
     TELEGRAM_BOT_TOKEN = '123456789:ABCdefGHIjklMNOpqrsTUVwxyz'
     TELEGRAM_CHAT_ID = '987654321'
     ```

4. **Test notifications:**
   ```bash
   python bot/notifier.py
   ```

**You'll receive notifications for:**
- ✓ Trade opened (symbol, direction, entry, SL, TP)
- ✓ Trade closed (profit/loss, duration, reason)
- ✓ Daily summary (P&L, win rate, trades)
- ✓ Warnings (daily loss approaching limit)
- ✓ Errors and important events

---

## 🎯 Current Bot Configuration

**Strategy:** FVG (Fair Value Gap)
- **Logic:** Trades gap fills on M15 timeframe
- **Win Rate:** ~64% (from backtesting)
- **Min Gap:** 5 pips
- **Risk/Reward:** 1:1.5

**Risk Management:**
- **Risk per Trade:** 1.0% of balance
- **Max Daily Loss:** 5.0% (stops at 4.5%)
- **Max Consecutive Losses:** 3 (then 4-hour pause)
- **News Filter:** Avoids ±30min around high-impact news

**Trading Pairs:**
- EURUSD
- GBPUSD
- USDJPY

**Timeframe:** M15 (15 minutes)

---

## 📈 What to Monitor

**First 24 Hours:**
- [ ] Check dashboard every 2-4 hours
- [ ] Verify trades match FVG strategy logic
- [ ] Confirm position sizes are ~1% risk
- [ ] Watch for any errors in bot terminal

**First Week:**
- [ ] Daily P&L should stay within ±3%
- [ ] Win rate should be 55-70%
- [ ] No more than 3 consecutive losses
- [ ] Position sizes consistent

**Warning Signs:**
- 🚨 Daily loss approaching 4.5%
- 🚨 More than 3 consecutive losses
- 🚨 Position sizes much larger than expected
- 🚨 Trading during news events
- 🚨 Frequent connection errors

---

## 🛑 How to Stop the Bot

**Graceful Shutdown:**
1. Press `Ctrl+C` in the bot terminal
2. Bot will close all open positions
3. Final report will be printed

**Emergency Stop:**
1. Close the terminal window
2. Manually close positions in MT5

---

## 📋 Daily Checklist

**Morning (Before Market Opens):**
- [ ] Check bot is still running
- [ ] Review overnight trades (if any)
- [ ] Verify account balance matches expectations

**During Trading (Check 2-3 times):**
- [ ] Monitor dashboard for new trades
- [ ] Check daily P&L (should be < ±3%)
- [ ] Verify no errors in bot terminal

**Evening (After Market Closes):**
- [ ] Review daily summary
- [ ] Check win rate and performance
- [ ] Compare to expected results

---

## 🔍 Troubleshooting

**Bot won't connect to MT5:**
- Make sure MT5 is open and logged in
- Check credentials in run_demo.bat
- Run `test_connection.py` to diagnose

**No trades being opened:**
- FVG strategy waits for specific gap patterns
- May take hours or a full day to find setups
- Check logs for "FVG detected" messages

**Dashboard shows "ERROR":**
- Make sure bot is running in another terminal
- Check MT5 is still connected
- Restart dashboard: `python monitor_bot.py`

**Telegram not working:**
- Verify bot token and chat ID are correct
- Run `python bot/notifier.py` to test
- Check internet connection

---

## 📊 Expected Performance

**Based on 42-trade backtest:**

- **Win Rate:** ~64%
- **Average Trade:** +$10-15
- **Max Drawdown:** 2-3% per symbol
- **Trades per Week:** 5-7 (all 3 symbols)

**Important:** These are estimates from limited data. Real performance may vary.

---

## ⚠️ Important Reminders

1. **This is a DEMO account** - Practice first!
2. **Monitor closely** for the first 30 days
3. **Collect 50-100 trades** before going live
4. **Run validation again** with more data
5. **Don't change parameters** during testing

---

## 🎓 Next Steps

**After 30 Days:**
1. Run `python run_strategy_validation.py` again
2. Compare demo results to backtest
3. Analyze win rate and drawdown
4. Decide if ready for live trading

**After 60 Days (100+ trades):**
1. Full statistical validation
2. Walk-forward analysis
3. Parameter stability check
4. Live deployment decision

---

## 📞 Support

**Having issues?**
1. Check logs in `logs/` folder
2. Run `test_connection.py` for diagnostics
3. Review error messages in terminal
4. Check bot/config.py for settings

**Files to check:**
- `test_connection.py` - Connection diagnostics
- `monitor_bot.py` - Real-time dashboard
- `run_demo.bat` - Launch script
- `bot/config.py` - Strategy settings
- `bot/notifier.py` - Telegram setup

---

**Good luck with demo trading! 🚀**

Remember: The goal is to validate the strategy with real market data before risking real money.
