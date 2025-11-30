"""
Test MT5 Connection and Bot Prerequisites.

Run this before launching the bot to verify everything is ready.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_mt5_connection():
    """Test MT5 connection and basic functionality."""
    print("\n" + "="*70)
    print("  MT5 CONNECTION TEST")
    print("="*70)

    try:
        import MetaTrader5 as mt5
        print("✓ MetaTrader5 module installed")
    except ImportError:
        print("✗ MetaTrader5 module NOT installed")
        print("  Install with: pip install MetaTrader5")
        return False

    # Initialize MT5
    if not mt5.initialize():
        print("✗ MT5 initialization failed")
        print("  Make sure MetaTrader 5 is running and logged in")
        return False

    print("✓ MT5 initialized successfully")

    # Get account info
    account_info = mt5.account_info()
    if account_info is None:
        print("✗ Could not get account info")
        mt5.shutdown()
        return False

    print("✓ Account info retrieved")
    print(f"\n  Account Number: {account_info.login}")
    print(f"  Server: {account_info.server}")
    print(f"  Balance: ${account_info.balance:.2f}")
    print(f"  Equity: ${account_info.equity:.2f}")
    print(f"  Leverage: 1:{account_info.leverage}")
    print(f"  Currency: {account_info.currency}")

    # Check if it's a demo account
    if "demo" in account_info.server.lower():
        print(f"  Account Type: DEMO ✓")
    else:
        print(f"  Account Type: LIVE ⚠")
        print("  WARNING: This appears to be a LIVE account!")

    # Check symbols
    print(f"\n  Checking Trading Symbols...")
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
    all_available = True

    for symbol in symbols:
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"  ✗ {symbol} - NOT AVAILABLE")
            all_available = False
        else:
            if symbol_info.visible:
                print(f"  ✓ {symbol} - Available (Spread: {symbol_info.spread} points)")
            else:
                print(f"  ⚠ {symbol} - Not visible in Market Watch")
                # Try to add to Market Watch
                if mt5.symbol_select(symbol, True):
                    print(f"    → Added to Market Watch")
                else:
                    print(f"    → Failed to add to Market Watch")
                    all_available = False

    # Check timeframe data
    print(f"\n  Checking M15 Historical Data...")
    for symbol in symbols:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 10)
        if rates is not None and len(rates) > 0:
            print(f"  ✓ {symbol} M15 data available ({len(rates)} bars)")
        else:
            print(f"  ✗ {symbol} M15 data NOT available")
            all_available = False

    mt5.shutdown()

    print("\n" + "="*70)
    if all_available:
        print("  CONNECTION TEST: PASSED ✓")
        print("  You're ready to launch the bot!")
    else:
        print("  CONNECTION TEST: FAILED ✗")
        print("  Fix the issues above before launching")
    print("="*70 + "\n")

    return all_available


def test_dependencies():
    """Test required Python packages."""
    print("\n" + "="*70)
    print("  DEPENDENCY CHECK")
    print("="*70)

    required = {
        'MetaTrader5': 'MetaTrader5',
        'numpy': 'numpy',
        'pandas': 'pandas',
        'scikit-learn': 'sklearn',
        'shap': 'shap',
        'requests': 'requests'
    }

    all_installed = True

    for package_name, import_name in required.items():
        try:
            __import__(import_name)
            print(f"  ✓ {package_name}")
        except ImportError:
            print(f"  ✗ {package_name} - NOT INSTALLED")
            all_installed = False

    print("="*70 + "\n")

    return all_installed


def test_bot_config():
    """Test bot configuration."""
    print("\n" + "="*70)
    print("  BOT CONFIGURATION CHECK")
    print("="*70)

    try:
        from bot.config import (
            ACTIVE_STRATEGY, ACTIVE_PHASE, STRATEGY_CONFIG,
            get_active_config
        )

        config = get_active_config()

        print(f"  Active Strategy: {ACTIVE_STRATEGY.value.upper()}")
        print(f"  Trading Phase: {config.name}")
        print(f"  Profit Target: {config.profit_target}%")
        print(f"  Max Daily Loss: {config.max_daily_loss}%")
        print(f"  Risk per Trade: {config.risk_per_trade_min}%-{config.risk_per_trade_max}%")
        print(f"  Symbols: {', '.join(STRATEGY_CONFIG['symbols'])}")
        print(f"  Timeframe: {STRATEGY_CONFIG['timeframe']}")
        print(f"\n  ✓ Configuration loaded successfully")

    except Exception as e:
        print(f"  ✗ Error loading configuration: {e}")
        return False

    print("="*70 + "\n")
    return True


def main():
    """Run all tests."""
    print("\n")
    print("*"*70)
    print("  ELASTIC BAND TRADING BOT - PRE-LAUNCH TEST")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("*"*70)

    # Run tests
    deps_ok = test_dependencies()
    config_ok = test_bot_config()
    mt5_ok = test_mt5_connection()

    # Final summary
    print("\n" + "="*70)
    print("  FINAL SUMMARY")
    print("="*70)

    if deps_ok and config_ok and mt5_ok:
        print("  ✓ All tests PASSED!")
        print("  ✓ Bot is ready to launch")
        print("\n  Next step: Edit run_demo.bat with your MT5 credentials")
        print("  Then run: run_demo.bat")
    else:
        print("  ✗ Some tests FAILED")
        print("  Please fix the issues above before launching the bot")

    print("="*70 + "\n")


if __name__ == "__main__":
    main()
