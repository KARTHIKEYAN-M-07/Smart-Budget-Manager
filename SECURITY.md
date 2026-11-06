# Security Policy & Guidelines: Smart Family Budget Manager

## 1. Security Philosophy & Mandate
Security, privacy, and financial accuracy strictly outrank feature velocity and speed of implementation. Because this application manages sensitive household financial intelligence, every design and implementation step must satisfy defense-in-depth principles.

---

## 2. Real-Data Gate (Non-Negotiable)
In accordance with `AGENTS.md` Section 7:
> **No real family information, bank statements, account numbers, or balances may be entered into this system until:**
> 1. Authentication and session revocation are implemented and tested.
> 2. Authorization and record visibility tests pass (including cross-household and IDOR checks).
> 3. Private file storage and authorization are verified.
> 4. Database isolation and field-level encryption are verified.
> 5. Secrets handling is verified (no hardcoded keys).
> 6. Automated encrypted backup and restore drills have succeeded.
> 7. The core security test suite passes 100%.
> 8. **The owner has explicitly granted permission in writing.**

Only synthetic data may be used in development and testing.

---

## 3. Core Security Controls

### 3.1 Authentication & Passwords
- **Hashing**: Argon2id (`t=3`, `m=65536` [64 MiB], `p=4`). Plaintext passwords must never be stored, cached, or logged.
- **Sessions**: Cryptographically secure 256-bit entropy random tokens stored as SHA-256 hashes in `user_sessions`.
- **Cookies**: Flagged with `HttpOnly`, `Secure`, and `SameSite=Strict`.
- **Brute Force Protection**: IP and user rate limiting with exponential backoff; lockout after 5 consecutive failed attempts.
- **Revocation**: Instant revocation of current session or global revocation across all active devices.

### 3.2 Authorization & Access Control
- **Role Hierarchy**:
  - `Owner`: Full administrative rights, household configuration, user management, and visibility overrides.
  - `Administrator`: Account management, member invitation, transaction management.
  - `Member`: Standard CRUD operations on accounts and transactions; visibility controls.
  - `ReadOnly`: Read-only access to shared household transactions and reports.
- **IDOR Protection**: Every request verifies that target resources belong to the authenticated user's active household. If a record is not accessible or private to another user, return **HTTP 404** (not 403) to prevent resource enumeration.
- **Context Derivation**: Never trust `user_id` or `household_id` from request bodies or URL path parameters; derive them from the verified session context.

### 3.3 CSRF & Injection Defense
- **CSRF**: Custom request header verification (`X-CSRF-Token`) matching the issued session CSRF secret required on all state-changing verbs (`POST`, `PUT`, `PATCH`, `DELETE`).
- **SQL Injection**: Exclusively use parameterized queries via SQLAlchemy 2.x ORM / Core. Raw string interpolation in queries is strictly prohibited.
- **Formula Injection**: Prevent CSV/Excel formula execution by stripping leading `=`, `+`, `-`, `@` characters and sanitizing raw cells upon import.
- **XSS**: Strict JSON serialization; content security policy (CSP) headers; no `dangerouslySetInnerHTML` on the frontend.

### 3.4 Encryption & Secrets Management
- **At Rest**: PostgreSQL database volume encryption and encrypted backup files.
- **In Transit**: Strict HTTPS/TLS termination with modern cipher suites and HSTS.
- **Field-Level Encryption**: AES-256-GCM for sensitive credentials and account numbers, using externalized keys passed via environment variables.

### 3.5 Privacy & Sensitive Data Handling
- Never ask for, accept, or store UPI PINs, net banking passwords, or OTPs.
- Never log full account numbers, session secrets, statement contents, or authentication tokens.
- Security events are recorded in `security_events` with sanitized metadata.

---

## 4. Vulnerability Disclosure & Audit
Any discovered vulnerability must immediately halt new feature development until a patch and regression test are deployed.
