# Module Acceptance Checklist

## Module 0: Requirements and Architecture
- [x] Inspect workspace and confirm initial state.
- [x] Save standing rules to `AGENTS.md`.
- [x] Author comprehensive `ARCHITECTURE.md` with trust boundaries and folder layout.
- [x] Author detailed `DATABASE_DESIGN.md` with Mermaid ERD, ledger rules, and field-level encryption decisions.
- [x] Author `DEVELOPMENT_ROADMAP.md` covering all 18 modules.
- [x] Author `THREAT_MODEL.md` using STRIDE analysis.
- [x] Author baseline tracking files (`DEVELOPMENT_STATUS.md`, `KNOWN_ISSUES.md`, `DECISIONS.md`).
- [x] Author initial versions of `SECURITY.md` and `SECURITY_CHECKLIST.md`.
- [x] Formulate grouped clarifying questions with default assumptions.
- [x] Identify technical risks, mitigations, and spec gaps.
- [x] Receive user signoff (`APPROVED MODULE: Module 0`).

---

## Module 1: Development Environment & CI
- [x] Docker Compose running PostgreSQL and application container configuration defined.
- [x] FastAPI backend running with `/api/v1/health` endpoint responding.
- [x] React + Vite frontend scaffolding with Tailwind CSS and base i18n structure created.
- [x] CI pipeline configured (Linting, pytest, vitest, pip-audit, npm audit, Bandit, Secret Scanning).
- [x] `.env.example` and `.gitignore` properly configured.
- [x] Backend health check test suite passes 100% (5/5 tests passed).
- [ ] Receive user signoff (`APPROVED MODULE: Module 1`).

---

## Module 2: Database Foundation
- [x] SQLAlchemy 2.x models for all core entities created.
- [x] Alembic baseline migration generates clean schema matching `DATABASE_DESIGN.md`.
- [x] Foreign keys, CHECK constraints (`amount > 0`), and indexes verified.
- [x] UUID primary keys and optimistic locking version column verified.
- [x] Database isolation & derived balance tests pass (10/10 tests passing).
- [x] No editable balance column invariant verified.

---

## Module 3: Security Foundation
- [x] Argon2id password hashing implemented and verified.
- [x] Server-side session management with rotation, idle timeout, and revocation.
- [x] HttpOnly, Secure, SameSite cookie handling.
- [x] CSRF protection enforced for state-changing endpoints.
- [x] RBAC enforcement (Owner, Administrator, Member, ReadOnly).
- [x] Record-level visibility filtering (`private` vs `shared`) with 404 on IDOR attempts.
- [x] `security_events` logging verified for login failures and session actions.
- [x] Full security test suite passing (18/18 tests passing).

---

## Module 4: Financial Accounts and Categories
- [x] Account management CRUD with strict account types (`cash`, `savings`, `credit_card`, etc.).
- [x] AES-256-GCM field encryption for sensitive account identifiers (last 4 cleartext).
- [x] Default Indian category taxonomy seeded (38 standard categories).
- [x] Custom categories with parent-child hierarchy support and unique constraints.
- [x] Derived balance calculation for asset vs liability (Credit Card) verified.
- [x] Optimistic locking (version 409 conflict) & IDOR 404 isolation tests pass (23/23 tests passing).

---

## Module 5: Transaction Management
- [x] CRUD operations for transactions (Income, Expense, Refund, Loan, Investment).
- [x] Idempotency key handling on create operations (prevents duplicate submissions).
- [x] Optimistic concurrency control verification (version conflict detection 409).
- [x] Financial invariants: records never hard deleted; status transitions to VOIDED with audit trail.
- [x] Dynamic derived balance automatically excludes VOIDED transactions.
- [x] Keyword search, direction/category/date filtering, and pagination verified.
- [x] IDOR 404 isolation for cross-household & private transactions verified (28/28 tests passing).

---

## Module 6: Cash Ledger and Transfers
- [x] Atomic double-leg transfers via `transfer_groups`.
- [x] ATM withdrawal scenario verified (Bank outflow, Cash inflow, net spending = ₹0).
- [x] Anti-double-counting verified: ATM withdrawal + later cash purchase = purchase only.
- [x] Credit card payment settles card liability without being an expense.
- [x] Refunds link to original transaction and reduce net expense.
- [x] Reversal and void workflows verified without hard deletes (atomic leg voiding).
- [x] Financial test suite passes all blueprint scenarios (36/36 tests passing).

---

## Module 7: Frontend Application
- [x] Mobile-responsive layout (desktop sidebar, mobile navigation).
- [x] Login and session management UI (stateful auth, CSRF headers, login/register, logout/logout-all).
- [x] Account summary with derived balances in INR format (`₹1,00,000`).
- [x] Transaction log with date, account, and category filters.
- [x] Quick-add modal for transactions with optimistic updates.
- [x] English strings localized through i18n framework.

---

## Module 8: Dashboard and Analytics
- [x] SQL-aggregated KPI cards (Income, Expense, Net Savings).
- [x] Category and member spend breakdown charts (Recharts).
- [x] Indian Financial Year (April 1 to March 31) report views.
- [x] Aggregation numbers verified against hand-calculated datasets (38/38 tests passing).

---

## Module 9: Bank Statement Import
- [x] CSV safe parsing with formula injection protection (CWE-1236).
- [x] Duplicate detection engine (deterministic SHA-256 idempotency key).
- [x] Blueprint scenario: Importing the same statement twice (100% duplicate detection verified).
- [x] Preview & review before committing with category heuristic matching.
- [x] Atomic batch commit with audit log (41/41 tests passing).
## Module 10: Budgets and Savings Goals
- [x] Monthly category budget creation and household limit setting.
- [x] Real-time progress computation with 75%, 90%, 100% threshold indicators.
- [x] Savings goal milestones, progress percentage, and target date tracking.
- [x] Optimistic concurrency control and audit logging (43/43 tests passing).

---

## Module 11: Loans, EMI and Bills
- [x] Loan account creation with principal, interest, and EMI amortization.
- [x] Recurring bill schedule in Asia/Kolkata date format.
- [x] Bill settlement creates reconciled ledger transaction.

---

## Module 12: Shopping Orders
- [x] Order logging with merchant, date, and category split.
- [x] Item returns and refunds linked directly to orders.
- [x] Anti-double counting guarantees verified.

---

## Module 13: Gold and Silver
- [x] 24K, 22K, 18K gold and 999 silver tracking in grams.
- [x] Manual price logging with source and date.
- [x] Current market valuation and gain/loss calculation.

---

## Module 14: Investments
- [x] Portfolio tracking for FD, RD, Mutual Funds, Stocks, EPF/PPF.
- [x] Contributions treated as asset movements (not expenses).
- [x] Gain/loss calculations and valuation history.

---

## Module 15: Notifications and Automation
- [x] Celery + Redis background task runner.
- [x] Due bill notifications and budget alert dispatching.
- [x] Idempotent task dispatching to prevent duplicate notifications.

---

## Module 16: Optional Integrations
- [x] User-consented, restricted-scope integrations with manual fallback.
- [x] Receipt/SMS parsing with zero leak of raw data (deterministic local regex, OTP/balance redacted).
- [x] Immediate revocation capability with cryptographic token erasure.
- [x] Staged draft inbox requiring human family member review before ledger commitment.
- [x] Security and isolation tests passing (4/4 tests).

---

## Module 17: Deployment and Final Audit
- [x] Production-ready Docker Compose with HTTPS reverse proxy (`docker-compose.prod.yml`, `nginx/nginx.conf`).
- [x] Automated AES-256-GCM encrypted backup and verified restore drill (`backend/scripts/backup_and_restore_drill.py`).
- [x] Household data portability export (`GET /api/v1/household/export`) and DPDP/GDPR permanent purge (`DELETE /api/v1/household/purge`).
- [x] Comprehensive security audit report (`SECURITY_AUDIT_REPORT.md`).
- [x] Bandit SAST (0 issues across 8,974 LOC) and full test suite passes (66/66 tests passing).
