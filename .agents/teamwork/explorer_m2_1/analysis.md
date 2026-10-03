# Technical Analysis: Google GenAI SDK Integration & Offline Mocking Design

**Author:** Milestone 2 Explorer 1 (`explorer_m2_1`)  
**Target Component:** `src/coach.py` (`AICoachService`)  
**Associated Interfaces:** `src/config.py`, `tests/conftest.py`, `tests/test_coach.py`  
**Dependencies:** `google-genai>=0.1.1` (tested on `google-genai==2.28.0`), `httpx>=0.28.1`, `python-dotenv>=1.0.0`

---

## 1. Executive Summary

Milestone 2 requires implementing `AICoachService` in `src/coach.py` using Google's modern GenAI SDK (`google-genai`) with model `gemini-2.5-flash`. The service must provide:
1. Completion praise and congratulation generation tied to streak counters.
2. An excuse vs. legitimate obstacle evaluator enforcing a 2-minute micro-habit for excuses.
3. Free-form interactive coaching dialogue with a rolling context window of recent messages.
4. Complete offline resilience: zero-network execution in unit/integration test suites, and robust fallback responses when API quotas, rate limits, or network disconnections occur in production.

This analysis provides the complete architectural blueprint, empirical SDK verification, exception hierarchy mapping, and zero-network mocking infrastructure for the Milestone 2 Worker.

---

## 2. Google GenAI SDK Architecture (`google-genai`)

### 2.1. Modern SDK vs Legacy SDK Distinction
| Characteristic | Legacy SDK (`google-generativeai`) | Modern SDK (`google-genai`) |
|---|---|---|
| Package Name | `google-generativeai` | `google-genai` (as specified in `requirements.txt`) |
| Root Import | `import google.generativeai as genai` | `from google import genai` |
| Client Factory | `genai.configure(api_key=...)` | `client = genai.Client(api_key=...)` |
| Async Client Access | Implicit / threadpool wrappers | First-class `client.aio` namespace |
| Content Generation | `model.generate_content_async(...)` | `await client.aio.models.generate_content(...)` |
| Error Hierarchy | `google.api_core.exceptions.*` | `google.genai.errors.*` |
| Type System | `google.ai.generativelanguage.*` | `google.genai.types.*` (Pydantic v2 based) |

### 2.2. SDK Instantiation & Lifecycle
- **Constructor:** `client = genai.Client(api_key=api_key)`
- **Empirical Observation:** `genai.Client(api_key=...)` is a lightweight, local object instantiation. It performs **no network I/O** upon construction.
- **Validation:** If `api_key` is empty string `""` or `None` and no `GEMINI_API_KEY` is present in `os.environ`, `genai.Client` raises `ValueError: No API key was provided.`
- **Client Invalidation/Cleanup:** `client.aio.aclose()` exists for explicit session teardown, though standard garbage collection suffices for normal bot lifecycles.

### 2.3. Asynchronous Model Invocations (`client.aio.models`)
The primary asynchronous entrypoint is:
```python
response = await client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=contents,
    config=config,
)
```
- **Signature parameters:**
  - `model`: Target model string (strictly `"gemini-2.5-flash"`).
  - `contents`: Accepts `str`, `types.Content`, `List[types.Content]`, or raw content dictionaries.
  - `config`: Instance of `types.GenerateContentConfig`.

### 2.4. Generation Configuration (`types.GenerateContentConfig`)
Empirical inspection of `google.genai.types.GenerateContentConfig` reveals key parameters:
```python
config = types.GenerateContentConfig(
    system_instruction=system_prompt,  # Direct string or types.Content
    temperature=0.7,                   # Balanced creativity and discipline
    max_output_tokens=256,             # Enforces concise responses (max 2-3 sentences)
    http_options=types.HttpOptions(
        timeout=15000                  # CRITICAL: timeout is in MILLISECONDS (15000 ms = 15s)
    ),
)
```
> ⚠️ **CRITICAL CAVEAT:** `types.HttpOptions.timeout` is specified in **milliseconds**, not seconds. Passing `15` would trigger a timeout after 15 milliseconds. For 15 seconds, use `15000`.

### 2.5. Response Structure & Text Extraction
- The response is an instance of `types.GenerateContentResponse`.
- Access text via `response.text`.
- **Safety / Empty Response Behavior:** If safety thresholds block the candidate or candidates are empty, `response.text` returns `None` (rather than raising an immediate exception). `AICoachService` must explicitly verify `if not response.text or not response.text.strip()` before processing.

---

## 3. Asynchronous Execution, Timeouts & Exception Hierarchy

### 3.1. Asynchronous Execution Imperative
`python-telegram-bot` (v20+) and `APScheduler` (`AsyncIOScheduler`) run within an `asyncio` event loop. Synchronous, blocking network calls freeze the event loop, causing:
- Telegram polling timeouts and dropped `/start` or button callback clicks.
- Missed or delayed proactive notification triggers in APScheduler.
- False positive timeouts for concurrent user sessions.

Therefore, `AICoachService` must strictly invoke `client.aio.models.generate_content(...)`.

### 3.2. Two-Layer Timeout Defense
To protect against both SDK-level and event-loop stalls:
1. **SDK Level:** `http_options=types.HttpOptions(timeout=15000)` configured on the request.
2. **Asyncio Task Level:** `asyncio.wait_for(coroutine, timeout=15.0)` wrapping the invocation.
If the underlying socket or HTTP connection stalls without closing, `asyncio.wait_for` immediately raises `asyncio.TimeoutError`, releasing the handler and activating the fallback response.

### 3.3. Exception Hierarchy
The error classes that can emerge from `client.aio.models.generate_content` form this hierarchy:

```text
BaseException
 └── Exception
      ├── google.genai.errors.APIError
      │    ├── google.genai.errors.ClientError   (HTTP 4xx: 400, 403, 404, 429)
      │    └── google.genai.errors.ServerError   (HTTP 5xx: 500, 502, 503, 504)
      ├── google.genai.errors.UnknownApiResponseError
      ├── httpx.HTTPError
      │    └── httpx.RequestError
      │         ├── httpx.TimeoutException
      │         └── httpx.NetworkError (ConnectError, CloseError)
      └── asyncio.TimeoutError / TimeoutError
```

### 3.4. Status Code Mapping & Fallback Behavior
| Error Condition | Error Type / Code | Cause | AICoachService Action |
|---|---|---|---|
| **Rate Limit / Quota Exceeded** | `errors.ClientError` (`code=429`) | Too many requests / quota exhaustion | Log warning, optional single retry (500ms delay), activate persona fallback. |
| **Invalid Prompt / Syntax** | `errors.ClientError` (`code=400`) | Malformed message or role sequence | Log error, activate fallback. |
| **Invalid API Key** | `errors.ClientError` (`code=403`) | Bad credentials | Log error, activate fallback without exposing key. |
| **Google Server Outage** | `errors.ServerError` (`code=500, 503`) | Gemini backend degradation | Log warning, activate fallback. |
| **Network Timeout** | `httpx.TimeoutException`, `asyncio.TimeoutError` | Dropped packet / slow connection | Log warning, activate fallback immediately. |
| **Network Disconnect** | `httpx.NetworkError` | DNS failure / offline machine | Log warning, activate fallback immediately. |
| **Safety Block / Empty Text** | `response.text is None` | Content blocked by Gemini safety filter | Log warning, activate fallback immediately. |

---

## 4. Zero-Network Offline Mocking Strategy

### 4.1. Architecture for Dependency Injection
Per the interface contract in `PROJECT.md`:
```python
class AICoachService:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        config: Optional[Union[dict, AppConfig]] = None,
        client: Optional[Any] = None,
    ):
```
The `client` parameter provides direct dependency injection:
- In production: `client=None` → `AICoachService` instantiates `self.client = genai.Client(api_key=api_key)`.
- In tests: `client=mock_client` → `AICoachService` assigns `self.client = client`, completely bypassing `genai.Client()` and ensuring **0 network requests**.

### 4.2. Mock Client Patterns for Unit and Integration Tests

#### Pattern A: Direct `AsyncMock` via standard unittest.mock
```python
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_gemini_client():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Xuất sắc! Kỷ luật 10/10."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    return mock_client
```

#### Pattern B: Fault Injection (Rate Limit, Server Error, Network Drop)
```python
from google.genai import errors
import httpx

# Simulating 429 Quota Exceeded
mock_client.aio.models.generate_content = AsyncMock(
    side_effect=errors.APIError(code=429, response_json={"error": {"message": "Quota exceeded"}})
)

# Simulating 503 Service Unavailable
mock_client.aio.models.generate_content = AsyncMock(
    side_effect=errors.ServerError(code=503, response_json={"error": {"message": "Service Unavailable"}})
)

# Simulating Network Timeout
mock_client.aio.models.generate_content = AsyncMock(
    side_effect=httpx.ConnectTimeout("Connection timed out")
)
```

#### Pattern C: Deterministic `FakeGenAIClient` Test Fixture
For multi-turn chat testing and classification assertions:
```python
class FakeGenAIClient:
    """Deterministic in-memory fake for google-genai client."""
    def __init__(self, canned_response: str = "Cố gắng lên!"):
        self.canned_response = canned_response
        self.calls = []
        self.aio = MagicMock()
        self.aio.models.generate_content = AsyncMock(side_effect=self._mock_generate)

    async def _mock_generate(self, model: str, contents: Any, config: Any = None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        resp = MagicMock()
        resp.text = self.canned_response
        return resp
```

---

## 5. Specification & Implementation Blueprint for `src/coach.py`

### 5.1. Sliding Context Window Management
- Maintain `self._history: collections.deque[types.Content]` with `maxlen=self.history_limit`.
- In `chat(user_message)`:
  1. Append `types.Content(role="user", parts=[types.Part.from_text(text=user_message)])`.
  2. Send `contents=list(self._history)`.
     - *Role alternation safeguard:* If previous window slicing leaves the oldest entry with `role="model"`, strip leading model items so Gemini API never rejects the payload for non-user start.
  3. On success, append `types.Content(role="model", parts=[types.Part.from_text(text=reply)])`.
  4. On failure, pop the pending user entry to maintain clean conversational state, and return the persona fallback message.
- In `clear_context()`:
  - Invoke `self._history.clear()`.

### 5.2. Skip Reason Classification Parsing
When `evaluate_skip_reason(session_type, reason)` calls the model:
1. Format prompt using `prompts["skip_evaluator"]` with `{session_name}`, `{detail}`, `{reason}`.
2. The model response must be parsed to extract `(classification: 'EXCUSE' | 'LEGITIMATE', response_text: str)`.
3. Extraction regex:
   ```python
   # 1. Match [EXCUSE] or [LEGITIMATE] prefix
   m = re.match(r"^\[(EXCUSE|LEGITIMATE)\]\s*(.*)", text, re.IGNORECASE | re.DOTALL)
   if m:
       return (m.group(1).upper(), m.group(2).strip() or text)
   # 2. Match EXCUSE: or LEGITIMATE: prefix
   m = re.match(r"^(EXCUSE|LEGITIMATE)[:\s-]+\s*(.*)", text, re.IGNORECASE | re.DOTALL)
   if m:
       return (m.group(1).upper(), m.group(2).strip() or text)
   # 3. Tag embedded anywhere in text
   if "[EXCUSE]" in text.upper():
       return ("EXCUSE", re.sub(r"\[EXCUSE\]", "", text, flags=re.IGNORECASE).strip())
   if "[LEGITIMATE]" in text.upper():
       return ("LEGITIMATE", re.sub(r"\[LEGITIMATE\]", "", text, flags=re.IGNORECASE).strip())
   # 4. Default fallback: EXCUSE
   return ("EXCUSE", text)
   ```
4. On API failure, offline classification heuristic:
   - Check if reason contains legitimate medical/emergency keywords (`sốt`, `bệnh`, `cấp cứu`, `tai nạn`, `tang`, `bác sĩ`, `nhập viện`, `sick`, `hospital`, `emergency`).
   - If true: return `("LEGITIMATE", self.fallbacks.get("offline_skip_legitimate", ...))`.
   - Else: return `("EXCUSE", self.fallbacks.get("offline_skip_excuse", ...))`.

### 5.3. Complete Proposed Code Structure (`src/coach.py`)
```python
"""AI Accountability Coach service integrating Google GenAI SDK (gemini-2.5-flash)."""

from __future__ import annotations

import asyncio
from collections import deque
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from google import genai
    from google.genai import errors, types
    GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    genai = None  # type: ignore
    errors = None  # type: ignore
    types = None  # type: ignore
    GENAI_AVAILABLE = False

from src.config import (
    AppConfig,
    DEFAULT_FALLBACKS,
    DEFAULT_PROMPTS,
    DEFAULT_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

LEGITIMATE_KEYWORDS = {
    "sốt", "bệnh", "ốm", "cấp cứu", "tai nạn", "bác sĩ", "viện", "nhập viện",
    "đau bụng", "ngộ độc", "tang", "chấn thương", "sick", "hospital", "emergency"
}


class AICoachService:
    """Two-way AI Accountability Coach using Gemini 2.5 Flash."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        config: Optional[Union[Dict[str, Any], AppConfig]] = None,
        client: Optional[Any] = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model_name = model_name or "gemini-2.5-flash"
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # Unpack configuration parameters
        if isinstance(config, AppConfig):
            self.prompts = dict(config.prompts)
            self.fallbacks = dict(config.fallbacks)
            self.system_prompt = config.system_prompt or self.prompts.get("system_instruction", DEFAULT_SYSTEM_PROMPT)
            self.history_limit = config.context_window_size
            if config.gemini_model:
                self.model_name = config.gemini_model
        elif isinstance(config, dict):
            self.prompts = dict(config.get("prompts", DEFAULT_PROMPTS))
            self.fallbacks = dict(config.get("fallbacks", DEFAULT_FALLBACKS))
            self.system_prompt = config.get("system_prompt", self.prompts.get("system_instruction", DEFAULT_SYSTEM_PROMPT))
            self.history_limit = int(config.get("history_limit", config.get("context_window_size", 10)))
            self.model_name = config.get("gemini_model", config.get("model", self.model_name))
        else:
            self.prompts = dict(DEFAULT_PROMPTS)
            self.fallbacks = dict(DEFAULT_FALLBACKS)
            self.system_prompt = DEFAULT_SYSTEM_PROMPT
            self.history_limit = 10

        self._history: deque[Any] = deque(maxlen=self.history_limit)

        # Setup GenAI client (Dependency Injection or native initialization)
        if client is not None:
            self.client = client
        else:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY must not be empty when no client is provided")
            if not GENAI_AVAILABLE:
                raise RuntimeError("google-genai package is not installed")
            self.client = genai.Client(api_key=self.api_key)

    async def _call_gemini(self, contents: Any) -> Optional[str]:
        """Executes asynchronous content generation with timeout, retry, and exception trapping."""
        timeout_ms = int(self.timeout_seconds * 1000)
        req_config = None
        if types is not None:
            req_config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=0.7,
                max_output_tokens=256,
                http_options=types.HttpOptions(timeout=timeout_ms),
            )

        for attempt in range(self.max_retries + 1):
            try:
                coro = self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=req_config,
                )
                response = await asyncio.wait_for(coro, timeout=self.timeout_seconds)
                if response is not None and getattr(response, "text", None):
                    text = str(response.text).strip()
                    if text:
                        return text
                logger.warning("Gemini returned empty response text (safety block or empty candidates).")
                return None
            except Exception as exc:
                is_transient = False
                if errors is not None and isinstance(exc, errors.APIError) and exc.code in (429, 500, 503):
                    is_transient = True
                elif isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
                    is_transient = True

                if is_transient and attempt < self.max_retries:
                    logger.warning("Transient Gemini API error (%s: %s). Retrying in 0.5s...", type(exc).__name__, exc)
                    await asyncio.sleep(0.5)
                    continue

                logger.warning("Gemini API call failed (%s: %s). Activating fallback.", type(exc).__name__, exc)
                return None
        return None

    async def get_congratulation(self, session_type: str, streak: int) -> str:
        """Generates congratulatory praise for completed session and streak."""
        template = self.prompts.get("completion_praise", DEFAULT_PROMPTS.get("completion_praise", ""))
        prompt = template.format(session_name=session_type, detail=session_type, streak=streak)

        result = await self._call_gemini(prompt)
        if result:
            return result
        return self.fallbacks.get("offline_praise", DEFAULT_FALLBACKS["offline_praise"])

    async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]:
        """Evaluates whether session skip reason is an EXCUSE or LEGITIMATE obstacle."""
        template = self.prompts.get("skip_evaluator", DEFAULT_PROMPTS.get("skip_evaluator", ""))
        prompt = template.format(session_name=session_type, detail=session_type, reason=reason)

        raw_result = await self._call_gemini(prompt)
        if raw_result:
            return self._parse_skip_response(raw_result)

        # Offline fallback classification heuristic
        reason_lower = reason.lower()
        if any(kw in reason_lower for kw in LEGITIMATE_KEYWORDS):
            return ("LEGITIMATE", self.fallbacks.get("offline_skip_legitimate", DEFAULT_FALLBACKS["offline_skip_legitimate"]))
        return ("EXCUSE", self.fallbacks.get("offline_skip_excuse", DEFAULT_FALLBACKS["offline_skip_excuse"]))

    def _parse_skip_response(self, text: str) -> Tuple[str, str]:
        """Parses model response text into classification tag and response body."""
        clean = text.strip()
        m = re.match(r"^\[(EXCUSE|LEGITIMATE)\]\s*(.*)", clean, re.IGNORECASE | re.DOTALL)
        if m:
            return (m.group(1).upper(), m.group(2).strip() or clean)
        m = re.match(r"^(EXCUSE|LEGITIMATE)[:\s-]+\s*(.*)", clean, re.IGNORECASE | re.DOTALL)
        if m:
            return (m.group(1).upper(), m.group(2).strip() or clean)
        if "[EXCUSE]" in clean.upper():
            return ("EXCUSE", re.sub(r"\[EXCUSE\]", "", clean, flags=re.IGNORECASE).strip())
        if "[LEGITIMATE]" in clean.upper():
            return ("LEGITIMATE", re.sub(r"\[LEGITIMATE\]", "", clean, flags=re.IGNORECASE).strip())
        return ("EXCUSE", clean)

    async def chat(self, user_message: str) -> str:
        """Engages in interactive conversation using sliding memory buffer."""
        user_content = None
        if types is not None:
            user_content = types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        else:
            user_content = {"role": "user", "parts": [{"text": user_message}]}

        self._history.append(user_content)

        # Ensure multi-turn conversation starts with 'user'
        contents = list(self._history)
        while contents and getattr(contents[0], "role", None) == "model":
            contents.pop(0)

        reply = await self._call_gemini(contents)
        if reply:
            if types is not None:
                model_content = types.Content(role="model", parts=[types.Part.from_text(text=reply)])
            else:
                model_content = {"role": "model", "parts": [{"text": reply}]}
            self._history.append(model_content)
            return reply

        # Total failure: drop the pending user turn to prevent conversation desync
        if self._history and self._history[-1] == user_content:
            self._history.pop()
        return self.fallbacks.get("offline_coach", DEFAULT_FALLBACKS["offline_coach"])

    def clear_context(self) -> None:
        """Resets the sliding conversation history deque."""
        self._history.clear()
```

---

## 6. Recommendations for Peer Explorers & Worker

1. **For Explorer 2 (Prompts & Persona):**
   - Align prompts so the model reliably outputs `[EXCUSE]` or `[LEGITIMATE]` as the very first token in `skip_evaluator`.
   - Maintain 2-3 sentence limit instruction in `system_prompt` and all task prompts.
2. **For Explorer 3 (Context & Test Suite):**
   - Provide `mock_gemini_client` fixture in `tests/conftest.py` that configures `mock_client.aio.models.generate_content = AsyncMock()`.
   - Test sliding window bounds by sending >10 messages and verifying `len(coach._history) == 10`.
   - Verify `clear_context()` resets `_history` to 0.
   - Test error injection: 429 rate limit, 503 server error, timeout, and empty response candidates.
3. **For Milestone 2 Worker:**
   - Implement `src/coach.py` strictly matching this blueprint.
   - Run tests without real API keys (`GEMINI_API_KEY="dummy"` or injected client). All tests must pass with 100% offline isolation.
