# RoamBot Codex Entry

Before working on this repository, read `docs/PROJECT_HANDOFF.md` and verify the
current Git branch and working tree. Treat current code and Git state as the
source of truth; dated handoff files are historical snapshots.

This project is in final course-delivery closeout, not feature development.

- Do not redesign confirmed product behavior or reopen resolved UI topics without new reproducible evidence.
- Do not create subagents or repeat the full test suite for documentation-only work.
- Automated checks must use Mock/demo mode. Do not run real provider tests unless the user explicitly requests them.
- Never ask for, print, store, or commit API keys, the credential-vault master password, cookies, or tokens.
- Keep Railway on one replica because production persistence uses SQLite on the mounted `/data` volume.
- `REFLECTION.md` must be written by the student from personal experience. AI may organize or proofread text the student supplies, but must not ghostwrite it.
- When project status changes, update `docs/PROJECT_HANDOFF.md` and any affected delivery evidence in the same documentation change.
