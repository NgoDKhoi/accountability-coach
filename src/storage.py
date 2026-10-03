"""Lightweight atomic JSON persistence layer for Autonomous Telegram Coach.

Handles crash-safe file writes, Windows NTFS replacement, asyncio lock serialization,
and calendar-day streak tracking in Asia/Ho_Chi_Minh timezone.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from datetime import date, datetime
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

HO_CHI_MINH_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class SessionStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    SNOOZED = "snoozed"
    SKIPPED = "skipped"
    AWAITING_REASON = "awaiting_reason"


@dataclass
class StreakData:
    current_streak: int
    best_streak: int
    last_completed_date: Optional[str]  # YYYY-MM-DD
    total_completions: int

    def get_effective_streak(self, today_str: Optional[str] = None) -> int:
        """Returns the active streak. If more than 1 calendar day has lapsed, returns 0."""
        if not self.last_completed_date or self.current_streak == 0:
            return 0
        if today_str is None:
            today_str = datetime.now(HO_CHI_MINH_TZ).strftime("%Y-%m-%d")
        try:
            today = date.fromisoformat(today_str)
            last = date.fromisoformat(self.last_completed_date)
            delta = (today - last).days
            if delta <= 1:
                return self.current_streak
            return 0
        except ValueError:
            return self.current_streak


@dataclass
class SessionRecord:
    session_id: str
    session_type: str
    status: str = SessionStatus.PENDING
    snooze_count: int = 0
    max_snoozes: int = 2
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    skip_reason: Optional[str] = None
    skip_classification: Optional[str] = None
    date: Optional[str] = None
    reason: Optional[str] = None
    classification: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


DEFAULT_DATA: Dict[str, Any] = {
    "version": 1,
    "streak": {
        "current_streak": 0,
        "best_streak": 0,
        "last_completed_date": None,
        "total_completions": 0,
    },
    "sessions": {},
    "active_sessions": {},
    "awaiting_reason": None,
    "history": [],
}


class AtomicJsonStore:
    """Crash-safe atomic JSON store using temporary files and os.replace."""

    def __init__(self, file_path: str = "data/records.json"):
        self.file_path = os.path.abspath(file_path)
        self.dir_name = os.path.dirname(self.file_path)
        self._lock = asyncio.Lock()
        os.makedirs(self.dir_name, exist_ok=True)

    def _sync_read(self) -> Dict[str, Any]:
        """Synchronous read with auto-creation and corruption recovery."""
        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) == 0:
            default_data = copy.deepcopy(DEFAULT_DATA)
            self._sync_write(default_data)
            return default_data

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise json.JSONDecodeError("JSON root must be an object", "", 0)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            logger.error("Failed to parse %s (%s). Creating backup and re-initializing.", self.file_path, exc)
            backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            try:
                os.replace(self.file_path, backup_path)
            except OSError:
                pass
            default_data = copy.deepcopy(DEFAULT_DATA)
            self._sync_write(default_data)
            return default_data

        # Enforce presence of all standard schema keys
        for key, val in DEFAULT_DATA.items():
            if key not in data:
                data[key] = copy.deepcopy(val)
            elif isinstance(val, dict) and not isinstance(data[key], dict):
                data[key] = copy.deepcopy(val)
            elif isinstance(val, list) and not isinstance(data[key], list):
                data[key] = copy.deepcopy(val)
        return data

    def _sync_write(self, data: Dict[str, Any]) -> None:
        """Synchronous atomic write protocol:
        1. Ensure directory exists.
        2. Create NamedTemporaryFile in SAME directory (data/).
        3. Write JSON, flush buffer, and fsync to disk.
        4. Close file handle in finally block (guaranteed before os.replace or os.remove).
        5. Atomically replace target file using os.replace.
        6. Clean up temporary file on failure.
        """
        os.makedirs(self.dir_name, exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=self.dir_name,
            prefix="records_",
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        )
        temp_path = temp_file.name
        try:
            try:
                json.dump(data, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            finally:
                temp_file.close()  # CRITICAL: releases Windows handle lock before replace or cleanup

            os.replace(temp_path, self.file_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    async def load_data(self) -> Dict[str, Any]:
        """Loads and returns the persisted data dictionary."""
        async with self._lock:
            return await asyncio.to_thread(self._sync_read)

    async def save_data(self, data: Dict[str, Any]) -> None:
        """Persists the provided data dictionary atomically."""
        async with self._lock:
            if os.path.exists(self.file_path) and os.path.getsize(self.file_path) > 0:
                current_data = await asyncio.to_thread(self._sync_read)
                for k, v in current_data.get("sessions", {}).items():
                    data.setdefault("sessions", {}).setdefault(k, v)
                for k, v in current_data.get("active_sessions", {}).items():
                    data.setdefault("active_sessions", {}).setdefault(k, v)
            await asyncio.to_thread(self._sync_write, data)

    async def get_streak(self) -> StreakData:
        """Retrieves the current streak record."""
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            raw = data.get("streak", {})
            return StreakData(
                current_streak=raw.get("current_streak", 0),
                best_streak=raw.get("best_streak", 0),
                last_completed_date=raw.get("last_completed_date"),
                total_completions=raw.get("total_completions", 0),
            )

    async def record_completion(
        self, session_id: str, session_type: str, today_str: Optional[str] = None
    ) -> StreakData:
        """Records session completion, increments streak on consecutive days,
        resets on gaps, keeps streak idempotent for same-day completions,
        and ensures duplicate completions for the same session_id are no-ops.
        """
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            if today_str is None:
                today_str = datetime.now(HO_CHI_MINH_TZ).strftime("%Y-%m-%d")
            now_iso = datetime.now(HO_CHI_MINH_TZ).isoformat()

            streak = data.setdefault("streak", copy.deepcopy(DEFAULT_DATA["streak"]))
            last_date_str = streak.get("last_completed_date")
            current_streak = streak.get("current_streak", 0)
            best_streak = streak.get("best_streak", 0)
            total_completions = streak.get("total_completions", 0)

            # Idempotency check: if this specific session was ALREADY completed, do not re-increment
            existing_session = data.get("sessions", {}).get(session_id)
            if existing_session and existing_session.get("status") == SessionStatus.COMPLETED:
                return StreakData(
                    current_streak=current_streak,
                    best_streak=best_streak,
                    last_completed_date=last_date_str,
                    total_completions=total_completions,
                )

            total_completions += 1
            today = date.fromisoformat(today_str)
            if last_date_str is None:
                current_streak = 1
                best_streak = max(best_streak, 1)
                last_date_str = today_str
            else:
                last_date = date.fromisoformat(last_date_str)
                delta = (today - last_date).days
                if delta == 0:
                    # Same day: idempotent, keep streak count unchanged
                    pass
                elif delta == 1:
                    # Consecutive day: increment streak
                    current_streak += 1
                    best_streak = max(best_streak, current_streak)
                    last_date_str = today_str
                elif delta > 1:
                    # Gap day: reset streak to 1, preserve best_streak
                    current_streak = 1
                    best_streak = max(best_streak, 1)
                    last_date_str = today_str
                else:
                    # Out-of-order date: do not regress streak
                    pass

            streak["current_streak"] = current_streak
            streak["best_streak"] = best_streak
            streak["last_completed_date"] = last_date_str
            streak["total_completions"] = total_completions

            session = data["sessions"].setdefault(
                session_id,
                {
                    "session_id": session_id,
                    "session_type": session_type,
                    "snooze_count": 0,
                    "max_snoozes": 2,
                    "created_at": now_iso,
                },
            )
            session["status"] = SessionStatus.COMPLETED
            session["session_type"] = session_type
            session["date"] = today_str
            session["today_str"] = today_str
            session["completed_at"] = now_iso
            session["updated_at"] = now_iso
            data["active_sessions"][session_id] = copy.deepcopy(session)

            if data.get("awaiting_reason") == session_id:
                data["awaiting_reason"] = None

            data["history"].append(
                {
                    "timestamp": now_iso,
                    "session_id": session_id,
                    "session_type": session_type,
                    "action": "completed",
                    "details": {
                        "today_str": today_str,
                        "current_streak": current_streak,
                        "best_streak": best_streak,
                    },
                }
            )

            await asyncio.to_thread(self._sync_write, data)
            return StreakData(
                current_streak=current_streak,
                best_streak=best_streak,
                last_completed_date=last_date_str,
                total_completions=total_completions,
            )

    async def record_snooze(self, session_id: str, new_count: Optional[int] = None) -> int:
        """Records session snooze and returns the updated snooze_count."""
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            now_iso = datetime.now(HO_CHI_MINH_TZ).isoformat()

            session = data["sessions"].setdefault(
                session_id,
                {
                    "session_id": session_id,
                    "session_type": "unknown",
                    "snooze_count": 0,
                    "max_snoozes": 2,
                    "created_at": now_iso,
                },
            )

            if new_count is not None:
                session["snooze_count"] = new_count
            else:
                session["snooze_count"] = session.get("snooze_count", 0) + 1

            session["status"] = SessionStatus.SNOOZED
            session["updated_at"] = now_iso
            data["active_sessions"][session_id] = copy.deepcopy(session)

            data["history"].append(
                {
                    "timestamp": now_iso,
                    "session_id": session_id,
                    "session_type": session.get("session_type", "unknown"),
                    "action": "snoozed",
                    "details": {"snooze_count": session["snooze_count"]},
                }
            )

            await asyncio.to_thread(self._sync_write, data)
            return session["snooze_count"]

    async def record_skip(
        self, session_id: str, reason: str, classification: str, timestamp_str: Optional[str] = None
    ) -> None:
        """Records session skip with justification rationale and AI classification."""
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            if timestamp_str is None:
                timestamp_str = datetime.now(HO_CHI_MINH_TZ).isoformat()

            session = data["sessions"].setdefault(
                session_id,
                {
                    "session_id": session_id,
                    "session_type": "unknown",
                    "snooze_count": 0,
                    "max_snoozes": 2,
                    "created_at": timestamp_str,
                },
            )

            session["status"] = SessionStatus.SKIPPED
            session["skip_reason"] = reason
            session["reason"] = reason
            session["skip_classification"] = classification
            session["classification"] = classification
            session["timestamp"] = timestamp_str
            session["updated_at"] = timestamp_str
            data["active_sessions"][session_id] = copy.deepcopy(session)

            if data.get("awaiting_reason") == session_id:
                data["awaiting_reason"] = None

            data["history"].append(
                {
                    "timestamp": timestamp_str,
                    "session_id": session_id,
                    "session_type": session.get("session_type", "unknown"),
                    "action": "skipped",
                    "details": {"reason": reason, "classification": classification},
                }
            )

            await asyncio.to_thread(self._sync_write, data)

    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves session status dictionary or None if not found."""
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            if session_id in data.get("sessions", {}):
                return copy.deepcopy(data["sessions"][session_id])
            if session_id in data.get("active_sessions", {}):
                return copy.deepcopy(data["active_sessions"][session_id])
            return None

    async def create_session(
        self,
        session_id: str,
        session_type: str,
        status: str = SessionStatus.PENDING,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Creates or registers a new session in persistence."""
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            now_iso = datetime.now(HO_CHI_MINH_TZ).isoformat()

            session = {
                "session_id": session_id,
                "session_type": session_type,
                "status": status,
                "snooze_count": 0,
                "max_snoozes": 2,
                "created_at": now_iso,
                "updated_at": now_iso,
                "completed_at": None,
                "skip_reason": None,
                "skip_classification": None,
                "metadata": metadata or {},
            }
            data["sessions"][session_id] = session
            data["active_sessions"][session_id] = copy.deepcopy(session)
            await asyncio.to_thread(self._sync_write, data)
            return copy.deepcopy(session)

    async def set_awaiting_reason(self, session_id: str) -> None:
        """Sets the state machine to await justification text for session_id."""
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            now_iso = datetime.now(HO_CHI_MINH_TZ).isoformat()
            data["awaiting_reason"] = session_id
            if session_id in data.get("sessions", {}):
                data["sessions"][session_id]["status"] = SessionStatus.AWAITING_REASON
                data["sessions"][session_id]["updated_at"] = now_iso
            if session_id in data.get("active_sessions", {}):
                data["active_sessions"][session_id]["status"] = SessionStatus.AWAITING_REASON
                data["active_sessions"][session_id]["updated_at"] = now_iso
            await asyncio.to_thread(self._sync_write, data)

    async def get_awaiting_reason(self) -> Optional[str]:
        """Returns the session_id currently awaiting reason, or None."""
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            return data.get("awaiting_reason")

    async def clear_awaiting_reason(self) -> None:
        """Clears the awaiting_reason state."""
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            data["awaiting_reason"] = None
            await asyncio.to_thread(self._sync_write, data)

    async def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns the most recent N history records (newest first)."""
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            history = data.get("history", [])
            return copy.deepcopy(history[-limit:][::-1])

    async def reset(self) -> None:
        """Resets the persistence store to initial default structure."""
        async with self._lock:
            default_data = copy.deepcopy(DEFAULT_DATA)
            await asyncio.to_thread(self._sync_write, default_data)
