# TEST_INFRA — Autonomous Telegram Personal Accountability Coach

## 1. Test Philosophy & Design Principles

The end-to-end (E2E) testing infrastructure for the Autonomous Telegram Personal Accountability Coach is engineered strictly as an **opaque-box, requirement-driven, zero-network test suite**.

### Core Tenets
1. **Opaque-Box Requirement-Driven Verification**:
   Tests evaluate visible observable behaviors, interface contracts, message contents, state transitions, and persistent storage mutations against `ORIGINAL_REQUEST.md` and `PROJECT.md`, rather than internal module implementations.
2. **Zero External Network Dependencies**:
   All external network I/O—including Telegram Bot API HTTP/long-polling calls and Google Gemini AI API endpoints—is intercepted and simulated using high-fidelity test doubles and mock fixtures. Tests must run 100% offline, deterministically, and fast without requiring API keys or internet access.
3. **Timezone & Time Advance Simulation**:
   Proactive scheduling and calendar-day streaks operate in the `Asia/Ho_Chi_Minh` (UTC+7) timezone. The test harness allows arbitrary virtual time progression without real-time delays or clock skew.
4. **Crash-Safe Persistence Integrity**:
   Storage operations are validated against crash safety, concurrency races, Windows file replacement semantics, and automated corruption recovery.
5. **Strict Security Isolation**:
   Telegram authorization filters are tested with adversarial inputs to ensure unauthorized chat IDs are permanently dropped or denied without triggering AI quota consumption.

---

## 2. Test Architecture

The testing framework is built on `pytest` and `pytest-asyncio`, organized into a 4-tier progressive hierarchy:

```
tests/
├── conftest.py                   # Shared fixtures, environment setups, mock doubles
├── mock_services.py              # Interface contract simulators & dynamic fallbacks
├── test_config.py                # Unit tests for configuration & env decoupling (M1)
├── test_storage.py               # Unit tests for atomic persistence & streaks (M1)
├── test_m1_adversarial.py        # Stress & crash safety tests (M1)
├── test_fuzz_storage_config.py   # Boundary & schema fuzzing (M1)
├── test_e2e_tier1_features.py    # Tier 1: Happy-path coverage of all 40 features
├── test_e2e_tier2_boundaries.py  # Tier 2: Boundary, corner case, & stress testing
├── test_e2e_tier3_pairwise.py    # Tier 3: Cross-feature pairwise interactions
└── test_e2e_tier4_scenarios.py   # Tier 4: Real-world end-to-end multi-step scenarios
```

### Mocking Layers in `tests/conftest.py` & `tests/mock_services.py`
- **Telegram Bot Mocking (`MockTelegramBot`, `MockApplication`, `MockUpdate`)**:
  Simulates message dispatch, inline button callbacks (`done`, `snooze`, `skip`), message editing, and authorization verification without contacting `api.telegram.org`.
- **Gemini AI Mocking (`MockGeminiClient`, `MockAICoachService`)**:
  Simulates `gemini-2.5-flash` model outputs for praise, excuse analysis (`[EXCUSE]` + 2-minute micro-habit), legitimate skip approvals (`[LEGITIMATE]`), and free-form coaching chat, with controllable fault injection (timeouts, API errors, offline fallback validation).
- **APScheduler Simulation (`MockSchedulerService`)**:
  Simulates cron triggers for Gym, TOEIC syllabus rotation, and Major study sessions, as well as dynamic one-shot `DateTrigger` 15-minute snooze jobs, with precise trigger execution and job cancellation.
- **Atomic Storage Isolation**:
  Each test executes against an isolated `tmp_path / "data" / "records.json"`, ensuring complete test independence.

---

## 3. Feature Inventory Mapping Across 4 Tiers

All 40 features identified in `PROJECT.md § Feature Inventory` are systematically tested across the 4 tiers:

| # | Feature Name | Tier 1 (Happy Path) | Tier 2 (Boundaries) | Tier 3 (Pairwise) | Tier 4 (Scenarios) |
|---|--------------|---------------------|---------------------|-------------------|--------------------|
| 1 | Whitelist Chat ID Filter | `test_f01_whitelist_allowed` | `test_t2_whitelist_variants` | `test_t3_unauthorized_callbacks` | `test_t4_unauthorized_intrusion` |
| 2 | Secret / Config Decoupling | `test_f02_secret_config_decoupling` | `test_t2_missing_malformed_env` | `test_t3_dynamic_config_reload` | `test_t4_full_lifecycle_boot` |
| 3 | Bot Lifecycle & Async Boot | `test_f03_bot_lifecycle_boot` | `test_t2_rapid_shutdown_restart` | `test_t3_boot_with_existing_store` | `test_t4_bot_restart_recovery` |
| 4 | `/start` Command Handler | `test_f04_start_command` | `test_t2_command_argument_extremes` | `test_t3_start_after_session_active`| `test_t4_day1_onboarding` |
| 5 | `/help` Command Handler | `test_f05_help_command` | `test_t2_help_special_characters` | `test_t3_help_mid_snooze` | `test_t4_user_guidance_flow` |
| 6 | `/status` / Streak Command | `test_f06_status_command` | `test_t2_status_zero_streak` | `test_t3_done_then_status` | `test_t4_streak_reporting_cycle` |
| 7 | Timezone-Aware Scheduler Setup| `test_f07_scheduler_timezone` | `test_t2_timezone_dst_rollover` | `test_t3_timezone_streak_alignment` | `test_t4_multi_day_schedule_cycle`|
| 8 | Gym Reminder (Mon, Tue, Thu)| `test_f08_gym_split1_reminder` | `test_t2_gym_split1_exact_minute` | `test_t3_gym_then_toeic` | `test_t4_weekly_workout_streak` |
| 9 | Gym Reminder (Wed, Sat) | `test_f09_gym_split2_reminder` | `test_t2_gym_split2_exact_minute` | `test_t3_split2_snooze_cycle` | `test_t4_weekly_workout_streak` |
| 10 | TOEIC Study Session Trigger | `test_f10_toeic_trigger` | `test_t2_toeic_boundary_time` | `test_t3_toeic_snooze_then_skip` | `test_t4_7day_toeic_rotation` |
| 11 | TOEIC 7-Day Syllabus Rotation| `test_f11_toeic_rotation` | `test_t2_rotation_modulo_overflow` | `test_t3_rotation_config_override`| `test_t4_7day_toeic_rotation` |
| 12 | Major Subject Study Trigger | `test_f12_major_trigger` | `test_t2_major_boundary_time` | `test_t3_major_after_toeic` | `test_t4_daily_three_session_cycle`|
| 13 | Inline Keyboard Generator | `test_f13_inline_keyboard` | `test_t2_button_payload_encoding` | `test_t3_keyboard_state_transitions`| `test_t4_interactive_inline_flow`|
| 14 | "Done" Completion Handler | `test_f14_done_action` | `test_t2_duplicate_done_clicks` | `test_t3_snooze_then_done` | `test_t4_escalating_snooze_to_done`|
| 15 | "Snooze 15m" Handler | `test_f15_snooze_action` | `test_t2_snooze_at_boundary` | `test_t3_snooze_then_skip` | `test_t4_multi_snooze_journey` |
| 16 | Snooze Cap & Escalation | `test_f16_snooze_limit_cap` | `test_t2_snooze_exceed_cap_attempt` | `test_t3_snooze_cap_then_excuse` | `test_t4_escalating_snooze_to_done`|
| 17 | Snooze Job Execution | `test_f17_snooze_job_fire` | `test_t2_snooze_job_jitter` | `test_t3_snooze_job_cancel_on_done`| `test_t4_multi_session_timeline` |
| 18 | "Skip with Reason" Trigger | `test_f18_skip_trigger` | `test_t2_skip_empty_reason` | `test_t3_skip_after_snooze` | `test_t4_excuse_challenge_recovery`|
| 19 | Skip Reason Evaluation Flow | `test_f19_skip_eval_flow` | `test_t2_reason_extreme_lengths` | `test_t3_skip_eval_network_failure`| `test_t4_excuse_challenge_recovery`|
| 20 | 2-Minute Micro-Habit Enforce | `test_f20_micro_habit_challenge`| `test_t2_micro_habit_compliance` | `test_t3_excuse_then_micro_habit` | `test_t4_excuse_challenge_recovery`|
| 21 | Legitimate Skip Approval | `test_f21_legitimate_skip` | `test_t2_legitimate_edge_cases` | `test_t3_legitimate_preserves_streak`| `test_t4_daily_three_session_cycle`|
| 22 | `google-genai` Integration | `test_f22_genai_integration` | `test_t2_genai_empty_response` | `test_t3_genai_rate_limit_backoff`| `test_t4_ai_coaching_dialogue` |
| 23 | IT & Game Dev Coach Persona | `test_f23_coach_persona` | `test_t2_persona_length_limit` | `test_t3_persona_tone_consistency` | `test_t4_full_conversation_flow` |
| 24 | Sliding Context Window | `test_f24_sliding_window` | `test_t2_window_eviction_boundary`| `test_t3_window_with_session_events`| `test_t4_multi_turn_coaching_chat` |
| 25 | Graceful Offline Fallback | `test_f25_offline_fallback` | `test_t2_complete_network_blackout`| `test_t3_fallback_during_skip_eval`| `test_t4_offline_recovery_flow` |
| 26 | Reactive Free-Form Chat | `test_f26_reactive_chat` | `test_t2_chat_special_markdown` | `test_t3_chat_while_awaiting_reason`| `test_t4_ai_coaching_dialogue` |
| 27 | Data Directory Auto-Creation | `test_f27_data_dir_creation` | `test_t2_nested_data_dir_creation` | `test_t3_dir_creation_concurrent` | `test_t4_cold_boot_persistence` |
| 28 | Atomic JSON File Write | `test_f28_atomic_json_write` | `test_t2_atomic_write_disk_full` | `test_t3_atomic_write_concurrency` | `test_t4_persistence_under_load` |
| 29 | JSON Schema Validation | `test_f29_json_schema_valid` | `test_t2_corrupt_json_keys` | `test_t3_schema_migration_safety` | `test_t4_long_term_data_integrity`|
| 30 | Calendar Day Streak Tracking| `test_f30_calendar_streak` | `test_t2_streak_leap_year_rollover`| `test_t3_streak_multi_session_day` | `test_t4_weekly_workout_streak` |
| 31 | Offline Telegram API Mocking| `test_f31_offline_telegram_mock`| `test_t2_telegram_mock_exceptions` | `test_t3_telegram_mock_event_stream`| `test_t4_end_to_end_mock_validation`|
| 32 | Offline Gemini API Mocking | `test_f32_offline_gemini_mock` | `test_t2_gemini_mock_malformed` | `test_t3_gemini_mock_error_stream` | `test_t4_end_to_end_mock_validation`|
| 33 | APScheduler Trigger Verif | `test_f33_scheduler_verification`| `test_t2_scheduler_drift_check` | `test_t3_scheduler_job_reschedule` | `test_t4_schedule_firing_timeline`|
| 34 | State Machine & Snooze Tests| `test_f34_state_machine_tests` | `test_t2_state_machine_invalid_tx`| `test_t3_state_race_conditions` | `test_t4_complex_state_progression`|
| 35 | Atomic Persistence Tests | `test_f35_persistence_tests` | `test_t2_persistence_stress_test` | `test_t3_persistence_recovery_test`| `test_t4_persistence_under_load` |
| 36 | Security Whitelist Tests | `test_f36_security_tests` | `test_t2_security_boundary_ids` | `test_t3_security_callback_forgery`| `test_t4_unauthorized_intrusion` |
| 37 | `.env.example` Template | `test_f37_env_example_spec` | `test_t2_env_missing_keys_check` | `test_t3_env_override_priority` | `test_t4_configuration_deployment` |
| 38 | `config.yaml` Configuration | `test_f38_config_yaml_spec` | `test_t2_config_yaml_syntax_fuzz` | `test_t3_config_yaml_to_objects` | `test_t4_configuration_deployment` |
| 39 | `Dockerfile` & `docker-compose`| `test_f39_docker_specs` | `test_t2_dockerfile_syntax_checks`| `test_t3_docker_volume_mapping` | `test_t4_deployment_readiness` |
| 40 | Single-Click Startup Scripts | `test_f40_startup_scripts_spec`| `test_t2_script_line_endings_syntax`| `test_t3_script_venv_activation` | `test_t4_deployment_readiness` |

---

## 4. Test Runner & Execution

### Execution Command
To run all E2E test suites with verbose output and test timing:
```bash
python -m pytest tests/test_e2e_tier1_features.py tests/test_e2e_tier2_boundaries.py tests/test_e2e_tier3_pairwise.py tests/test_e2e_tier4_scenarios.py -v
```

### Full Project Test Run
To run all unit, fuzz, adversarial, and E2E test suites:
```bash
python -m pytest -v
```

### Zero Network Guarantee
Execution operates strictly in local memory and filesystem. No socket connections to Telegram (`api.telegram.org`) or Google (`generativelanguage.googleapis.com`) are established.
