"""
News Filter Module - ForexFactory Calendar Integration.

Blocks trading during high-impact news events to avoid volatility spikes.
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import xml.etree.ElementTree as ET

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger
from bot.config import STRATEGY_CONFIG


class NewsEvent:
    """Represents a news event from the calendar."""

    def __init__(
        self,
        title: str,
        currency: str,
        impact: str,
        event_time: datetime,
        actual: str = "",
        forecast: str = "",
        previous: str = ""
    ):
        self.title = title
        self.currency = currency
        self.impact = impact
        self.event_time = event_time
        self.actual = actual
        self.forecast = forecast
        self.previous = previous

    def __repr__(self):
        return f"{self.event_time.strftime('%H:%M')} | {self.currency} | {self.impact} | {self.title}"


class NewsFilter:
    """
    News Filter - Prevents trading during high-impact news.

    Fetches calendar data from ForexFactory and applies blackout windows
    around high-impact events.
    """

    def __init__(self, account_name: str):
        self.logger = setup_logger(f"NEWS:{account_name}")
        self.events: List[NewsEvent] = []
        self.last_fetch: Optional[datetime] = None
        self.fetch_interval_hours = 4

        # Configuration
        self.blackout_before = STRATEGY_CONFIG['news_blackout_minutes_before']
        self.blackout_after = STRATEGY_CONFIG['news_blackout_minutes_after']
        self.currencies = STRATEGY_CONFIG['high_impact_currencies']

        # ForexFactory calendar URL
        self.calendar_url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

    def fetch_calendar(self) -> bool:
        """
        Fetch this week's calendar from ForexFactory.

        Returns:
            True if fetch successful.
        """
        try:
            self.logger.info("Fetching ForexFactory calendar...")
            response = requests.get(self.calendar_url, timeout=10)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)
            self.events = []

            for event in root.findall('event'):
                title = event.find('title').text or ""
                currency = event.find('country').text or ""
                impact = event.find('impact').text or ""
                date_str = event.find('date').text or ""
                time_str = event.find('time').text or ""

                # Only high impact events for our currencies
                if impact.lower() != 'high':
                    continue

                if currency.upper() not in self.currencies:
                    continue

                # Parse datetime
                event_time = self._parse_event_time(date_str, time_str)
                if event_time is None:
                    continue

                news_event = NewsEvent(
                    title=title,
                    currency=currency.upper(),
                    impact=impact,
                    event_time=event_time,
                    actual=event.find('actual').text or "" if event.find('actual') is not None else "",
                    forecast=event.find('forecast').text or "" if event.find('forecast') is not None else "",
                    previous=event.find('previous').text or "" if event.find('previous') is not None else ""
                )
                self.events.append(news_event)

            self.last_fetch = datetime.now()
            self.logger.info(f"Loaded {len(self.events)} high-impact events")

            # Log upcoming events
            upcoming = self.get_upcoming_events(hours=24)
            if upcoming:
                self.logger.info(f"Upcoming events in next 24h: {len(upcoming)}")
                for evt in upcoming[:5]:  # Show max 5
                    self.logger.info(f"  - {evt}")

            return True

        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch calendar: {e}")
            return False
        except ET.ParseError as e:
            self.logger.error(f"Failed to parse calendar XML: {e}")
            return False

    def _parse_event_time(self, date_str: str, time_str: str) -> Optional[datetime]:
        """
        Parse event date and time strings.

        Args:
            date_str: Date string (e.g., "11-25-2024")
            time_str: Time string (e.g., "8:30am")

        Returns:
            Datetime object or None if parsing fails.
        """
        try:
            if not date_str or not time_str or time_str.lower() in ['all day', 'tentative']:
                return None

            # Parse date
            date_parts = date_str.split('-')
            month = int(date_parts[0])
            day = int(date_parts[1])
            year = int(date_parts[2])

            # Parse time
            time_str = time_str.lower().strip()
            is_pm = 'pm' in time_str
            time_str = time_str.replace('am', '').replace('pm', '').strip()

            if ':' in time_str:
                hour, minute = map(int, time_str.split(':'))
            else:
                hour = int(time_str)
                minute = 0

            # Convert to 24-hour
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0

            return datetime(year, month, day, hour, minute)

        except (ValueError, IndexError) as e:
            return None

    def update_if_needed(self):
        """Update calendar if fetch interval has passed."""
        if self.last_fetch is None:
            self.fetch_calendar()
            return

        hours_since_fetch = (datetime.now() - self.last_fetch).total_seconds() / 3600
        if hours_since_fetch >= self.fetch_interval_hours:
            self.fetch_calendar()

    def is_in_blackout(self, symbol: str = None) -> bool:
        """
        Check if current time is in a news blackout window.

        Args:
            symbol: Optional symbol to filter by currency (e.g., EURUSD checks EUR and USD).

        Returns:
            True if in blackout period.
        """
        self.update_if_needed()

        now = datetime.now()

        # Determine which currencies to check
        currencies_to_check = self.currencies
        if symbol:
            currencies_to_check = self._get_symbol_currencies(symbol)

        for event in self.events:
            # Check if event currency is relevant
            if event.currency not in currencies_to_check:
                continue

            # Calculate blackout window
            blackout_start = event.event_time - timedelta(minutes=self.blackout_before)
            blackout_end = event.event_time + timedelta(minutes=self.blackout_after)

            if blackout_start <= now <= blackout_end:
                self.logger.warning(
                    f"NEWS BLACKOUT | {event.currency} | {event.title} | "
                    f"Event at {event.event_time.strftime('%H:%M')}"
                )
                return True

        return False

    def _get_symbol_currencies(self, symbol: str) -> List[str]:
        """
        Get currencies from a symbol pair.

        Args:
            symbol: Trading symbol (e.g., EURUSD).

        Returns:
            List of currencies (e.g., ['EUR', 'USD']).
        """
        # Remove any suffix (e.g., EURUSD.r -> EURUSD)
        clean_symbol = symbol.split('.')[0]

        if len(clean_symbol) >= 6:
            return [clean_symbol[:3].upper(), clean_symbol[3:6].upper()]
        return []

    def get_upcoming_events(self, hours: int = 24) -> List[NewsEvent]:
        """
        Get events in the next N hours.

        Args:
            hours: Number of hours to look ahead.

        Returns:
            List of upcoming events.
        """
        self.update_if_needed()

        now = datetime.now()
        cutoff = now + timedelta(hours=hours)

        upcoming = [
            event for event in self.events
            if now <= event.event_time <= cutoff
        ]

        return sorted(upcoming, key=lambda x: x.event_time)

    def get_next_event(self, symbol: str = None) -> Optional[NewsEvent]:
        """
        Get the next upcoming event.

        Args:
            symbol: Optional symbol to filter by currency.

        Returns:
            Next event or None.
        """
        self.update_if_needed()

        now = datetime.now()

        # Filter by currency if symbol provided
        currencies_to_check = self.currencies
        if symbol:
            currencies_to_check = self._get_symbol_currencies(symbol)

        future_events = [
            event for event in self.events
            if event.event_time > now and event.currency in currencies_to_check
        ]

        if not future_events:
            return None

        return min(future_events, key=lambda x: x.event_time)

    def get_time_to_next_event(self, symbol: str = None) -> Optional[timedelta]:
        """
        Get time until next event.

        Args:
            symbol: Optional symbol to filter by currency.

        Returns:
            Timedelta to next event or None.
        """
        next_event = self.get_next_event(symbol)
        if next_event is None:
            return None

        return next_event.event_time - datetime.now()

    def can_trade(self, symbol: str = None) -> bool:
        """
        Check if trading is allowed (not in blackout).

        Args:
            symbol: Optional symbol to check.

        Returns:
            True if safe to trade.
        """
        return not self.is_in_blackout(symbol)

    def get_status(self) -> Dict[str, Any]:
        """Get current news filter status."""
        return {
            'events_loaded': len(self.events),
            'last_fetch': self.last_fetch.isoformat() if self.last_fetch else None,
            'in_blackout': self.is_in_blackout(),
            'next_event': str(self.get_next_event()) if self.get_next_event() else None
        }
