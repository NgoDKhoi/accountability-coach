# Dispatch: Milestone 2 Explorer 2 — Persona, Prompts & Excuse Evaluator

## Task Assignment
- Role: `teamwork_preview_explorer`
- Working Directory: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_2/`
- Mission: Investigate persona system instructions, prompt engineering, excuse vs legitimate obstacle classification, and resilient offline fallbacks.

## Required Reading
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md`

## Investigation Focus
1. Coach Persona: IT student & indie game developer context, Vietnamese language, tough love, max 2-3 sentences, slightly sarcastic toward procrastination, encouraging for genuine completion.
2. Excuse vs Legitimate Obstacle Evaluator:
   - Classification logic: `EXCUSE` vs `LEGITIMATE`.
   - Prompt format: structured response (e.g. `CLASSIFICATION: EXCUSE\nRESPONSE: ...` or JSON schema).
   - Micro-habit challenge: When classified as `EXCUSE`, enforce a 2-minute micro-habit (e.g., "Mở IDE viết 1 hàm duy nhất", "Làm đúng 5 câu TOEIC rồi tính").
3. Fallback Responses: Persona-matched pre-baked fallbacks when API times out or is offline (`fallbacks` from `config.yaml`).
4. Deliver `analysis.md` and `handoff.md` with prompt templates and evaluation logic.


## 2026-10-03T11:59:52Z
[Message] sender=ac41226a-6cc6-45bc-9027-605104e502f4
You are teamwork_preview_explorer for Milestone 2 (Explorer 2).
Your working directory: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_2/
Please read:
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m2_2/DISPATCH.md

Investigate IT & Game Dev coach persona (Vietnamese, 2-3 sentences), excuse vs legitimate obstacle classification, 2-minute micro-habit routing, and resilient offline fallbacks.
Deliver analysis.md and handoff.md in your directory. When done, message the orchestrator.
