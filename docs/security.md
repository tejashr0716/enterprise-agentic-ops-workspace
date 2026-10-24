# Enterprise Security & Governance Architecture

## 1. Data Loss Prevention (PII Financial Leakage Firewall)
The PII Firewall adapter intercepts all raw incoming prompts and outgoing audit payloads before they reach agent reasoning loops or storage layers.

### 1.1 Algorithmic Verification
1. **Payment Card PANs (Luhn Mod-10 Check):**
   - Regex matches continuous or hyphenated digit sequences (13 to 19 digits).
   - Validates checksum via Luhn Mod-10 algorithm.
   - Non-compliant numeric sequences (e.g., inventory tracking numbers, serials) are preserved without false-positive masking.
   - Valid PANs are partially masked to preserve issuer prefix and audit suffix: `4532-XXXX-XXXX-0007`.
2. **US Social Security Numbers (SSN Exclusion Rules):**
   - Matches standard 9-digit format (`\d{3}-\d{2}-\d{4}`).
   - Enforces Social Security Administration (SSA) validity rules: rejects area codes `000`, `666`, or `900-999`, group `00`, and serial `0000`.
   - Valid SSNs are masked as `XXX-XX-6789`.
3. **Secret API Credentials & Private Keys:**
   - Detects Stripe secret keys (`sk_test_[0-9a-zA-Z]{24,}`).
   - Detects AWS access keys (`AKIA[0-9A-Z]{16}`).
   - Detects PEM private key blocks (`-----BEGIN RSA PRIVATE KEY-----`).
   - Redacts keys while preserving high-level identification for debugging.

---

## 2. Sovereign Access Tiers & Policy Scoping
Corporate policies indexed from Microsoft 365 SharePoint are tagged with strict access tiers:
- **`PUBLIC`:** Available to external contractors, temporary staff, and all internal employees (e.g., General Office Ergonomics, Vendor Codes of Conduct).
- **`INTERNAL`:** Available only to authenticated internal employees (e.g., Standard IT Equipment Catalog, Spending Matrix Thresholds).
- **`RESTRICTED`:** Available only to Executive Leadership and Corporate Directors (e.g., Executive Spending Discretion, Mergers & Strategic CapEx).

The Hybrid RAG retriever enforces pre-filtering: any document chunk where $\text{UserTier} < \text{DocTier}$ is dropped before dense vector scoring or lexical indexing, mitigating cross-tenant information disclosure.

---

## 3. Human-in-the-Loop Governance Gates

### 3.1 Self-Approval Prevention
Under enterprise governance rules, employees with approval authority cannot approve purchase orders they requisitioned themselves.
- If `current_user.id == approval.requester_id`, the system raises `403 Forbidden: Self-approval prohibited`.
- The requisition must be reviewed and authorized by an independent manager or executive.

### 3.2 Authority Delegation Matrix
| Requisition Amount (USD) | Authority Required | Typical Role |
| :--- | :--- | :--- |
| **$0.00 – $999.99** | Delegated Employee or Approver | `REQUESTER` (if limit allows) or `APPROVER` |
| **$1,000.00 – $9,999.99** | Operational Manager Approval | `APPROVER` (`bob.manager@company.internal`) |
| **$10,000.00+** | Executive Leadership Approval | `EXECUTIVE_APPROVER` (`carol.vp@company.internal`) |

### 3.3 Cryptographic Payload Fingerprinting
The proposed action generates a canonical SHA-256 fingerprint:
$$\text{Hash} = \text{SHA256}(\text{CanonicalJson}(\text{action\_type}, \text{vendor\_id}, \text{sku}, \text{quantity}, \text{unit\_price}, \text{total\_amount}, \text{cost\_center}))$$
During approval execution, the hash is recomputed against the active payload. Any tampering results in an immediate `400 Bad Request`.

---

## 4. Immutable Audit Logging
All critical operations (approvals, rejections, ERP purchase order creations, and policy queries) are persisted to the SQLite WAL `audit_logs` table with:
- Correlation ID (`corr-xxxxxxxx`)
- Actor ID, Name, and Role
- Action Type and Target Environment
- Timestamp in ISO 8601 UTC
- Masked JSON payload
