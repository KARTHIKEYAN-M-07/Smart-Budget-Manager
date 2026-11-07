# Security Verification Checklist

This checklist has been reviewed and executed across all modules (Module 0 through Module 17).

---

## 1. Authentication & Session Security
- [x] Passwords hashed using Argon2id with adequate memory/time cost parameters.
- [x] No plaintext passwords, salts, or session tokens logged anywhere in application logs.
- [x] Session tokens generated with cryptographically secure random bytes (min 256 bits).
- [x] Session tokens stored as hashes (SHA-256) in the database.
- [x] Session cookies configured with `HttpOnly`, `Secure`, and `SameSite=Lax/Strict` attributes.
- [x] Session expiry and idle timeout enforced on backend.
- [x] Session rotation executed on login and privilege escalation.
- [x] Global session revocation ("Log out everywhere") functional and tested.
- [x] Rate limiting and account lockout active on login and password reset routes.

---

## 2. Authorization & Tenant Isolation
- [x] `household_id` and `user_id` derived exclusively from server-side session, never client input.
- [x] Cross-household access attempts return HTTP 404 (IDOR prevention).
- [x] Private records belonging to other users return HTTP 404.
- [x] Explicit authorization tests written for every protected endpoint:
  - Allowed role check.
  - Denied role check.
  - Other household check (isolation test).
- [x] Role-Based Access Control (`Owner`, `Administrator`, `Member`, `ReadOnly`) verified.

---

## 3. Data Integrity & Financial Precision
- [x] Monetary columns strictly typed as `NUMERIC(14,2)` in SQL and `Decimal` in Python.
- [x] Floating-point types forbidden for monetary calculations.
- [x] Negative and zero amounts rejected where applicable (`CHECK (amount > 0)`).
- [x] Upper limit boundary check on amounts (`CHECK (amount <= 100000000000.00)`).
- [x] Transfers enforce dual balanced legs under one `transfer_group` in a single DB transaction.
- [x] No hard deletes on financial transactions (`VOIDED` / `REVERSED` statuses only).
- [x] Optimistic locking verified via `version` column.
- [x] Idempotency keys enforced on state-changing financial mutations.

---

## 4. Input Validation & Injection Defenses
- [x] Pydantic v2 schemas strictly validate and sanitize all incoming request bodies.
- [x] Output schemas strip internal database fields and sensitive attributes.
- [x] All database queries parameterized through SQLAlchemy 2.x ORM / Core.
- [x] Anti-CSRF protection enforced on all state-changing endpoints (`POST`, `PUT`, `PATCH`, `DELETE`).
- [x] CSV/Excel bank statement ingestion sanitizes leading formula triggers (`=`, `+`, `-`, `@`).
- [x] File uploads validate file extension, magic byte MIME type, and maximum file size (10MB limit).

---

## 5. Encryption & Secrets Management
- [x] Sensitive account numbers and integration tokens encrypted with AES-256-GCM.
- [x] Encryption keys sourced exclusively from environment variables outside the database.
- [x] Only last 4 digits of bank/card accounts stored in cleartext.
- [x] Amounts, dates, and categories kept unencrypted to preserve SQL indexing and aggregation.
- [x] No secrets, keys, or passwords committed to Git.
- [x] Automated secret scanning active in CI.

---

## 6. Audit Logging & Telemetry
- [x] Critical financial mutations recorded in `audit_logs` with pre/post state changes.
- [x] Security events (failed logins, permission denials, session revocations, exports) logged in `security_events`.
- [x] Logs contain zero sensitive information (no passwords, OTPs, full card numbers, or full statements).
