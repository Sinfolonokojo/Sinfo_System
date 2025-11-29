"""
Run Backtest for Validation - Generate Real Trade-Level Data.

Runs backtests on all 3 symbols with conservative 5% DD parameters
to generate individual trade data with market features for ML validation.
"""

import sys
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from bot.backtester import Backtester
from bot.config import PHASE_CONFIGS, TradingPhase, STRATEGY_CONFIG
from utils import setup_logger

logger = setup_logger("BACKTEST_VALIDATION")

def main():
    """Run backtests to generate validation data."""
    logger.info("="*80)
    logger.info("RUNNING BACKTEST FOR ML VALIDATION")
    logger.info("="*80)
    logger.info("Generating individual trade data with market features...")
    logger.info("")

    # Initialize MT5
    if not mt5.initialize():
        logger.error("MT5 initialization failed")
        return

    try:
        # Backtest parameters
        symbols = STRATEGY_CONFIG['symbols']  # ['EURUSD', 'GBPUSD', 'USDJPY']
        phase = TradingPhase.PHASE_1
        phase_config = PHASE_CONFIGS[phase]

        # Date range (90 days as used in optimization)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)

        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"Symbols: {', '.join(symbols)}")
        logger.info(f"Phase: {phase_config.name}")
        logger.info("")

        # Create backtester (phase parameter, not phase_config)
        backtester = Backtester(phase=phase)

        # Run backtest for each symbol
        all_results = []
        for symbol in symbols:
            logger.info(f"\n{'='*60}")
            logger.info(f"BACKTESTING {symbol}")
            logger.info('='*60)

            result = backtester.run(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            all_results.append(result)

            logger.info(f"✓ {symbol} complete - {result.total_trades} trades generated")

        # Summary
        logger.info("\n" + "="*80)
        logger.info("VALIDATION DATA GENERATION COMPLETE")
        logger.info("="*80)

        total_trades = sum(r.total_trades for r in all_results)
        total_profit = sum(r.net_profit for r in all_results)
        avg_win_rate = sum(r.win_rate for r in all_results) / len(all_results)

        logger.info(f"Total Trades Generated: {total_trades}")
        logger.info(f"Total Net Profit: ${total_profit:.2f}")
        logger.info(f"Average Win Rate: {avg_win_rate:.2f}%")
        logger.info("")
        logger.info("Trade files saved to: tests/validation_data/")
        logger.info("  - EURUSD_trades.json")
        logger.info("  - GBPUSD_trades.json")
        logger.info("  - USDJPY_trades.json")
        logger.info("")
        logger.info("Ready for ML validation with StrategyValidator!")
        logger.info("="*80 + "\n")

    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
