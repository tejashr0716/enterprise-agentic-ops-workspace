# Platform Scope & Technical Boundaries

In strict compliance with portfolio integrity standards, this document explicitly defines what is production-executed, what operates in local simulation, and what represents architectural boundaries.

---

## 1. Simulated vs. Live Enterprise Infrastructure

| Subsystem | Active Mode | Production Reality & Honest Boundaries |
| :--- | :--- | :--- |
| **SAP S/4HANA OData** | `LOCAL_SIMULATOR` (Default) / `SAP_SANDBOX` | **Simulated / Sandbox**: Enterprise SAP tenants require corporate VPNs, private RFC gateways, and commercial license agreements. The local adapter strictly implements OData v2/v4 HTTP schema specifications and returns valid `{"d": {"PurchaseOrder": "PO-4500xxxxxx"}}` structures, but does not debit real corporate bank accounts. |
| **M365 SharePoint Graph** | `LOCAL_SIMULATOR` (Default) / `GRAPH_LIVE` | **Simulated Corpus**: SharePoint Graph integration supports Microsoft Entra ID app credentials (`M365_CLIENT_ID`), but out-of-the-box indexes sovereign local enterprise documents in Hybrid BM25 + Vector RAG rather than exposing private enterprise tenancies. |
| **Model Context Protocol** | `LOCAL_IN_PROCESS` | **Protocol Compliant**: Built against official `mcp==2.3.0` tools (`@mcp_server.tool()`). Tools are directly executable in-process to ensure deterministic sub-millisecond execution without external daemon dependencies. |
| **PII Financial Firewall** | `LIVE_DETERMINISTIC_ENGINE` | **Fully Verified & Active**: Luhn Mod-10 algorithmic checksums, SSA exclusion rules, and regex redactors execute on real strings with zero mock dependencies. |
| **State Persistence** | `SQLITE_WAL_ACTIVE` | **Real Production Storage**: Real disk persistence via SQLite operating under Write-Ahead Logging (`PRAGMA journal_mode=WAL`), with foreign key enforcement and durable crash survival. |

---

## 2. LLM Reasoning Engine
- **Default Engine (`LOCAL_DETERMINISTIC_ENGINE`):**
  - When no external cloud API key is supplied, the multi-agent system uses deterministic rule-based classifiers and templated synthesis.
  - This guarantees reproducible benchmarks, zero API costs, zero hallucination of financial figures, and 100% test determinism.
- **Optional Cloud Providers:**
  - Setting `LLM_PROVIDER=openai` or `azure_openai` enables live generative model completions if credentials are provided in `.env`.

---

## 3. Catalog & Cost Center Boundaries
- Catalog is bounded to 4 pre-seeded enterprise items (`WS-ERGO-01`, `SRV-EDGE-X8`, `SW-LANG-PRO`, `WS-GREY-CLONE`).
- Pre-seeded cost centers: `8820` (IT Engineering), `7710` (HR), `9900` (Executive).
