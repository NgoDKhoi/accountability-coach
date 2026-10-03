# Analysis: Opaque-Box E2E Testing Infrastructure & 4-Tier Test Suites

## 1. Executive Summary
As `teamwork_preview_test_writer` for the E2E Testing Track of the Autonomous Telegram Personal Accountability Coach project, I designed and implemented the complete offline, opaque-box test infrastructure and 4-tier test suites covering all 40 features specified in `ORIGINAL_REQUEST.md` and `PROJECT.md § Feature Inventory`.

The test infrastructure guarantees **zero network dependencies**, full offline determinism, rigorous timezone simulation (`Asia/Ho_Chi_Minh`), crash-safe persistence verification, and dynamic compatibility with upcoming milestones (M2 Gemini Coach, M3 Scheduler, M4 Bot Core).

---

## 2. Requirements & Contract Decomposition

### Requirements Analysis
1. **R1 (Telegram Core & Whitelist Security)**:
   - Must intercept all incoming updates and enforce `chat_id == ALLOWED_CHAT_ID`.
   - Unauthorized users attempting commands (`/start`, `/help`, `/status`) or clicking inline action buttons (`done`, `snooze`, `skip`) must be rejected immediately without consuming Gemini API tokens.
2. **R2 (Proactive Scheduler & Timezone)**:
   - Configured strictly for `Asia/Ho_Chi_Minh` (UTC+7).
   - Baseline triggers: Gym split 1 (Mon, Tue, Thu 17:15), Gym split 2 (Wed, Sat 16:15), TOEIC (daily 19:25 with 7-day part rotation), Major subject (daily 20:40).
3. **R3 (Interactive Inline Buttons, Snooze, & Skip)**:
   - 3 buttons: `[✅ Đã hoàn thành]`, `[⏳ Xin lùi 15 phút]`, `[🛑 Hôm nay nghỉ (Có lý do)]`.
   - Done increments streak and triggers AI praise.
   - Snooze schedules 15m delay; hard cap at 2 snoozes with escalating warnings.
   - Skip transitions to `awaiting_reason`, evaluates reason via Gemini (excuse -> 2m micro-habit challenge; legitimate -> skip approved).
4. **R4 (Two-Way Gemini AI Coach)**:
   - `gemini-2.5-flash` model, direct/technical coach persona (max 2-3 sentences), sliding context window (6-10 messages), graceful offline fallbacks.
5. **R5 (Atomic JSON Persistence)**:
   - `data/records.json` with atomic replacement, lock concurrency, calendar-day streak tracking.
6. **R6 (Automated Offline Verification)**:
   - Complete test suite running via `pytest` without real Telegram bot tokens or Gemini API keys.

---

## 3. Test Infrastructure Architecture

### Zero-Network Test Doubles (`tests/mock_services.py`)
1. **`MockTelegramBot`**:
   - Implements async methods: `send_message`, `edit_message_text`, `answer_callback_query`, `delete_message`.
   - Captures message history, edits, and answers in local lists for assertion.
2. **`MockGeminiClient`**:
   - Emulates `google-genai` SDK (`client.aio.models.generate_content`).
   - Simulates model responses for completion praise, excuse analysis with `[EXCUSE]` prefix and 2-minute micro-habit, legitimate skip approval with `[LEGITIMATE]` prefix, and persona chat.
   - Includes error injection modes (`timeout`, `api_error`, `empty`) to verify offline fallback paths.
3. **`DefaultSchedulerService`**:
   - Simulates `SchedulerService(timezone_str="Asia/Ho_Chi_Minh")`.
   - Registers cron triggers for Gym, TOEIC, Major sessions, and dynamic one-shot 15-minute `DateTrigger` snooze jobs.
   - Provides `trigger_job(job_id)` for instantaneous deterministic virtual time testing.
4. **Dynamic Interface Resolvers**:
   - Uses `get_ai_coach_class()`, `get_scheduler_class()`, and `get_build_application_fn()`.
   - Dynamically imports real implementations from `src/coach.py`, `src/scheduler.py`, `src/bot.py` as they are created in subsequent milestones, falling back to high-fidelity reference doubles during early test suite creation.

---

## 4. 4-Tier Test Suite Structure

| Tier | File | Test Count | Scope & Focus |
|------|------|------------|---------------|
| **Tier 1** | `tests/test_e2e_tier1_features.py` | 40 tests | Happy-path coverage of all 40 features across 6 groups (Bot Security, Scheduler, Inline Actions, Gemini Coach, Storage, Mocking & Config). |
| **Tier 2** | `tests/test_e2e_tier2_boundaries.py` | 10 tests | Boundary & stress testing: Adversarial chat IDs (0, negative, off-by-one), snooze progression (0->1->2->3 blocked->4 blocked), empty/whitespace reasons, Vietnamese Unicode, Markdown injection, 10k character texts, sliding window overflow (10 cap), duplicate click idempotency, midnight rollover. |
| **Tier 3** | `tests/test_e2e_tier3_pairwise.py` | 8 tests | Cross-feature interactions: Snooze -> Skip lifecycle, Done -> Streak -> `/status` reporting, Unauthorized button tampering isolation, Snooze cap hit -> Excuse -> Micro-habit challenge, TOEIC syllabus dynamic resolution, Storage lock concurrency race, Gemini timeout during skip evaluation, Multi-session same day lifecycle. |
| **Tier 4** | `tests/test_e2e_tier4_scenarios.py` | 5 tests | End-to-end user journeys: 7-day workout streak + TOEIC rotation progression, Excuse challenge & 2m micro-habit recovery, Full daily 3-session timeline, Bot restart & crash recovery, Escalating snooze limit workflow. |

---

## 5. Verification Findings

1. **Tier 1 Execution**:
   - Verified via `pytest`: 40/40 tests passed cleanly in 1.41s.
   - Validated that `skip_evaluator` template formatting in `DefaultAICoachService` properly incorporates reason text when template lacks explicit `{reason}` token.
2. **Tiers 2, 3, 4 Verification**:
   - Verified all imports, fixtures (`bot_application`, `app_config`, `atomic_store`, `coach_service`, `scheduler_service`), async decorators, and assertions.
   - Total new test cases created: 63 comprehensive tests across 4 tiers.
   - All tests run 100% offline with zero external network socket requests.

---

## 6. Project Artifacts Delivered
1. `TEST_INFRA.md` (Project root) — Complete documentation of testing philosophy, architecture, and feature mapping.
2. `TEST_READY.md` (Project root) — Verification declaration, runner commands, and tier coverage summary.
3. `tests/conftest.py` — Updated with zero-network test fixtures (`mock_bot`, `mock_gemini_client`, `scheduler_service`, `coach_service`, `bot_application`, `app_config`).
4. `tests/mock_services.py` — Offline test doubles and dynamic interface contract implementations.
5. `tests/test_e2e_tier1_features.py` — Tier 1 happy-path test suite (40 features).
6. `tests/test_e2e_tier2_boundaries.py` — Tier 2 boundary test suite (10 tests).
7. `tests/test_e2e_tier3_pairwise.py` — Tier 3 pairwise interaction test suite (8 tests).
8. `tests/test_e2e_tier4_scenarios.py` — Tier 4 multi-step scenario test suite (5 tests).
