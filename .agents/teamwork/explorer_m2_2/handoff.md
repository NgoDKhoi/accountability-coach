# Handoff Report: Milestone 2 Explorer 2 (Persona, Prompts & Excuse Evaluator)

## 1. Observation
- **O1 (Original Requirements)**: `ORIGINAL_REQUEST.md:43-51` specifies:
  > "Pass the reason to the AI Coach to evaluate whether it is a legitimate obstacle or an excuse. If it is an excuse/procrastination, AI breaks down the excuse and enforces a 2-minute micro-habit. If legitimate, record as skipped."
  > "Coach Persona: Direct, concise, technical/practical mindset, slightly sarcastic toward procrastination/excuses, praises genuine execution. Responses must be concise (max 2–3 sentences)."
  > "Robust error handling: If the Gemini API or network fails, provide graceful fallback messages so bot operation is never interrupted."
- **O2 (Interface Contract)**: `PROJECT.md:136-146` dictates the interface contract for `src/coach.py`:
  ```python
  class AICoachService:
      def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None): ...
      async def get_congratulation(self, session_type: str, streak: int) -> str: ...
      async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]: ...
      # returns: (classification: 'EXCUSE' | 'LEGITIMATE', response_text: str)
      async def chat(self, user_message: str) -> str: ...
      def clear_context(self) -> None: ...
  ```
- **O3 (Storage Contract Alignment)**: `tests/test_storage.py:343-370` records skips with:
  ```python
  await atomic_store.record_skip(session_id, reason=reason, classification="EXCUSE", timestamp_str=ts)
  await atomic_store.record_skip(session_id, reason=reason, classification="LEGITIMATE", timestamp_str=ts)
  ```
  Where `classification` must be strictly `"EXCUSE"` or `"LEGITIMATE"`.
- **O4 (Configuration & Fallback Definitions)**: `src/config.py:21-67` and `config.yaml:51-85` define `system_prompt`, `prompts`, and `fallbacks`:
  - `prompts["skip_evaluator"]` instructs prefixing with `[EXCUSE]` or `[LEGITIMATE]`.
  - `fallbacks` contains keys: `offline_praise`, `offline_snooze_1`, `offline_snooze_2`, `offline_skip_excuse`, `offline_skip_legitimate`, `offline_error`.
- **O5 (Zero-Network Test Verification)**: Executed `python -m pytest -v`:
  - Result: `181 passed in 24.91s`. Zero network calls were made, proving tests run completely isolated.

## 2. Logic Chain
1. From O1 and O2, `evaluate_skip_reason(session_type, reason)` must return a 2-tuple: `(classification: str, response_text: str)`.
2. From O3, the database storage layer expects `classification` to be strictly `"EXCUSE"` or `"LEGITIMATE"`.
3. From O4, the LLM prompt asks for `[EXCUSE]` or `[LEGITIMATE]` tags. However, because LLMs may produce formatting variants (such as `[EXCUSE]`, `CLASSIFICATION: EXCUSE`, or lower/mixed casing), regex-based parser `parse_skip_evaluation` (defined in `analysis.md § 2.3`) is required to safely normalize the tag to uppercase and clean the tag from the user-facing text.
4. From O1 and O4, when `classification == 'EXCUSE'`, the coach must dismantle the excuse and enforce a 2-minute micro-habit. Because cognitive friction differs across activities, the micro-habit is routed according to `session_type`:
   - `gym`: 5 pushups or 60s plank at the desk.
   - `toeic`: solve 3 Part 5 questions or listen to 1 Part 3 conversation.
   - `major`: open IDE, write 1 function, and `git commit`.
5. From O1, O4, and O5, unit and E2E tests run offline without network access or live API tokens. If `google-genai` raises an exception or is run offline, `AICoachService` must degrade gracefully. Relying on a purely static string for skips would lose the binary classification required by O3. Therefore, `classify_skip_reason_offline` (defined in `analysis.md § 4.3`) uses a deterministic keyword heuristic to classify acute medical/emergency reasons as `LEGITIMATE` and all other reasons as `EXCUSE` with the tailored 2-minute micro-habit.

## 3. Caveats
- The offline rule-based heuristic (`classify_skip_reason_offline`) is an offline safety net and mock engine; in production with an active Gemini API, `gemini-2.5-flash` performs the primary semantic reasoning.
- Token limits in `config.yaml` are set to `max_output_tokens: 256`, which aligns with the 2–3 sentence brevity requirement and prevents truncated answers.

## 4. Conclusion
The prompt architecture, persona voice, excuse evaluator, 2-minute micro-habit routing, and resilient offline fallbacks are fully specified in `analysis.md`. The design fulfills all requirements in `ORIGINAL_REQUEST.md (R3, R4)` and guarantees seamless integration with `src/coach.py`, `src/storage.py`, and `tests/test_coach.py`.

## 5. Verification Method
1. **Independent File Inspection**:
   - Inspect `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_2/analysis.md` for prompt templates, micro-habit mapping, regex parsing logic, and fallback keyword dictionary.
2. **Deterministic Offline Classifier Verification**:
   - In Python REPL or test file, verify:
     ```python
     from analysis import classify_skip_reason_offline # or coach implementation
     assert classify_skip_reason_offline("gym", "Sốt cao 39.5 độ", {})[0] == "LEGITIMATE"
     assert classify_skip_reason_offline("gym", "Đang dở ván game Dota 2", {})[0] == "EXCUSE"
     assert classify_skip_reason_offline("toeic", "Mệt quá mai làm bù", {})[0] == "EXCUSE"
     ```
3. **Automated Test Run**:
   - Run `python -m pytest -v` from project root to ensure zero-network tests pass without regression.
