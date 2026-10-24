# Verified Résumé Recommendations: NTT DATA Full Stack Multi-Agent AI

**Candidate:** Tejas H R  
**Degree:** Bachelor of Engineering in Information Science and Engineering (ISE), 2026 Graduate, CGPA: 8.01  
**Target Role:** NTT DATA — Full Stack Developer (Multi-Agentic AI), Req ID 395031, Bengaluru, India  
**Flagship Project:** `enterprise-agentic-ops-workspace`

---

## 1. Verified XYZ Résumé Bullets

### Bullet 1 (Multi-Agent Architecture & Human-in-the-Loop Governance)
> Engineered a full-stack multi-agent enterprise procurement workspace with **6 LangGraph nodes** and **SSE streaming**, enforcing **Human-in-the-Loop approval gates**, self-approval prevention, and durable SQLite WAL state checkpoints that **survive server restarts**, verified across **30 automated regression tests (100% pass rate)**.

### Bullet 2 (Enterprise Systems Integration & Tool Protocols)
> Integrated **SAP S/4HANA OData v2/v4** purchase order creation and **Model Context Protocol (MCP 2.x)** freight/tax calculation with canonical **SHA-256 payload tampering detection**, achieving a **6.80 ms P50 end-to-end turn latency** across benchmarked multi-agent requisition cycles.

### Bullet 3 (Data Loss Prevention & Sovereign Hybrid RAG)
> Built a high-throughput **PII Financial Leakage Firewall** using **Luhn Mod-10** and SSA exclusion checks operating at **0.015 ms P50 latency**, fused with a **Hybrid BM25 + Dense Cosine Vector RAG engine (0.071 ms P50)** enforcing sovereign 3-tier access control over Microsoft SharePoint governance policies.

---

## 2. Claim-to-Evidence Matrix

| Claimed Feature / Metric | Measured Evidence Value | Source Code / Artifact Reference | Verifying Test Case |
| :--- | :--- | :--- | :--- |
| **Test Suite Pass Rate** | **30 passed / 0 failed (100.0%)** | `artifacts/test-results.xml`, `artifacts/test-summary.json` | Complete `pytest backend/tests -v` suite |
| **Multi-Agent Turn Latency** | **P50: 6.801 ms \| P95: 8.227 ms** | `artifacts/benchmark-results.json` | `artifacts/benchmark_harness.py` (30 iterations) |
| **PII Firewall Sanitization** | **P50: 0.015 ms \| P95: 0.017 ms** | `artifacts/benchmark-results.json` | `test_unit.py::test_pii_firewall_redacts_valid_pan` |
| **Hybrid Policy RAG Retrieval** | **P50: 0.071 ms \| P95: 0.085 ms** | `artifacts/benchmark-results.json` | `test_unit.py::test_hybrid_rag_initialization_and_retrieval` |
| **Payload Hash Latency** | **P50: 0.004 ms \| P95: 0.004 ms** | `artifacts/benchmark-results.json` | `test_unit.py::test_compute_payload_hash_deterministic` |
| **Restart Durability** | **100% state restoration from WAL** | `backend/src/storage/database.py` | `test_integration.py::test_workflow_resumption_and_erp_execution_surviving_restart` |
| **Self-Approval Prevention** | **403 Forbidden on Requester Signoff** | `backend/src/main.py#L305` | `test_security_negative.py::test_self_approval_prevention` |
| **Payload Tampering Defense** | **400 Bad Request on Hash Mismatch** | `backend/src/agents/graph.py#L35` | `test_security_negative.py::test_payload_tampering_hash_verification` |
| **Prohibited Supplier Guard** | **Deterministic rejection (Section 4.2)** | `integrations/sap_adapter.py` | `test_security_negative.py::test_prohibited_grey_market_vendor_rejection` |

---

## 3. Forbidden Claims Guide (Anti-Hallucination Guardrails)

| ❌ Forbidden / Disallowed Claim | Why It Is Forbidden | ✅ Approved Accurate Phrasing |
| :--- | :--- | :--- |
| *"Deployed to live production SAP S/4HANA enterprise tenant."* | Production SAP requires private corporate RFC gateways and commercial licensing. The platform connects to an OData v2/v4 compliant local simulator and SAP Accelerator Sandbox. | *"Engineered dual-mode SAP S/4HANA OData v2/v4 integration with sandbox and local ERP simulation."* |
| *"Guaranteed 100% zero leakage against all PII."* | No regex or algorithmic detector can guarantee zero false negatives against obfuscated adversarial text without bounded scope. | *"Enforced deterministic Luhn Mod-10 credit card PAN and SSA-compliant SSN redaction with zero mock dependencies."* |
| *"Connected to live production Microsoft 365 SharePoint tenant with confidential data."* | Tenant credentials are not committed and sovereign policies are pre-seeded corporate governance documents. | *"Developed Microsoft 365 SharePoint Graph adapter with sovereign hybrid BM25 + vector RAG and role-based access tiers."* |
| *"Trained custom generative LLM model."* | The project uses LangGraph state machine orchestration with local deterministic rule execution and pluggable cloud API adapters. | *"Orchestrated a 6-node LangGraph multi-agent architecture with typed state handoffs and human-in-the-loop authorization."* |
