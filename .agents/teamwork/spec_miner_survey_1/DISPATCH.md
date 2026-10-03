# Task Assignment: Survey Phase - Specification Mining

## 2026-10-03T09:25:00Z
You are teamwork_preview_spec_miner for the Survey Phase.
Your assigned working directory is: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/spec_miner_survey_1/
Please immediately read the authoritative requirements in:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
Also read your dispatch task at:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/spec_miner_survey_1/DISPATCH.md

Your task:
- Mine and document all detailed specifications across R1 - R6 and acceptance criteria:
  1. Telegram Bot Core & Security: commands, unauthorized handling (drop or deny), environment vars.
  2. APScheduler: Asia/Ho_Chi_Minh timezone, Gym schedule windows and triggers, TOEIC 7-day rotation, Major subject daily trigger, dynamic message formatting with inline buttons.
  3. Inline actions & state machine: Done flow (streak increment, records.json update, AI congrats), Snooze flow (15-min one-shot job, max 2 limit, escalating firmness), Skip reason flow (user justification text capture, Gemini reason evaluation: excuse vs legitimate obstacle, 2-minute micro-habit enforcement vs skip).
  4. Gemini AI Coach: google-genai library, gemini-2.5-flash model, persona rules (direct, concise 2-3 sentences, sarcastic to procrastination, praise execution), short-term sliding context window (6-10 messages), fallback on error/offline.
  5. Atomic JSON Persistence: data/records.json schema, fields, atomic write technique (temp file + rename/replace), streak calculation rules across calendar days.
  6. Test suite requirements: pytest + pytest-asyncio, mocking Telegram and Gemini, 100% pass without real tokens or internet.
  7. Files to deliver: .env.example, config.yaml, requirements.txt, Dockerfile, docker-compose.yml, start.sh, start.bat, src/, tests/.

Output:
Write your full detailed specification analysis to:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/spec_miner_survey_1/analysis.md
and a complete handoff report to:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/spec_miner_survey_1/handoff.md
Update progress.md in your directory as you work.
When finished, send a message to the orchestrator.
