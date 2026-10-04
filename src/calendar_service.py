"""Google Calendar iCal (.ics) integration service.

Fetches and parses iCalendar (RFC 5545) feeds from Google Calendar secret iCal URLs,
providing structured events for today and upcoming schedules with in-memory caching.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
import re
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    """Represents a scheduled calendar event."""

    summary: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool = False
    description: str = ""

    @property
    def duration_minutes(self) -> int:
        delta = self.end_time - self.start_time
        return max(0, int(delta.total_seconds() // 60))

    def format_time_range(self) -> str:
        if self.is_all_day:
            return "Cả ngày"
        return f"{self.start_time.strftime('%H:%M')} – {self.end_time.strftime('%H:%M')}"


def _unfold_ics_lines(raw_ics: str) -> List[str]:
    """Unfolds folded lines in iCalendar text (RFC 5545).

    Lines starting with space or tab are continuations of the previous line.
    """
    lines: List[str] = []
    for line in raw_ics.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith(" ") or line.startswith("\t"):
            if lines:
                lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _parse_ics_datetime(value_str: str, timezone: ZoneInfo) -> Tuple[datetime, bool]:
    """Parses iCal DTSTART/DTEND values into timezone-aware datetimes.

    Supports:
    - YYYYMMDDTHHMMSSZ (UTC)
    - YYYYMMDDTHHMMSS (local)
    - YYYYMMDD (all-day date)
    """
    clean_val = value_str.strip()

    # All-day event: YYYYMMDD (8 digits)
    if re.match(r"^\d{8}$", clean_val):
        d = datetime.strptime(clean_val, "%Y%m%d").date()
        dt_start = datetime.combine(d, time.min, tzinfo=timezone)
        return dt_start, True

    # UTC datetime: YYYYMMDDTHHMMSSZ
    if clean_val.endswith("Z"):
        dt = datetime.strptime(clean_val, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(timezone), False

    # Standard datetime without Z: YYYYMMDDTHHMMSS
    if "T" in clean_val:
        parts = clean_val.split("T")
        d_str, t_str = parts[0], parts[1][:6]
        dt = datetime.strptime(f"{d_str}T{t_str}", "%Y%m%dT%H%M%S")
        return dt.replace(tzinfo=timezone), False

    # Fallback
    dt_fallback = datetime.now(timezone)
    return dt_fallback, False


class CalendarService:
    """Async service to fetch and parse events from a Google Calendar Secret iCal URL."""

    def __init__(
        self,
        ical_url: Optional[str] = None,
        timezone: Optional[ZoneInfo] = None,
        cache_ttl_seconds: int = 300,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.ical_url = (ical_url or "").strip()
        self.timezone = timezone or ZoneInfo("Asia/Ho_Chi_Minh")
        self.cache_ttl_seconds = cache_ttl_seconds
        self._http_client = http_client
        self._cached_events: List[CalendarEvent] = []
        self._last_fetch_time: Optional[datetime] = None

    @property
    def is_configured(self) -> bool:
        """Returns True if a valid iCal URL has been configured."""
        return bool(self.ical_url and self.ical_url.startswith("http"))

    def parse_ics_content(self, ics_text: str) -> List[CalendarEvent]:
        """Parses raw iCalendar content into a list of CalendarEvent objects."""
        if not ics_text:
            return []

        lines = _unfold_ics_lines(ics_text)
        events: List[CalendarEvent] = []
        in_vevent = False
        current_event: dict[str, Any] = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line == "BEGIN:VEVENT":
                in_vevent = True
                current_event = {}
                continue

            if line == "END:VEVENT":
                in_vevent = False
                if "start_time" in current_event:
                    start_dt = current_event["start_time"]
                    end_dt = current_event.get("end_time")
                    is_all_day = current_event.get("is_all_day", False)
                    if not end_dt:
                        end_dt = start_dt + (timedelta(days=1) if is_all_day else timedelta(hours=1))

                    summary = current_event.get("summary", "Không có tiêu đề")
                    description = current_event.get("description", "")
                    events.append(
                        CalendarEvent(
                            summary=summary,
                            start_time=start_dt,
                            end_time=end_dt,
                            is_all_day=is_all_day,
                            description=description,
                        )
                    )
                continue

            if not in_vevent:
                continue

            if ":" not in line:
                continue

            prop_header, prop_value = line.split(":", 1)
            prop_name = prop_header.split(";")[0].upper()

            if prop_name == "SUMMARY":
                # Unescape standard iCal characters
                summary = prop_value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
                current_event["summary"] = summary
            elif prop_name == "DESCRIPTION":
                desc = prop_value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
                current_event["description"] = desc
            elif prop_name == "DTSTART":
                dt, all_day = _parse_ics_datetime(prop_value, self.timezone)
                current_event["start_time"] = dt
                current_event["is_all_day"] = all_day
            elif prop_name == "DTEND":
                dt, _ = _parse_ics_datetime(prop_value, self.timezone)
                current_event["end_time"] = dt

        # Sort events chronologically
        events.sort(key=lambda e: e.start_time)
        return events

    async def fetch_events(self, force_refresh: bool = False) -> List[CalendarEvent]:
        """Fetches and caches events from the iCal URL."""
        if not self.is_configured:
            return []

        now = datetime.now(self.timezone)
        if (
            not force_refresh
            and self._last_fetch_time
            and (now - self._last_fetch_time).total_seconds() < self.cache_ttl_seconds
        ):
            return self._cached_events

        try:
            if self._http_client:
                resp = await self._http_client.get(self.ical_url)
                resp.raise_for_status()
                text = resp.text
            else:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    resp = await client.get(self.ical_url)
                    resp.raise_for_status()
                    text = resp.text

            events = self.parse_ics_content(text)
            self._cached_events = events
            self._last_fetch_time = now
            logger.info("Successfully fetched %d events from Google Calendar iCal feed.", len(events))
            return events
        except Exception as exc:
            logger.warning("Could not fetch Google Calendar iCal feed (%s): %s", self.ical_url, exc)
            return self._cached_events

    async def get_today_events(self, now: Optional[datetime] = None) -> List[CalendarEvent]:
        """Returns events occurring on the current day."""
        if now is None:
            now = datetime.now(self.timezone)

        today_date = now.date()
        events = await self.fetch_events()

        today_events: List[CalendarEvent] = []
        for e in events:
            # Check if event spans or intersects today
            event_start_date = e.start_time.date()
            event_end_date = e.end_time.date()
            if event_start_date <= today_date <= event_end_date:
                today_events.append(e)

        return today_events

    async def get_upcoming_events(
        self,
        hours_ahead: int = 24,
        now: Optional[datetime] = None,
    ) -> List[CalendarEvent]:
        """Returns events starting within the next `hours_ahead` hours."""
        if now is None:
            now = datetime.now(self.timezone)

        limit_time = now + timedelta(hours=hours_ahead)
        events = await self.fetch_events()

        upcoming: List[CalendarEvent] = []
        for e in events:
            if now <= e.end_time and e.start_time <= limit_time:
                upcoming.append(e)

        return upcoming

    def format_events_summary(self, events: List[CalendarEvent]) -> str:
        """Formats a list of CalendarEvent into a human-readable markdown string."""
        if not events:
            return "Không có sự kiện nào từ Google Calendar."

        lines = []
        for idx, e in enumerate(events, 1):
            time_str = e.format_time_range()
            lines.append(f"• `{time_str}`: *{e.summary}*")
            if e.description:
                first_line_desc = e.description.split("\n")[0].strip()
                if first_line_desc:
                    lines.append(f"  └ _{first_line_desc[:60]}_")
        return "\n".join(lines)
