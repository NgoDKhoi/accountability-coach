# Handoff Report: Milestone 1 Storage & Persistence Specification

**Agent**: teamwork_preview_explorer (explorer_m1_2)  
**Task**: Milestone 1 - Atomic Storage & Streak Engine Specification  
**Recipient**: orchestrator (`ac41226a-6cc6-45bc-9027-605104e502f4`) / Milestone 1 Implementer  
**Working Directory**: `.agents/teamwork/explorer_m1_2/`  

---

## 1. Observation

1. **Windows NTFS File Locking Trap**:
   Running `tempfile.NamedTemporaryFile` directly into `os.replace` without closing the file handle produced verbatim:
   ```text
   Traceback (most recent call last):
     File "<string>", line 1, in <module>
       import tempfile, os; f = tempfile.NamedTemporaryFile('w', dir='.', delete=False); f.write('{}'); os.replace(f.name, 'test_tmp.json')
   PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\khoi1\\Documents\\antigravity\\serene-bohr\\tmpgxzogbjj' -> 'test_tmp.json'
   ```
2. **Handle Closure Fix**:
   Executing the 4-step sequence (`temp_file.flush()`, `os.fsync(temp_file.fileno())`, `temp_file.close()`, `os.replace(temp_path, target_path)`) exited with return code `0` and verified atomic replacement on Windows NTFS.
3. **Timezone Availability**:
   Python 3.12 standard library `zoneinfo` verified:
   `from zoneinfo import ZoneInfo; tz = ZoneInfo('Asia/Ho_Chi_Minh'); now = datetime.now(tz)` resolved cleanly to `2026-10-03T16:37:56.235724+07:00` (UTC+7).
4. **Concurrency Safety Benchmark**:
   Tested 50 concurrent `asyncio` coroutines performing read-modify-write operations on a single file using `asyncio.Lock` and `asyncio.to_thread`. Output: `Final counter: 50`, return code `0`, zero file lock collisions.
5. **Streak Engine & Session Lifecycle Verification**:
   Executed a multi-day streak and session state lifecycle simulation:
   - Day 1 first checkin: `current_streak=1`, `best_streak=1`, `total_completions=1`.
   - Day 1 second checkin (same day): `current_streak=1` (idempotent), `total_completions=2`.
   - Day 2 consecutive checkin: `current_streak=2`, `best_streak=2`, `total_completions=3`.
   - Day 5 gap checkin (+3 days): `current_streak=1` (reset to 1), `best_streak=2` (preserved), `total_completions=4`.
   - Snooze progression: `snooze_count=1`, then `snooze_count=2`, status=`snoozed`.
   - Skip justification flow: status=`skipped`, reason=`"Sốt 39 độ"`, classification=`"LEGITIMATE"`, `awaiting_reason` cleared.
   Output: `All comprehensive integration tests PASSED successfully!` (exit code `0`).
6. **Interface Contract Compliance**:
   Checked `orchestrator/PROJECT.md` lines 113–133 and confirmed exact interface alignment for `StreakData` dataclass and `AtomicJsonStore` methods (`load_data`, `save_data`, `get_streak`, `record_completion`, `record_snooze`, `record_skip`, `get_session_status`).

---

## 2. Logic Chain

1. **Obs 1 & 2 $\rightarrow$ Atomic Write Design**: Because Windows NTFS enforces mandatory file sharing locks, keeping a file descriptor open during `os.replace` triggers fatal `WinError 32`. Therefore, the atomic write protocol in `AtomicJsonStore._sync_write` must explicitly call `temp_file.flush()`, `os.fsync(temp_file.fileno())`, and `temp_file.close()` prior to `os.replace`.
2. **Obs 2 $\rightarrow$ Same-Directory File Placement**: Because `os.replace` is only atomic when source and target reside on the same filesystem volume (avoiding `EXDEV` cross-device link errors, especially inside Docker mounts), temporary files must be created directly within `dir=os.path.dirname(self.file_path)` (i.e. `data/`).
3. **Obs 4 $\rightarrow$ Concurrency Architecture**: Because Telegram webhook/polling updates and APScheduler background triggers run concurrently on the same `asyncio` loop, wrapping store mutations in `async with self._lock:` and offloading disk I/O via `asyncio.to_thread` guarantees serialization and non-blocking operation.
4. **Obs 3 & 5 $\rightarrow$ Calendar Streak Accounting**: By evaluating date deltas $\Delta = D_{today} - D_{last}$ in `Asia/Ho_Chi_Minh`:
   - $\Delta = 0$ is idempotent (streak unchanged, completions count incremented).
   - $\Delta = 1$ increments `current_streak` and advances `best_streak`.
   - $\Delta > 1$ resets `current_streak` to `1` while keeping `best_streak` intact.
   Accepting an optional `today_str: Optional[str]` allows deterministic testing without mocking system time while defaulting to live local time in production.
5. **Obs 5 & 6 $\rightarrow$ Session State Machine**: Tracking `pending`, `snoozed` (with `snooze_count` capped at 2), `skipped` (with reason and classification), and `awaiting_reason` satisfies Requirements R3 and R5 completely.

---

## 3. Caveats

1. **Timezone Package**: While `zoneinfo` is standard library in Python 3.9+, minimal Linux/Docker images require `tzdata` in `requirements.txt` to populate the IANA database.
2. **Process Scope**: `asyncio.Lock` synchronizes coroutines within a single process. Since the bot is deployed as a single standalone container/process per `PROJECT.md`, in-process locking combined with atomic file replacement is completely sufficient.
3. **No External Network Dependencies**: The persistence store uses only Python standard library modules (`os`, `json`, `asyncio`, `tempfile`, `dataclasses`, `datetime`, `zoneinfo`, `copy`). No third-party packages are required for `src/storage.py`.

---

## 4. Conclusion

1. The exact architecture and production-ready implementation for `src/storage.py` and `data/records.json` is fully specified and empirically validated.
2. All requirements from `ORIGINAL_REQUEST.md` (R3, R5) and contracts from `PROJECT.md` are completely met.
3. Comprehensive test suite scenarios have been defined for explorer_m1_3 (`tests/test_storage.py`).
4. Full specifications and source blueprints are documented in:
   `.agents/teamwork/explorer_m1_2/analysis.md`

---

## 5. Verification Method

To independently verify the complete storage specification and streak engine:

Run the following command in the project root:
```powershell
python -c "
import asyncio, os, tempfile, json, copy
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import date, datetime
from zoneinfo import ZoneInfo

HO_CHI_MINH_TZ = ZoneInfo('Asia/Ho_Chi_Minh')

@dataclass
class StreakData:
    current_streak: int
    best_streak: int
    last_completed_date: Optional[str]
    total_completions: int

DEFAULT_DATA = {
    'version': 1,
    'streak': {'current_streak': 0, 'best_streak': 0, 'last_completed_date': None, 'total_completions': 0},
    'sessions': {},
    'active_sessions': {},
    'awaiting_reason': None,
    'history': []
}

class AtomicJsonStore:
    def __init__(self, file_path='data/records.json'):
        self.file_path = os.path.abspath(file_path)
        self.dir_name = os.path.dirname(self.file_path)
        self._lock = asyncio.Lock()
        os.makedirs(self.dir_name, exist_ok=True)

    def _sync_read(self):
        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) == 0:
            d = copy.deepcopy(DEFAULT_DATA); self._sync_write(d); return d
        with open(self.file_path, 'r', encoding='utf-8') as f: return json.load(f)

    def _sync_write(self, data):
        os.makedirs(self.dir_name, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile('w', dir=self.dir_name, delete=False, encoding='utf-8')
        p = tmp.name
        try:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp.flush(); os.fsync(tmp.fileno()); tmp.close()
            os.replace(p, self.file_path)
        except Exception:
            if os.path.exists(p): os.remove(p)
            raise

    async def record_completion(self, sid, stype, today_str):
        async with self._lock:
            data = await asyncio.to_thread(self._sync_read)
            s = data['streak']
            last = s['last_completed_date']
            curr, best, tot = s['current_streak'], s['best_streak'], s['total_completions'] + 1
            today = date.fromisoformat(today_str)
            if last is None: curr, best, last = 1, max(best, 1), today_str
            else:
                d = (today - date.fromisoformat(last)).days
                if d == 1: curr += 1; best = max(best, curr); last = today_str
                elif d > 1: curr, best, last = 1, max(best, 1), today_str
            s['current_streak'], s['best_streak'], s['last_completed_date'], s['total_completions'] = curr, best, last, tot
            await asyncio.to_thread(self._sync_write, data)
            return StreakData(curr, best, last, tot)

async def test():
    store = AtomicJsonStore('test_verify.json')
    s1 = await store.record_completion('s1', 'gym', '2026-10-01')
    assert (s1.current_streak, s1.best_streak, s1.total_completions) == (1, 1, 1)
    s2 = await store.record_completion('s2', 'toeic', '2026-10-01')
    assert (s2.current_streak, s2.best_streak, s2.total_completions) == (1, 1, 2)
    s3 = await store.record_completion('s3', 'gym', '2026-10-02')
    assert (s3.current_streak, s3.best_streak, s3.total_completions) == (2, 2, 3)
    s4 = await store.record_completion('s4', 'gym', '2026-10-05')
    assert (s4.current_streak, s4.best_streak, s4.total_completions) == (1, 2, 4)
    os.remove('test_verify.json')
    print('VERIFICATION SUCCESSFUL')

asyncio.run(test())
"
```

**Expected output**:
```text
VERIFICATION SUCCESSFUL
```

**Invalidation conditions**:
- Any `PermissionError: [WinError 32]` raised during atomic file replacement.
- Any non-deterministic streak result for same-day, consecutive, or gap days.
- Inability to handle missing or 0-byte persistence files.
