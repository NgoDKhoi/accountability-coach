# Handoff Report: Milestone 2 Reviewer 1 (Quality & Adversarial Review)

**Target**: Milestone 2 Review (`src/coach.py` & `tests/test_coach.py`)  
**Sender**: Milestone 2 Reviewer 1 (`reviewer_m2_1`)  
**Recipient**: Orchestrator (`ac41226a-6cc6-45bc-9027-605104e502f4`)  
**Profile**: reviewer / critic  
**Status**: Hard Handoff (Review Complete)  
**Verdict**: **APPROVE**  

---

## 1. Observation

1. **Target Files**:
   - `src/coach.py` (403 lines): Implements `AICoachService`, `SESSION_MICRO_HABIT_MAP`, `LEGITIMATE_KEYWORDS`, `EXCUSE_KEYWORDS`, `get_micro_habit_for_session`, `parse_skip_evaluation`, and `classify_skip_reason_offline`.
   - `tests/test_coach.py` (403 lines): Implements 32 offline unit tests across 7 test classes using dependency-injected mock GenAI clients (`AsyncMock` on `client.aio.models.generate_content`).

2. **Interface Contract Verification**:
   - `PROJECT.md:136-146` specifies:
     ```python
     class AICoachService:
         def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None): ...
         async def get_congratulation(self, session_type: str, streak: int) -> str: ...
         async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]: ...
         # returns: (classification: 'EXCUSE' | 'LEGITIMATE', response_text: str)
         async def chat(self, user_message: str) -> str: ...
         def clear_context(self) -> None: ...
     ```
   - In `src/coach.py`:
     - Line 138-164: `def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[Union[Dict[str, Any], Any]] = None, client: Optional[Any] = None)`
     - Line 237-279: `async def get_congratulation(self, session_type: str, streak: int) -> str`
     - Line 280-342: `async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]`
     - Line 343-399: `async def chat(self, user_message: str) -> str`
     - Line 400-403: `def clear_context(self) -> None`
     - Line 216-224: `@property def context_window(self) -> List[Tuple[str, str]]`

3. **Asynchronous Non-Blocking Execution**:
   - `src/coach.py:264-270`, `src/coach.py:327-333`, `src/coach.py:375-381`:
     All API invocations strictly use `await asyncio.wait_for(self.client.aio.models.generate_content(...), timeout=15.0)`. No blocking calls (`time.sleep` or synchronous SDK methods) are present.

4. **Sliding Window & History Invariant Handling**:
   - `src/coach.py:158`: `self._history: deque[types.Content] = deque(maxlen=self.history_limit)`
   - `src/coach.py:357-358`, `src/coach.py:395-396`: When deque FIFO evicts the oldest user message, `src/coach.py` immediately pops any leading model messages (`while self._history and self._history[0].role == "model": self._history.popleft()`).
   - `src/coach.py:226-235`: `_get_sanitized_history_contents()` ensures request payloads to Gemini strictly begin with `role="user"`.

5. **Test Suite Execution**:
   - Command: `python -m pytest tests/test_coach.py -v`
     Output: `32 passed, 1 warning in 0.73s`
   - Command: `python -m pytest tests/test_config.py tests/test_storage.py tests/test_coach.py -v`
     Output: `109 passed, 1 warning in 2.48s`
   - The warning is:
     `DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17` in `google/genai/types.py:42`, originating from upstream Google SDK under Python 3.14.

6. **Integrity Check**:
   - No hardcoded test responses or facade methods found in `src/coach.py`.
   - All tests in `tests/test_coach.py` perform real assertions on mock call arguments, returned types, and parsed outputs.

---

## 2. Logic Chain

1. From Observation 2, `src/coach.py` strictly adheres to the method signatures and type contracts mandated by `PROJECT.md:136-146`, including the `context_window` property required by downstream boundary suites.
2. From Observation 3, asynchronous safety is ensured through `client.aio.models.generate_content` wrapped in `asyncio.wait_for` with dual 15-second timeouts at both asyncio and HTTP option levels, ensuring the bot event loop never hangs.
3. From Observation 4, the sliding context window prevents HTTP 400 errors with the Gemini API caused by leading model messages after FIFO eviction, and maintains the alternating `(user, model)` invariant across online and offline turns.
4. From Observation 5, all 32 unit tests pass in under 1 second, and the joint test suite of 109 tests across M1 and M2 passes with 100% success rate without requiring internet access.
5. From Observation 6, no integrity violations, facade implementations, or bypass shortcuts exist.
6. Therefore, the implementation in Milestone 2 is verified, sound, and ready for integration into Milestone 3 (Scheduler) and Milestone 4 (Bot Core).

---

## 3. Caveats

1. **Python 3.14 SDK Deprecation Warning**: Upstream warning in `google.genai.types` line 42 regarding `_UnionGenericAlias`. It has zero impact on functionality.
2. **Defensive None Check in `session_type`**: `get_congratulation` and `evaluate_skip_reason` assume `session_type` is a string and call `.lower()`. Callers in current architecture always supply valid string names (`"gym"`, `"toeic"`, `"major"`).
3. **Serial Chat Assumption**: `AICoachService.chat()` does not use an `asyncio.Lock`. This is safe for single-user Telegram polling where messages from `ALLOWED_CHAT_ID` arrive serially.

---

## 4. Conclusion

**Verdict: APPROVE**

- `src/coach.py` cleanly implements `AICoachService` meeting all functional and non-functional requirements.
- `tests/test_coach.py` provides 100% offline, robust test coverage with 32 passing tests.
- Full backwards compatibility with Milestone 1 (`test_config.py`, `test_storage.py`) is verified.
- Milestone 2 satisfies all acceptance criteria.

---

## 5. Verification Method

To independently verify this assessment:

1. **Run Coach Unit Tests**:
   ```powershell
   python -m pytest tests/test_coach.py -v
   ```
   *Expected result*: 32 passed, 1 warning in <1.5s.

2. **Run Joint Milestone 1 & 2 Test Suite**:
   ```powershell
   python -m pytest tests/test_config.py tests/test_storage.py tests/test_coach.py -v
   ```
   *Expected result*: 109 passed, 1 warning in <3.0s.

3. **Invalidation Conditions**:
   - Any test failure in `tests/test_coach.py`.
   - `evaluate_skip_reason` returning any tuple whose first element is not `'EXCUSE'` or `'LEGITIMATE'`.
   - Memory leak or history deque growth beyond `history_limit`.
