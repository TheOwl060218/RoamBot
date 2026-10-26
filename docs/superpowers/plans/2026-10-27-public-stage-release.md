# Public Stage Release Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; AGENTS.md forbids subagents and staging this shared checkout.

**Goal:** Publish the current local domestic RoamBot experience to the existing Railway public service.
**Architecture:** Add a validated runtime workflow selector so production can select the same source workflow as the local launcher. Freeze an allowlisted deployment bundle, preserve the existing provider model and persistent volume, and verify public build hashes and read-only API responses.
**Tech Stack:** FastAPI, Pydantic Settings, SQLite, React/Vite, Railway Dockerfile.
**Spec:** User request to update the existing public URL; docs/STAGE_SUMMARY_2026-10-26.md.

## Global Constraints
- No overseas expansion, model change, 8026 operation, shared-checkout staging, or automatic paid acceptance queries.
- One production replica and the existing /data volume; create a consistent pre-initialization SQLite backup. Railway snapshots require Pro and were unavailable.
- Never print/persist credentials; existing production secrets remain on the service.

## Review Focus
- Missing search key must be configured securely before source workflow can serve recommendations.
- Source workflow must be explicitly selected, not silently fall back to legacy.
- Existing database tables must remain compatible; only additive create_all is acceptable without a reviewed migration.
- Release bundle excludes local data, credentials, ignored runtime snapshots and untracked experiments.
- HTTP 200 is not proof of paid recommendation quality; report verification limits.

## Task 1: Runtime parity
- [x] Add settings/environment tests proving source selection, application-state propagation and invalid-value rejection; run to confirm expected failures.
- [x] Add Literal workflow setting with legacy compatibility default and set application state in create_app.
- [x] Run configuration/startup and relevant API tests; retain unrelated existing failures separately.

## Task 2: Release package and recovery
- [x] Confirm project/service/environment/domain/one replica, record old deployment ID and safe configuration presence.
- [x] Create consistent SQLite backup before application initialization; confirm integrity in production startup logs. Offline schema comparison preserves 15 old tables.
- [x] Freeze source and SHA256 manifest; after cloud pip build failure, use verified frontend and fixed offline Linux runtime wheels.
- [x] Configure source workflow, local-equivalent timeouts and missing existing search credential via stdin without exposing secrets. User explicitly authorized credential transfer after auto-review initially rejected it.

## Task 3: Publish and verify
- [x] Upload frozen bundle to the explicit existing production service, wait for build and runtime success.
- [x] Verify public frontend resource hashes, health, itinerary/region routes and production map configuration flags without provider calls or real-account writes.
- [x] Browser-check desktop homepage and actual navigation to explore; save screenshot and record remaining acceptance limitations. Mobile and later itinerary browser checks were not completed after two control timeouts; reuse unchanged build's prior local responsive evidence without claiming a fresh public-mobile pass.

Ruling: follow AGENTS.md's explicit prohibition on subagents and staging; perform release-focused self-review, not an independent code review. Preserve known existing test/lint issues in the release record.
