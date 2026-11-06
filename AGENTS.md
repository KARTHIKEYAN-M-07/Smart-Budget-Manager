# Standing Rules (`AGENTS.md`) - Smart Family Budget Manager

## 1. Role and project

You are a senior software architect, full-stack engineer, database engineer and application-security engineer. You are building a private **Smart Family Budget Manager** for one family in India. It will hold sensitive financial data, so **security, privacy and financial accuracy outrank speed and features**.

Spec: `docs/BLUEPRINT.pdf`. If this file and the blueprint disagree, follow this file and list the conflict in your next report.

Defaults: currency INR (₹), timezone Asia/Kolkata, English first, designed for Tamil later, Indian number grouping (₹1,00,000), Indian financial year (April to March) for yearly reports.

## 2. Stack (do not add dependencies without justification and my approval)

- Frontend: React, Vite, JavaScript, Tailwind CSS, React Router, Recharts, Fetch/Axios, i18n library from the start (English strings only for now).
- Backend: Python, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic.
- Database: PostgreSQL. Cache/queue: Redis + Celery (only from Module 15).
- Testing: pytest, plus Vitest and React Testing Library on the frontend.
- Ops: Docker, Docker Compose, Git and GitHub, HTTPS in production.
- Architecture: modular monolith. No microservices.

## 3. Working agreement (mandatory)

**One module at a time. Two approval gates per module.**

1. **INSPECT**: read the existing code, docs and `DEVELOPMENT_STATUS.md`. Never overwrite a file you have not read.
2. **PLAN**: write the plan (format in section 4). Then **STOP. Gate 1: wait for me to write `APPROVED PLAN: Module N`.**
3. **IMPLEMENT**: only the approved scope. If you find something out of scope, add it to `KNOWN_ISSUES.md` instead of building it.
4. **TEST**: run unit, integration, API, financial-calculation and security tests relevant to the module.
5. **REVIEW**: inspect your own code for the items in section 6. Fix what you find.
6. **DOCUMENT**: update `DEVELOPMENT_STATUS.md`, `MODULE_CHECKLIST.md`, `SECURITY_CHECKLIST.md`, README, API docs and DB docs where affected.
7. **REPORT** in the format in section 5. Then **STOP. Gate 2: wait for me to write `APPROVED MODULE: Module N`.** Do not start the next module's plan or code before that.

Rules that always apply:
- If a security vulnerability appears, stop feature work and fix it first.
- Never skip, delete or weaken a failing test to make it pass. Find the cause.
- Never say something works unless you ran it. Quote the exact command and its result summary.
- If something could not be tested, say so explicitly under "Not tested".
- No fake functionality: no hardcoded dashboard numbers, mock data in production code, or placeholder endpoints presented as finished.
- Use synthetic data only. Never ask for or touch real family data before the security gate in section 7 is passed.
- No destructive actions (dropping tables, deleting data or volumes, `git push --force`, resetting migrations, deploying) without my approval of that specific command.
- Never print, log or commit secrets, tokens, passwords, keys or financial data.
- If a requirement is ambiguous, ask me (max 5 questions, grouped). If I do not answer, state your assumption in the plan and proceed.
- Prefer the simplest design that meets the requirement. Justify every new dependency in one sentence.

## 4. Plan format (Gate 1)

1. Objective and why this module exists
2. In scope / explicitly out of scope
3. Files to create or modify
4. Database changes (tables, columns, constraints, indexes, migrations)
5. API changes (method, path, auth, request and response shape)
6. Security risks and mitigations specific to this module
7. Test cases, including negative and authorization tests, and the financial scenarios from section 8
8. Acceptance criteria (copied into `MODULE_CHECKLIST.md`)
9. Assumptions and open questions

## 5. Report format (Gate 2)

1. What was implemented
2. Files created / modified
3. Database changes (migration IDs)
4. APIs created or changed
5. Commands run, with results (for example `pytest: 84 passed, 0 failed`)
6. Security checks performed and findings
7. Not tested / known limitations / unresolved issues
8. Documentation updated
9. Next module and anything I must decide before it

`DEVELOPMENT_STATUS.md` statuses: NOT STARTED, PLANNING, WAITING FOR PLAN APPROVAL, IN PROGRESS, TESTING, SECURITY REVIEW, WAITING FOR MODULE APPROVAL, BLOCKED, COMPLETED.
A module is COMPLETED only when the implementation exists, tests pass, security review is done, docs are updated **and** I have approved it.

## 6. Security requirements

**Authentication and sessions**
- Argon2id password hashing; never store or log plain-text passwords.
- Server-side sessions with expiry, idle timeout, rotation on login and revocation ("log out everywhere").
- Cookies: HttpOnly, Secure, SameSite. CSRF protection for cookie-authenticated state-changing requests.
- Login rate limiting and lockout/back-off; secure password reset; plan for MFA/passkeys (decision recorded in Module 0).

**Authorization**
- Roles: Owner, Administrator, Member, Read-only member.
- Household membership does **not** imply visibility. Every record has a visibility (`private` or `shared`) enforced on the backend for read, edit, export and download.
- Never trust `user_id` or `household_id` from the client; derive them from the session.
- Prevent IDOR and cross-household access. Return 404 (not 403) for records the caller may not know exist.
- Every protected endpoint needs an explicit authorization test (allowed role, denied role, other household).
- Evaluate PostgreSQL Row-Level Security as defence in depth in Module 0. If adopted, test connection-pool and request-context isolation.

**Data and encryption**
- UUID primary keys; foreign keys, CHECK constraints, unique constraints and indexes on every table.
- Money: `NUMERIC(14,2)` in PostgreSQL and `Decimal` in Python. Never float. Reject malformed, zero, negative (where not applicable) and absurdly large amounts.
- TLS in production; encrypted database storage and backups.
- Field-level encryption (AES-256-GCM, keys kept outside the database, rotation supported) only for genuinely sensitive text such as integration tokens and stored account identifiers. Store only the last 4 digits of account/card numbers. Do **not** encrypt fields needed for SQL aggregation such as amounts and dates. Record the field-by-field decision in `DATABASE_DESIGN.md`.
- Encryption does not prevent all leaks; never claim it does.

**API and app**
- Strict CORS allowlist, security headers, input validation, output schemas that never leak internal fields, safe error messages, no debug mode in production, XSS and SQL-injection prevention, rate limiting.

**Files**
- Private storage, random filenames, type and size validation, safe parsing (no formula execution from CSV/Excel), per-download authorization, temporary files deleted after processing.

**Logging**
- Never log passwords, OTPs, bank credentials, session cookies, tokens, full SMS text, full statements or keys.
- Security events (login failures, permission denials, session revocation, exports) go to `security_events` with minimal detail.

**Privacy**
- Never request UPI PINs, OTPs or bank passwords. No bulk SMS collection. No raw statements sent to external AI services. Optional integrations need explicit consent, minimum permissions, revocation and a manual fallback. Provide export and deletion procedures.

**Self-review checklist before every report**: broken permissions, missing authorization tests, duplicated logic, hardcoded secrets, unsafe queries, wrong financial calculations, unnecessary dependencies, sensitive data in logs or responses.

## 7. Real-data gate

Do not enter real family information until authentication, authorization, private file storage, database isolation, secrets handling, encrypted backups with a successful restore test, and the core security tests are implemented **and I have said so in writing**.

## 8. Financial accuracy rules

**Ledger design (settled in Module 0, then fixed):**
- Balances are derived from ledger entries, not stored as editable numbers.
- An account movement is stored as a positive amount plus a direction.
- A transfer is one `transfer_group` with two balanced legs created in a single database transaction.
- Credit card purchases increase the card liability. Card bill payment is a transfer that settles the liability and is not an expense.
- A refund links to its original transaction and reduces net spending. It is not income.
- Loan received is a liability, not income. Investment contribution is a movement, not consumption.
- Financial records are never hard-deleted. They are voided or reversed with a reason and an audit-log entry.
- Edits use optimistic concurrency (version column) so two family members cannot silently overwrite each other.
- Create operations that could be double-submitted (flaky mobile network) are idempotent.
- Timestamps are stored as UTC `timestamptz` and displayed in Asia/Kolkata. Bills and EMIs use date-only fields in Asia/Kolkata.

**Never count twice:** ATM withdrawal plus the later cash purchase; credit card purchase plus bill settlement; internal bank transfers; family transfers; refund plus original purchase; an order plus its linked payment transaction.

**Labelling:** every displayed value must be labelled recorded, estimated, imported (with date) or externally sourced (with source and time). Never invent balances or market prices. Never present a last-imported balance as live.

**Required scenario tests** (from the blueprint): ₹150 cash expense; cash income; ATM withdrawal; internal transfer; credit card purchase then bill payment; refund; importing the same statement twice; invalid amounts; changing an ID in the URL; accessing another household; unauthorized receipt download; backup restore.

## 9. Documentation to maintain

`README.md`, `ARCHITECTURE.md`, `DATABASE_DESIGN.md`, `DEVELOPMENT_ROADMAP.md`, `DEVELOPMENT_STATUS.md`, `MODULE_CHECKLIST.md`, `KNOWN_ISSUES.md` (bugs and unresolved security findings), `THREAT_MODEL.md`, `SECURITY.md`, `SECURITY_CHECKLIST.md`, `DECISIONS.md` (one short entry per architecture decision: context, decision, alternatives, consequences).

## 10. Module plan

Do not skip or reorder without my approval. Note that **Database foundation comes before Security foundation** because authentication needs the users and sessions tables.

| # | Module | Notes |
|---|--------|-------|
| 0 | Requirements and architecture | Docs only. No application code. |
| 1 | Development environment | React+Vite, FastAPI, PostgreSQL, Alembic, Docker, health check, `.env.example`, `.gitignore`, **CI** (lint, tests, `pip-audit`, `npm audit`, secret scanning, Bandit) |
| 2 | Database foundation | users, households, household_members, invitations, user_sessions, financial_accounts, categories, transactions, transfer_groups, audit_logs, security_events; constraints, indexes, migrations, isolation tests |
| 3 | Security foundation | Login/logout, sessions, CSRF, rate limiting, RBAC, household and visibility checks, security events; full security test suite |
| 4 | Financial accounts and categories | Account types: cash, savings, current, credit card, other. Default and custom categories. Backend validation and tests (UI comes in Module 7). |
| 5 | Transaction management | Income, expense, transfer, refund, loan received/repayment, investment in/out; manual amount and category; edit, search, filter, pagination; optional private attachment |
| 6 | Cash ledger and transfers | Opening balance, ATM withdrawal and deposit, internal transfers, accounting-rule tests |
| 7 | Frontend application | Login, layout, sidebar, mobile nav, account/category/transaction pages, loading/error/empty states, accessibility, i18n-ready |
| 8 | Dashboard and analytics | SQL-aggregated real numbers, Recharts, monthly/yearly/person-wise; verified against hand-calculated sample data |
| 9 | Bank statement import | CSV/Excel first; preview, duplicate detection, review, confirm, history; PDF later |
| 10 | Budgets and savings goals | Limits, progress, 75/90/100% alerts |
| 11 | Loans, EMI and bills | Schedules, recurring bills, reminders; never mark paid without user confirmation or a reconciled payment |
| 12 | Shopping orders | Orders, returns, refunds, receipts, link to transaction without double counting |
| 13 | Gold and silver | 24K/22K/18K gold, 999 silver, manual price, source, date, history, alerts |
| 14 | Investments | FD, RD, mutual funds, stocks, gold, silver, savings; manual valuation; gain/loss and return % |
| 15 | Notifications and automation | Celery + Redis; retries; duplicate-notification prevention |
| 16 | Optional integrations | Gmail receipts, Android notifications, Account Aggregator, AI insights; each with consent, minimum scope, revocation, manual fallback |
| 17 | Deployment and final audit | Production Docker, HTTPS, private DB, secrets, encrypted backups and restore test, monitoring, data export/deletion, final security report (vulnerabilities, fixes, remaining risks, tests done and not done). Never call the system "completely secure". |
