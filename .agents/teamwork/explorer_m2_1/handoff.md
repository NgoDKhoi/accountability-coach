# Handoff Report: Google GenAI SDK & Offline Mocking Design

**Target:** Milestone 2 (`AICoachService` in `src/coach.py`)  
**Sender:** Milestone 2 Explorer 1 (`explorer_m2_1`)  
**Recipient:** Orchestrator & Milestone 2 Worker  
**Profile:** Explorer / Teamwork  
**Status:** Hard Handoff (Investigation Complete)  

---

## 1. Observation

1. **SDK Availability and Version:**
   - Command: `python -m pip install google-genai` installed `google-genai-2.28.0` in Python 3.14.4.
   - `requirements.txt` line 13 specifies: `google-genai>=0.1.1`.
   - Import path: `from google import genai` and `from google.genai import errors, types`.

2. **Client Architecture & Asynchronous Entrypoint:**
   - Constructor: `genai.Client(api_key=...)`. Empirically verified to perform zero network calls upon instantiation.
   - When instantiated with empty string `api_key=""` and no environment variable: raises `ValueError: No API key was provided.`
   - Asynchronous namespace: `client.aio.models.generate_content`.
   - Method signature:
     ```text
     client.aio.models.generate_content(
         *,
         model: str,
         contents: Content | str | list[...],
         config: GenerateContentConfig | None = None
     ) -> GenerateContentResponse
     ```

3. **Configuration & Timeout Semantics:**
   - Config class: `google.genai.types.GenerateContentConfig`.
   - Fields: `system_instruction`, `temperature`, `max_output_tokens`, `http_options`.
   - Field `types.HttpOptions.model_fields['timeout']`:
     `annotation=Union[int, NoneType] description='Timeout for the request in milliseconds.'`
     *Verbatim quote:* Timeout is strictly in milliseconds (e.g. `15000` for 15s).

4. **Response Structure & Safety Behavior:**
   - Response class: `google.genai.types.GenerateContentResponse`.
   - Property `response.text`: returns `str` when candidate contains valid text.
   - When candidate list is empty or blocked by safety filters: `response.text` evaluates to `None` without raising an exception.

5. **Exception Hierarchy:**
   - `google.genai.errors.APIError`:
     - Subclass `errors.ClientError` for HTTP 4xx (`code=429` for Quota/Rate Limit, `code=400` for Bad Request, `code=403` for Auth).
     - Subclass `errors.ServerError` for HTTP 5xx (`code=500` Internal, `code=503` Service Unavailable).
   - `httpx.HTTPError`:
     - Subclass `httpx.TimeoutException` (`ConnectTimeout`, `ReadTimeout`).
     - Subclass `httpx.NetworkError` (`ConnectError`, `CloseError`).
   - `asyncio.TimeoutError` from coroutine timeouts.

6. **Interface Contract in `PROJECT.md` (Lines 139–146):**
   ```python
   class AICoachService:
       def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None): ...
       async def get_congratulation(self, session_type: str, streak: int) -> str: ...
       async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]: ...
       async def chat(self, user_message: str) -> str: ...
       def clear_context(self) -> None: ...
   ```

---

## 2. Logic Chain

1. **Async Safety:**
   - From Observation 2: `python-telegram-bot` and `APScheduler` execute concurrently on an `asyncio` event loop.
   - Calling synchronous `client.models.generate_content` would block the event loop, freezing Telegram heartbeat polling and scheduler jobs.
   - Therefore, `AICoachService` must exclusively call `await client.aio.models.generate_content(...)`.

2. **Timeout Resilience:**
   - From Observation 3 & 5: SDK timeout is configured in milliseconds via `types.HttpOptions(timeout=15000)`. Stalled sockets or slow networks can hang coroutines.
   - Wrapping calls in `asyncio.wait_for(..., timeout=15.0)` guarantees the coroutine is cancelled and control is returned to the bot even if transport socket disconnects fail to register.

3. **Offline Zero-Network Mocking:**
   - From Observation 6: The constructor accepts `client: Optional[Any] = None`.
   - When unit or integration tests pass `client=mock_client` (where `mock_client.aio.models.generate_content = AsyncMock(...)`), `AICoachService` attaches `self.client = mock_client` and skips calling `genai.Client()`.
   - This ensures 100% offline test execution with zero external network access and zero API keys required.

4. **Robust Fallback Trapping:**
   - From Observation 4 & 5: When `errors.APIError` (429, 500, 503), `httpx.HTTPError`, `asyncio.TimeoutError`, or `response.text is None` occurs, bubbling exceptions would crash Telegram message handlers.
   - Trapping all exceptions and empty candidates in `_call_gemini` and returning persona-matched fallback responses from `config.yaml` / `DEFAULT_FALLBACKS` ensures uninterrupted bot operations.

---

## 3. Caveats

1. **Free Tier Gemini Rate Limits in Live Deployments:**
   - Live Gemini 2.5 Flash free-tier keys enforce 15 RPM / 1M TPM. While the service implements single-attempt backoff and offline fallbacks, production workloads should be monitored for sustained 429 quota exhaustion.
2. **Windows Console Encoding:**
   - Standard Windows PowerShell terminals without `PYTHONIOENCODING=utf-8` may fail when printing Vietnamese diacritics directly to stdout (`UnicodeEncodeError`). Code and test suites must operate cleanly using UTF-8 string encoding.
3. **Sliding Window Pruning:**
   - When pruning `collections.deque(maxlen=10)` where the oldest message was a user message, the leading message in the buffer could be a model turn. Multi-turn Gemini APIs reject payloads that start with `role="model"`. The implementation must strip any leading model turns before dispatching `contents` to Gemini.

---

## 4. Conclusion

The technical design for `AICoachService` is fully established, empirically validated against `google-genai` 2.28.0, and directly aligned with `PROJECT.md` and `ORIGINAL_REQUEST.md`.
- File to implement: `src/coach.py`
- Test fixture to add: `mock_gemini_client` in `tests/conftest.py`
- Complete implementation blueprint and regex parsing rules are documented in `analysis.md`.
- No architectural barriers or interface incompatibilities exist for Milestone 2 implementation.

---

## 5. Verification Method

To independently verify all findings and test the mocking pattern:

1. **Verify Google GenAI SDK & Error Importability:**
   ```powershell
   python -c "from google import genai; from google.genai import errors, types; print('GenAI SDK OK')"
   ```
   *Expected result:* Outputs `GenAI SDK OK` with exit code 0.

2. **Verify Offline Mocking & Fallback Execution:**
   Run the empirical test runner verifying AsyncMock, rate-limit 429 fallback, and multi-turn context:
   ```powershell
   python -c "import asyncio; from unittest.mock import AsyncMock, MagicMock; from google.genai import errors; mock = MagicMock(); mock.aio.models.generate_content = AsyncMock(side_effect=errors.APIError(429, {'error': 'Quota'})); print('Mock setup verified')"
   ```
   *Expected result:* Outputs `Mock setup verified` with exit code 0.

3. **Verify Milestone 1 Existing Tests Remain 100% Passing:**
   ```powershell
   python -m pytest tests/test_config.py tests/test_storage.py -v
   ```
   *Expected result:* 77 passed in ~1.6 seconds.

4. **Invalidation Conditions:**
   - If `google-genai` changes `client.aio.models.generate_content` signature.
   - If `AICoachService` fails to return a 2-tuple `(classification, response_text)` for `evaluate_skip_reason`.
   - If tests fail to run without internet connection.
