# Architecture Decision Records (ADRs)

## ADR 001: Modular Monolith Architecture
- **Context**: The application manages personal financial data for a single household/family. Scalability needs are modest, but data integrity, security, and developer ergonomics are paramount.
- **Decision**: Adopt a modular monolith architecture (FastAPI backend + React frontend) sharing a single PostgreSQL database.
- **Alternatives Considered**: Microservices (e.g., separate auth, ledger, and reporting services). Rejected due to operational complexity, distributed transaction challenges, and unnecessary network overhead.
- **Consequences**: Simplified ACID transactions across accounts and transfers; easy local deployment via Docker; clean domain boundaries maintained inside code directories.

---

## ADR 002: Derived Ledger Balances with Immutable History
- **Context**: Financial accounts are prone to silent drift if balances are stored as mutable values that can be updated out of sync with transactions.
- **Decision**: Eliminate editable balance columns. Account balances are strictly derived by summing posted transaction inflows and outflows. Transfers are recorded as balanced double legs inside a single `transfer_group`. Financial records are voided or reversed, never hard deleted.
- **Alternatives Considered**: Storing a running `balance` column on `financial_accounts` updated by triggers. Rejected because trigger failures or direct updates can introduce ledger discrepancies without an audit trail.
- **Consequences**: Guaranteed mathematical auditability; slightly higher SQL query aggregation overhead, mitigated by compound indexing (`account_id`, `transaction_date`) and optional read-only summary caching in later modules.

---

## ADR 003: Server-Side Stateful Sessions with HttpOnly Cookies
- **Context**: Need secure authentication mechanism immune to XSS token theft, supporting immediate revocation ("Log out everywhere").
- **Decision**: Use server-side stateful sessions stored hashed in `user_sessions` and delivered via `HttpOnly`, `Secure`, `SameSite=Strict` cookies. State-changing requests require a synchronized CSRF token header (`X-CSRF-Token`).
- **Alternatives Considered**: Stateless JSON Web Tokens (JWT) stored in `localStorage` or `sessionStorage`. Rejected due to vulnerability to XSS extraction and inability to reliably revoke tokens immediately without a server-side denylist.
- **Consequences**: Immediate logout and session invalidation capability; slight database lookup per authenticated request, indexed on session token hash.

---

## ADR 004: Exact Fixed-Point Representation for Currency
- **Context**: Floating-point math (`FLOAT`, `DOUBLE PRECISION`, JavaScript `Number`) introduces rounding anomalies (e.g., `0.1 + 0.2 != 0.3`).
- **Decision**: Enforce `NUMERIC(14,2)` at the PostgreSQL database layer, `Decimal` in Python, and integer-cent/fixed-string decimal parsing in JavaScript/TypeScript.
- **Alternatives Considered**: Floating-point numbers or 64-bit integer paise. `NUMERIC(14,2)` was chosen over pure integer paise for clarity in SQL reporting and natural decimal alignment.
- **Consequences**: Absolute financial precision up to ₹999,999,999,999.99; strict validation rejects malformed amounts and floating rounding leaks.

---

## ADR 005: Selective Field-Level Encryption
- **Context**: Sensitive financial credentials (bank account identifiers, API tokens) must be safeguarded in case of raw database exfiltration, but SQL aggregations (`SUM()`, `AVG()`) and indexing on amounts and dates must remain fast and functional.
- **Decision**: Encrypt only genuine credentials and full account numbers using AES-256-GCM with keys stored in environment variables outside the database. Store the last 4 digits in cleartext. Amounts, dates, and categories remain unencrypted.
- **Alternatives Considered**: Encrypting entire rows or database-wide column encryption. Rejected because it destroys SQL aggregation performance and full-text search capabilities.
- **Consequences**: Defense in depth for account identifiers without sacrificing query performance for dashboard metrics.

---

## ADR 006: Hybrid Row-Level Security (RLS) Strategy
- **Context**: Need defense in depth against accidental tenant or visibility leaks in multi-user/household environments.
- **Decision**: Enforce household and visibility isolation primarily in the application layer (FastAPI dependencies and queries returning 404 for missing or unauthorized resources). Support PostgreSQL RLS policies as secondary defense in depth with connection-pool reset verification.
- **Alternatives Considered**: Relying solely on PostgreSQL RLS. Rejected due to complexity with connection pooling (potential tenant context leakage if connection variables are not reset on checkout).
- **Consequences**: Robust multi-layered protection; comprehensive authorization tests at the API layer.

---

## ADR 007: Zero External AI & Local Deterministic Parsing for Integrations
- **Context**: Users want automatic intake of bank SMS alerts and e-commerce receipts, but third-party AI APIs (e.g. cloud LLMs) pose unacceptable privacy risks of leaking family financial amounts, merchant names, and balances.
- **Decision**: Reject all external AI API calls. Implement deterministic, local regex parsing for standard Indian banking formats (HDFC, SBI, ICICI, Axis, UPI) and receipts. Automatically redact OTPs, PINs, and account balances before persisting. Stage parsed items into an inbox requiring manual family review before ledger entry.
- **Alternatives Considered**: Sending anonymized snippets to OpenAI/Claude. Rejected because prompt extraction risks and third-party data retention violate family privacy invariants.
- **Consequences**: 100% data privacy; zero external network calls; instant local parsing with no subscription or token costs.

---

## ADR 008: Automated Cryptographic Backup Verification & DPDP Right-to-be-Forgotten
- **Context**: A backup is useless unless proven restorable. Furthermore, Indian DPDP and GDPR require user data portability and permanent erasure.
- **Decision**: Implement an automated restore drill (`backup_and_restore_drill.py`) verifying AES-256-GCM decryption, SHA-256 checksums, and schema/table reconstitution into an isolated database. Provide machine-readable data portability (`GET /api/v1/household/export`) and cascading right-to-be-forgotten deletion (`DELETE /api/v1/household/purge`) guarded by Owner RBAC and an explicit confirmation phrase.
- **Alternatives Considered**: Relying solely on `pg_dump` cron jobs without verification. Rejected because unverified backups frequently fail during actual emergencies due to corruption or schema incompatibilities.
- **Consequences**: Certified real-data readiness; full regulatory compliance for privacy and data portability.
