# Milestone 4 Handoff Report: Telegram Bot Core & Security Whitelist Architecture

**Agent**: `explorer_m4_1`  
**Target Milestone**: Milestone 4 (Telegram Bot Core & Security Whitelist)  
**Date**: 2026-10-04  
**Working Directory**: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m4_1/`  

---

## 1. Observation

1. **Missing Component**:
   Inspection of `src/` confirmed that `src/coach.py`, `src/config.py`, `src/scheduler.py`, and `src/storage.py` exist, but `src/bot.py` and `src/main.py` are not yet implemented.

2. **Interface Contract in `PROJECT.md`**:
   `PROJECT.md` (lines 162–168) states:
   ```python
   ### `src/bot.py`
   from telegram.ext import Application
   from typing import Any

   def build_application(config: Any, storage: Any, coach: Any, scheduler: Any) -> Application: ...
   ```

3. **Subsystem Exposure Assertion**:
   `tests/test_e2e_tier1_features.py` (lines 56–65, `test_f03_bot_lifecycle_boot`) strictly asserts:
   ```python
   assert bot_application is not None
   assert bot_application.config.allowed_chat_id == app_config.allowed_chat_id
   assert bot_application.storage is atomic_store
   assert bot_application.coach is not None
   assert bot_application.scheduler is not None
   ```

4. **Dynamic Module Resolution in `tests/mock_services.py`**:
   Lines 700–706 in `tests/mock_services.py` define:
   ```python
   def get_build_application_fn() -> Any:
       try:
           from src.bot import build_application
           return build_application
       except ImportError:
           def _build_app(config: Any, storage: Any, coach: Any, scheduler: Any) -> DefaultBotApplication:
               return DefaultBotApplication(config, storage, coach, scheduler)
           return _build_app
   ```
   When `src/bot.py` exists with `build_application`, all tests across Tiers 1–4 immediately import and use it.

5. **Test Harness Interaction via `process_update`**:
   In `tests/test_e2e_tier1_features.py` (e.g. line 38, line 51, line 72, line 96) and across Tiers 2–4:
   ```python
   update = make_text_update(chat_id=app_config.allowed_chat_id, text="/start")
   resp = await bot_application.process_update(update)
   assert resp is not None
   assert "Chào mừng" in resp["text"] or "Kỷ Luật" in resp["text"]
   ```
   `process_update` is awaited directly with `MockUpdate` and must return the response dictionary created by `bot.send_message`, `bot.edit_message_text`, or `query.answer`.

6. **Bot Property Assignment in `tests/conftest.py`**:
   Lines 252–254 in `tests/conftest.py` state:
   ```python
   if hasattr(app, "bot"):
       app.bot = mock_bot
   ```
   In PTB v20+, `Application.bot` is a read-only property without a setter. Subclassing `Application` requires an explicit `@bot.setter` to prevent `AttributeError`.

7. **Whitelist Rejection Assertions**:
   `tests/test_e2e_tier1_features.py` (lines 53, 509) and `test_e2e_tier2_boundaries.py` (line 43) check:
   `assert "từ chối" in resp["text"] or "Access denied" in resp["text"] or "ủy quyền" in resp["text"]`
   For callback queries (`test_t2_unauthorized_user_inline_callback_rejection`, line 210), unauthorized queries are answered with alert and reject modifying session storage (`status is None`).

8. **Command Handler Assertions**:
   - `/start` (`test_f04`, line 74–75): must contain `"/status"` and `"/help"`.
   - `/help` (`test_f05`, line 85–87): must contain `"Đã hoàn thành"`, `"Xin lùi 15 phút"`, `"Hôm nay nghỉ"`.
   - `/status` (`test_f06`, line 98–99): must contain `"BÁO CÁO KỶ LUẬT"` or `"streak"`, plus current streak count.

---

## 2. Logic Chain

1. **Subsystem Binding** (derived from Observation 2, 3):
   `build_application` must accept `(config, storage, coach, scheduler)` and set them as instance attributes (`app.config`, `app.storage`, `app.coach`, `app.scheduler`).

2. **Extending `telegram.ext.Application`** (derived from Observation 2, 6):
   To conform to `PROJECT.md` typing while supporting the mock bot injection from `conftest.py`, `BotApplication` must subclass `Application` and implement `@property def bot(self)` and `@bot.setter def bot(self, value)`.

3. **Universal `process_update()` Dispatcher** (derived from Observation 5):
   Standard PTB `Application.process_update()` returns `None`. However, all 40+ E2E test cases assert `resp = await bot_application.process_update(update)` where `resp["text"]` is inspected. Therefore, `BotApplication.process_update()` must intercept incoming updates, run the whitelist gate and command/callback/text routers, and return the resulting response dictionary.

4. **Whitelist Security Perimeter** (derived from Observation 7):
   Incoming updates must check `int(update.effective_chat.id) == int(self.config.allowed_chat_id)` prior to executing any command or calling Gemini. Unauthorized text updates receive `"⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền."` and unauthorized callback queries receive alert `"⛔ Truy cập bị từ chối!"`. No state or AI quota is consumed.

5. **Command Output Exactness** (derived from Observation 8):
   `/start`, `/help`, and `/status` handlers must include the exact Vietnamese phrases required by `test_f04`, `test_f05`, and `test_f06`. `/status` must call `storage.get_streak()` and use `streak_data.get_effective_streak(today_str)` to accurately report consecutive days.

---

## 3. Caveats

1. **Dual Runtime vs Pure Live Polling**:
   In live production polling (`python src/main.py`), Telegram delivers `telegram.Update` instances via HTTP long polling. In test environments, `tests/mock_services.py` delivers `MockUpdate` instances. The universal `process_update()` design handles both transparently.
2. **Gemini SDK Offline Fallbacks**:
   When network is unavailable, `coach.chat()`, `coach.get_congratulation()`, and `coach.evaluate_skip_reason()` must fall back gracefully to configured fallback strings as verified in Milestone 2.
3. **Division of Responsibility**:
   Inline action state machine details (`done`, `snooze` scheduling, `skip` justification) are being analyzed in parallel by `explorer_m4_2`, while `src/main.py` and `tests/test_bot.py` are analyzed by `explorer_m4_3`. The code blueprint in `analysis.md` provides complete cross-compatible coverage.

---

## 4. Conclusion

Milestone 4's Telegram Bot Core and Whitelist Security architecture is fully mapped:
1. `src/bot.py` should implement `BotApplication(Application)` and `build_application(config, storage, coach, scheduler) -> BotApplication`.
2. The whitelist gate in `process_update()` guarantees 100% rejection of unauthorized chat IDs (including negative, zero, and off-by-one IDs) with zero side effects.
3. `/start`, `/help`, and `/status` command handlers are fully specified with required keyword assertions and streak retrieval mechanics.
4. A complete reference implementation is documented in `analysis.md`.

---

## 5. Verification Method

To verify the Milestone 4 Telegram Bot Core implementation:
1. **Run Tier 1 Bot Security & Command tests**:
   ```powershell
   pytest tests/test_e2e_tier1_features.py -k "TestGroup1BotSecurityAndCommands or test_f36" -v
   ```
   *Expected*: All tests pass (F01, F03, F04, F05, F06, F36).
2. **Run Tier 2 Boundary Whitelist tests**:
   ```powershell
   pytest tests/test_e2e_tier2_boundaries.py -k "test_t2_whitelist" -v
   ```
   *Expected*: Adversarial chat IDs strictly rejected.
3. **Run Tier 3 Pairwise Security tests**:
   ```powershell
   pytest tests/test_e2e_tier3_pairwise.py -k "test_t3_p3" -v
   ```
   *Expected*: Unauthorized button tampering leaves storage intact.
4. **Inspect code artifacts**:
   Inspect `src/bot.py` to ensure `build_application` exposes `config`, `storage`, `coach`, and `scheduler`, and `@bot.setter` exists.
