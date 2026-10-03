# Milestone 2 Quality & Adversarial Review Analysis: AICoachService

**Reviewer**: Milestone 2 Reviewer 1 (`reviewer_m2_1`)  
**Target**: `src/coach.py` & `tests/test_coach.py`  
**Reference Contracts**: `PROJECT.md:136-146` (`AICoachService`), `ORIGINAL_REQUEST.md:47-52` (R4), `worker_m2_1/handoff.md`  
**Verdict**: **APPROVE**  

---

## 1. Executive Summary

Milestone 2 implementation delivers `AICoachService` in `src/coach.py` and a comprehensive 32-test unit test suite in `tests/test_coach.py`. The implementation fulfills all specifications for R4 (Two-Way AI Accountability Coach), including asynchronous GenAI SDK integration (`google-genai` 2.28.0), Vietnamese IT/Game Dev coaching persona, sliding context history with leading model eviction, excuse vs. legitimate obstacle evaluation with domain-specific 2-minute micro-habits, and zero-network offline fallbacks.

All 32 tests in `tests/test_coach.py` pass cleanly in 0.73s, and all 109 tests across Milestone 1 & 2 (`test_config.py`, `test_storage.py`, `test_coach.py`) pass cleanly in 2.48s with zero network access required. No integrity violations or bypasses were detected.

---

## 2. Integrity Verification

The implementation and test suite were scrutinized against integrity violation criteria:
- **Hardcoded Test Assertions / Outputs in Source**: NONE. The implementation uses dynamic template substitution, prompt assembly, and client API dispatch. Fallbacks are sourced from configuration or defaults.
- **Dummy / Facade Implementation**: NONE. Real Google GenAI SDK constructs (`genai.Client`, `types.Content`, `types.Part.from_text`, `types.GenerateContentConfig`, `types.HttpOptions`) and real async calls (`client.aio.models.generate_content`) are used.
- **Bypassed Core Logic**: NONE. The sliding context deque, regex parser, rule-based offline classifier, and history sanitizer are fully implemented.
- **Fabricated Outputs or Attestation**: NONE. Independent execution of pytest confirmed 32/32 and 109/109 passes directly on the host environment.
- **Self-Certifying Work**: NONE. Verification was conducted independently by inspecting source code and running test suites.

---

## 3. Quality Review

### 3.1 Interface Contract Conformance (`PROJECT.md:136-146`)
- `AICoachService.__init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None)`: Matches contract. Supports dependency injection via `client` parameter for 100% offline unit and integration testing.
- `async get_congratulation(self, session_type: str, streak: int) -> str`: Matches contract. Asynchronous, formats prompt with streak and session name, dispatches to Gemini or falls back gracefully.
- `async evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]`: Matches contract. Returns strict `(classification: 'EXCUSE' | 'LEGITIMATE', response_text: str)`.
- `async chat(self, user_message: str) -> str`: Matches contract. Non-blocking async multi-turn chat maintaining sliding history.
- `clear_context(self) -> None`: Matches contract. Resets sliding deque.

### 3.2 Asynchronous Correctness
- All I/O operations strictly invoke `await self.client.aio.models.generate_content(...)`.
- Calls are wrapped in `asyncio.wait_for(..., timeout=15.0)` and configured with `http_options=types.HttpOptions(timeout=15000)` to eliminate risk of hanging event loops on network stalls.
- No synchronous blocking calls (e.g., `requests.get`, `time.sleep`) are present.

### 3.3 Sliding Context Window & Multi-Turn Turn Invariants
- In-memory rolling buffer uses `collections.deque(maxlen=self.history_limit)`.
- **Gemini Invariant**: The Gemini multi-turn API rejects conversation payloads where the first message has `role='model'`. When `deque(maxlen=10)` evicts Turn 0's user message on Turn 5's addition, `src/coach.py` actively pops any leading model messages (`while self._history and self._history[0].role == 'model': self._history.popleft()`).
- Additionally, `_get_sanitized_history_contents()` creates a sanitized copy starting strictly with `role='user'` before sending payloads to Gemini.
- Event-driven calls (`get_congratulation`, `evaluate_skip_reason`) do not pollute `_history`, preserving chat continuity.
- Error/fallback responses in `chat()` are recorded as `role='model'` in `_history`, ensuring the alternating turn sequence `(user, model, user, model)` is maintained even during network outages.

### 3.4 Findings & Observations

#### [Minor] Finding 1: Defensive handling for None session_type
- **Where**: `src/coach.py:244`, `src/coach.py:290`
- **What**: `s_name = session_name_map.get(session_type.lower(), session_type)`
- **Why**: If a caller passes `session_type=None`, `session_type.lower()` will raise `AttributeError`. Although callers in scheduler and bot pass string literals, defensive handling `st = (session_type or "").lower()` (as used in `get_micro_habit_for_session`) is more resilient.
- **Risk**: Low (internal callers pass string literals `"gym"`, `"toeic"`, `"major"`).
- **Suggestion**: Consider `(session_type or "").lower()` in future refactor.

#### [Minor] Finding 2: Concurrency guard for rapid consecutive chat messages
- **Where**: `src/coach.py:343-398`
- **What**: `AICoachService.chat()` does not acquire an `asyncio.Lock` during the `append(user) -> await generate_content -> append(model)` cycle.
- **Why**: If two incoming chat updates are awaited concurrently, user messages could be appended in succession before model responses arrive.
- **Risk**: Low (Telegram updates for a single user are typically sequential).
- **Suggestion**: If multi-user or rapid burst updates occur, guard `chat()` with an `asyncio.Lock()`.

---

## 4. Adversarial Review & Stress Testing

### 4.1 Stress Test Dimensions

1. **Assumption: Gemini API responses always follow bracket format `[EXCUSE]` / `[LEGITIMATE]`**
   - *Attack Scenario*: Gemini outputs varying formats (e.g. `CLASSIFICATION: LEGITIMATE`, lower-case `[excuse]`, or free-form text containing the word "EXCUSE").
   - *Tested*: Handled by `parse_skip_evaluation` using a 3-tier cascade: (1) Bracket regex, (2) Line prefix regex, (3) Word presence check, defaulting safely to `EXCUSE`.
   - *Result*: **PASS**.

2. **Assumption: Network disconnects or API rate limits (429) do not crash the bot**
   - *Attack Scenario*: Gemini returns 429 Resource Exhausted, 500 Internal Error, or connection drops.
   - *Tested*: `test_fallback_on_api_timeout`, `test_fallback_on_rate_limit_429`, `test_fallback_on_server_error_500`, `test_fallback_on_connection_error`.
   - *Result*: **PASS**. Exception caught, warning logged, fallback returned.

3. **Assumption: Offline rule-based classifier handles Vietnamese diacritics and slang**
   - *Attack Scenario*: User enters excuses in Vietnamese with varying casing and keywords ("lười quá", "buồn ngủ mai học bù", "đang chơi game dota").
   - *Tested*: `classify_skip_reason_offline` matches keywords across 20+ excuse and 20+ emergency terms, returning tailored 2-minute micro-habits.
   - *Result*: **PASS**.

4. **Assumption: History deque eviction does not violate Gemini payload schema**
   - *Attack Scenario*: 14 consecutive chat messages pushed to a 10-message deque.
   - *Tested*: `test_chat_request_payload_always_starts_with_user` and `test_chat_history_trimmed_at_maxlen_10`.
   - *Result*: **PASS**. Leading model messages are evicted; payload always starts with `role='user'`.

---

## 5. Verification Commands and Output

1. **Unit Test Suite**:
   ```powershell
   python -m pytest tests/test_coach.py -v
   ```
   *Result*: `32 passed, 1 warning in 0.73s`

2. **Regression / Joint Suite**:
   ```powershell
   python -m pytest tests/test_config.py tests/test_storage.py tests/test_coach.py -v
   ```
   *Result*: `109 passed, 1 warning in 2.48s`

---

## 6. Review Summary & Recommendation

- Quality: Excellent
- Test Coverage: 32 unit tests covering all paths, boundaries, and fallbacks
- Contract Compliance: 100%
- Integrity Violations: None
- Recommendation: **APPROVE**. Milestone 2 is ready to be marked complete.
