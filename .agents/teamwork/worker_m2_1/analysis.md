# Analysis: Milestone 2 Implementation of AICoachService and Test Suite

**Author**: `teamwork_preview_worker` (Milestone 2)  
**Target Code**: `src/coach.py`, `tests/test_coach.py`  
**Working Directory**: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m2_1/`  
**Date**: 2026-10-03  

---

## 1. Executive Summary & Objective

This document analyzes the requirements, architecture, interface contracts, and implementation plan for Milestone 2:
- Implementing `AICoachService` in `src/coach.py` complying with `PROJECT.md:136-146`, `ORIGINAL_REQUEST.md:43-52`, and explorer blueprints (`explorer_m2_1`, `explorer_m2_2`, `explorer_m2_3`).
- Implementing the 32 unit test suite in `tests/test_coach.py` verifying full offline functionality, zero-network mock dependency injection, sliding context window pruning, micro-habit routing, and resilient fallbacks.
- Ensuring zero regressions against existing tests (`test_config.py`, `test_storage.py`, `test_e2e_tier1_features.py`).

---

## 2. Evidence Chain & Observations

1. **Google GenAI SDK Integration**:
   - `google-genai` version 2.28.0 is installed in Python 3.14.4.
   - Entry point: `from google import genai` and `from google.genai import types, errors`.
   - Asynchronous generation method: `await client.aio.models.generate_content(...)`.
   - Timeout parameter is in milliseconds: `types.HttpOptions(timeout=15000)`.
   - Coroutine timeout wrapping with `asyncio.wait_for(..., timeout=15.0)` guarantees event loop safety against socket hangs.

2. **Interface Contract (`PROJECT.md:136-146`)**:
   ```python
   class AICoachService:
       def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None): ...
       async def get_congratulation(self, session_type: str, streak: int) -> str: ...
       async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]: ...
       async def chat(self, user_message: str) -> str: ...
       def clear_context(self) -> None: ...
   ```
   - `evaluate_skip_reason` strictly returns `(classification: 'EXCUSE' | 'LEGITIMATE', response_text: str)`.
   - `get_ai_coach_class()` in `tests/mock_services.py` attempts dynamic import of `src.coach.AICoachService`. Once `src/coach.py` is created, E2E tests will run against this implementation.

3. **Sliding Context Window & Gemini Multi-Turn Invariant**:
   - In-memory buffer: `collections.deque(maxlen=self.history_limit)` where default limit is 10.
   - Buffer stores `types.Content` objects (`role="user"` and `role="model"`).
   - Invariant: Gemini API mandates multi-turn payloads must start with `role="user"`.
   - When `maxlen=10` evicts Turn 0's user message upon Turn 5's new message, the head of the deque becomes a model message.
   - Solution: Prune leading model messages whenever deque eviction occurs and before dispatching payloads via `_get_sanitized_history_contents()`.
   - Compatibility: Provide `@property def context_window(self)` returning `self._history` so existing tests checking `len(coach_service.context_window) <= 10` succeed.

4. **Micro-Habit Routing Engine**:
   - `gym`: 5 pushups or 60s plank (`"5 cái chống đẩy hoặc plank 60s tại chỗ"`).
   - `toeic`: 3 Part 5 questions or 1 Part 3 conversation (`"giải đúng 3 câu Part 5 hoặc nghe 1 đoạn Part 3"`).
   - `major`: open IDE, write 1 function, git commit (`"mở IDE viết đúng 1 function và commit git"`).

5. **Offline Fallback Engine**:
   - `classify_skip_reason_offline`: Rule-based keyword matching for medical emergencies and unforeseen events vs excuses.
   - Fallback responses pulled from `self.fallbacks` (`offline_praise`, `offline_coach`, `offline_error`, `offline_skip_excuse`, `offline_skip_legitimate`).

---

## 3. Concrete Implementation Plan

### Step 1: Implement `src/coach.py`
1. Define constants: `SESSION_MICRO_HABIT_MAP`, `LEGITIMATE_KEYWORDS`, `EXCUSE_KEYWORDS`.
2. Implement helper functions:
   - `get_micro_habit_for_session(session_type: str) -> str`
   - `parse_skip_evaluation(raw_text: str, default_classification: str = "EXCUSE") -> Tuple[str, str]`
   - `classify_skip_reason_offline(session_type: str, reason: str, fallbacks: Optional[Dict[str, str]] = None) -> Tuple[str, str]`
3. Implement `AICoachService`:
   - `__init__`: Extract config (dict or AppConfig), set model parameters (`temperature=0.7`, `max_output_tokens=256`), initialize `self._history`, inject or create GenAI client.
   - `context_window` property: Returns `self._history` for test compatibility.
   - `_get_sanitized_history_contents()`: Returns copy of history ensuring head has `role="user"`.
   - `get_congratulation(session_type: str, streak: int) -> str`: Formats completion praise prompt, calls Gemini API asynchronously, returns response or `offline_praise`.
   - `evaluate_skip_reason(session_type: str, reason: str) -> Tuple[str, str]`: Formats skip prompt with micro-habit, calls Gemini, parses tag with `parse_skip_evaluation`, falls back to `classify_skip_reason_offline` on error.
   - `chat(user_message: str) -> str`: Manages sliding history, calls Gemini asynchronously with multi-turn contents, appends response to history, falls back to `offline_coach` on error.
   - `clear_context() -> None`: Empties `self._history`.

### Step 2: Implement `tests/test_coach.py` (32 Unit Tests)
1. Setup test fixtures: `mock_genai_response_factory`, `mock_genai_client`, `coach_service`.
2. Implement 7 test classes:
   - `TestAICoachInitAndConfig` (4 tests)
   - `TestCongratulationGeneration` (5 tests)
   - `TestExcuseEvaluation` (7 tests)
   - `TestSlidingConversationHistory` (6 tests)
   - `TestContextReset` (3 tests)
   - `TestOfflineFallbacksAndExceptions` (5 tests)
   - `TestPromptConstructionAndSafeguards` (2 tests)
   Total: 32 tests.

### Step 3: Run Full Test Suite & Verification
1. Run `python -m pytest tests/test_coach.py -v`.
2. Run `python -m pytest tests/test_config.py tests/test_storage.py tests/test_coach.py -v`.
3. Run `python -m pytest tests/test_e2e_tier1_features.py -v`.

### Step 4: Documentation & Delivery
1. Update `BRIEFING.md` and `progress.md`.
2. Write comprehensive `handoff.md` following the 5-component protocol.
3. Send coordination message to orchestrator via `send_message`.
