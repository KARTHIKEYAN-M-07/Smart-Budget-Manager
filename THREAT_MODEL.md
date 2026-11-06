# Threat Model: Smart Family Budget Manager

## 1. Assets to Protect
1. **Financial Transaction Data**: Income, expenses, loans, balances, merchant history, gold/silver holdings, and investments.
2. **Identity & Credentials**: User email addresses, Argon2id password hashes, active session tokens, and CSRF tokens.
3. **Private Financial Attachments**: Bank statements, invoices, salary slips, and receipts stored on disk.
4. **Integration Credentials**: OAuth access/refresh tokens for optional services (e.g., Gmail/Account Aggregator).
5. **System Integrity**: Accuracy of the double-entry ledger, transaction immutability, audit logs, and backup integrity.

---

## 2. Threat Actors & Personas
- **External Opportunistic Attacker**: Internet-based actor scanning for exposed ports, default credentials, unpatched vulnerabilities, or OWASP Top 10 flaws.
- **Compromised Client Device**: Malicious extensions, malware, or keyloggers running on a family member's phone or laptop.
- **Curious/Unauthorized Household Member**: A family member attempting to view accounts or transactions marked `private` by another family member.
- **Physical Device Possessor**: Someone who gains brief physical access to an unlocked laptop or phone in the home.
- **Supply Chain / Third-Party Vendor**: Compromised Python (PyPI) or JavaScript (npm) dependency introducing malicious code.

---

## 3. Trust Boundaries

```
[ Family Member Client / Device ]
             │  (Trust Boundary 1: Network Ingress)
             ▼
[ Reverse Proxy / TLS Termination (Caddy / Nginx) ]
             │  (Trust Boundary 2: Web Server to App Monolith)
             ▼
[ FastAPI Monolith (Session Auth, CSRF, RBAC, Validation) ]
             │  (Trust Boundary 3: Storage Engine & Encrypted Files)
             ▼
[ PostgreSQL Database (Private Network) & Vault File Storage ]
```

---

## 4. Attack Paths & Mitigations (STRIDE Framework)

### 4.1 Spoofing (Identity & Authentication)
- **Threat**: Attacker attempts credential stuffing or brute-forces user logins.
  - *Mitigation*: Argon2id hashing with high memory cost; IP and account-level rate limiting with exponential backoff; lockout after 5 consecutive failed attempts; recording in `security_events`.
- **Threat**: Attacker steals or hijacks session tokens.
  - *Mitigation*: Cryptographically random 256-bit session tokens; tokens stored hashed (SHA-256) in the database; `HttpOnly`, `Secure`, `SameSite=Strict` cookie attributes; session rotation upon login; server-side idle timeout (2 hours) and absolute expiry (7 days); "Log out everywhere" revocation.

### 4.2 Tampering (Data & Integrity)
- **Threat**: Modifying another user's transaction or altering financial ledger balances via IDOR.
  - *Mitigation*: Application derives `household_id` and `user_id` strictly from validated server session, ignoring client-provided tenant/user IDs. Non-accessible records return HTTP 404 (preventing existence probing). Optimistic locking (`version` column) prevents lost updates.
- **Threat**: Submitting malicious CSV/Excel bank statements containing formula injection (`=cmd|' /C...'`).
  - *Mitigation*: Strict parsing of raw cell values without formula execution; stripping leading `=`, `+`, `-`, `@` characters; type validation on all columns.
- **Threat**: Cross-Site Request Forgery (CSRF) submitting unauthorized transactions.
  - *Mitigation*: Anti-CSRF double-submit / custom header token validation required on all state-changing endpoints (`POST`, `PUT`, `PATCH`, `DELETE`).

### 4.3 Repudiation (Accountability & Audit)
- **Threat**: A user alters or deletes a transaction and denies doing so.
  - *Mitigation*: Immutability policy—financial records are never hard-deleted (`status IN ('POSTED', 'VOIDED', 'REVERSED')`). All mutations record pre/post states into an immutable `audit_logs` table with user UUID, timestamp, and IP.

### 4.4 Information Disclosure (Confidentiality & Privacy)
- **Threat**: Exposure of household financial data through SQL injection.
  - *Mitigation*: 100% parameterized queries via SQLAlchemy 2.x ORM / Core. Static analysis with Bandit and CodeQL in CI.
- **Threat**: Leaking internal database IDs, stack traces, or credentials in API error responses.
  - *Mitigation*: Pydantic v2 output schemas strictly sanitize returned fields; generic error messages in production; debug mode disabled in production.
- **Threat**: Unauthorized download of receipts or bank statement attachments.
  - *Mitigation*: Files stored outside the web root with non-guessable random UUIDs; served strictly via an authenticated streaming endpoint that checks household and visibility permissions before reading from disk.
- **Threat**: Database dump theft exposing account numbers or third-party tokens.
  - *Mitigation*: Sensitive account numbers and integration tokens encrypted with AES-256-GCM. Encryption keys loaded from environment variables outside the database. Only last 4 digits stored unencrypted.

### 4.5 Denial of Service (Availability)
- **Threat**: Uploading massive files or flooding the API to exhaust server memory and disk.
  - *Mitigation*: Reverse proxy and FastAPI middleware enforce max 10MB upload limit; rate limiting on API endpoints; memory-safe streaming for file parsing.

### 4.6 Elevation of Privilege (Authorization)
- **Threat**: A `Member` or `ReadOnly` user attempts to invite users or modify household settings.
  - *Mitigation*: Role-Based Access Control (`Owner`, `Administrator`, `Member`, `ReadOnly`) checked at the endpoint dependency layer. Unit tests for every role on every endpoint.

---

## 5. Residual Risks & Operational Caveats
1. **Physical Host Compromise**: If the physical home server/NAS is stolen and the root drive is not encrypted with full-disk encryption (BitLocker / LUKS), an attacker could access the raw files and database volume.
   - *Recommendation*: Deploy on an encrypted filesystem with volume passwords prompted at boot.
2. **Client-Side Keyloggers**: Compromised user phones or browser extensions could capture passwords before encryption.
   - *Recommendation*: Future implementation of WebAuthn / Passkeys (MFA) will mitigate stolen passwords.
3. **Backup Key Loss**: If the AES-256 encryption key used for backups is lost, encrypted backups cannot be restored.
   - *Recommendation*: Secure offline paper backup (or password manager vault) of encryption keys during Module 17 setup.
