# Prop Firm Trading System

A comprehensive trading system for Proprietary Trading Firms (FTMO, Apex, Funded Engineer, etc.) consisting of two main components:

1. **Elastic Band Trading Bot** - Automated mean reversion strategy for passing prop firm challenges
2. **Multi-Account Copy Trading** - Trade copying infrastructure across multiple accounts

---

## Component 1: Elastic Band Trading Bot

A high-win-rate mean reversion strategy designed to pass prop firm evaluations within strict drawdown limits.

**Core Philosophy:** Risk Management is the primary driver; Trade Signals are secondary.

### Quick Start

```bash
# 🚀 NEW: Complete automated optimization (ONE COMMAND!)
python bot/automate_optimization.py --symbols EURUSD,GBPUSD --phase 1 --days 90 --auto-apply

# Run the bot with optimized settings
python bot/main.py --account YOUR_ACCOUNT --password YOUR_PASSWORD --server YOUR_SERVER

# Run backtests
python bot/backtest_runner.py --symbols EURUSD,GBPUSD,USDJPY --phase 1 --days 90

# Run tests
python -m pytest tests/ -v
```

**Full Documentation:**
- [AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md) - **NEW! Complete automation system**
- [docs/ELASTIC_BAND_BOT.md](docs/ELASTIC_BAND_BOT.md) - Bot details
- [GRID_SEARCH_GUIDE.md](GRID_SEARCH_GUIDE.md) - Parameter optimization

### Key Features

🚀 **Full Automation**
- One-command optimization across all 4 strategies
- Automatic parameter application (no manual editing!)
- Batch testing for multiple strategies/phases
- Unified comparison and ranking

📊 **4 Trading Strategies**
- Elastic Band: Mean reversion with EMA bands
- FVG (Fair Value Gap): 61% win rate gap trading
- MACD + RSI: Momentum-based combination
- Elastic BB: Enhanced with Bollinger Bands

🛡️ **Robust Risk Management**
- Daily Loss Guard with tilt protection
- Dynamic position sizing based on account phase
- News filter integration (ForexFactory)
- Automatic SL/TP management

🧪 **Advanced Testing**
- Historical backtesting with MT5 data
- Grid search parameter optimization
- Multi-metric ranking (profit, win rate, drawdown, risk-adjusted)
- Resume capability for interrupted tests

### Strategy Overview

- **Type:** Trend-Following Mean Reversion
- **Timeframe:** M15
- **Assets:** EURUSD, GBPUSD, USDJPY

| Phase | Profit Target | Daily Loss Limit | Risk/Trade |
|-------|--------------|------------------|------------|
| Challenge | 10% | 4.5% buffer | 1.0% |
| Verification | 8% | 4.5% buffer | 0.5-0.8% |
| Funded | Growth | 3.0% buffer | 0.25-0.5% |

---

## Component 2: Multi-Account Copy Trading

A low-latency, cross-broker trade copying infrastructure. Bypasses MT5's single-account limitation using asynchronous multiprocessing and ZeroMQ message bus.

## Architecture

- **Pattern:** Publisher-Subscriber (PUB/SUB) with Hub-and-Spoke topology
- **Process Isolation:** Each MT5 terminal runs in its own Python process
- **Communication:** ZeroMQ for inter-process communication (<1ms latency)
- **Persistence:** MongoDB for configuration and trade mapping

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Master    │     │   ZeroMQ    │     │   Slave 1   │
│   Node      │────▶│    Bus      │────▶│   Node      │
│  (Signal)   │     │  (PUB/SUB)  │     │ (Executor)  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │            ┌─────────────┐
                           └───────────▶│   Slave 2   │
                                        │   Node      │
                                        └─────────────┘
```

## Requirements

- **Python:** 3.6 - 3.12 (64-bit) - MetaTrader5 library limitation
- **OS:** Windows only (MT5 requirement)
- **MongoDB:** Community Server (localhost:27017)
- **MT5 Terminals:** One per account (Master + Slaves)

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install MetaTrader5 Library

```bash
pip install MetaTrader5
```

> **Note:** MetaTrader5 requires Python 3.6-3.12. If you're using Python 3.13+, create a virtual environment with an older Python version.

### 3. Install MongoDB

Download and install [MongoDB Community Server](https://www.mongodb.com/try/download/community).

### 4. Initialize Database

```bash
python setup_db.py
```

This creates indexes and sample account configurations.

## Configuration

### Account Configuration (MongoDB)

Accounts are stored in the `prop_copy_trader.accounts` collection:

#### Master Account Example
```json
{
  "name": "FTMO_Master",
  "type": "MASTER",
  "path": "C:/Program Files/FTMO MT5/terminal64.exe",
  "enabled": true
}
```

#### Slave Account Example
```json
{
  "name": "Apex_Slave_01",
  "type": "SLAVE",
  "path": "C:/Program Files/Apex MT5/terminal64.exe",
  "enabled": true,
  "suffix": ".c",
  "symbol_map": {
    "XAUUSD": "GOLD",
    "US30": "DJ30"
  },
  "slippage_tolerance": 50
}
```

### Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | String | Unique account identifier |
| `type` | String | "MASTER" or "SLAVE" |
| `path` | String | Absolute path to terminal64.exe |
| `enabled` | Boolean | Include/exclude from launcher |
| `suffix` | String | Broker suffix (e.g., ".c", ".pro") |
| `symbol_map` | Object | Manual symbol overrides |
| `slippage_tolerance` | Integer | Max deviation in points |

### System Configuration

Edit `config.py` to customize:

```python
# MongoDB
MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "prop_copy_trader"

# ZeroMQ
ZMQ_PUB_PORT = 5555

# Polling
MASTER_POLL_INTERVAL_MS = 100  # Position check frequency

# Trading
DEFAULT_SLIPPAGE_TOLERANCE = 50  # Points
DEFAULT_MAGIC_NUMBER = 234000
```

## Usage

### Start the System

```bash
python launcher.py
```

The launcher will:
1. Connect to MongoDB
2. Load all enabled accounts
3. Spawn master process(es)
4. Wait 1 second for publisher initialization
5. Spawn slave processes
6. Monitor all processes

### Stop the System

Press `Ctrl+C` to gracefully stop all processes.

### Run Individual Nodes (Development)

```bash
# Master node
python nodes/master.py --name FTMO_Master --path "C:/path/to/terminal64.exe"

# Slave node
python nodes/slave.py --name Apex_Slave_01 --path "C:/path/to/terminal64.exe"
```

## Features

### Symbol Translation

The system handles broker-specific symbol naming:

1. **Manual Mapping:** Check `symbol_map` first
   - `XAUUSD` → `GOLD`
   - `US30` → `DJ30`

2. **Automatic Suffix:** Append broker suffix
   - `EURUSD` → `EURUSD.c`

### Slippage Protection

Before executing, the slave checks if the current price is within tolerance:

```
|current_price - master_price| / point <= slippage_tolerance
```

If exceeded, the trade is aborted with a warning log.

### Trade Lifecycle Tracking

The `trades` collection maps master ↔ slave tickets:

```json
{
  "master_ticket": 12345678,
  "slave_ticket": 87654321,
  "slave_name": "Apex_Slave_01",
  "symbol": "EURUSD.c",
  "direction": "BUY",
  "status": "OPEN",
  "open_time": "2025-11-23T10:30:00Z"
}
```

When the master closes a position, the system queries this mapping to close the correct slave ticket.

### Order Execution

- **Action:** `TRADE_ACTION_DEAL` (Market Execution)
- **Filling:** `ORDER_FILLING_IOC` (Immediate or Cancel)
- **Comment:** Contains master ticket for traceability

## Project Structure

```
Sinfo_System/
├── config.py                  # Global configuration
├── launcher.py                # Copy trading orchestrator
├── setup_db.py                # Database initialization
├── requirements.txt           # Dependencies
├── README.md                  # This file
│
├── bot/                       # Elastic Band Trading Bot
│   ├── __init__.py
│   ├── config.py              # Phase & strategy configs
│   ├── risk_manager.py        # Risk management module
│   ├── indicators.py          # EMA, RSI, ATR
│   ├── strategy.py            # Signal detection
│   ├── news_filter.py         # ForexFactory integration
│   ├── trader.py              # Order execution
│   ├── main.py                # Bot entry point
│   ├── backtester.py          # Historical testing
│   └── backtest_runner.py     # Backtest CLI
│
├── tests/                     # Unit tests
│   ├── __init__.py
│   ├── test_risk_manager.py
│   ├── test_strategy.py
│   └── test_indicators.py
│
├── docs/                      # Documentation
│   └── ELASTIC_BAND_BOT.md    # Bot documentation
│
├── db/                        # MongoDB
│   ├── __init__.py
│   ├── connection.py          # Connection manager
│   └── models.py              # Account & Trade models
│
├── messaging/                 # ZeroMQ
│   ├── __init__.py
│   └── zmq_bus.py             # PUB/SUB classes
│
├── nodes/                     # Copy trading nodes
│   ├── __init__.py
│   ├── master.py              # Signal Generator
│   └── slave.py               # Execution Engine
│
└── utils/                     # Utilities
    ├── __init__.py
    ├── logger.py              # Logging setup
    └── symbol_translator.py   # Symbol normalization
```

## Database Schema

### Collection: `accounts`

Stores connectivity details and configuration for each prop firm account.

### Collection: `trades`

Maps the lifecycle of copied trades:

| Field | Type | Description |
|-------|------|-------------|
| `master_ticket` | Integer | Ticket ID from Master Broker |
| `slave_ticket` | Integer | Ticket ID from Slave Broker |
| `slave_name` | String | Identifier of the Slave account |
| `symbol` | String | Symbol traded on the Slave |
| `direction` | String | "BUY" or "SELL" |
| `status` | String | "OPEN" or "CLOSED" |
| `open_time` | Timestamp | Time of execution |
| `close_time` | Timestamp | Time of closure (if closed) |

## Performance Specifications

- **Internal Bus Latency:** < 5ms
- **Tick-to-Trade Time:** < 500ms (excluding broker latency)
- **Polling Rate:** 50-100ms

## Limitations

- **Same-Size Accounts:** Lot sizes copied 1:1 (no scaling)
- **Windows Only:** MetaTrader5 requirement
- **Python 3.6-3.12:** MetaTrader5 library limitation

## Troubleshooting

### MT5 Initialization Failed
- Ensure terminal64.exe path is correct
- Check if MT5 is already running (only one connection per terminal)
- Verify the account is logged in

### Symbol Not Found
- Add mapping to `symbol_map` in account config
- Verify the symbol exists on the slave broker
- Check broker suffix

### Slippage Exceeded
- Increase `slippage_tolerance` in account config
- Check for high volatility periods
- Verify broker execution speed

### MongoDB Connection Failed
- Ensure MongoDB is running on localhost:27017
- Check firewall settings
- Verify MongoDB service status

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
