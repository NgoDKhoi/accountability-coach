# Dispatch: Milestone 2 Implementation Worker

## Task Assignment
- Role: `teamwork_preview_worker`
- Working Directory: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m2_1/`
- Mission: Implement `AICoachService` in `src/coach.py` and comprehensive unit test suite in `tests/test_coach.py` conforming to interface contracts in `PROJECT.md` and explorer blueprints.

## Required Reading
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md` (Lines 136–146)
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_1/handoff.md` (SDK, async client, offline mock injection)
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_2/handoff.md` (Persona, excuse classification, micro-habit routing, offline fallback heuristics)
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_3/handoff.md` (Sliding deque history, leading model pruning, 32 unit tests blueprint)

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership
- Exclusively owns: `src/coach.py`, `tests/test_coach.py`, and additions to `tests/conftest.py`.

## Implementation Requirements
1. `src/coach.py`:
   - Implement `AICoachService` with constructor:
     `def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None)`
   - Asynchronous methods:
     - `async def get_congratulation(self, session_type: str, streak: int) -> str`
     - `async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]` (strictly returns `('EXCUSE' | 'LEGITIMATE', response_text)`)
     - `async def chat(self, user_message: str) -> str`
     - `def clear_context(self) -> None`
   - Use Google GenAI SDK: `from google import genai` and `from google.genai import types, errors`.
   - Support zero-network dependency injection (`client=mock_client`).
   - Async calls via `await self.client.aio.models.generate_content(...)` with 15s timeout.
   - Persona system prompt: Vietnamese, IT student & indie game dev context, max 2-3 sentences.
   - Micro-habit routing for excuses:
     - `gym`: 5 pushups or 60s plank.
     - `toeic`: 3 Part 5 questions or 1 Part 3 conversation.
     - `major`: open IDE, write 1 function, git commit.
   - Sliding context buffer using `collections.deque(maxlen=10)` storing `types.Content`.
   - Implement `_get_sanitized_history_contents()` to prune leading `model` turns to preserve Gemini alternating protocol.
   - Offline fallback engine with keyword heuristics for resilient zero-network execution.
2. `tests/test_coach.py`:
   - Implement the 32 unit tests designed by `explorer_m2_3`.
   - Verify 100% pass offline without external internet calls.
3. Verification:
   - Run `python -m pytest tests/test_coach.py -v`
   - Run `python -m pytest tests/test_config.py tests/test_storage.py tests/test_coach.py -v`
   - Run `python -m pytest tests/test_e2e_tier1_features.py -v`
4. Deliver `analysis.md` and `handoff.md` in your working directory, then message the orchestrator.

## 2026-10-03T12:16:34Z
You are teamwork_preview_worker for Milestone 2.
Your working directory: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m2_1/
Please read:
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m2_1/DISPATCH.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_1/handoff.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_2/handoff.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_3/handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Implement AICoachService in src/coach.py and 32 unit tests in tests/test_coach.py.
Follow all interface contracts, asynchronous patterns, sliding history pruning, micro-habit routing, and offline fallbacks.
Run tests:
python -m pytest tests/test_coach.py -v
python -m pytest tests/test_config.py tests/test_storage.py tests/test_coach.py -v
python -m pytest tests/test_e2e_tier1_features.py -v
Deliver analysis.md and handoff.md in your directory. When done, message the orchestrator.

