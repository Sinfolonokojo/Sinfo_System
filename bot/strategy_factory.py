"""
Strategy Factory.

Creates strategy instances based on configuration.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import get_active_strategy, StrategyType, get_strategy_name
from bot.strategy import ElasticBandStrategy
from bot.strategy_fvg import FVGStrategy
from bot.strategy_macd_rsi import MACDRSIStrategy
from bot.strategy_elastic_bb import ElasticBBStrategy
from utils import setup_logger


def create_strategy(account_name: str):
    """
    Create a strategy instance based on active configuration.

    Args:
        account_name: Account name for logging.

    Returns:
        Strategy instance (ElasticBandStrategy, FVGStrategy, etc.)
    """
    logger = setup_logger(f"FACTORY:{account_name}")

    active_strategy = get_active_strategy()
    strategy_name = get_strategy_name()

    logger.info(f"Creating strategy: {strategy_name}")

    if active_strategy == StrategyType.ELASTIC_BAND:
        return ElasticBandStrategy(account_name)
    elif active_strategy == StrategyType.FVG:
        return FVGStrategy(account_name)
    elif active_strategy == StrategyType.MACD_RSI:
        return MACDRSIStrategy(account_name)
    elif active_strategy == StrategyType.ELASTIC_BB:
        return ElasticBBStrategy(account_name)
    else:
        logger.error(f"Unknown strategy type: {active_strategy}")
        # Default to Elastic Band
        return ElasticBandStrategy(account_name)
