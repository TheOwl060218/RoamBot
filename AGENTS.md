# RoamBot conversational business development

Read `docs/PROJECT_HANDOFF.md`, inspect the branch and working tree, and use current
code and current verification evidence as the source of truth.

- This branch is authorized feature development; the competition archive is frozen.
- Preserve other contributors' changes. Do not reset, clean, or stage the shared checkout.
- Do not create subagents. Do not change the configured model or deploy without a new request.
- Automated tests use Mock and isolated databases. Real provider tests require explicit user authorization.
- The user authorized limited real-model acceptance on 2026-10-15 for this task, with no deployment.
- Never print, persist in reports, or commit API keys, vault unlock material, cookies or authentication tokens.
- Do not stop or restart the separate 8026 service. Test servers use separate ports.
- Reuse existing authorization, CSRF, invitation identity and business-state checks.
- Keep existing buttons, beach/glass styling and layered transitions.
- Distinguish implemented code, Mock tests, browser interactions and real-model evidence.
- Update the handoff and acceptance record when project status changes.
- Keep Railway on one replica while SQLite is used. `REFLECTION.md` is student-authored.
