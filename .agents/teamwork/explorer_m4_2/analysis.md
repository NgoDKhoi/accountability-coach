# Milestone 4 Architecture Analysis: Interactive Inline Action State Machine & Dialog Workflows

**Author**: Milestone 4 Explorer 2 (`teamwork_preview_explorer`)  
**Scope**: Milestone 4 — Interactive Inline Buttons, State Machine, Dialog Routing (`src/bot.py`, `src/main.py`)  
**Target Features**: Features 13–21, 26, 34; Boundary cases (Tier 2); Pairwise interactions (Tier 3); Scenarios 1–5 (Tier 4)  
**Date**: 2026-10-04  
**Status**: Investigation Complete  

---

## 1. Executive Summary & Objective

Milestone 4 delivers the interactive user experience and dialogue state machine of the Autonomous Telegram Personal Accountability Coach. It bridges Telegram's UI capabilities (`python-telegram-bot` v20+) with the completed persistence layer (`src/storage.py`), AI coaching engine (`src/coach.py`), and scheduling service (`src/scheduler.py`).

The primary objectives investigated in this report:
1. **Interactive Inline Keyboard Markup**: Designing and generating the standard 3-button Telegram layout:
   - `[✅ Đã hoàn thành]`
   - `[⏳ Xin lùi 15 phút]`
   - `[🛑 Hôm nay nghỉ (Có lý do)]`
   and defining the callback data serialization and parsing protocol (`action:session_id`).
2. **"Done" Completion Workflow**: Idempotent streak incrementation, calendar-day calculation in `Asia/Ho_Chi_Minh`, atomic disk recording, AI praise generation via `coach.get_congratulation`, and message UI updates.
3. **"Snooze 15m" Escalation Workflow**: Tracking consecutive snooze attempts per session, enforcing the strict cap of 2 snoozes (`max_snoozes`), scheduling dynamic one-shot `DateTrigger` reminder jobs via `scheduler.schedule_snooze_job`, and rejecting further snoozes with escalating firmness.
4. **"Skip with Reason" State Machine & Excuse Evaluation**: State transition into `awaiting_reason`, intercepting free-form justification text, evaluating validity via `coach.evaluate_skip_reason`, branching into 2-minute micro-habit challenges (for excuses) vs approved skip recording (for legitimate reasons), and atomic state cleanup.
5. **Reactive Free-Form Coaching Chat**: Contextual dialogue routing to `coach.chat` outside scheduled reminder contexts, maintaining sliding context memory and persona constraints.
6. **Test Assertion Inventory**: Verifying compliance against all test requirements in Tier 1 Group 3 (Features 13–21, 26, 34), Tier 2 boundary cases, Tier 3 pairwise dynamics, and Tier 4 multi-step user scenarios.

---

## 2. Interface Contracts & Component Architecture

### 2.1 Subsystem Dependencies & Integration Points

The bot component in `src/bot.py` acts as the central orchestrator connecting four dependencies:

```
                  ┌────────────────────────────────────────┐
                  │       Telegram / MockTelegramBot       │
                  └───────────────────▲────────────────────┘
                                      │ process_update / send / edit
                                      ▼
                  ┌────────────────────────────────────────┐
                  │          BotApplication Core           │
                  │              (src/bot.py)              │
                  └──────┬────────────┼────────────┬───────┘
                         │            │            │
          ┌──────────────▼───┐ ┌──────▼──────┐ ┌───▼──────────────┐
          │  AtomicJsonStore │ │  Scheduler  │ │  AICoachService  │
          │ (src/storage.py) │ │(scheduler.py│ │  (src/coach.py)  │
          └──────────────────┘ └─────────────┘ └──────────────────┘
```

1. **`AppConfig` (`src/config.py`)**:
   - `allowed_chat_id: int` — Security whitelist boundary.
   - `timezone: str` — Defaults to `"Asia/Ho_Chi_Minh"`.
   - `max_snoozes: int` — Limit for consecutive snoozes (default: `2`).
   - `snooze_minutes: int` — Duration of snooze delay (default: `15`).
   - `prompts: Dict[str, str]` — Templates for praise, snooze warnings, skip evaluator.
   - `fallbacks: Dict[str, str]` — Deterministic offline messages for offline resilience.

2. **`AtomicJsonStore` (`src/storage.py`)**:
   - `record_completion(session_id: str, session_type: str, today_str: Optional[str]) -> StreakData`
   - `record_snooze(session_id: str, new_count: Optional[int]) -> int`
   - `record_skip(session_id: str, reason: str, classification: str, timestamp_str: Optional[str]) -> None`
   - `get_session_status(session_id: str) -> Optional[Dict[str, Any]]`
   - `load_data() -> Dict[str, Any]` & `save_data(data: Dict[str, Any]) -> None`
   - `set_awaiting_reason(session_id: str) -> None` & `get_awaiting_reason() -> Optional[str]`

3. **`SchedulerService` (`src/scheduler.py`)**:
   - `schedule_snooze_job(session_id, session_type, snooze_count, delay_minutes, callback) -> str`
   - Generates job ID `f"snooze_{session_id}_{snooze_count}"`.
   - Fires `callback(session_id, session_type, snooze_count)` after `delay_minutes`.

4. **`AICoachService` (`src/coach.py`)**:
   - `get_congratulation(session_type: str, streak: int) -> str`
   - `evaluate_skip_reason(session_type: str, reason: str) -> Tuple[str, str]`
     - Returns `(classification, response_text)` where classification is strictly `"EXCUSE"` or `"LEGITIMATE"`.
   - `chat(user_message: str) -> str`

---

## 3. Detailed Investigation of the 6 Inquired Areas

### Area 1: Inline Keyboard Markup & Callback Data Encoding

#### 1.1 Visual Markup & Button Specifications
Requirement R3 and Feature 13 mandate 3 distinct buttons arranged vertically:
- Button 1: `✅ Đã hoàn thành`
- Button 2: `⏳ Xin lùi 15 phút`
- Button 3: `🛑 Hôm nay nghỉ (Có lý do)`

Implementation signature:
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def make_inline_action_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Builds standard 3-button keyboard for session."""
    keyboard = [
        [InlineKeyboardButton("✅ Đã hoàn thành", callback_data=f"done:{session_id}")],
        [InlineKeyboardButton("⏳ Xin lùi 15 phút", callback_data=f"snooze:{session_id}")],
        [InlineKeyboardButton("🛑 Hôm nay nghỉ (Có lý do)", callback_data=f"skip:{session_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)
```

#### 1.2 Callback Data Serialization & Parsing Protocol
All tests across Tiers 1–4 (`test_e2e_tier1_features.py`, `test_e2e_tier2_boundaries.py`, `test_e2e_tier3_pairwise.py`, `test_e2e_tier4_scenarios.py`) encode callback data as:
`{action}:{session_id}`

Examples from test suite:
- `done:session_gym_today`
- `snooze:session_gym_today`
- `skip:sess_skip_test`
- `done:f34_session`
- `done:toeic_2026-10-05`
- `done:pending_sess`

To support both 2-part (`action:session_id`) and 3-part (`action:session_type:session_id`) encodings while guaranteeing 100% backward compatibility:
```python
parts = callback_data.split(":", 2)
action = parts[0]
if len(parts) == 3:
    session_type = parts[1]
    session_id = parts[2]
elif len(parts) == 2:
    session_id = parts[1]
    session_type = _infer_session_type(session_id)
else:
    session_id = "default_session"
    session_type = "session"
```

Where `_infer_session_type` checks:
1. If `"gym"` in `session_id.lower()` -> `"gym"`
2. If `"toeic"` in `session_id.lower()` -> `"toeic"`
3. If `"major"` in `session_id.lower()` -> `"major"`
4. Else inspect stored status via `storage.get_session_status(session_id)` for `"session_type"`, defaulting to `"session"`.

---

### Area 2: "Done" Flow (Completion & Streak Advancement)

#### 2.1 Operational Sequence
When the user clicks `[✅ Đã hoàn thành]`:
1. **Security Gate**: Validate `update.effective_chat.id == config.allowed_chat_id`. If unauthorized, answer query with alert `⛔ Truy cập bị từ chối!` and return.
2. **Acknowledge Click**: Immediately invoke `await query.answer("Ghi nhận hoàn thành!")` to dismiss the Telegram loading spinner.
3. **Resolve Calendar Date**: Calculate current date string in `Asia/Ho_Chi_Minh`:
   ```python
   today_str = datetime.now(ZoneInfo(config.timezone)).strftime("%Y-%m-%d")
   ```
4. **Atomic Persistence**: Invoke `storage.record_completion(session_id, session_type, today_str)`:
   - If session was already completed (rapid duplicate clicks): returns existing streak data without double counting (`test_t2_duplicate_rapid_clicks_idempotency`).
   - If consecutive day: increments `current_streak` by 1 and updates `best_streak`.
   - If same day (e.g. gym then toeic): preserves streak without double increment.
   - If gap day (>1 day lapsed): resets streak to 1.
   - Cleans up `awaiting_reason` if it matched `session_id`.
5. **AI Praise Generation**: Query `coach.get_congratulation(session_type, streak_data.current_streak)`. If Gemini times out or is offline, the coach returns `fallbacks.offline_praise`.
6. **Edit Message UI**: Replace the interactive message text and remove buttons:
   ```python
   text = (
       f"✅ *HOÀN THÀNH XUẤT SẮC!*\n"
       f"Chuỗi streak: *{streak_data.current_streak}* ngày liên tiếp.\n\n"
       f"🤖 Coach: _{praise}_"
   )
   return await query.edit_message_text(text)
   ```

#### 2.2 Key Assertions Verified
- `test_f14_done_completion_handler`:
  - `assert "HOÀN THÀNH" in resp["text"] or "kỷ luật" in resp["text"].lower()`
  - `assert streak.current_streak >= 1`
- `test_t2_duplicate_rapid_clicks_idempotency`:
  - 5 rapid clicks for same session -> `streak.current_streak == 1`, `streak.total_completions == 1`.
- `test_s1_seven_day_progression_streak_and_toeic_rotation`:
  - 7 daily consecutive completions -> `streak_data.current_streak == 7`, `best_streak == 7`.

---

### Area 3: "Snooze 15m" Flow (Cap Enforcement & Scheduling)

#### 3.1 Operational Sequence
When the user clicks `[⏳ Xin lùi 15 phút]`:
1. **Security Gate**: Whitelist check.
2. **Inspect Current Snooze Count**:
   ```python
   status = await storage.get_session_status(session_id)
   curr_count = status.get("snooze_count", 0) if status else 0
   new_count = curr_count + 1
   ```
3. **Evaluate Against Max Limit (`config.max_snoozes`, default: 2)**:
   - **Case A: `new_count > config.max_snoozes` (Attempt 3+)**:
     - Immediate rejection alert: `await query.answer("Đã đạt giới hạn lùi giờ!", show_alert=True)`.
     - Retrieve firm warning template:
       `warning_2 = config.prompts.get("snooze_warning_2") or config.fallbacks.get("offline_snooze_2")`.
     - Do NOT increment snooze count in storage (remains at 2, per `test_t2_snooze_limit_hard_boundary`).
     - Do NOT schedule a scheduler job.
     - Edit message text:
       ```python
       text = f"⚠️ *HẾT QUYỀN LÙI GIỜ!*\n\n{warning_2}"
       return await query.edit_message_text(text)
       ```
   - **Case B: `new_count <= config.max_snoozes` (Attempt 1 or 2)**:
     - Persist new snooze count: `await storage.record_snooze(session_id, new_count)`.
     - Schedule one-shot DateTrigger job in scheduler:
       ```python
       scheduler.schedule_snooze_job(
           session_id=session_id,
           session_type=session_type,
           snooze_count=new_count,
           delay_minutes=config.snooze_minutes,
           callback=self._snooze_job_callback,
       )
       ```
     - Acknowledge callback: `await query.answer(f"Đã lùi {config.snooze_minutes} phút (Lần {new_count}/{config.max_snoozes})")`.
     - Select escalating warning text:
       - Lần 1: `config.fallbacks.get("offline_snooze_1", "Đã lùi 15 phút (Lần 1/2).")`
       - Lần 2: `config.fallbacks.get("offline_snooze_2", "Đã lùi 15 phút (Lần 2/2).")`
     - Edit message text, maintaining inline buttons so the user can still complete, snooze (if count==1), or skip:
       ```python
       text = f"⏳ *ĐÃ LÙI {config.snooze_minutes} PHÚT (Lần {new_count}/{config.max_snoozes})*\n\n{warning}"
       return await query.edit_message_text(
           text,
           reply_markup=make_inline_action_keyboard(session_id),
       )
       ```

#### 3.2 Snooze Job Execution Callback
When the scheduler's 15-minute `DateTrigger` fires:
```python
async def _snooze_job_callback(self, session_id: str, session_type: str, snooze_count: int) -> None:
    text = (
        f"⏰ *HẾT {self.config.snooze_minutes} PHÚT LÙI GIỜ!*\n"
        f"Phiên `{session_type}` đang chờ bạn hoàn thành. (Lần lùi: {snooze_count}/{self.config.max_snoozes})"
    )
    await self.bot.send_message(
        self.config.allowed_chat_id,
        text,
        reply_markup=make_inline_action_keyboard(session_id),
    )
```

#### 3.3 Key Assertions Verified
- `test_f15_snooze_15m_handler`:
  - `assert "15 PHÚT" in resp["text"] or "Lần 1/2" in resp["text"]`
  - `assert status["snooze_count"] == 1`
- `test_f16_snooze_cap_enforcement`:
  - Pre-seeded 2 snoozes -> 3rd attempt:
  - `assert "GIỚI HẠN" in resp["text"] or "HẾT QUYỀN" in resp["text"]`
- `test_t2_snooze_limit_hard_boundary`:
  - Snooze attempts 1, 2, 3, 4:
  - Attempt 1: "Lần 1/2", `snooze_count == 1`
  - Attempt 2: "Lần 2/2", `snooze_count == 2`
  - Attempt 3: "HẾT QUYỀN", `snooze_count == 2` (capped)
  - Attempt 4: "HẾT QUYỀN", `snooze_count == 2` (capped)
- `test_s5_escalating_snooze_limit_to_completion`:
  - Warning 1 -> Warning 2 -> Rejection -> User clicks Done -> `SessionStatus.COMPLETED`, `snooze_count == 2`.

---

### Area 4: "Skip with Reason" Flow & State Machine

#### 4.1 Step 1: Entering `awaiting_reason` State
When the user clicks `[🛑 Hôm nay nghỉ (Có lý do)]`:
1. Security check.
2. Acknowledge click: `await query.answer("Nhập lý do xin nghỉ.")`.
3. Set state in memory AND persist to `data/records.json`:
   ```python
   self.active_session_awaiting_reason = {"session_id": session_id, "session_type": session_type}
   data_dict = await self.storage.load_data()
   data_dict["awaiting_reason"] = {"session_id": session_id, "session_type": session_type}
   await self.storage.save_data(data_dict)
   ```
   *Note: In `test_storage.py`, `awaiting_reason` is sometimes set as string `session_id`, while in `test_e2e_tier1_features.py` (lines 272, 280, 298), it is checked as `dict`: `{"session_id": session_id, "session_type": session_type}`. The dispatcher must handle both formats seamlessly.*
4. Edit message prompt:
   ```python
   text = (
       "🛑 *XIN NGHỈ CÓ LÝ DO*\n\n"
       "Hãy gửi tin nhắn giải trình lý do bạn không thể hoàn thành phiên này. "
       "AI Coach sẽ đánh giá xem đây là lý do chính đáng hay sự trì hoãn!"
   )
   return await query.edit_message_text(text)
   ```

#### 4.2 Step 2: Intercepting Justification Text
When the authorized user sends a free-form text message:
1. Check `awaiting_reason` state from storage / memory:
   ```python
   data_dict = await self.storage.load_data()
   awaiting = data_dict.get("awaiting_reason") or self.active_session_awaiting_reason
   ```
2. If `awaiting` is active:
   - Extract `session_id` and `session_type`:
     ```python
     if isinstance(awaiting, dict):
         session_id = awaiting.get("session_id", "session")
         session_type = awaiting.get("session_type", _infer_session_type(session_id))
     else:
         session_id = str(awaiting)
         session_type = _infer_session_type(session_id)
     ```
   - Evaluate reason with AI coach:
     ```python
     classification, response_text = await self.coach.evaluate_skip_reason(session_type, message.text)
     ```
   - Record skip in persistence:
     ```python
     timestamp_str = datetime.now(ZoneInfo(self.config.timezone)).isoformat()
     await self.storage.record_skip(session_id, message.text, classification, timestamp_str)
     ```
   - Clear `awaiting_reason` state in both memory and storage:
     ```python
     data_dict["awaiting_reason"] = None
     self.active_session_awaiting_reason = None
     await self.storage.save_data(data_dict)
     ```
   - Format response based on classification:
     - **If `classification == "LEGITIMATE"`**:
       ```python
       reply = (
           f"🛑 *LÝ DO CHÍNH ĐÁNG ĐƯỢC CHẤP NHẬN*\n\n"
           f"🤖 Coach: _{response_text}_\n\n"
           f"Phiên này được ghi nhận nghỉ có lý do. Không ảnh hưởng chuỗi streak."
       )
       ```
     - **If `classification == "EXCUSE"`**:
       ```python
       reply = (
           f"⚡ *BÓC TRẦN LÝ DO BAO BIỆN!*\n\n"
           f"🤖 Coach: _{response_text}_\n\n"
           f"👉 *THỬ THÁCH MICRO-HABIT 2 PHÚT*: Thực hiện ngay để không đứt gãy tính kỷ luật!"
       )
       ```
       *(Session is recorded, but the user is challenged with micro-habit. If the user later clicks Done on the session, `record_completion` successfully marks it completed and increments streak, as in Scenario 2).*

#### 4.3 Key Assertions Verified
- `test_f18_skip_with_reason_trigger`:
  - `assert "LÝ DO" in resp["text"]`
  - `assert data["awaiting_reason"]["session_id"] == "sess_skip_test"`
- `test_f19_f20_skip_excuse_triggers_micro_habit`:
  - Input: "Hôm nay em lười quá, muốn nằm xem video YouTube"
  - `assert "BAO BIỆN" in resp["text"] or "MICRO-HABIT" in resp["text"] or "2 PHÚT" in resp["text"]`
- `test_f21_legitimate_skip_approval`:
  - Input: "Em bị sốt cao 39 độ phải vào bệnh viện cấp cứu gấp"
  - `assert "CHÍNH ĐÁNG" in resp["text"] or "phục hồi" in resp["text"].lower()`
  - `assert status["status"] == SessionStatus.SKIPPED`
  - `assert status["classification"] == "LEGITIMATE"`
- `test_t2_reason_empty_or_whitespace_handling`:
  - Whitespace-only input -> Classified safely as EXCUSE with micro-habit, no crash.
- `test_t2_reason_unicode_and_vietnamese_diacritics`:
  - Complex Vietnamese characters stored without encoding corruption.
- `test_t2_reason_markdown_and_special_character_injection`:
  - Markdown, HTML, and SQL metacharacters handled without crashing.
- `test_t2_reason_extreme_large_text`:
  - 8,000+ character justifications handled cleanly.
- `test_t3_p1_snooze_then_skip_lifecycle`:
  - Snooze then Skip properly transitions from SNOOZED to SKIPPED.
- `test_t3_p7_gemini_timeout_during_skip_reason_evaluation`:
  - Gemini timeout uses offline fallback and completes recording without exception.

---

### Area 5: Reactive Free-Form Coaching Chat

#### 5.1 Operational Sequence
When the authorized user sends a text message that:
1. Is NOT a command (`/start`, `/help`, `/status`).
2. Is NOT in `awaiting_reason` state (`awaiting_reason is None`).

The message is routed directly to the AI coach:
```python
coach_reply = await self.coach.chat(message.text)
return await self.bot.send_message(message.chat.id, f"🤖 *Coach*: {coach_reply}")
```

#### 5.2 Constraints & Key Assertions
- Persona constraint: Maximum 2–3 sentences, technical mindset, direct tone (`test_f23_coach_persona_conciseness`).
- Sliding context buffer: Preserves sliding window of up to 10 dialogue turns in memory (`test_f24_sliding_context_window`, `test_t2_sliding_window_overflow_boundary`).
- Offline fallback: If Gemini API fails or times out, returns `config.fallbacks.offline_coach` (`test_f25_graceful_offline_fallback`).
- Feature 26: `test_f26_reactive_free_form_chat`:
  - Input: "Làm sao để tối ưu hoá thời gian cày TOEIC và game dev?"
  - Output: `assert "Coach" in resp["text"]`.

---

### Area 6: Comprehensive Assertion Matrix across Tiers

| Feature / Scenario | Test Name | Input Trigger | Key Assertions / Verifications |
|---|---|---|---|
| **F13** | `test_f13_inline_keyboard_generator` | `make_inline_action_keyboard("gym_101")` | `len(markup.inline_keyboard) == 3`<br>`cb[0] == "done:gym_101"`<br>`cb[1] == "snooze:gym_101"`<br>`cb[2] == "skip:gym_101"` |
| **F14** | `test_f14_done_completion_handler` | `done:session_gym_today` callback | `"HOÀN THÀNH" in resp["text"]`<br>`streak.current_streak >= 1` |
| **F15** | `test_f15_snooze_15m_handler` | `snooze:session_gym_today` callback | `"15 PHÚT" in resp["text"]` or `"Lần 1/2"`<br>`status["snooze_count"] == 1` |
| **F16** | `test_f16_snooze_cap_enforcement` | `snooze:sess_test` after 2 snoozes | `"GIỚI HẠN" in resp["text"]` or `"HẾT QUYỀN"` |
| **F18** | `test_f18_skip_with_reason_trigger` | `skip:sess_skip_test` callback | `"LÝ DO" in resp["text"]`<br>`data["awaiting_reason"]["session_id"] == "sess_skip_test"` |
| **F19 & F20** | `test_f19_f20_skip_excuse_triggers_micro_habit` | Text excuse: "em lười quá..." | `"BAO BIỆN" in resp["text"]` or `"MICRO-HABIT"` or `"2 PHÚT"` |
| **F21** | `test_f21_legitimate_skip_approval` | Text valid: "sốt cao 39 độ cấp cứu..." | `"CHÍNH ĐÁNG" in resp["text"]`<br>`status["status"] == SessionStatus.SKIPPED`<br>`status["classification"] == "LEGITIMATE"` |
| **F26** | `test_f26_reactive_free_form_chat` | Text: "Làm sao để tối ưu..." | `"Coach" in resp["text"]` |
| **F34** | `test_f34_state_machine_coverage` | `snooze:f34_session` -> `done:f34_session` | `snooze_count == 1` -> `status == SessionStatus.COMPLETED` |
| **Scenario 1** | `test_s1_seven_day_progression_streak_and_toeic_rotation` | Mon-Sun 7 daily completions | `streak == 7`, `best_streak == 7`, `total == 7`, TOEIC syllabus rotation matched |
| **Scenario 2** | `test_s2_excuse_challenge_and_micro_habit_recovery` | Skip -> Excuse -> Micro-habit -> Done | `"BAO BIỆN"` -> `"HOÀN THÀNH"` -> streak incremented |
| **Scenario 3** | `test_s3_full_daily_three_session_timeline` | Gym Snooze/Done -> TOEIC Done -> Major Legitimate Skip | Gym `COMPLETED`, TOEIC `COMPLETED`, Major `SKIPPED (LEGITIMATE)`, `/status` verified |
| **Scenario 4** | `test_s4_bot_restart_and_crash_recovery` | Reboot with fresh app instance | Streak 3 preserved across restart, pending session completed on new instance |
| **Scenario 5** | `test_s5_escalating_snooze_limit_to_completion` | Snooze 1 -> Snooze 2 -> Snooze 3 (Blocked) -> Done | "Lần 1/2" -> "Lần 2/2" -> "HẾT QUYỀN" -> "HOÀN THÀNH" (`snooze_count == 2`) |

---

## 4. Implementation Blueprint for `src/bot.py`

### 4.1 Dual-Compatibility Architecture

To ensure 100% compliance with both:
1. `tests/mock_services.py` and the offline test suite (which passes `MockUpdate` and expects synchronous dictionary returns from `process_update`), and
2. Production Telegram runtime (`python-telegram-bot` v20+ async event loop and `Application`),

`src/bot.py` should implement a cohesive `BotApplication` class that wraps PTB `Application` (or adapts it) and exposes `process_update(update)`:

```python
"""Telegram Bot Core & Interactive Dialog State Machine.

Implements strict chat_id whitelist filtering, command handlers (/start, /help, /status),
interactive inline keyboards (Done, Snooze, Skip), snooze escalation limits,
excuse evaluation with 2-minute micro-habits, and reactive free-form coaching.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import AppConfig
from src.storage import AtomicJsonStore, SessionStatus, StreakData

logger = logging.getLogger(__name__)


def make_inline_action_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Builds standard 3-button keyboard for session."""
    keyboard = [
        [InlineKeyboardButton("✅ Đã hoàn thành", callback_data=f"done:{session_id}")],
        [InlineKeyboardButton("⏳ Xin lùi 15 phút", callback_data=f"snooze:{session_id}")],
        [InlineKeyboardButton("🛑 Hôm nay nghỉ (Có lý do)", callback_data=f"skip:{session_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)

# Backward-compatible alias
build_inline_action_keyboard = make_inline_action_keyboard


class BotApplication:
    """Central bot dispatcher providing PTB v20+ integration and test double execution."""

    def __init__(
        self,
        config: AppConfig,
        storage: AtomicJsonStore,
        coach: Any,
        scheduler: Any,
        bot: Optional[Any] = None,
    ):
        self.config = config
        self.storage = storage
        self.coach = coach
        self.scheduler = scheduler
        self.active_session_awaiting_reason: Optional[Dict[str, str]] = None

        if bot is not None:
            self.bot = bot
        else:
            from tests.mock_services import MockTelegramBot
            self.bot = MockTelegramBot(token=config.bot_token)

    def _infer_session_type(self, session_id: str) -> str:
        sid_lower = session_id.lower()
        if "gym" in sid_lower:
            return "gym"
        elif "toeic" in sid_lower:
            return "toeic"
        elif "major" in sid_lower or "game" in sid_lower:
            return "major"
        return "session"

    async def process_update(self, update: Any) -> Optional[Dict[str, Any]]:
        """Processes incoming update adhering strictly to whitelist security gate."""
        chat = getattr(update, "effective_chat", None)
        user = getattr(update, "effective_user", None)
        if not chat:
            return None

        # Feature 1 & 36: Whitelist Security Gate
        if chat.id != self.config.allowed_chat_id:
            if getattr(update, "message", None):
                return await self.bot.send_message(
                    chat.id,
                    "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.",
                )
            elif getattr(update, "callback_query", None):
                return await update.callback_query.answer(
                    "⛔ Truy cập bị từ chối!", show_alert=True
                )
            return None

        # Callback queries handling
        if getattr(update, "callback_query", None):
            return await self._handle_callback(update.callback_query)

        # Message text / command handling
        if getattr(update, "message", None) and getattr(update.message, "text", None):
            text = update.message.text.strip()
            if text.startswith("/start"):
                return await self._handle_start(update.message)
            elif text.startswith("/help"):
                return await self._handle_help(update.message)
            elif text.startswith("/status"):
                return await self._handle_status(update.message)
            else:
                return await self._handle_text(update.message)

        return None

    async def _handle_start(self, message: Any) -> Dict[str, Any]:
        text = (
            "🚀 *Chào mừng bạn đến với Huấn Luyện Viên Kỷ Luật Cá Nhân!*\n\n"
            "Tôi là bot giám sát tiến độ thực chiến dành cho kỹ sư IT & game dev.\n"
            "Các lệnh khả dụng:\n"
            "• `/status` - Xem chuỗi streak và lịch sử check-in\n"
            "• `/help` - Xem hướng dẫn chi tiết\n"
        )
        return await self.bot.send_message(message.chat.id, text)

    async def _handle_help(self, message: Any) -> Dict[str, Any]:
        text = (
            "📖 *HƯỚNG DẪN SỬ DỤNG:*\n\n"
            "1. Bot sẽ chủ động gửi thông báo theo lịch đã cài đặt.\n"
            "2. Khi nhận thông báo, chọn 1 trong 3 nút:\n"
            "   - `[✅ Đã hoàn thành]`: Ghi nhận hoàn thành và tăng streak.\n"
            "   - `[⏳ Xin lùi 15 phút]`: Lùi tối đa 2 lần.\n"
            "   - `[🛑 Hôm nay nghỉ (Có lý do)]`: Nhập lý do để AI đánh giá.\n"
        )
        return await self.bot.send_message(message.chat.id, text)

    async def _handle_status(self, message: Any) -> Dict[str, Any]:
        streak_data = await self.storage.get_streak()
        today_str = datetime.now(ZoneInfo(self.config.timezone)).strftime("%Y-%m-%d")
        effective_streak = streak_data.get_effective_streak(today_str)
        text = (
            f"📊 *BÁO CÁO KỶ LUẬT THỰC CHIẾN*\n\n"
            f"🔥 Chuỗi streak hiện tại: *{effective_streak}* ngày\n"
            f"🏆 Kỷ lục streak tốt nhất: *{streak_data.best_streak}* ngày\n"
            f"✅ Tổng số phiên hoàn thành: *{streak_data.total_completions}*\n"
            f"📅 Lần cuối hoàn thành: `{streak_data.last_completed_date or 'Chưa có'}`"
        )
        return await self.bot.send_message(message.chat.id, text)

    async def _handle_callback(self, query: Any) -> Dict[str, Any]:
        data = query.data
        parts = data.split(":")
        action = parts[0]
        if len(parts) >= 3:
            session_type = parts[1]
            session_id = ":".join(parts[2:])
        elif len(parts) == 2:
            session_id = parts[1]
            session_type = self._infer_session_type(session_id)
        else:
            session_id = "default_session"
            session_type = "session"

        if action == "done":
            await query.answer("Ghi nhận hoàn thành!")
            today_str = datetime.now(ZoneInfo(self.config.timezone)).strftime("%Y-%m-%d")
            streak_data = await self.storage.record_completion(session_id, session_type, today_str)
            praise = await self.coach.get_congratulation(session_type, streak_data.current_streak)
            text = (
                f"✅ *HOÀN THÀNH XUẤT SẮC!*\n"
                f"Chuỗi streak: *{streak_data.current_streak}* ngày liên tiếp.\n\n"
                f"🤖 Coach: _{praise}_"
            )
            return await query.edit_message_text(text)

        elif action == "snooze":
            status = await self.storage.get_session_status(session_id)
            curr_count = status.get("snooze_count", 0) if status else 0
            new_count = curr_count + 1

            if new_count > self.config.max_snoozes:
                await query.answer("Đã đạt giới hạn lùi giờ!", show_alert=True)
                warning_2 = self.config.prompts.get(
                    "snooze_warning_2",
                    "⚠️ ĐÃ ĐẠT GIỚI HẠN LÙI GIỜ (Lần 2/2)! Nghiêm túc dẹp điện thoại và bắt tay vào việc ngay!",
                )
                return await query.edit_message_text(f"⚠️ *HẾT QUYỀN LÙI GIỜ!*\n\n{warning_2}")

            await self.storage.record_snooze(session_id, new_count)
            self.scheduler.schedule_snooze_job(
                session_id=session_id,
                session_type=session_type,
                snooze_count=new_count,
                delay_minutes=self.config.snooze_minutes,
                callback=self._snooze_job_callback,
            )
            await query.answer(f"Đã lùi {self.config.snooze_minutes} phút (Lần {new_count}/{self.config.max_snoozes})")

            warning = (
                self.config.fallbacks.get("offline_snooze_1", "Đã lùi 15 phút (Lần 1/2).")
                if new_count == 1
                else self.config.fallbacks.get("offline_snooze_2", "Đã lùi 15 phút (Lần 2/2).")
            )
            return await query.edit_message_text(
                f"⏳ *ĐÃ LÙI {self.config.snooze_minutes} PHÚT (Lần {new_count}/{self.config.max_snoozes})*\n\n{warning}",
                reply_markup=make_inline_action_keyboard(session_id),
            )

        elif action == "skip":
            await query.answer("Nhập lý do xin nghỉ.")
            self.active_session_awaiting_reason = {"session_id": session_id, "session_type": session_type}
            data_dict = await self.storage.load_data()
            data_dict["awaiting_reason"] = {"session_id": session_id, "session_type": session_type}
            await self.storage.save_data(data_dict)
            return await query.edit_message_text(
                "🛑 *XIN NGHỈ CÓ LÝ DO*\n\n"
                "Hãy gửi tin nhắn giải trình lý do bạn không thể hoàn thành phiên này. "
                "AI Coach sẽ đánh giá xem đây là lý do chính đáng hay sự trì hoãn!"
            )

        return await query.answer("Không nhận diện được thao tác.")

    async def _handle_text(self, message: Any) -> Dict[str, Any]:
        data_dict = await self.storage.load_data()
        awaiting = data_dict.get("awaiting_reason") or self.active_session_awaiting_reason

        if awaiting:
            if isinstance(awaiting, dict):
                session_id = awaiting.get("session_id", "session")
                session_type = awaiting.get("session_type", self._infer_session_type(session_id))
            else:
                session_id = str(awaiting)
                session_type = self._infer_session_type(session_id)

            reason_text = message.text

            classification, response_text = await self.coach.evaluate_skip_reason(session_type, reason_text)
            timestamp_str = datetime.now(ZoneInfo(self.config.timezone)).isoformat()
            await self.storage.record_skip(session_id, reason_text, classification, timestamp_str)

            data_dict["awaiting_reason"] = None
            self.active_session_awaiting_reason = None
            await self.storage.save_data(data_dict)

            if classification == "LEGITIMATE":
                reply = (
                    f"🛑 *LÝ DO CHÍNH ĐÁNG ĐƯỢC CHẤP NHẬN*\n\n"
                    f"🤖 Coach: _{response_text}_\n\n"
                    f"Phiên này được ghi nhận nghỉ có lý do. Không ảnh hưởng chuỗi streak."
                )
            else:
                reply = (
                    f"⚡ *BÓC TRẦN LÝ DO BAO BIỆN!*\n\n"
                    f"🤖 Coach: _{response_text}_\n\n"
                    f"👉 *THỬ THÁCH MICRO-HABIT 2 PHÚT*: Thực hiện ngay để không đứt gãy tính kỷ luật!"
                )
            return await self.bot.send_message(message.chat.id, reply)

        # Reactive free-form coaching chat
        coach_reply = await self.coach.chat(message.text)
        return await self.bot.send_message(message.chat.id, f"🤖 *Coach*: {coach_reply}")

    async def _snooze_job_callback(self, session_id: str, session_type: str, snooze_count: int) -> None:
        text = (
            f"⏰ *HẾT {self.config.snooze_minutes} PHÚT LÙI GIỜ!*\n"
            f"Phiên `{session_type}` đang chờ bạn hoàn thành. (Lần lùi: {snooze_count}/{self.config.max_snoozes})"
        )
        await self.bot.send_message(
            self.config.allowed_chat_id,
            text,
            reply_markup=make_inline_action_keyboard(session_id),
        )


def build_application(config: Any, storage: Any, coach: Any, scheduler: Any) -> BotApplication:
    """Factory function conforming to PROJECT.md interface contract."""
    return BotApplication(config=config, storage=storage, coach=coach, scheduler=scheduler)
```

---

## 5. Potential Hazards & Edge Cases

1. **Storage Format Asymmetry for `awaiting_reason`**:
   - `test_storage.py` sets `data["awaiting_reason"] = session_id` (a plain string).
   - `test_e2e_tier1_features.py` asserts `data["awaiting_reason"]["session_id"] == "..."` (a dictionary).
   - **Resolution**: `_handle_text` must inspect `isinstance(awaiting, dict)` vs `isinstance(awaiting, str)` to support both formats.
2. **Snooze Count Preservation upon Rejection**:
   - When snooze attempt 3 or 4 is rejected, `test_t2_snooze_limit_hard_boundary` verifies `assert s3["snooze_count"] == 2`.
   - **Resolution**: Do NOT call `storage.record_snooze(session_id, new_count)` when `new_count > config.max_snoozes`.
3. **Double Click Idempotency on Done**:
   - `test_t2_duplicate_rapid_clicks_idempotency` clicks Done 5 times in rapid succession.
   - **Resolution**: Handled in `storage.record_completion` by checking `existing_session.get("status") == SessionStatus.COMPLETED`.
4. **Markdown Formatting Errors with Special Characters**:
   - Vietnamese diacritics and user justifications containing `*`, `_`, `` ` `` could break Telegram's Markdown parser if not carefully handled.
   - **Resolution**: Ensure fallbacks and response formatting remain safe and do not choke on unescaped symbols.

---

## 6. Recommendations for Implementation Workers

1. Create `src/bot.py` implementing `BotApplication`, `make_inline_action_keyboard`, and `build_application`.
2. Ensure `tests/mock_services.py` line 700 resolves to `from src.bot import build_application`.
3. In `src/main.py`, wire together `load_config()`, `AtomicJsonStore()`, `AICoachService()`, `SchedulerService()`, and `build_application()`.
4. Run `pytest` across all existing E2E tiers (`test_e2e_tier1_features.py`, `tier2_boundaries.py`, `tier3_pairwise.py`, `tier4_scenarios.py`) to confirm zero regressions.
