# Handoff Report: Milestone 1 (Config & Environment Specification)

**Agent:** `teamwork_preview_explorer` (explorer_m1_1)  
**Working Directory:** `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_1/`  
**Handoff Type:** Hard (Task complete)  
**Timestamp:** 2026-10-03T09:41:00Z  

---

## 1. Observation

1. **Authoritative Request File (`ORIGINAL_REQUEST.md`):**
   - File Path: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md`
   - Line 13–15: "Implement an asynchronous Telegram bot using `python-telegram-bot` (v20+). Enforce strict user authorization: only respond to and accept commands from the user matching `ALLOWED_CHAT_ID` configured via `.env`."
   - Line 15: "Provide clear setup instructions, environment template (`.env.example`), configuration file (`config.yaml`), containerization (`Dockerfile`, `docker-compose.yml`), and single-click startup scripts (`start.bat` for Windows and `start.sh` for Linux/macOS)."
   - Line 18–26: "Integrate an async scheduler using `APScheduler` (`AsyncIOScheduler`) configured for the `Asia/Ho_Chi_Minh` timezone. Schedules must be driven by `config.yaml` with the following baseline jobs: 1. Gym Session (1 hour): Mon, Tue, Thu at 17:15... Wed, Sat at 16:15... 2. TOEIC Study Session (1 hour): Daily at 19:25... dynamically pulling the day's focus topic based on a 7-day TOEIC parts rotation defined in `config.yaml`... 3. Major Subject Study & Preparation (1 hour): Daily at 20:40..."
   - Line 48–51: "Connect to Google Gemini API using `google-genai` with model `gemini-2.5-flash`. Coach Persona: Direct, concise... max 2–3 sentences... sliding context window (6–10 messages). Robust error handling: graceful fallback messages..."
   - Line 70–72: "Configuration separates secrets (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID` in `.env`) from operational parameters (schedules, TOEIC syllabus, prompts in `config.yaml`)."

2. **Project Blueprint & Interface Contracts (`orchestrator/PROJECT.md`):**
   - File Path: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md`
   - Lines 70–110 specify the exact interface contract for `src/config.py`:
     ```python
     @dataclass(frozen=True)
     class GymScheduleConfig:
         cron_days_split1: str # 'mon,tue,thu'
         time_split1: str      # '17:15'
         cron_days_split2: str # 'wed,sat'
         time_split2: str      # '16:15'
         duration_minutes: int # 60

     @dataclass(frozen=True)
     class ToeicScheduleConfig:
         time: str             # '19:25'
         duration_minutes: int # 60
         syllabus_rotation: List[str] # 7 parts (Mon-Sun)

     @dataclass(frozen=True)
     class MajorScheduleConfig:
         time: str             # '20:40'
         duration_minutes: int # 60

     @dataclass(frozen=True)
     class AppConfig:
         bot_token: str
         gemini_api_key: str
         allowed_chat_id: int
         timezone: str         # 'Asia/Ho_Chi_Minh'
         max_snoozes: int      # 2
         snooze_minutes: int   # 15
         context_window_size: int # 10
         gym: GymScheduleConfig
         toeic: ToeicScheduleConfig
         major: MajorScheduleConfig
         prompts: Dict[str, str]
         fallbacks: Dict[str, str]

     def load_config(config_path: str = "config.yaml", env_path: str = ".env") -> AppConfig: ...
     ```

3. **Workspace State:**
   - Workspace root `c:/Users/khoi1/Documents/antigravity/serene-bohr` is a greenfield repository containing `.git/` and `.agents/`.
   - Host Python environment is Python 3.14.4 on Windows with `ZoneInfo`, `PyYAML` (6.0.3), `python-dotenv` (1.0.1), and `tzdata` (2026.3) installed.

4. **Task Assignment (`DISPATCH.md`):**
   - File Path: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_1/DISPATCH.md`
   - Scope: "Analyze and recommend the exact implementation for `src/config.py`, `config.yaml`, `.env.example`, and requirements. Define dataclasses, validation rules (ALLOWED_CHAT_ID as int, required secrets, fallback values), YAML structure for Gym, TOEIC 7-day rotation, Major study, prompts, and limits."

---

## 2. Logic Chain

1. **Premise 1 (Decoupling Requirement):** Observation 1 & 2 establish that configuration must strictly separate secrets (`.env`) from operational parameters (`config.yaml`). Therefore, no secret token or chat ID should be stored in `config.yaml`, and no operational schedule or prompt should be hardcoded into `.env`.
2. **Premise 2 (Type & Boundary Safety):** Observation 1 requires `ALLOWED_CHAT_ID` to be configured via `.env` and used for strict authorization. Because environment variables are always read as strings from `os.environ`, `load_config` must validate and cast `ALLOWED_CHAT_ID` to a pure Python `int`, handling extraneous whitespace (`"  123456  "`), negative chat IDs (group chats), and rejecting non-numeric strings or zero with descriptive `ValueError`s.
3. **Premise 3 (Interface Alignment):** Observation 2 defines the exact dataclass contracts (`AppConfig`, `GymScheduleConfig`, `ToeicScheduleConfig`, `MajorScheduleConfig`). Any deviation in class names or required attribute names would break downstream modules and tests. Therefore, all dataclass structures in `src/config.py` match `PROJECT.md` line-for-line, while extending them with optional default attributes (`gemini_model`, `data_dir`, `records_file`, `micro_habit_duration_minutes`, `system_prompt`) and convenient helper methods (`get_part_for_weekday`, `hour_split1`, `mask_secret`).
4. **Premise 4 (Runtime Robustness & Fallbacks):** If `config.yaml` is partially missing prompt keys or fallback texts, raising `KeyError` at runtime during an offline outage would violate Requirement R4 ("graceful fallback messages so bot operation is never interrupted"). Therefore, `load_config` deep-merges YAML contents with default dictionaries (`DEFAULT_PROMPTS`, `DEFAULT_FALLBACKS`, `DEFAULT_SYSTEM_PROMPT`).
5. **Premise 5 (Zero-Network Test Isolation):** Unit tests frequently run with `monkeypatch.setenv()` without writing a physical `.env` file to disk. Therefore, `load_dotenv(dotenv_path=env_path, override=False)` must only be invoked if `env_path` exists on disk, and `os.environ` must be inspected directly.
6. **Inference & Conclusion:** The complete specification, sample configurations, full source code implementation (`proposed_config.py`), and test suite (`proposed_test_config.py`) have been synthesized and verified against these criteria.

---

## 3. Caveats

- **Operating System Timezone Database:** Windows NT does not include a system IANA timezone database. `tzdata` must remain in `requirements.txt` to ensure `zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")` operates correctly on Windows host machines.
- **Custom Config Paths:** In containerized or testing environments, operators can pass custom paths directly to `load_config(config_path, env_path)` or export `CONFIG_PATH` in environment variables.

---

## 4. Conclusion

Milestone 1 configuration and environment analysis is complete. The builder agent can immediately proceed to instantiate:
- `requirements.txt` from `proposed_requirements.txt`
- `.env.example` from `proposed_env.example`
- `config.yaml` from `proposed_config.yaml`
- `src/config.py` from `proposed_config.py`
- `tests/test_config.py` using test scenarios from `proposed_test_config.py`

All specifications fully satisfy Requirements R1–R7, adhere strictly to `PROJECT.md` interface contracts, and include comprehensive validation and fallback handling.

---

## 5. Verification Method

To independently verify this specification:
1. **Inspect Deliverable Files in Explorer Directory:**
   ```powershell
   # Confirm all proposed artifacts exist and are populated
   Get-ChildItem -Path .agents/teamwork/explorer_m1_1/
   ```
   Check contents of:
   - `analysis.md`
   - `proposed_config.py`
   - `proposed_config.yaml`
   - `proposed_env.example`
   - `proposed_requirements.txt`
   - `proposed_test_config.py`
2. **Verify Interface Contract Compliance:**
   Compare dataclasses in `proposed_config.py` against `orchestrator/PROJECT.md` lines 70–110. Confirm that:
   - `GymScheduleConfig` has `cron_days_split1`, `time_split1`, `cron_days_split2`, `time_split2`, `duration_minutes`.
   - `ToeicScheduleConfig` has `time`, `duration_minutes`, `syllabus_rotation`.
   - `MajorScheduleConfig` has `time`, `duration_minutes`.
   - `AppConfig` has all 12 positional/keyword attributes matching `PROJECT.md`.
3. **Verify Validation Coverage:**
   Review `proposed_test_config.py` to confirm that all 18 edge case test methods (missing secrets, invalid chat IDs, malformed YAML, timezone errors, TOEIC list/dict conversions) are accounted for.
