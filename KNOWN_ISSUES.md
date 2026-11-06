# Known Issues & Backlog

This document tracks known issues, technical debt, out-of-scope discoveries, and deferred findings in accordance with `AGENTS.md`.

---

## Active Issues
*None currently.*

---

## Technical Debt & Deferred Items
1. **Blueprint Document Missing from Workspace**:
   - `docs/BLUEPRINT.pdf` is not currently present in the project workspace directory.
   - *Impact*: Module 0 has proceeded using the comprehensive rules in `AGENTS.md`. Specific product specifications in the blueprint will be cross-referenced once uploaded.
2. **Local Environment Dependencies (Host Machine)**:
   - `node`, `docker`, and `psql` are not currently installed or not present in the system `PATH` on this host.
   - Python 3.12 and pip 25.0 are present.
   - *Impact*: Local running of Vite frontend and Docker Compose requires installing Node.js and Docker Desktop (or running tests via Python virtualenv and SQLite compatibility modes for unit tests, while full integration tests run in GitHub Actions CI where PostgreSQL and Node are standard).
3. **MFA / WebAuthn Support**:
   - Deferred to a later enhancement phase to keep initial session infrastructure lean and thoroughly audited. Baseline username + Argon2id password + secure session cookies will form the initial core.

---

## Resolved Issues
*None yet.*
