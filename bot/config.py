"""
Bot configuration for different trading phases.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List


class TradingPhase(Enum):
    PHASE_1 = "challenge"
    PHASE_2 = "verification"
    PHASE_3 = "funded"


@dataclass
class PhaseConfig:
    """Configuration for a specific trading phase."""
    name: str
    profit_target: float  # Percentage
    max_daily_loss: float  # Percentage
    daily_loss_buffer: float  # Hard stop before actual limit
    max_total_loss: float  # Percentage
    risk_per_trade_min: float  # Percentage
    risk_per_trade_max: float  # Percentage


# Phase configurations
PHASE_CONFIGS = {
    TradingPhase.PHASE_1: PhaseConfig(
        name="Challenge",
        profit_target=10.0,
        max_daily_loss=5.0,
        daily_loss_buffer=4.5,  # Stop at 4.5% to protect 5% limit
        max_total_loss=10.0,
        risk_per_trade_min=1.0,
        risk_per_trade_max=1.0
    ),
    TradingPhase.PHASE_2: PhaseConfig(
        name="Verification",
        profit_target=8.0,
        max_daily_loss=5.0,
        daily_loss_buffer=4.5,
        max_total_loss=10.0,
        risk_per_trade_min=0.5,
        risk_per_trade_max=0.8
    ),
    TradingPhase.PHASE_3: PhaseConfig(
        name="Funded",
        profit_target=0.0,  # No target, growth mode
        max_daily_loss=5.0,
        daily_loss_buffer=3.0,  # More conservative for funded
        max_total_loss=10.0,
        risk_per_trade_min=0.25,
        risk_per_trade_max=0.5
    )
}


# Strategy parameters
STRATEGY_CONFIG = {
    # Timeframe
    'timeframe': 'M15',
    'timeframe_minutes': 15,

    # Assets to trade
    'symbols': ['EURUSD', 'GBPUSD', 'USDJPY'],

    # Indicator periods
    'ema_trend_period': 200,
    'ema_reversion_period': 50,
    'rsi_period': 7,
    'atr_period': 14,

    # RSI levels
    'rsi_oversold': 30,
    'rsi_overbought': 70,

    # Entry tolerance (pips)
    'ema_touch_tolerance_pips': 2,

    # Exit parameters
    'atr_sl_multiplier': 1.5,
    'risk_reward_ratio': 1.0,  # 1:1 TP ratio
    'max_trade_duration_minutes': 180,  # 3 hours

    # Tilt protection
    'max_consecutive_losses': 3,
    'tilt_pause_hours': 4,

    # News filter
    'news_blackout_minutes_before': 30,
    'news_blackout_minutes_after': 30,
    'high_impact_currencies': ['USD', 'EUR', 'GBP', 'JPY']
}


# Current active phase (change this to switch phases)
ACTIVE_PHASE = TradingPhase.PHASE_1


def get_active_config() -> PhaseConfig:
    """Get the configuration for the currently active phase."""
    return PHASE_CONFIGS[ACTIVE_PHASE]


def get_risk_percentage() -> float:
    """
    Get the risk percentage for current phase.
    Uses the middle of min/max range.
    """
    config = get_active_config()
    return (config.risk_per_trade_min + config.risk_per_trade_max) / 2
