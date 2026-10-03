# Dispatch: E2E Testing Track — Test Suite Creation

## Task Assignment
- Role: `teamwork_preview_test_writer`
- Working Directory: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/test_writer_e2e_1/`
- Mission: Design and implement the opaque-box E2E test infrastructure and test suites covering all 40 features from `PROJECT.md § Feature Inventory` and `ORIGINAL_REQUEST.md`.

## Required Reading
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md` (authoritative user requirements)
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md` (architecture, 40 features, interface contracts)

## Key Responsibilities
1. Create `TEST_INFRA.md` at project root following the Project Pattern template:
   - Test philosophy (opaque-box, requirement-driven, zero external network access)
   - Feature Inventory mapping across 4 Tiers
   - Test architecture and runner command (`python -m pytest tests/test_e2e_*.py -v`)
2. Implement robust offline test fixtures in `tests/conftest.py` (or shared test helpers):
   - Mock Telegram Bot API (`Bot`, `Update`, `Message`, `CallbackQuery`, `Application`)
   - Mock Gemini API (`google-genai` client, structured content generation)
   - Mock APScheduler / Timezone (`Asia/Ho_Chi_Minh`, fake time advancement)
3. Implement 4-tier opaque-box test suites:
   - `tests/test_e2e_tier1_features.py`: Happy-path feature coverage across all 40 features (>=5 per major feature group).
   - `tests/test_e2e_tier2_boundaries.py`: Boundary and corner cases (empty strings, Unicode, null chars, time boundaries, snooze limits).
   - `tests/test_e2e_tier3_pairwise.py`: Cross-feature interactions (e.g., snooze -> skip, done -> streak -> status command, unauthorized user -> snooze button).
   - `tests/test_e2e_tier4_scenarios.py`: Real-world end-to-end user workflows (e.g., 7-day workout streak + TOEIC rotation + excuse challenge + 2-minute micro-habit).
4. Verify tests run cleanly with zero network dependencies.
5. Create `TEST_READY.md` at project root with test command and coverage summary.
6. Deliver `analysis.md` and `handoff.md` in your working directory, then message the orchestrator.

## 2026-10-03T11:59:52Z
You are teamwork_preview_test_writer for the E2E Testing Track.
Your working directory: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/test_writer_e2e_1/
Please read:
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/test_writer_e2e_1/DISPATCH.md

Design and create the opaque-box test infrastructure and test suites:
1. Create TEST_INFRA.md at project root.
2. Build mock fixtures in tests/conftest.py for zero-network Telegram API, Gemini API, and APScheduler simulation.
3. Write test suites for Tiers 1-4: tests/test_e2e_tier1_features.py, tests/test_e2e_tier2_boundaries.py, tests/test_e2e_tier3_pairwise.py, tests/test_e2e_tier4_scenarios.py.
4. Verify tests pass offline, then create TEST_READY.md at project root.
Deliver analysis.md and handoff.md in your directory. When done, message the orchestrator.
