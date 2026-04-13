"""Calendar domain: uses exchange_calendars library for accurate trade dates."""

from __future__ import annotations

import exchange_calendars as xcals


class Calendar:
    """Trading calendar using exchange_calendars (XSHG: Shanghai). Implements CalendarProtocol."""

    def __init__(self) -> None:
        # XSHG: Shanghai Stock Exchange
        self._calendar = xcals.get_calendar("XSHG")

    def get_trade_dates(self, start_date: str, end_date: str) -> list[str]:
        """Return list of trade dates (YYYYMMDD) in [start_date, end_date], ascending.
        
        Uses exchange_calendars for accurate Chinese stock market holidays.
        """
        try:
            # Validate date format
            if not start_date or not end_date or len(start_date) != 8 or len(end_date) != 8:
                return []
            
            # Convert YYYYMMDD to pandas Timestamp format
            start_ts = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            end_ts = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            
            # Get all sessions in range
            sessions = self._calendar.sessions_in_range(start_ts, end_ts)
            
            # Convert to YYYYMMDD format
            return [ts.strftime("%Y%m%d") for ts in sessions]
        except Exception as e:
            # Log error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to get trade dates for {start_date}~{end_date}: {e}")
            return []

    def is_trade_day(self, date: str) -> bool:
        """Return True if date is a trade day (YYYYMMDD).
        
        Uses exchange_calendars for accurate Chinese stock market holidays.
        """
        try:
            # Convert YYYYMMDD to pandas Timestamp format
            date_ts = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
            return bool(self._calendar.is_session(date_ts))
        except Exception:
            return False

    def get_latest_trade_date(self, before_date: str) -> str | None:
        """Return the latest trade date strictly before before_date (YYYYMMDD), or None.
        
        Uses exchange_calendars for accurate Chinese stock market holidays.
        
        Note: Returns the latest trade date < before_date (not <=)
        """
        try:
            # Convert YYYYMMDD to pandas Timestamp format
            before_ts = f"{before_date[:4]}-{before_date[4:6]}-{before_date[6:8]}"
            
            # Strategy: Get all sessions up to before_date, then take the last one before before_date
            # We need to go back a bit to ensure we find at least one session
            from datetime import timedelta
            import pandas as pd
            
            before_dt = pd.Timestamp(before_ts)
            # Go back 30 days to ensure we find a trading day
            start_search = before_dt - timedelta(days=30)
            
            # Get all sessions in the search range
            sessions = self._calendar.sessions_in_range(start_search, before_dt)
            
            if len(sessions) == 0:
                return None
            
            # Find the latest session that is strictly before before_date
            for session in reversed(sessions):
                if session < before_dt:
                    return session.strftime("%Y%m%d")
            
            # If no session is strictly before, return None
            return None
        except Exception as e:
            # Log error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to get latest trade date before {before_date}: {e}")
            return None
