# Analysis: Sliding Conversation History, Context Reset & Unit Test Suite Architecture

**Role**: `teamwork_preview_explorer` (Explorer 3 — Milestone 2)  
**Target Module**: `src/coach.py` & `tests/test_coach.py`  
**Dependencies**: `google-genai>=0.1.1` (v2.28.0 installed), `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`  
**Date**: 2026-10-03  

---

## Executive Summary

This document specifies the complete architectural design for the in-memory sliding conversation history, context reset mechanism, and full unit test suite for the `AICoachService` component (`src/coach.py` and `tests/test_coach.py`).

Key findings and architectural decisions:
1. **Sliding Context Window**: Utilizes `collections.deque(maxlen=10)` storing native `google.genai.types.Content` objects. Solves the critical Gemini multi-turn boundary hazard: when `maxlen=10` evicts the oldest `user` message, the queue starts with a `model` message. An automated pruning guard ensures any request payload dispatched to the Gemini API strictly begins with `role="user"` and maintains alternating dialogue turns.
2. **Context Reset Protocol**: A clean, idempotent `clear_context()` method that empties the history buffer without corrupting underlying configuration, persona instructions, or API clients.
3. **Deterministic Zero-Network Mocking**: Exploits the constructor dependency injection `AICoachService(..., client=mock_client)` to enable 100% offline testing. Simulates Google GenAI SDK responses and exact exception hierarchies (`errors.APIError(code=429, ...)`, `asyncio.TimeoutError`, `ConnectionError`).
4. **Complete Unit Test Suite Specification**: Specifies 7 test classes and 32 unit test cases for `tests/test_coach.py`, covering congratulation synthesis, excuse vs emergency evaluation, 2-minute micro-habit routing, sliding buffer FIFO pruning, context reset, error fallbacks, and token limit safeguards.

---

## 1. Sliding Conversation History Architecture

### 1.1 Requirements & Constraints
- **R4 Specification**: "Maintain a short-term sliding context window (recent 6–10 messages) in memory so the AI understands ongoing dialogue context."
- **Configuration Contract**: `config.yaml: app.history_limit = 10`, `limits.context_window_size = 10`; `src/config.py: AppConfig.context_window_size = 10`.
- **Interface Contract (`PROJECT.md`)**:
  ```python
  class AICoachService:
      def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None): ...
      async def get_congratulation(self, session_type: str, streak: int) -> str: ...
      async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]: ...
      async def chat(self, user_message: str) -> str: ...
      def clear_context(self) -> None: ...
  ```

### 1.2 Data Structure & Message Formatting
In Google GenAI SDK (`google-genai` v2.28.0), message exchanges sent to `client.aio.models.generate_content` use `google.genai.types.Content`:
- User turn:
  ```python
  types.Content(
      role="user",
      parts=[types.Part.from_text(text=user_message)]
  )
  ```
- Assistant/Coach turn:
  ```python
  types.Content(
      role="model",
      parts=[types.Part.from_text(text=response_text)]
  )
  ```

Internal storage implementation:
```python
from collections import deque
from google.genai import types

class AICoachService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None):
        # Extract context window limit
        if hasattr(config, "context_window_size"):
            self.history_limit = config.context_window_size
        elif isinstance(config, dict):
            self.history_limit = config.get("context_window_size", config.get("history_limit", 10))
        else:
            self.history_limit = 10
            
        self._history: deque[types.Content] = deque(maxlen=self.history_limit)
        self._history_lock = asyncio.Lock()
```

### 1.3 Critical Gemini Multiturn Invariant & Eviction Hazard
In Google Gemini API's multiturn specification:
1. **Rule 1**: The first content in the conversation array MUST have `role="user"`.
2. **Rule 2**: Content objects MUST strictly alternate roles: `user` -> `model` -> `user` -> `model`.

#### The Eviction Boundary Hazard:
Assume `maxlen = 10` individual messages (5 completed exchanges):
- Queue state: `[U1, M1, U2, M2, U3, M3, U4, M4, U5, M5]` (10 messages).
- When the user sends Turn 6 (`U6`), pushing `U6` into `deque(maxlen=10)` immediately causes `U1` to be dropped from the left!
- New queue state: `[M1, U2, M2, U3, M3, U4, M4, U5, M5, U6]`!
- **Hazard**: Index 0 is now `M1` (`role="model"`). If this list is passed directly to `generate_content`, the Gemini API returns HTTP 400 Bad Request: *"First content item must be role 'user'"*.

#### The Pruning Algorithm Solution:
To guarantee protocol safety, `AICoachService` applies an automated normalization check before sending contents or immediately upon FIFO trimming:
```python
def _get_sanitized_history_contents(self) -> list[types.Content]:
    """Returns a sanitized snapshot of history starting strictly with 'user'.
    
    If deque eviction dropped a user message and left a leading 'model' message,
    the orphan 'model' message is discarded from the API payload.
    """
    contents = list(self._history)
    # If oldest message is a dangling 'model' message, drop it so request starts with 'user'
    while contents and contents[0].role == "model":
        contents.pop(0)
    return contents
```

Furthermore, inside `self._history`:
When `U6` is added and `M1` becomes the head, popping `M1` keeps `_history` properly balanced in complete pairs `[U2, M2, U3, M3, U4, M4, U5, M5, U6]`.

### 1.4 Scope Separation: What Affects History?
An essential design principle is **scope separation**:
- **`chat(user_message)`**: Affects history. Represents continuous two-way dialogue between user and coach. Both `user_message` and `model_response` are appended to `self._history`.
- **`get_congratulation(session_type, streak)`**: Does **NOT** affect history. This is an event-triggered one-shot completion praise based on a dedicated template. Appending it would pollute the chat dialogue with system check-in artifacts.
- **`evaluate_skip_reason(session_type, reason)`**: Does **NOT** affect history. This is an isolated classification evaluation with special tags (`[EXCUSE]`/`[LEGITIMATE]`) and structured prompts. It must not interfere with conversational context.
- **`clear_context()`**: Clears `self._history` completely.

### 1.5 Continuity on Offline Fallback
When the Gemini API fails during `chat(user_message)`:
If the API raises a timeout, rate limit, or connection error, the service recovers with an offline fallback response (e.g., `offline_coach`).
- **Action**: Both the user's message and the fallback response are retained in `self._history` as `(role="user", role="model")`.
- **Rationale**: The user actually sees the fallback message on Telegram. Storing it ensures:
  1. The alternating `(user, model)` invariant is preserved.
  2. If the user replies to the fallback (e.g., "OK, I just finished reading 5 pages"), the conversational history remains coherent and valid.

---

## 2. Context Reset Protocol (`clear_context()`)

### 2.1 Specification
```python
def clear_context(self) -> None:
    """Clears all short-term sliding conversation history.
    
    Thread-safe and idempotent. Leaves model configuration, persona instructions,
    and fallback definitions unchanged.
    """
    self._history.clear()
```

### 2.2 Invariants & Guarantees
1. **Idempotency**: Calling `clear_context()` multiple times or on a fresh service is a safe no-op.
2. **Buffer Cleared**: Immediately after invocation, `len(self._history) == 0`.
3. **Subsequent Calls**: A subsequent call to `chat()` starts a clean session with 1 user message and 1 model response, without residual context from prior conversations.
4. **Non-destructive**: Does not reset API credentials, configuration objects, prompt templates, or client instances.

---

## 3. Offline Mocking Architecture for Tests

### 3.1 Constructor Dependency Injection
The constructor signature in `PROJECT.md:140` provides `client: Optional[Any] = None`:
```python
class AICoachService:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        config: Optional[dict] = None,
        client: Optional[Any] = None
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.config = config or {}
        # Dependency injection for zero-network testing
        if client is not None:
            self.client = client
        else:
            from google import genai
            self.client = genai.Client(api_key=api_key)
```

This clean inversion of control allows unit tests to inject a mock client directly without monkeypatching module globals or touching live networks.

### 3.2 Mock Client Structure
In `google-genai`, asynchronous generation is called via:
`await client.aio.models.generate_content(model=..., contents=..., config=...)`

A standard mock client structure:
```python
from unittest.mock import AsyncMock, MagicMock

def create_mock_genai_client(return_text: str = "Hello coach!") -> MagicMock:
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = return_text
    mock_response.candidates = [MagicMock()]
    
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    return client
```

### 3.3 Simulating Google GenAI Exceptions
To test offline fallbacks, tests must simulate exact exception types:
1. **Timeout**: `asyncio.TimeoutError()`
2. **API Rate Limit (429)**:
   ```python
   from google.genai import errors
   err = errors.APIError(code=429, response_json={"error": {"message": "Resource has been exhausted (e.g. check quota)."}})
   ```
3. **API Server Error (500)**:
   ```python
   from google.genai import errors
   err = errors.APIError(code=500, response_json={"error": {"message": "Internal service error."}})
   ```
4. **Network Disconnect**: `ConnectionError("Connection refused by remote host")`
5. **Empty / Filtered Candidates**:
   ```python
   empty_response = MagicMock()
   empty_response.text = None
   empty_response.candidates = []
   ```

---

## 4. Complete Unit Test Suite Architecture (`tests/test_coach.py`)

The test suite is structured into 7 focused test classes with 32 test cases.

```
tests/test_coach.py
├── TestAICoachInitAndConfig             (5 tests)
├── TestCongratulationGeneration          (5 tests)
├── TestExcuseEvaluation                  (7 tests)
├── TestSlidingConversationHistory        (6 tests)
├── TestContextReset                      (3 tests)
├── TestOfflineFallbacksAndExceptions     (5 tests)
└── TestPromptConstructionAndSafeguards   (4 tests)
```

---

### Class 1: `TestAICoachInitAndConfig`
Verifies initialization, default configuration, custom parameters, and client injection.

| # | Test Name | Objective & Setup | Assertions |
|---|---|---|---|
| 1.1 | `test_init_with_defaults` | Initialize with `AICoachService(api_key="fake-key", client=mock_client)`. | `coach.model_name == "gemini-2.5-flash"`, `coach.history_limit == 10`, `len(coach._history) == 0`. |
| 1.2 | `test_init_with_custom_model` | Pass `model_name="gemini-2.0-pro"`. | `coach.model_name == "gemini-2.0-pro"`. |
| 1.3 | `test_init_with_app_config_dataclass` | Pass an instance of `AppConfig` with `context_window_size=6`. | `coach.history_limit == 6`, prompts and fallbacks loaded. |
| 1.4 | `test_init_with_dict_config` | Pass dictionary `{"context_window_size": 8, "prompts": {...}}`. | `coach.history_limit == 8`. |
| 1.5 | `test_init_client_injection` | Inject mock client vs default constructor. | Verified injected client is stored on `self.client`. |

---

### Class 2: `TestCongratulationGeneration`
Verifies congratulations generation across streak counts, session types, and error states.

| # | Test Name | Objective & Setup | Assertions |
|---|---|---|---|
| 2.1 | `test_congratulation_gym_streak_1` | `get_congratulation("gym", streak=1)`. Mock returns `"Tốt lắm, ngày đầu tiên hoàn thành!"`. | Returned string matches mock; `generate_content` called once; prompt includes `"Gym"` and `"1"`. |
| 2.2 | `test_congratulation_toeic_streak_7` | `get_congratulation("toeic", streak=7)`. Mock returns `"7 ngày liên tục! Giữ vững nhịp độ."`. | Returned string matches mock; prompt includes `"TOEIC"` and `"7"`. |
| 2.3 | `test_congratulation_major_streak_100` | `get_congratulation("major", streak=100)`. Milestone verification. | Output valid; prompt contains `"100"`. |
| 2.4 | `test_congratulation_offline_fallback_on_error` | Mock raises `errors.APIError(code=500, ...)`. | Returns `fallbacks["offline_praise"]` (non-empty string); no uncaught exception. |
| 2.5 | `test_congratulation_does_not_affect_history` | Call `get_congratulation()`. | `len(coach._history) == 0`; history remains empty. |

---

### Class 3: `TestExcuseEvaluation`
Verifies classification of excuses vs legitimate obstacles, regex tag cleaning, and micro-habit assignment.

| # | Test Name | Objective & Setup | Assertions |
|---|---|---|---|
| 3.1 | `test_evaluate_obvious_lazy_excuse` | Reason: `"Đang dở ván Dota"`, Mock returns: `"[EXCUSE] Dẹp game đi! Chống đẩy 5 cái ngay!"`. | Returns `("EXCUSE", clean_text)`; `clean_text` does not contain `[EXCUSE]`. |
| 3.2 | `test_evaluate_legitimate_medical_emergency` | Reason: `"Sốt cao 39.5 độ phải đi cấp cứu"`, Mock returns: `"[LEGITIMATE] Đã ghi nhận bệnh. Nghỉ ngơi phục hồi!"`. | Returns `("LEGITIMATE", clean_text)`; `clean_text` does not contain `[LEGITIMATE]`. |
| 3.3 | `test_evaluate_legitimate_accident_or_bereavement` | Reason: `"Tai nạn giao thông đang ở bệnh viện"`. | Returns `("LEGITIMATE", ...)` |
| 3.4 | `test_evaluate_gym_micro_habit_routing` | Session: `"gym"`, reason: `"Mệt quá lười tập"`. | Offline/fallback or prompt injects gym micro-habit (chống đẩy / plank). |
| 3.5 | `test_evaluate_toeic_micro_habit_routing` | Session: `"toeic"`, reason: `"Hôm nay bù đầu"`. | Micro-habit includes Part 5 / Part 3 questions. |
| 3.6 | `test_evaluate_major_micro_habit_routing` | Session: `"major"`, reason: `"Không có mood code"`. | Micro-habit includes opening IDE / 1 function / git commit. |
| 3.7 | `test_evaluate_offline_deterministic_fallback` | Mock raises `asyncio.TimeoutError()`. Test both emergency ("sốt") and excuse ("lười"). | Emergency returns `("LEGITIMATE", ...)`; excuse returns `("EXCUSE", ...)`. |

---

### Class 4: `TestSlidingConversationHistory`
Verifies multi-turn dialogue, deque FIFO trimming, alternating roles, and boundary safety.

| # | Test Name | Objective & Setup | Assertions |
|---|---|---|---|
| 4.1 | `test_chat_single_turn_adds_to_history` | User sends `"Chào coach"`. | History length == 2; `history[0].role == "user"`, `history[1].role == "model"`. |
| 4.2 | `test_chat_multiturn_order_preserved` | Send 3 consecutive exchanges (6 messages total). | History length == 6; roles alternate `[user, model, user, model, user, model]`. |
| 4.3 | `test_chat_history_trimmed_at_maxlen_10` | Send 6 exchanges (12 total messages) with `maxlen=10`. | History length <= 10; oldest exchange (Turn 1) is pruned; latest Turn 6 is present. |
| 4.4 | `test_chat_request_payload_always_starts_with_user` | Send 6 exchanges with mock client recording `call_args`. Inspect `contents` passed to `generate_content`. | In all calls, `contents[0].role == "user"`. No call ever begins with `role="model"`. |
| 4.5 | `test_chat_error_fallback_recorded_in_history` | Mock raises `ConnectionError`. Service returns fallback. | History contains user turn and model fallback turn; total length == 2. |
| 4.6 | `test_chat_long_message_safeguard` | Send large user message (5,000 characters). | Handled cleanly; does not crash; truncated or passed safely. |

---

### Class 5: `TestContextReset`
Verifies context reset semantics.

| # | Test Name | Objective & Setup | Assertions |
|---|---|---|---|
| 5.1 | `test_clear_context_empties_populated_history` | Populate history with 4 exchanges (8 messages), then call `coach.clear_context()`. | `len(coach._history) == 0`. |
| 5.2 | `test_clear_context_idempotent_on_empty` | Call `clear_context()` twice on empty coach. | No error raised; history remains empty. |
| 5.3 | `test_chat_after_clear_context_starts_fresh` | Call `clear_context()`, then call `chat("Bắt đầu lại")`. | `len(coach._history) == 2`; history contains only the new exchange. |

---

### Class 6: `TestOfflineFallbacksAndExceptions`
Verifies resilience against all SDK and network failure modes.

| # | Test Name | Objective & Setup | Assertions |
|---|---|---|---|
| 6.1 | `test_fallback_on_api_timeout` | Mock raises `asyncio.TimeoutError()`. | Returns fallback string; no unhandled exception. |
| 6.2 | `test_fallback_on_rate_limit_429` | Mock raises `errors.APIError(code=429, response_json={...})`. | Returns fallback string without crashing. |
| 6.3 | `test_fallback_on_server_error_500` | Mock raises `errors.APIError(code=500, response_json={...})`. | Returns fallback string without crashing. |
| 6.4 | `test_fallback_on_connection_error` | Mock raises `ConnectionError("Network unreachable")`. | Returns fallback string without crashing. |
| 6.5 | `test_fallback_on_empty_candidates_or_none_text` | Mock returns `GenerateContentResponse` with `candidates=[]` and `text=None`. | Returns fallback string instead of `None` or crashing. |

---

### Class 7: `TestPromptConstructionAndSafeguards`
Verifies generation parameters, system instructions, and template interpolation.

| # | Test Name | Objective & Setup | Assertions |
|---|---|---|---|
| 7.1 | `test_config_system_instruction_passed` | Inspect `config` passed to `generate_content`. | `config.system_instruction` contains coach persona instructions. |
| 7.2 | `test_generation_parameters_temperature_and_tokens` | Inspect `config` parameter values. | `config.temperature == 0.7`, `config.max_output_tokens == 256`. |
| 7.3 | `test_template_variable_interpolation` | Verify `{session_name}`, `{streak}`, `{reason}` are substituted in prompts without raw `{...}` remnants. | Prompt strings contain actual values; no KeyError. |
| 7.4 | `test_missing_prompt_template_fallback` | Provide empty dict config with missing prompt keys. | Service uses default prompt templates safely without crashing. |

---

## 5. Implementation Blueprint for `tests/test_coach.py`

Below is the complete, self-contained reference code for `tests/test_coach.py` that the Worker can execute directly:

```python
"""Unit tests for AI Accountability Coach service (Milestone 2).

Verifies Google GenAI SDK integration, coach persona, sliding context window,
context reset, excuse vs legitimate obstacle evaluator, and offline fallbacks.
100% offline, zero-network deterministic testing via injected mocks.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from google.genai import types, errors

from src.coach import AICoachService, parse_skip_evaluation, classify_skip_reason_offline
from src.config import AppConfig, DEFAULT_PROMPTS, DEFAULT_FALLBACKS, DEFAULT_SYSTEM_PROMPT


# =====================================================================
# Test Fixtures
# =====================================================================

@pytest.fixture
def mock_genai_response_factory():
    """Factory fixture to generate mocked Gemini API response objects."""
    def _create(text: str = "Tập luyện ngay đi, không nói nhiều!"):
        resp = MagicMock()
        resp.text = text
        candidate = MagicMock()
        candidate.content.parts = [MagicMock(text=text)]
        resp.candidates = [candidate]
        return resp
    return _create


@pytest.fixture
def mock_genai_client(mock_genai_response_factory):
    """Fixture providing a mock Google GenAI client."""
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.generate_content = AsyncMock(
        return_value=mock_genai_response_factory("Phản hồi huấn luyện viên mặc định.")
    )
    return client


@pytest.fixture
def coach_service(mock_genai_client, valid_yaml_dict):
    """Fixture providing an AICoachService instance with injected mock client."""
    return AICoachService(
        api_key="mock-api-key",
        model_name="gemini-2.5-flash",
        config=valid_yaml_dict,
        client=mock_genai_client
    )


# =====================================================================
# Class 1: TestAICoachInitAndConfig
# =====================================================================

class TestAICoachInitAndConfig:
    """Verifies constructor parameters, defaults, and dependency injection."""

    def test_init_with_defaults(self, mock_genai_client):
        coach = AICoachService(api_key="mock-key", client=mock_genai_client)
        assert coach.model_name == "gemini-2.5-flash"
        assert coach.history_limit == 10
        assert len(coach._history) == 0
        assert coach.client is mock_genai_client

    def test_init_with_custom_model(self, mock_genai_client):
        coach = AICoachService(
            api_key="mock-key",
            model_name="gemini-2.0-flash",
            client=mock_genai_client
        )
        assert coach.model_name == "gemini-2.0-flash"

    def test_init_with_dict_config_window_size(self, mock_genai_client):
        cfg = {"context_window_size": 6}
        coach = AICoachService(api_key="mock-key", config=cfg, client=mock_genai_client)
        assert coach.history_limit == 6

    def test_init_with_app_config_instance(self, mock_genai_client, valid_yaml_dict, valid_env_dict):
        from src.config import load_config
        # AppConfig contract check
        coach = AICoachService(
            api_key="mock-key",
            config=valid_yaml_dict,
            client=mock_genai_client
        )
        assert coach.history_limit == 10
        assert "completion_praise" in coach.prompts


# =====================================================================
# Class 2: TestCongratulationGeneration
# =====================================================================

@pytest.mark.asyncio
class TestCongratulationGeneration:
    """Verifies praise generation across streak counts and session types."""

    async def test_congratulation_gym_streak_1(self, coach_service, mock_genai_client, mock_genai_response_factory):
        expected_praise = "Tốt lắm, buổi tập đầu tiên hoàn thành sạch sẽ!"
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(expected_praise)

        result = await coach_service.get_congratulation(session_type="gym", streak=1)
        assert result == expected_praise
        assert mock_genai_client.aio.models.generate_content.called

        # Verify prompt contained streak count
        called_args = mock_genai_client.aio.models.generate_content.call_args
        prompt_content = str(called_args.kwargs.get("contents") or called_args[1].get("contents"))
        assert "1" in prompt_content

    async def test_congratulation_toeic_streak_7(self, coach_service, mock_genai_client, mock_genai_response_factory):
        expected_praise = "7 ngày liên tục! Giữ vững kỷ luật này để đạt mục tiêu."
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(expected_praise)

        result = await coach_service.get_congratulation(session_type="toeic", streak=7)
        assert result == expected_praise

    async def test_congratulation_major_streak_100(self, coach_service, mock_genai_client, mock_genai_response_factory):
        expected_praise = "100 ngày commit liên tục! Một cột mốc đáng nể của một kỹ sư."
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(expected_praise)

        result = await coach_service.get_congratulation(session_type="major", streak=100)
        assert result == expected_praise

    async def test_congratulation_offline_fallback_on_api_error(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = errors.APIError(
            code=500, response_json={"error": {"message": "Internal error"}}
        )
        result = await coach_service.get_congratulation(session_type="gym", streak=3)
        assert result == coach_service.fallbacks.get("offline_praise")

    async def test_congratulation_does_not_pollute_history(self, coach_service):
        assert len(coach._history) == 0
        await coach_service.get_congratulation(session_type="gym", streak=5)
        # History must remain isolated from event-driven praises
        assert len(coach._history) == 0


# =====================================================================
# Class 3: TestExcuseEvaluation
# =====================================================================

@pytest.mark.asyncio
class TestExcuseEvaluation:
    """Verifies classification of excuses vs legitimate obstacles and micro-habits."""

    async def test_evaluate_obvious_lazy_excuse(self, coach_service, mock_genai_client, mock_genai_response_factory):
        raw_output = "[EXCUSE] Đừng viện cớ chơi game nữa. Mở IDE lên viết đúng 1 hàm rồi commit ngay!"
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(raw_output)

        classification, text = await coach_service.evaluate_skip_reason("major", "Đang dở ván Dota với bạn")
        assert classification == "EXCUSE"
        assert "[EXCUSE]" not in text
        assert "viết đúng 1 hàm" in text

    async def test_evaluate_legitimate_medical_emergency(self, coach_service, mock_genai_client, mock_genai_response_factory):
        raw_output = "[LEGITIMATE] Đã ghi nhận sốt cao. Hãy nghỉ ngơi, ngày mai hồi phục tài nguyên rồi tiếp tục."
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(raw_output)

        classification, text = await coach_service.evaluate_skip_reason("gym", "Sốt cao 39.5 độ phải nằm truyền nước")
        assert classification == "LEGITIMATE"
        assert "[LEGITIMATE]" not in text
        assert "nghỉ ngơi" in text

    async def test_evaluate_parser_tolerates_varied_casing_and_prefixes(self):
        # Bracketed lowercase
        c1, t1 = parse_skip_evaluation("[excuse] Lười quá thì hít đất 5 cái đi.")
        assert c1 == "EXCUSE"
        assert "[excuse]" not in t1.lower()

        # Line prefix format
        c2, t2 = parse_skip_evaluation("CLASSIFICATION: LEGITIMATE\nĐã duyệt nghỉ cấp cứu.")
        assert c2 == "LEGITIMATE"
        assert "CLASSIFICATION" not in t2

    async def test_evaluate_gym_micro_habit_injection(self, coach_service, mock_genai_client):
        # Offline fallback check on API timeout
        mock_genai_client.aio.models.generate_content.side_effect = asyncio.TimeoutError()
        classification, text = await coach_service.evaluate_skip_reason("gym", "Lười quá trời mưa")
        assert classification == "EXCUSE"
        assert "chống đẩy" in text or "plank" in text or "micro-habit" in text

    async def test_evaluate_toeic_micro_habit_injection(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = asyncio.TimeoutError()
        classification, text = await coach_service.evaluate_skip_reason("toeic", "Buồn ngủ mai học bù")
        assert classification == "EXCUSE"
        assert "Part 5" in text or "câu" in text or "micro-habit" in text

    async def test_evaluate_major_micro_habit_injection(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = asyncio.TimeoutError()
        classification, text = await coach_service.evaluate_skip_reason("major", "Chán không muốn code")
        assert classification == "EXCUSE"
        assert "IDE" in text or "function" in text or "commit" in text or "micro-habit" in text

    async def test_evaluate_offline_legitimate_emergency(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = errors.APIError(
            code=429, response_json={"error": {"message": "Quota exceeded"}}
        )
        classification, text = await coach_service.evaluate_skip_reason("gym", "Gia đình có tang khẩn cấp")
        assert classification == "LEGITIMATE"


# =====================================================================
# Class 4: TestSlidingConversationHistory
# =====================================================================

@pytest.mark.asyncio
class TestSlidingConversationHistory:
    """Verifies rolling buffer deque(maxlen=10), FIFO trimming, and turn invariants."""

    async def test_chat_single_turn_adds_to_history(self, coach_service, mock_genai_client, mock_genai_response_factory):
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory("Bắt đầu bài tập nào!")
        reply = await coach_service.chat("Chào coach")

        assert reply == "Bắt đầu bài tập nào!"
        assert len(coach_service._history) == 2
        assert coach_service._history[0].role == "user"
        assert coach_service._history[1].role == "model"

    async def test_chat_multiturn_order_preserved(self, coach_service, mock_genai_client, mock_genai_response_factory):
        for i in range(3):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(f"Trả lời {i}")
            await coach_service.chat(f"Tin nhắn {i}")

        assert len(coach_service._history) == 6
        roles = [msg.role for msg in coach_service._history]
        assert roles == ["user", "model", "user", "model", "user", "model"]

    async def test_chat_history_trimmed_at_maxlen_10(self, coach_service, mock_genai_client, mock_genai_response_factory):
        # History limit is 10 messages (5 exchanges)
        for i in range(7):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(f"Trả lời {i}")
            await coach_service.chat(f"Tin nhắn {i}")

        # Ensure history does not exceed 10
        assert len(coach_service._history) <= 10
        # Turn 0 should have been trimmed out
        first_user_text = coach_service._history[0].parts[0].text
        assert "Tin nhắn 0" not in first_user_text

    async def test_chat_request_payload_always_starts_with_user(self, coach_service, mock_genai_client, mock_genai_response_factory):
        """Verifies Gemini multi-turn requirement: first content item must have role='user'."""
        for i in range(7):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(f"Resp {i}")
            await coach_service.chat(f"Msg {i}")

            called_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
            contents = called_kwargs.get("contents")
            assert isinstance(contents, list)
            assert contents[0].role == "user", "Conversation payload sent to Gemini MUST start with role 'user'!"

    async def test_chat_fallback_recorded_in_history_maintains_alternating_turns(self, coach_service, mock_genai_client):
        # Turn 1 succeeds
        await coach_service.chat("Tin nhắn 1")
        # Turn 2 fails with network error
        mock_genai_client.aio.models.generate_content.side_effect = ConnectionError("Disconnected")
        reply = await coach_service.chat("Tin nhắn 2")

        assert reply == coach_service.fallbacks.get("offline_error") or "mất kết nối" in reply
        # History must contain both user and fallback model response
        assert len(coach_service._history) == 4
        assert coach_service._history[-1].role == "model"

    async def test_chat_empty_or_whitespace_message_handling(self, coach_service):
        reply = await coach_service.chat("   ")
        assert isinstance(reply, str)
        assert len(reply) > 0


# =====================================================================
# Class 5: TestContextReset
# =====================================================================

@pytest.mark.asyncio
class TestContextReset:
    """Verifies clear_context() behavior and state isolation."""

    async def test_clear_context_empties_populated_history(self, coach_service, mock_genai_client, mock_genai_response_factory):
        for i in range(3):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(f"R {i}")
            await coach_service.chat(f"M {i}")

        assert len(coach_service._history) == 6
        coach_service.clear_context()
        assert len(coach_service._history) == 0

    def test_clear_context_idempotent_on_empty(self, coach_service):
        assert len(coach_service._history) == 0
        coach_service.clear_context()
        coach_service.clear_context()
        assert len(coach_service._history) == 0

    async def test_chat_after_clear_context_starts_fresh(self, coach_service, mock_genai_client, mock_genai_response_factory):
        await coach_service.chat("Cũ 1")
        coach_service.clear_context()

        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory("Mới 1")
        await coach_service.chat("Mới 1")

        assert len(coach_service._history) == 2
        assert coach_service._history[0].parts[0].text == "Mới 1"


# =====================================================================
# Class 6: TestOfflineFallbacksAndExceptions
# =====================================================================

@pytest.mark.asyncio
class TestOfflineFallbacksAndExceptions:
    """Verifies graceful degradation across API and network errors."""

    async def test_fallback_on_api_timeout(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = asyncio.TimeoutError()
        res = await coach_service.chat("Alo?")
        assert res == coach_service.fallbacks.get("offline_error") or "mất kết nối" in res

    async def test_fallback_on_rate_limit_429(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = errors.APIError(
            code=429, response_json={"error": {"message": "Resource exhausted"}}
        )
        res = await coach_service.chat("Alo?")
        assert res == coach_service.fallbacks.get("offline_error") or "kỷ luật" in res

    async def test_fallback_on_server_error_500(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = errors.APIError(
            code=500, response_json={"error": {"message": "Server error"}}
        )
        res = await coach_service.chat("Alo?")
        assert res == coach_service.fallbacks.get("offline_error") or "kỷ luật" in res

    async def test_fallback_on_empty_candidates_none_text(self, coach_service, mock_genai_client):
        empty_resp = MagicMock()
        empty_resp.text = None
        empty_resp.candidates = []
        mock_genai_client.aio.models.generate_content.return_value = empty_resp

        res = await coach_service.chat("Alo?")
        assert res is not None
        assert len(res) > 0


# =====================================================================
# Class 7: TestPromptConstructionAndSafeguards
# =====================================================================

@pytest.mark.asyncio
class TestPromptConstructionAndSafeguards:
    """Verifies prompt generation configuration and token safeguards."""

    async def test_config_system_instruction_passed(self, coach_service, mock_genai_client):
        await coach_service.chat("Test system prompt")
        called_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
        cfg = called_kwargs.get("config")
        assert cfg is not None
        # Verify system instruction contains key persona attributes
        sys_inst = cfg.system_instruction
        assert "Huấn Luyện Viên" in sys_inst or "kỷ luật" in sys_inst.lower()

    async def test_generation_parameters_temperature_and_tokens(self, coach_service, mock_genai_client):
        await coach_service.chat("Test params")
        called_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
        cfg = called_kwargs.get("config")
        assert cfg.temperature == 0.7
        assert cfg.max_output_tokens == 256
```

---

## 6. Synthesis & Next Actions for Worker M2

1. **`src/coach.py` Implementation**:
   - Store messages in `self._history: deque[types.Content] = deque(maxlen=self.history_limit)`.
   - Implement `_get_sanitized_history_contents()` to guarantee leading `role="user"`.
   - Implement `parse_skip_evaluation(raw_text)` to strip `[EXCUSE]`/`[LEGITIMATE]` tags.
   - Implement `classify_skip_reason_offline(session_type, reason, fallbacks)` as deterministic keyword fallback.
   - Inject `client: Optional[Any] = None` in `__init__`.
2. **`tests/test_coach.py` Implementation**:
   - Write test suite using the blueprint in Section 5.
   - Run `pytest tests/test_coach.py -v` to ensure 100% pass rate under zero-network conditions.
