# Task Assignment: Milestone 1 Iteration 2 Worker - Storage Fix Implementation

Read:
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_r2_1/analysis.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_r2_2/analysis.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_r2_3/analysis.md`

Your Working Directory:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m1_r2/`

Files to modify:
- `src/storage.py`
- `tests/test_fuzz_storage_config.py`

Task Requirements:
1. In `src/storage.py` `_sync_write`:
   Guarantee file handle closure via `try...finally: temp_file.close()` before `os.replace` on success and before `os.remove` on failure.
2. In `src/storage.py` `_sync_read`:
   - Catch `(json.JSONDecodeError, OSError, UnicodeDecodeError)`.
   - Validate `if not isinstance(data, dict): raise json.JSONDecodeError("JSON root must be an object", "", 0)` so non-dict root types trigger backup and fallback initialization.
3. In `tests/test_fuzz_storage_config.py`:
   Update lines 395–452 (the 4 tests written by Challenger 2 that asserted unpatched defect presence) to assert the healed self-recovery behavior (e.g. valid recovery, no tmp file leaks).
4. Run all 4 test suites:
   `python -m pytest tests/test_config.py tests/test_storage.py tests/test_m1_adversarial.py tests/test_fuzz_storage_config.py -v`
   Ensure 181/181 tests pass 100%.
5. Deliver `analysis.md` and `handoff.md` in your directory.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.


## 2026-10-03T10:12:10Z
[Message] timestamp=2026-10-03T10:12:10Z sender=ac41226a-6cc6-45bc-9027-605104e502f4 priority=MESSAGE_PRIORITY_HIGH content=You are teamwork_preview_worker for Milestone 1 Iteration 2.
Your working directory: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m1_r2/
Read:
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m1_r2/DISPATCH.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_r2_1/analysis.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_r2_2/analysis.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_r2_3/analysis.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Apply the 3 storage fixes in src/storage.py:
1. Guarantee temp file closure in try...finally in _sync_write.
2. Catch UnicodeDecodeError and non-dict JSON roots in _sync_read.
3. Align tests in tests/test_fuzz_storage_config.py to assert healed recovery.
Run all 4 test suites:
python -m pytest tests/test_config.py tests/test_storage.py tests/test_m1_adversarial.py tests/test_fuzz_storage_config.py -v
Ensure all 181 tests pass 100%.
Deliver analysis.md and handoff.md in your directory. When done, message the orchestrator.
