# Milestone 2 Adversarial & Quality Review Report (Reviewer 2)

**Target**: Milestone 2 AICoachService (`src/coach.py`, `tests/test_coach.py`)  
**Reviewer**: `reviewer_m2_2` (teamwork_preview_reviewer / critic)  
**Parent / Caller**: `ac41226a-6cc6-45bc-9027-605104e502f4`  
**Date**: 2026-10-03  
**Verdict**: **APPROVE**

---

## 1. Review Summary

The Milestone 2 work product consists of:
- `src/coach.py`: Implementation of `AICoachService`, regex evaluation parser `parse_skip_evaluation`, offline keyword fallback `classify_skip_reason_offline`, and micro-habit mapping `get_micro_habit_for_session`.
- `tests/test_coach.py`: 32 comprehensive unit tests across 7 test classes.
- Additional test suites verified: `tests/test_m2_adversarial.py` (48 tests), `tests/test_m2_challenger_stress.py` (73 tests), `tests/test_e2e_tier1_features.py` (40 tests), and `tests/test_e2e_tier2_boundaries.py` (10 tests).

### Verdict: **APPROVE**
- **Integrity**: Full compliance. No hardcoded test responses, no facade logic, no shortcuts, no fabricated outputs. Direct integration with Google GenAI SDK (`google-genai`).
- **Error Handling & Timeout Safety**: Dual timeout mechanism (15s HTTP options + 15.0s `asyncio.wait_for`). Robust `try...except Exception` wrapping gracefully catches 429 rate limits, 500 server errors, network drops, empty text responses, and safety blocks without crashing the application.
- **Contract Conformance**: Strictly conforms to `PROJECT.md` specifications for `AICoachService` methods (`get_congratulation`, `evaluate_skip_reason`, `chat`, `clear_context`, `context_window`).
- **Test Results**: 100% pass rate (82/82 in requested joint suite; 280/280 in complete regression suite).

---

## 2. Integrity Assessment

| Integrity Check Item | Assessment | Evidence |
|---|---|---|
| Hardcoded test outputs | **PASS** | No hardcoded output mappings. Dynamic prompt templates are interpolated and dispatched to `client.aio.models.generate_content`. |
| Dummy / Facade implementations | **PASS** | Real implementation with `deque(maxlen=N)`, sanitization of alternating roles, regex parsing, and rule-based keyword fallback. |
| Shortcuts / Task bypass | **PASS** | Correctly implemented against Google GenAI SDK v2.28.0 using `google.genai`. |
| Fabricated verification logs | **PASS** | Tests independently executed via CLI; verified 82 passing joint tests and 280 total passing tests. |
| Self-certifying without verification | **PASS** | Independent adversarial stress-testing conducted covering race conditions, safety blocks, diacritics, and injection attacks. |

---

## 3. Adversarial Analysis & Findings

### Finding 1 (Minor / Non-blocking): Concurrent `chat()` Calls May Interleave History Roles
- **Location**: `src/coach.py:356-394`
- **Mechanism**: In `chat()`, `user_content` is appended to `self._history` immediately before the network call (`await asyncio.wait_for(...)`), and `model_content` is appended after receiving the reply. If two coroutines invoke `coach.chat()` concurrently, the history deque records `['user', 'user', 'model', 'model']`.
- **Impact**: While PTB with single-user whitelist (`ALLOWED_CHAT_ID`) processes messages sequentially in normal operation, rapid concurrent updates could cause consecutive identical roles in Gemini multi-turn payload.
- **Recommendation**: In a future refactor, guard `chat()` with an `asyncio.Lock()` to serialize history updates.

### Finding 2 (Minor / Non-blocking): Offline Heuristic Keywords Rely on Accented Vietnamese
- **Location**: `src/coach.py:31-36` (`LEGITIMATE_KEYWORDS`)
- **Mechanism**: Offline emergency keywords use accented Vietnamese (`"sốt"`, `"bệnh"`, `"cấp cứu"`, `"tai nạn"`). An unaccented string like `"sot cao 40 do"` is classified as `EXCUSE` when offline.
- **Impact**: In offline fallback mode, the system defaults to prompting a 2-minute micro-habit instead of approving skip. When online, Gemini handles unaccented Vietnamese semantically without issues.
- **Recommendation**: Optionally add unaccented variants or a diacritic stripper (`unicodedata.normalize`) to `LEGITIMATE_KEYWORDS`.

### Finding 3 (Informational): Upstream Python 3.14 GenAI SDK Deprecation Warning
- **Location**: `google/genai/types.py:42`
- **Notice**: `DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17`.
- **Impact**: Originates strictly within Google's external SDK under Python 3.14. Does not affect application logic or test execution.

---

## 4. Verified Claims

1. **Error Handling & Fallbacks**:
   - `429 Too Many Requests`: Verified via `TestOfflineFallbacksAndExceptions::test_fallback_on_rate_limit_429` → **PASS**
   - `500 Server Error`: Verified via `TestOfflineFallbacksAndExceptions::test_fallback_on_server_error_500` → **PASS**
   - `asyncio.TimeoutError`: Verified via `TestOfflineFallbacksAndExceptions::test_fallback_on_api_timeout` → **PASS**
   - `ConnectionError`: Verified via `TestOfflineFallbacksAndExceptions::test_fallback_on_connection_error` → **PASS**
   - `Safety Block (ValueError on .text)`: Verified via independent test harness → **PASS**
   - `Empty / None Response Candidates`: Verified via `TestOfflineFallbacksAndExceptions::test_fallback_on_empty_candidates_none_text` → **PASS**

2. **`evaluate_skip_reason` Contract**:
   - Return type strictly `Tuple[str, str]` with `classification in ('EXCUSE', 'LEGITIMATE')` → **PASS**
   - Micro-habit suggestions correctly tailored by domain (`gym`: pushup/plank; `toeic`: Part 5/Part 3; `major`: IDE function/git commit) → **PASS**
   - Tolerates case-insensitivity (`[excuse]`, `[legitimate]`), line prefixes (`CLASSIFICATION: ...`), and absence of tags (defaults to `EXCUSE`) → **PASS**

3. **`context_window` Property**:
   - Returns `List[Tuple[str, str]]` matching `(role, text)` format → **PASS**
   - Cleanly unpackable via `[msg for role, msg in coach.context_window]` → **PASS**
   - Bound by `len(coach.context_window) <= 10` across 20, 50, and 100 turns → **PASS**
   - Immutability: Mutating the list returned by `context_window` does not mutate internal `self._history` → **PASS**
   - Request payloads sent to Gemini always start with `role="user"` → **PASS**

---

## 5. Test Suite Execution Matrix

| Test Suite | Command | Result | Duration |
|---|---|---|---|
| Joint Suite (Dispatch Required) | `python -m pytest tests/test_coach.py tests/test_e2e_tier1_features.py tests/test_e2e_tier2_boundaries.py -v` | **82 passed, 1 warning** | 2.73s |
| Milestone 2 Unit Suite | `python -m pytest tests/test_coach.py -v` | **32 passed, 1 warning** | 0.87s |
| Milestone 2 Adversarial Suite | `python -m pytest tests/test_m2_adversarial.py -v` | **48 passed, 1 warning** | 0.90s |
| Milestone 2 Challenger Suite | `python -m pytest tests/test_m2_challenger_stress.py -v` | **73 passed, 1 warning** | 0.78s |
| Full Regression Suite (M1-M2 + E2E) | `python -m pytest tests/test_config.py tests/test_storage.py tests/test_coach.py tests/test_m2_adversarial.py tests/test_m2_challenger_stress.py tests/test_e2e_tier1_features.py tests/test_e2e_tier2_boundaries.py` | **280 passed, 1 warning** | 4.91s |

---

## 6. Recommendation

Issue formal approval (**APPROVE**) for Milestone 2. Proceed to Milestone 3 (Proactive Scheduler integration in `src/scheduler.py`).
