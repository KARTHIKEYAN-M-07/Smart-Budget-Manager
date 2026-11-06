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
- [ ] Argon2id password hashing implemented and verified.
- [ ] Server-side session management with rotation, idle timeout, and revocation.
- [ ] HttpOnly, Secure, SameSite cookie handling.
- [ ] CSRF protection enforced for state-changing endpoints.
- [ ] RBAC enforcement (Owner, Administrator, Member, ReadOnly).
- [ ] Record-level visibility filtering (`private` vs `shared`) with 404 on IDOR attempts.
- [ ] Rate limiting on authentication endpoints.
- [ ] `security_events` logging verified.

---

## Module 4: Financial Accounts and Categories
- [ ] Account management CRUD with strict account types.
- [ ] AES-256-GCM field encryption for sensitive account identifiers (last 4 cleartext).
- [ ] Default Indian category taxonomy seeded.
- [ ] Custom categories with parent-child hierarchy support.

---

## Module 5: Transaction Management
- [ ] CRUD operations for transactions (Income, Expense, Refund, Loan, Investment).
- [ ] Idempotency key handling on create operations.
- [ ] Optimistic concurrency control verification.
- [ ] Private file attachment upload with size and MIME validation.
- [ ] 404 returned on unauthorized attachment downloads.

---

## Module 6: Cash Ledger and Transfers
- [ ] Atomic double-leg transfers via `transfer_groups`.
- [ ] ATM withdrawal scenario verified (Bank outflow, Cash inflow).
- [ ] Credit card payment settles card liability without being an expense.
- [ ] Refunds link to original transaction and reduce net expense.
- [ ] Reversal and void workflows verified without hard deletes.
- [ ] Financial test suite passes all blueprint scenarios.

---

## Module 7: Frontend Application
- [ ] Mobile-responsive layout (desktop sidebar, mobile navigation).
- [ ] Login and session management UI.
- [ ] Account summary with derived balances in INR format (`₹1,00,000`).
- [ ] Transaction log with date, account, and category filters.
- [ ] Quick-add modal for transactions with optimistic updates.
- [ ] English strings localized through i18n framework.

---

## Module 8: Dashboard and Analytics
- [ ] SQL-aggregated KPI cards (Income, Expense, Net Savings).
- [ ] Category and member spend breakdown charts (Recharts).
- [ ] Indian Financial Year (April 1 to March 31) report views.
- [ ] Aggregation numbers verified against hand-calculated datasets.

---

## Module 9: Bank Statement Import
- [ ] CSV and Excel parser safely extracting rows without formula execution.
- [ ] Duplicate detection engine flags previously imported rows.
- [ ] Review and commit workflow with import history audit.

---

## Module 10: Budgets and Savings Goals
- [ ] Monthly category budget creation with rollover.
- [ ] Real-time progress computation with 75%, 90%, 100% threshold indicators.
- [ ] Savings goal milestones and target date tracking.

---

## Module 11: Loans, EMI and Bills
- [ ] Loan account creation with principal, interest, and EMI amortization.
- [ ] Recurring bill schedule in Asia/Kolkata date format.
- [ ] Bill settlement creates reconciled ledger transaction.

---

## Module 12: Shopping Orders
- [ ] Order logging with merchant, date, and category split.
- [ ] Item returns and refunds linked directly to orders.
- [ ] Anti-double counting guarantees verified.

---

## Module 13: Gold and Silver
- [ ] 24K, 22K, 18K gold and 999 silver tracking in grams.
- [ ] Manual price logging with source and date.
- [ ] Current market valuation and gain/loss calculation.

---

## Module 14: Investments
- [ ] Portfolio tracking for FD, RD, Mutual Funds, Stocks, EPF/PPF.
- [ ] Contributions treated as asset movements (not expenses).
- [ ] Gain/loss calculations and valuation history.

---

## Module 15: Notifications and Automation
- [ ] Celery + Redis background task runner.
- [ ] Due bill notifications and budget alert dispatching.
- [ ] Idempotent task dispatching to prevent duplicate notifications.

---

## Module 16: Optional Integrations
- [ ] User-consented, restricted-scope integrations with manual fallback.
- [ ] Receipt/SMS parsing with zero leak of raw data.
- [ ] Immediate revocation capability.

---

## Module 17: Deployment and Final Audit
- [ ] Production-ready Docker Compose with HTTPS reverse proxy.
- [ ] Automated encrypted backup and verified restore drill.
- [ ] Household data export and full deletion workflow.
- [ ] Comprehensive security audit and penetration test report.
