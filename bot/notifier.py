"""
Notification System for Trading Bot.

Sends notifications via Telegram for trades and important events.
"""

import requests
import json
from datetime import datetime
from typing import Optional
from utils import setup_logger


class TelegramNotifier:
    """Send notifications via Telegram bot."""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Your Telegram chat ID
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        self.logger = setup_logger("NOTIFIER")

        if not self.enabled:
            self.logger.warning("Telegram notifications disabled (no token/chat_id)")
        else:
            self.logger.info("Telegram notifications enabled")

    def send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send a message via Telegram.

        Args:
            message: Message text (supports HTML formatting)
            parse_mode: 'HTML' or 'Markdown'

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            else:
                self.logger.error(f"Telegram error: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False

    def notify_trade_opened(self, symbol: str, direction: str, volume: float,
                           entry_price: float, sl: float, tp: float, ticket: int):
        """Notify when a trade is opened."""
        message = (
            f"<b>🔔 TRADE OPENED</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Direction:</b> {direction}\n"
            f"<b>Volume:</b> {volume:.2f} lots\n"
            f"<b>Entry:</b> {entry_price:.5f}\n"
            f"<b>SL:</b> {sl:.5f}\n"
            f"<b>TP:</b> {tp:.5f}\n"
            f"<b>Ticket:</b> #{ticket}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def notify_trade_closed(self, symbol: str, direction: str, volume: float,
                            entry_price: float, exit_price: float,
                            profit: float, reason: str, ticket: int,
                            duration_minutes: int = None):
        """Notify when a trade is closed."""
        profit_emoji = "✅" if profit >= 0 else "❌"
        profit_sign = "+" if profit >= 0 else ""

        duration_str = f"{duration_minutes} min" if duration_minutes else "N/A"

        message = (
            f"<b>{profit_emoji} TRADE CLOSED</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Direction:</b> {direction}\n"
            f"<b>Volume:</b> {volume:.2f} lots\n"
            f"<b>Entry:</b> {entry_price:.5f}\n"
            f"<b>Exit:</b> {exit_price:.5f}\n"
            f"<b>Profit:</b> {profit_sign}${profit:.2f}\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Duration:</b> {duration_str}\n"
            f"<b>Ticket:</b> #{ticket}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def notify_daily_summary(self, balance: float, equity: float,
                            trades_today: int, wins: int, losses: int,
                            daily_pnl: float, win_rate: float):
        """Send daily performance summary."""
        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
        pnl_sign = "+" if daily_pnl >= 0 else ""

        message = (
            f"<b>{pnl_emoji} DAILY SUMMARY</b>\n\n"
            f"<b>Balance:</b> ${balance:,.2f}\n"
            f"<b>Equity:</b> ${equity:,.2f}\n"
            f"<b>Daily P&L:</b> {pnl_sign}${daily_pnl:.2f}\n\n"
            f"<b>Trades Today:</b> {trades_today}\n"
            f"<b>Wins:</b> {wins} | <b>Losses:</b> {losses}\n"
            f"<b>Win Rate:</b> {win_rate:.1f}%\n"
            f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}"
        )
        return self.send_message(message)

    def notify_warning(self, warning_type: str, message_text: str):
        """Send warning notification."""
        message = (
            f"<b>⚠️ WARNING: {warning_type}</b>\n\n"
            f"{message_text}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def notify_error(self, error_type: str, error_message: str):
        """Send error notification."""
        message = (
            f"<b>🚨 ERROR: {error_type}</b>\n\n"
            f"{error_message}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def notify_bot_started(self, strategy: str, phase: str, symbols: list):
        """Notify when bot starts."""
        message = (
            f"<b>🤖 BOT STARTED</b>\n\n"
            f"<b>Strategy:</b> {strategy}\n"
            f"<b>Phase:</b> {phase}\n"
            f"<b>Symbols:</b> {', '.join(symbols)}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Bot is now monitoring the market..."
        )
        return self.send_message(message)

    def notify_bot_stopped(self, reason: str = "Manual stop"):
        """Notify when bot stops."""
        message = (
            f"<b>🛑 BOT STOPPED</b>\n\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def notify_daily_limit_reached(self, daily_loss_pct: float, limit_pct: float):
        """Notify when daily loss limit is reached."""
        message = (
            f"<b>🛑 DAILY LOSS LIMIT REACHED</b>\n\n"
            f"<b>Daily Loss:</b> {daily_loss_pct:.2f}%\n"
            f"<b>Limit:</b> {limit_pct:.2f}%\n\n"
            f"Trading stopped for today.\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def notify_tilt_protection(self, consecutive_losses: int):
        """Notify when tilt protection activates."""
        message = (
            f"<b>⏸️ TILT PROTECTION ACTIVATED</b>\n\n"
            f"<b>Consecutive Losses:</b> {consecutive_losses}\n\n"
            f"Trading paused for 4 hours to prevent emotional trading.\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def test_connection(self) -> bool:
        """Test Telegram connection."""
        if not self.enabled:
            print("Telegram notifications not configured")
            return False

        test_message = (
            "<b>🧪 TEST MESSAGE</b>\n\n"
            "Telegram notifications are working correctly!\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        result = self.send_message(test_message)
        if result:
            print("✓ Test message sent successfully!")
        else:
            print("✗ Failed to send test message")

        return result


# Configuration (set your credentials here or in environment variables)
TELEGRAM_BOT_TOKEN = None  # Get from @BotFather on Telegram
TELEGRAM_CHAT_ID = None    # Get from @userinfobot on Telegram

# Create global notifier instance
notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)


if __name__ == "__main__":
    print("="*70)
    print("  TELEGRAM NOTIFIER SETUP")
    print("="*70)
    print("\nTo enable Telegram notifications:")
    print("1. Create a bot: Message @BotFather on Telegram")
    print("2. Get your chat ID: Message @userinfobot on Telegram")
    print("3. Edit bot/notifier.py and add your credentials:")
    print("   TELEGRAM_BOT_TOKEN = 'your-bot-token'")
    print("   TELEGRAM_CHAT_ID = 'your-chat-id'")
    print("\nThen run this script again to test:")
    print("   python bot/notifier.py")
    print("="*70 + "\n")

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("Testing connection...")
        notifier.test_connection()
    else:
        print("Please configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first")
