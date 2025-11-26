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


# Strategy selection
class StrategyType(Enum):
    ELASTIC_BAND = "elastic_band"  # Original trend-following mean reversion
    FVG = "fvg"  # Fair Value Gap strategy
    MACD_RSI = "macd_rsi"  # MACD + RSI combination
    ELASTIC_BB = "elastic_bb"  # Enhanced Elastic Band with Bollinger Bands


# Active strategy (change this to switch strategies)
ACTIVE_STRATEGY = StrategyType.MACD_RSI


# Strategy parameters
STRATEGY_CONFIG = {
    # Timeframe
    'timeframe': 'M15',
    'timeframe_minutes': 15,

    # Assets to trade
    'symbols': ['EURUSD', 'GBPUSD', 'USDJPY'],

    # === ELASTIC BAND PARAMETERS ===
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

    # === FVG STRATEGY PARAMETERS ===
    'fvg_min_gap_pips': 5,  # Minimum gap size to trade
    'fvg_risk_reward_ratio': 1.5,  # Better RR for gap fills
    'fvg_max_duration_minutes': 75,  # 5 bars * 15min = 75min

    # === MACD + RSI PARAMETERS ===
    'macd_fast': 12,
    'macd_slow': 27,
    'macd_signal': 9,
    'macd_rsi_atr_sl': 2.0,  # Wider stops for momentum
    'macd_rsi_rr_ratio': 2.0,  # Let momentum run
    'macd_rsi_max_duration': 240,  # 4 hours

    # === ELASTIC BB PARAMETERS ===
    'bb_period': 20,
    'bb_std_dev': 2.0,
    'bb_touch_tolerance_pct': 0.1,  # 0.1% of price
    'elastic_bb_rr_ratio': 1.5,

    # === SHARED PARAMETERS ===
    # Tilt protection
    'max_consecutive_losses': 3,
    'tilt_pause_hours': 4,

    # News filter
    'news_blackout_minutes_before': 30,
    'news_blackout_minutes_after': 30,
    'high_impact_currencies': ['USD', 'EUR', 'GBP', 'JPY'],

    # === ADVANCED TRADE MANAGEMENT ===
    # Breakeven management
    'enable_breakeven': True,
    'breakeven_trigger_r': 0.5,  # Move to BE after 0.5R profit

    # Partial exits
    'enable_partial_exits': False,  # Set to True to enable
    'partial_exit_r': 1.0,  # Close partial at 1R
    'partial_exit_percent': 0.5,  # Close 50% of position

    # Trailing stops
    'enable_trailing_stop': False,  # Set to True to enable
    'trailing_start_r': 1.0,  # Start trailing after 1R profit
    'trailing_distance_r': 0.5,  # Trail by 0.5R below/above price
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


def get_active_strategy():
    """
    Get the active strategy type.
    Returns the StrategyType enum value.
    """
    return ACTIVE_STRATEGY


def get_strategy_name() -> str:
    """Get the name of the active strategy."""
    strategy_names = {
        StrategyType.ELASTIC_BAND: "Elastic Band (Trend-Following Mean Reversion)",
        StrategyType.FVG: "Fair Value Gap (FVG)",
        StrategyType.MACD_RSI: "MACD + RSI Combination",
        StrategyType.ELASTIC_BB: "Enhanced Elastic Band with Bollinger Bands"
    }
    return strategy_names.get(ACTIVE_STRATEGY, "Unknown")
