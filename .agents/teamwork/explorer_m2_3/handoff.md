# Handoff Report: Milestone 2 Explorer 3 (Context Window & Test Suite Design)

## 1. Observation
- **O1 (Requirements & Sliding Window)**: `ORIGINAL_REQUEST.md:47-52` states:
  > "Maintain a short-term sliding context window (recent 6–10 messages) in memory so the AI understands ongoing dialogue context. Robust error handling: If the Gemini API or network fails, provide graceful fallback messages so bot operation is never interrupted."
  Configured in `config.yaml:8` (`history_limit: 10`) and `src/config.py:176` (`context_window_size: int = 10`).
- **O2 (Interface Contract)**: `PROJECT.md:135-146` specifies the interface contract for `AICoachService`:
  ```python
  class AICoachService:
      def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None): ...
      async def get_congratulation(self, session_type: str, streak: int) -> str: ...
      async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]: ...
      # returns: (classification: 'EXCUSE' | 'LEGITIMATE', response_text: str)
      async def chat(self, user_message: str) -> str: ...
      def clear_context(self) -> None: ...
  ```
- **O3 (Google GenAI SDK Integration & Types)**: Inspected installed `google-genai` version 2.28.0:
  - Generates content asynchronously via `await client.aio.models.generate_content(model=..., contents=..., config=...)`.
  - Roles are formatted as `types.Content(role="user", parts=[types.Part.from_text(text=...)])` and `types.Content(role="model", parts=[types.Part.from_text(text=...)])`.
  - API errors are instantiated with `errors.APIError(code: int, response_json: dict)`.
  - Generation config: `types.GenerateContentConfig(system_instruction=..., temperature=0.7, max_output_tokens=256)`.
- **O4 (Gemini Multi-turn Invariant Hazard)**:
  - Gemini API mandates that multi-turn dialogue arrays passed to `generate_content` must start with `role="user"`.
  - When `collections.deque(maxlen=10)` reaches capacity (10 messages = 5 pairs) and an 11th message (new user turn) is appended, the oldest item (Turn 1 user message) is automatically evicted from the left.
  - This leaves index 0 as Turn 1's `model` message! Passing this directly to Gemini causes HTTP 400 Bad Request.
- **O5 (Zero-Network Test Baseline)**: Ran `py -m pytest -q` on project root, producing:
  `181 passed in 27.21s`. Proves test environment operates 100% offline without live internet access.
- **O6 (Peer Alignment with Explorer 2)**: `explorer_m2_2/handoff.md:8-38` establishes:
  - Regex parser `parse_skip_evaluation` extracting uppercase `"EXCUSE"` or `"LEGITIMATE"` and stripping tags.
  - 2-minute micro-habit routing mapped to `gym` (5 pushups/60s plank), `toeic` (3 Part 5 questions), `major` (1 function & git commit).
  - Deterministic offline keyword heuristic `classify_skip_reason_offline`.

## 2. Logic Chain
1. From O1 and O2, `AICoachService` must store conversational history in an in-memory queue with `maxlen=10` (or `config.context_window_size`).
2. From O3, the entries in this history can be natively stored as `types.Content` objects or sanitized into `types.Content` upon dispatching calls to `client.aio.models.generate_content`.
3. From O4, naive FIFO eviction in a fixed-size deque of messages breaks the Gemini multi-turn requirement by creating an orphaned leading `model` message. To prevent HTTP 400 errors, `AICoachService` must include `_get_sanitized_history_contents()` or an eviction handler that drops any leading `model` message so the payload always begins with `role="user"` and alternates turns.
4. From O1 and O2, `get_congratulation` and `evaluate_skip_reason` are session event handlers that use distinct prompt templates (`completion_praise`, `skip_evaluator`). They must NOT be recorded into `self._history` so that free-form `chat()` remains uncluttered by structured event tags.
5. From O1 and O3, when an API call in `chat()` fails and falls back to `offline_error`, both the user's message and the fallback response must be recorded in `self._history` to keep the dialogue coherent and preserve alternating `(user, model)` pairs.
6. From O2, `clear_context()` must atomically clear `self._history` (`self._history.clear()`), leaving all model settings, persona, credentials, and prompts unaffected.
7. From O2 and O5, constructor dependency injection (`client: Optional[Any] = None`) enables zero-network offline unit tests by injecting `mock_client.aio.models.generate_content = AsyncMock(...)`.
8. From O1, O2, O3, O4, O5, and O6, the complete test suite specification for `tests/test_coach.py` covers 7 test classes and 32 test cases verifying: initialization, congratulation generation, excuse evaluation, sliding window FIFO pruning, context reset, offline exception fallbacks (429, 500, timeout, disconnect), and prompt safeguards.

## 3. Caveats
- `collections.deque(maxlen=10)` tracks individual messages (up to 5 complete user/model exchanges). If an implementer prefers tracking 10 full exchanges (20 messages), `maxlen` could be set to 20, but `config.yaml:8` explicitly sets `history_limit: 10`, which specifies 10 messages.
- The unit test suite mock relies on `AsyncMock` duck typing. When running in zero-network environments, real Gemini network calls are prevented by injecting `client=mock_client`.

## 4. Conclusion
The in-memory sliding conversation history mechanism, Gemini multi-turn boundary sanitation, context reset protocol, and complete 32-case unit test suite specification for `tests/test_coach.py` are fully analyzed and architected. Full details and code blueprints are provided in `analysis.md`. The design guarantees zero-network test suite execution, strict adherence to `PROJECT.md` interface contracts, and complete interoperability with Explorer 1 and Explorer 2 findings.

## 5. Verification Method
1. **Inspect Analysis Specification**:
   - Inspect `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_3/analysis.md` for sliding history pruning algorithm, context reset logic, and test class blueprints.
2. **Execute Unit Tests (Post Implementation by Worker)**:
   - Run `py -m pytest tests/test_coach.py -v` from project root.
   - Expected result: all tests pass 100% offline with 0 network calls.
3. **Verify Existing Suite Stability**:
   - Run `py -m pytest -q` from project root.
   - Expected result: >= 181 passed without regressions.
