"""Tests for Google Calendar iCal (.ics) integration service."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo
import pytest

from src.calendar_service import CalendarEvent, CalendarService, _parse_ics_datetime, _unfold_ics_lines

SAMPLE_ICS_FEED = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Inc//Google Calendar 70.9054//EN
CALSCALE:GREGORIAN
BEGIN:VEVENT
DTSTART:20261004T070000Z
DTEND:20261004T083000Z
SUMMARY:Họp Team Game Dev
DESCRIPTION:Thảo luận về shader và level design
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Asia/Ho_Chi_Minh:20261004T150000
DTEND;TZID=Asia/Ho_Chi_Minh:20261004T160000
SUMMARY:Ôn thi Hệ Điều Hành
DESCRIPTION:Xem lại chương quản lý bộ nhớ
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261004
DTEND;VALUE=DATE:20261005
SUMMARY:Ngày hội tuyển dụng IT
DESCRIPTION:Gặp nhà tuyển dụng game
END:VEVENT
END:VCALENDAR"""


def test_unfold_ics_lines() -> None:
    raw = "SUMMARY:Line one\n and continuation\nDESCRIPTION:Normal line"
    unfolded = _unfold_ics_lines(raw)
    assert len(unfolded) == 2
    assert unfolded[0] == "SUMMARY:Line oneand continuation"
    assert unfolded[1] == "DESCRIPTION:Normal line"


def test_parse_ics_datetime_utc() -> None:
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    # 07:00 UTC = 14:00 Asia/Ho_Chi_Minh (+7)
    dt, all_day = _parse_ics_datetime("20261004T070000Z", tz)
    assert not all_day
    assert dt.hour == 14
    assert dt.minute == 0
    assert dt.day == 4


def test_parse_ics_datetime_all_day() -> None:
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    dt, all_day = _parse_ics_datetime("20261004", tz)
    assert all_day
    assert dt.hour == 0
    assert dt.minute == 0
    assert dt.day == 4


def test_parse_ics_content() -> None:
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    svc = CalendarService(timezone=tz)
    events = svc.parse_ics_content(SAMPLE_ICS_FEED)

    assert len(events) == 3
    # Check all day event
    all_day_event = next(e for e in events if e.is_all_day)
    assert all_day_event.summary == "Ngày hội tuyển dụng IT"
    assert all_day_event.format_time_range() == "Cả ngày"

    # Check timed events
    game_dev = next(e for e in events if "Game Dev" in e.summary)
    assert game_dev.start_time.hour == 14
    assert game_dev.end_time.hour == 15
    assert game_dev.end_time.minute == 30
    assert game_dev.duration_minutes == 90


@pytest.mark.asyncio
async def test_calendar_service_fetch_with_mock_client() -> None:
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    mock_response = MagicMock()
    mock_response.text = SAMPLE_ICS_FEED
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    svc = CalendarService(
        ical_url="https://calendar.google.com/calendar/ical/test/basic.ics",
        timezone=tz,
        http_client=mock_client,
    )
    assert svc.is_configured

    events = await svc.fetch_events()
    assert len(events) == 3
    assert mock_client.get.call_count == 1

    # Test cache: second call should not re-fetch
    events_cached = await svc.fetch_events(force_refresh=False)
    assert len(events_cached) == 3
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_calendar_service_today_events() -> None:
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    mock_response = MagicMock()
    mock_response.text = SAMPLE_ICS_FEED
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    svc = CalendarService(
        ical_url="https://calendar.google.com/calendar/ical/test/basic.ics",
        timezone=tz,
        http_client=mock_client,
    )

    test_now = datetime(2026, 10, 4, 12, 0, tzinfo=tz)
    today_events = await svc.get_today_events(now=test_now)
    assert len(today_events) == 3

    # On a different day
    tomorrow = datetime(2026, 10, 5, 12, 0, tzinfo=tz)
    tomorrow_events = await svc.get_today_events(now=tomorrow)
    # Only the all-day event ends on Oct 5
    assert len(tomorrow_events) == 1


def test_calendar_service_format_summary() -> None:
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    svc = CalendarService(timezone=tz)
    events = [
        CalendarEvent(
            summary="Họp đồ án",
            start_time=datetime(2026, 10, 4, 14, 0, tzinfo=tz),
            end_time=datetime(2026, 10, 4, 15, 0, tzinfo=tz),
            description="Báo cáo tiến độ",
        )
    ]
    summary = svc.format_events_summary(events)
    assert "Họp đồ án" in summary
    assert "14:00 – 15:00" in summary
    assert "Báo cáo tiến độ" in summary


@pytest.mark.asyncio
async def test_unconfigured_calendar_service_returns_empty() -> None:
    svc = CalendarService()
    assert not svc.is_configured
    events = await svc.fetch_events()
    assert events == []
    assert svc.format_events_summary([]) == "Không có sự kiện nào từ Google Calendar."
