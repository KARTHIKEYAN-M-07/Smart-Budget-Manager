# Security Verification Checklist

This checklist must be reviewed and executed before submitting Gate 2 reports for each module.

---

## 1. Authentication & Session Security
- [ ] Passwords hashed using Argon2id with adequate memory/time cost parameters.
- [ ] No plaintext passwords, salts, or session tokens logged anywhere in application logs.
- [ ] Session tokens generated with cryptographically secure random bytes (min 256 bits).
- [ ] Session tokens stored as hashes (SHA-256) in the database.
- [ ] Session cookies configured with `HttpOnly`, `Secure`, and `SameSite=Strict` attributes.
- [ ] Session expiry and idle timeout enforced on backend.
- [ ] Session rotation executed on login and privilege escalation.
- [ ] Global session revocation ("Log out everywhere") functional and tested.
- [ ] Rate limiting and account lockout active on login and password reset routes.

---

## 2. Authorization & Tenant Isolation
- [ ] `household_id` and `user_id` derived exclusively from server-side session, never client input.
- [ ] Cross-household access attempts return HTTP 404 (IDOR prevention).
- [ ] Private records belonging to other users return HTTP 404.
- [ ] Explicit authorization tests written for every protected endpoint:
  - Allowed role check.
  - Denied role check.
  - Other household check (isolation test).
- [ ] Role-Based Access Control (`Owner`, `Administrator`, `Member`, `ReadOnly`) verified.

---

## 3. Data Integrity & Financial Precision
- [ ] Monetary columns strictly typed as `NUMERIC(14,2)` in SQL and `Decimal` in Python.
- [ ] Floating-point types forbidden for monetary calculations.
- [ ] Negative and zero amounts rejected where applicable (`CHECK (amount > 0)`).
- [ ] Upper limit boundary check on amounts (`CHECK (amount <= 100000000000.00)`).
- [ ] Transfers enforce dual balanced legs under one `transfer_group` in a single DB transaction.
- [ ] No hard deletes on financial transactions (`VOIDED` / `REVERSED` statuses only).
- [ ] Optimistic locking verified via `version` column.
- [ ] Idempotency keys enforced on state-changing financial mutations.

---

## 4. Input Validation & Injection Defenses
- [ ] Pydantic v2 schemas strictly validate and sanitize all incoming request bodies.
- [ ] Output schemas strip internal database fields and sensitive attributes.
- [ ] All database queries parameterized through SQLAlchemy 2.x ORM / Core.
- [ ] Anti-CSRF protection enforced on all state-changing endpoints (`POST`, `PUT`, `PATCH`, `DELETE`).
- [ ] CSV/Excel bank statement ingestion sanitizes leading formula triggers (`=`, `+`, `-`, `@`).
- [ ] File uploads validate file extension, magic byte MIME type, and maximum file size (10MB limit).

---

## 5. Encryption & Secrets Management
- [ ] Sensitive account numbers and integration tokens encrypted with AES-256-GCM.
- [ ] Encryption keys sourced exclusively from environment variables outside the database.
- [ ] Only last 4 digits of bank/card accounts stored in cleartext.
- [ ] Amounts, dates, and categories kept unencrypted to preserve SQL indexing and aggregation.
- [ ] No secrets, keys, or passwords committed to Git.
- [ ] Automated secret scanning active in CI.

---

## 6. Audit Logging & Telemetry
- [ ] Critical financial mutations recorded in `audit_logs` with pre/post state changes.
- [ ] Security events (failed logins, permission denials, session revocations) logged in `security_events`.
- [ ] Logs contain zero sensitive information (no passwords, OTPs, full card numbers, or full statements).
