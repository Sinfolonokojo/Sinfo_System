"""
Backtesting Module - Historical Strategy Testing.

Tests the Elastic Band strategy on historical data to validate performance
before live trading.
"""

import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.config import STRATEGY_CONFIG, PHASE_CONFIGS, TradingPhase


@dataclass
class BacktestTrade:
    """Represents a trade in backtesting."""
    entry_time: datetime
    exit_time: datetime
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    entry_price: float
    exit_price: float
    sl: float
    tp: float
    volume: float
    profit: float
    profit_pips: float
    exit_reason: str  # 'TP', 'SL', 'TIME'
    duration_minutes: int


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    symbol: str
    phase: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float

    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Profit metrics
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0

    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_consecutive_losses: int = 0

    # Performance metrics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    expectancy: float = 0.0

    # Trade list
    trades: List[BacktestTrade] = field(default_factory=list)

    # Equity curve
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)


class Backtester:
    """
    Historical backtester for trading strategies.

    Uses MT5 historical data to simulate strategy performance.
    """

    def __init__(self, phase: TradingPhase = TradingPhase.PHASE_1, strategy_class=None):
        self.logger = setup_logger("BACKTEST")
        self.phase = phase
        self.phase_config = PHASE_CONFIGS[phase]

        # Store strategy class (if None, use default Elastic Band)
        self.strategy_class = strategy_class

        # Strategy parameters (keep for backward compatibility with hardcoded logic)
        self.ema_trend_period = STRATEGY_CONFIG['ema_trend_period']
        self.ema_reversion_period = STRATEGY_CONFIG['ema_reversion_period']
        self.rsi_period = STRATEGY_CONFIG['rsi_period']
        self.atr_period = STRATEGY_CONFIG['atr_period']
        self.rsi_oversold = STRATEGY_CONFIG['rsi_oversold']
        self.rsi_overbought = STRATEGY_CONFIG['rsi_overbought']
        self.atr_sl_multiplier = STRATEGY_CONFIG['atr_sl_multiplier']
        self.rr_ratio = STRATEGY_CONFIG['risk_reward_ratio']
        self.ema_tolerance_pips = STRATEGY_CONFIG['ema_touch_tolerance_pips']
        self.max_duration = STRATEGY_CONFIG['max_trade_duration_minutes']

    def run(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float = 10000.0
    ) -> BacktestResult:
        """
        Run backtest on a symbol.

        Args:
            symbol: Trading symbol.
            start_date: Backtest start date.
            end_date: Backtest end date.
            initial_balance: Starting account balance.

        Returns:
            BacktestResult with performance metrics.
        """
        # Initialize strategy if provided
        strategy_instance = None
        strategy_name = "Elastic_Band"
        if self.strategy_class:
            try:
                strategy_instance = self.strategy_class("BACKTEST")
                strategy_name = self.strategy_class.__name__
            except Exception as e:
                self.logger.warning(f"Failed to initialize strategy class: {e}, using default")
                strategy_instance = None

        self.logger.info(
            f"Starting backtest | {symbol} | {start_date.date()} to {end_date.date()} | "
            f"Phase: {self.phase_config.name} | Strategy: {strategy_name}"
        )

        # Fetch historical data
        rates = self._fetch_historical_data(symbol, start_date, end_date)
        if rates is None or len(rates) < self.ema_trend_period + 100:
            self.logger.error("Insufficient historical data")
            return BacktestResult(
                symbol=symbol,
                phase=self.phase_config.name,
                start_date=start_date,
                end_date=end_date,
                initial_balance=initial_balance,
                final_balance=initial_balance
            )

        # Calculate indicators for entire dataset
        close = rates['close']
        high = rates['high']
        low = rates['low']
        times = rates['time']

        ema_trend = self._calculate_ema(close, self.ema_trend_period)
        ema_reversion = self._calculate_ema(close, self.ema_reversion_period)
        rsi = self._calculate_rsi(close, self.rsi_period)
        atr = self._calculate_atr(rates, self.atr_period)

        # Get pip size for symbol
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Failed to get symbol info for {symbol}")
            return BacktestResult(
                symbol=symbol,
                phase=self.phase_config.name,
                start_date=start_date,
                end_date=end_date,
                initial_balance=initial_balance,
                final_balance=initial_balance
            )

        if symbol_info.digits == 3 or symbol_info.digits == 5:
            pip_size = symbol_info.point * 10
        else:
            pip_size = symbol_info.point

        pip_tolerance = self.ema_tolerance_pips * pip_size

        # Simulation state
        balance = initial_balance
        equity_curve = [(datetime.fromtimestamp(times[0]), balance)]
        trades: List[BacktestTrade] = []

        # Position state
        in_position = False
        position_entry_idx = 0
        position_direction = None
        position_entry_price = 0.0
        position_sl = 0.0
        position_tp = 0.0
        position_volume = 0.0

        # Start after we have enough data for indicators
        start_idx = self.ema_trend_period + 10

        # Main simulation loop
        for i in range(start_idx, len(rates)):
            current_time = datetime.fromtimestamp(times[i])

            # Check exit conditions if in position
            if in_position:
                exit_reason = None
                exit_price = 0.0

                if position_direction == 'BUY':
                    # Check SL
                    if low[i] <= position_sl:
                        exit_reason = 'SL'
                        exit_price = position_sl
                    # Check TP
                    elif high[i] >= position_tp:
                        exit_reason = 'TP'
                        exit_price = position_tp
                else:  # SELL
                    # Check SL
                    if high[i] >= position_sl:
                        exit_reason = 'SL'
                        exit_price = position_sl
                    # Check TP
                    elif low[i] <= position_tp:
                        exit_reason = 'TP'
                        exit_price = position_tp

                # Check time exit
                duration_minutes = (i - position_entry_idx) * STRATEGY_CONFIG['timeframe_minutes']
                if duration_minutes >= self.max_duration and exit_reason is None:
                    exit_price = close[i]
                    # Only time exit if profitable
                    if position_direction == 'BUY' and exit_price > position_entry_price:
                        exit_reason = 'TIME'
                    elif position_direction == 'SELL' and exit_price < position_entry_price:
                        exit_reason = 'TIME'

                # Close position
                if exit_reason:
                    # Calculate profit
                    if position_direction == 'BUY':
                        profit_pips = (exit_price - position_entry_price) / pip_size
                    else:
                        profit_pips = (position_entry_price - exit_price) / pip_size

                    # Calculate money profit (simplified)
                    tick_value = symbol_info.trade_tick_value
                    tick_size = symbol_info.trade_tick_size
                    pip_value = (pip_size / tick_size) * tick_value
                    profit = profit_pips * pip_value * position_volume

                    balance += profit

                    # Record trade
                    trade = BacktestTrade(
                        entry_time=datetime.fromtimestamp(times[position_entry_idx]),
                        exit_time=current_time,
                        symbol=symbol,
                        direction=position_direction,
                        entry_price=position_entry_price,
                        exit_price=exit_price,
                        sl=position_sl,
                        tp=position_tp,
                        volume=position_volume,
                        profit=profit,
                        profit_pips=profit_pips,
                        exit_reason=exit_reason,
                        duration_minutes=duration_minutes
                    )
                    trades.append(trade)

                    in_position = False
                    equity_curve.append((current_time, balance))

            # Check entry signals if not in position
            if not in_position:
                # Use strategy instance if available, otherwise use hardcoded logic
                if strategy_instance:
                    # Update strategy indicators (simplified for backtesting)
                    # We'll use the default _check_signal for now as strategy classes
                    # need live MT5 data. TODO: Refactor strategies for backtest compatibility
                    signal = self._check_signal(
                        close[i], close[i-1], high[i], low[i],
                        ema_trend[i], ema_reversion[i],
                        rsi[i], rsi[i-1],
                        pip_tolerance
                    )
                else:
                    signal = self._check_signal(
                        close[i], close[i-1], high[i], low[i],
                        ema_trend[i], ema_reversion[i],
                        rsi[i], rsi[i-1],
                        pip_tolerance
                    )

                if signal:
                    # Calculate position size
                    atr_pips = atr[i] / pip_size
                    sl_pips = atr_pips * self.atr_sl_multiplier
                    sl_distance = sl_pips * pip_size
                    tp_distance = sl_distance * self.rr_ratio

                    risk_pct = (self.phase_config.risk_per_trade_min +
                               self.phase_config.risk_per_trade_max) / 2
                    risk_amount = balance * (risk_pct / 100)

                    tick_value = symbol_info.trade_tick_value
                    tick_size = symbol_info.trade_tick_size
                    pip_value = (pip_size / tick_size) * tick_value

                    if sl_pips > 0 and pip_value > 0:
                        volume = risk_amount / (sl_pips * pip_value)
                        volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step
                        volume = max(symbol_info.volume_min, min(volume, symbol_info.volume_max))

                        if signal == 'BUY':
                            entry_price = close[i]  # Simplified: use close as entry
                            position_sl = entry_price - sl_distance
                            position_tp = entry_price + tp_distance
                        else:  # SELL
                            entry_price = close[i]
                            position_sl = entry_price + sl_distance
                            position_tp = entry_price - tp_distance

                        # Enter position
                        in_position = True
                        position_entry_idx = i
                        position_direction = signal
                        position_entry_price = entry_price
                        position_volume = volume

        # Calculate results
        result = self._calculate_results(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            final_balance=balance,
            trades=trades,
            equity_curve=equity_curve
        )

        self._log_results(result)
        return result

    def _fetch_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[np.ndarray]:
        """Fetch historical OHLC data from MT5."""
        timeframe = mt5.TIMEFRAME_M15

        rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)

        if rates is None or len(rates) == 0:
            self.logger.error(f"Failed to fetch historical data for {symbol}")
            return None

        self.logger.info(f"Fetched {len(rates)} bars for {symbol}")
        return rates

    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA."""
        ema = np.zeros(len(data))
        multiplier = 2 / (period + 1)

        ema[period - 1] = np.mean(data[:period])

        for i in range(period, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i - 1] * (1 - multiplier))

        return ema

    def _calculate_rsi(self, close: np.ndarray, period: int) -> np.ndarray:
        """Calculate RSI."""
        rsi = np.zeros(len(close))
        deltas = np.diff(close)

        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        if avg_loss == 0:
            rsi[period] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[period] = 100 - (100 / (1 + rs))

        for i in range(period, len(close) - 1):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi[i + 1] = 100
            else:
                rs = avg_gain / avg_loss
                rsi[i + 1] = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_atr(self, rates: np.ndarray, period: int) -> np.ndarray:
        """Calculate ATR."""
        high = rates['high']
        low = rates['low']
        close = rates['close']

        atr = np.zeros(len(rates))
        tr = np.zeros(len(rates))
        tr[0] = high[0] - low[0]

        for i in range(1, len(rates)):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i - 1])
            lc = abs(low[i] - close[i - 1])
            tr[i] = max(hl, hc, lc)

        atr[period - 1] = np.mean(tr[:period])

        multiplier = 2 / (period + 1)
        for i in range(period, len(rates)):
            atr[i] = (tr[i] * multiplier) + (atr[i - 1] * (1 - multiplier))

        return atr

    def _check_signal(
        self,
        close: float,
        prev_close: float,
        high: float,
        low: float,
        ema_trend: float,
        ema_reversion: float,
        rsi: float,
        prev_rsi: float,
        tolerance: float
    ) -> Optional[str]:
        """Check for entry signal."""
        # LONG signal
        if (close > ema_trend and
            low <= (ema_reversion + tolerance) and
            prev_rsi < self.rsi_oversold and
            rsi >= self.rsi_oversold):
            return 'BUY'

        # SHORT signal
        if (close < ema_trend and
            high >= (ema_reversion - tolerance) and
            prev_rsi > self.rsi_overbought and
            rsi <= self.rsi_overbought):
            return 'SELL'

        return None

    def _calculate_results(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float,
        final_balance: float,
        trades: List[BacktestTrade],
        equity_curve: List[Tuple[datetime, float]]
    ) -> BacktestResult:
        """Calculate backtest performance metrics."""
        result = BacktestResult(
            symbol=symbol,
            phase=self.phase_config.name,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            final_balance=final_balance,
            trades=trades,
            equity_curve=equity_curve
        )

        if not trades:
            return result

        # Basic counts
        result.total_trades = len(trades)
        result.winning_trades = sum(1 for t in trades if t.profit > 0)
        result.losing_trades = sum(1 for t in trades if t.profit <= 0)

        # Profit metrics
        result.gross_profit = sum(t.profit for t in trades if t.profit > 0)
        result.gross_loss = abs(sum(t.profit for t in trades if t.profit < 0))
        result.net_profit = final_balance - initial_balance

        # Win rate
        result.win_rate = (result.winning_trades / result.total_trades * 100) if result.total_trades > 0 else 0

        # Profit factor
        result.profit_factor = (result.gross_profit / result.gross_loss) if result.gross_loss > 0 else 0

        # Average win/loss
        if result.winning_trades > 0:
            result.average_win = result.gross_profit / result.winning_trades
        if result.losing_trades > 0:
            result.average_loss = result.gross_loss / result.losing_trades

        # Expectancy
        if result.total_trades > 0:
            result.expectancy = result.net_profit / result.total_trades

        # Max drawdown
        peak = initial_balance
        max_dd = 0
        for _, equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd

        result.max_drawdown = max_dd
        result.max_drawdown_pct = (max_dd / initial_balance * 100) if initial_balance > 0 else 0

        # Max consecutive losses
        max_consec = 0
        current_consec = 0
        for trade in trades:
            if trade.profit <= 0:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0

        result.max_consecutive_losses = max_consec

        return result

    def _log_results(self, result: BacktestResult):
        """Log backtest results."""
        self.logger.info("=" * 60)
        self.logger.info(f"BACKTEST RESULTS - {result.symbol} ({result.phase})")
        self.logger.info("=" * 60)
        self.logger.info(f"Period: {result.start_date.date()} to {result.end_date.date()}")
        self.logger.info(f"Initial Balance: ${result.initial_balance:.2f}")
        self.logger.info(f"Final Balance: ${result.final_balance:.2f}")
        self.logger.info(f"Net Profit: ${result.net_profit:.2f} ({result.net_profit/result.initial_balance*100:.1f}%)")
        self.logger.info("-" * 60)
        self.logger.info(f"Total Trades: {result.total_trades}")
        self.logger.info(f"Winning Trades: {result.winning_trades}")
        self.logger.info(f"Losing Trades: {result.losing_trades}")
        self.logger.info(f"Win Rate: {result.win_rate:.1f}%")
        self.logger.info("-" * 60)
        self.logger.info(f"Gross Profit: ${result.gross_profit:.2f}")
        self.logger.info(f"Gross Loss: ${result.gross_loss:.2f}")
        self.logger.info(f"Profit Factor: {result.profit_factor:.2f}")
        self.logger.info(f"Average Win: ${result.average_win:.2f}")
        self.logger.info(f"Average Loss: ${result.average_loss:.2f}")
        self.logger.info(f"Expectancy: ${result.expectancy:.2f}")
        self.logger.info("-" * 60)
        self.logger.info(f"Max Drawdown: ${result.max_drawdown:.2f} ({result.max_drawdown_pct:.1f}%)")
        self.logger.info(f"Max Consecutive Losses: {result.max_consecutive_losses}")
        self.logger.info("=" * 60)
