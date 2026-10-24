# Enterprise Integrations Specification

## 1. SAP S/4HANA OData v2/v4 Integration
The platform connects to SAP S/4HANA Cloud via the official `API_PURCHASEORDER_PROCESS_SRV` OData endpoint.

### 1.1 Dual-Mode Operation
- **`LOCAL_SIMULATOR` (Default):**
  - Serves in-memory catalog fixtures matching verified SAP material numbers (`WS-ERGO-01`, `SRV-EDGE-X8`, `SW-LANG-PRO`, `WS-GREY-CLONE`).
  - Simulates transactional OData v2 payload packaging, JSON response wrappers (`{"d": {"PurchaseOrder": "PO-4500xxxxxx", ...}}`), and HTTP status `201 Created`.
  - Operates completely offline with zero credential dependencies.
- **`SAP_SANDBOX`:**
  - Communicates with SAP Business Accelerator Hub Sandbox: `https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV`.
  - Requires `SAP_API_KEY` header (`APIKey: <token>`).
  - Automatically falls back to `LOCAL_SIMULATOR` if sandbox returns 4xx/5xx errors or network timeout.

### 1.2 OData Purchase Order Schema
```json
{
  "PurchaseOrderType": "NB",
  "CompanyCode": "1010",
  "PurchasingOrganization": "1010",
  "PurchasingGroup": "001",
  "Supplier": "99104",
  "to_PurchaseOrderItem": {
    "results": [
      {
        "PurchaseOrderItem": "10",
        "Plant": "1010",
        "OrderQuantity": "5",
        "PurchaseOrderQuantityUnit": "EA",
        "NetPriceAmount": "250.00",
        "DocumentCurrency": "USD",
        "Material": "WS-ERGO-01"
      }
    ]
  }
}
```

---

## 2. Microsoft 365 SharePoint Graph Adapter
The platform connects to sovereign corporate SharePoint policy repositories.

### 2.1 Governance Corpus
The hybrid RAG index primes three corporate governance documents:
1. **`IT Hardware Standards & Procurement Guidelines (v4.2)`** — Document ID: `DOC-SHP-2026-001`. Mandates ergonomic certifications, approved suppliers (`SAP-VEN-99104`), and bans unauthorized grey-market hardware (Section 4.2).
2. **`Software Licensing & Cloud Service Acquisition Policy (v3.0)`** — Document ID: `DOC-SHP-2026-002`. Details seat provisioning and developer licenses.
3. **`Enterprise Delegation of Financial Authority & Spending Limits Matrix (v5.1)`** — Document ID: `DOC-SHP-2026-003`. Defines approval tiers: <$1,000 delegated, $1,000–$10,000 manager signoff, $10,000+ executive leadership.

### 2.2 Dual-Mode Operation
- **`LOCAL_SIMULATOR`:**
  - Indexes structured Markdown policies with BM25 keyword overlap and character n-gram cosine vector similarity.
- **`GRAPH_LIVE`:**
  - Syncs via Microsoft Graph REST API `https://graph.microsoft.com/v1.0/sites/{site-id}/drive/root/children` using OAuth2 Client Credentials (`M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CLIENT_SECRET`).

---

## 3. Model Context Protocol (MCP 2.x) Tools
Implemented using the official Model Context Protocol 2.x standard (`mcp==2.3.0`):
- **`mcp_get_approved_catalog`:** Returns active ERP vendor catalog filtered by hardware/software category.
- **`mcp_calculate_shipping_and_tax`:** Computes regional statutory GST/tax rates and freight logistics fees.
- **`mcp_verify_cost_center_budget`:** Queries department cost centers (`8820` IT Engineering, `7710` HR, `9900` Executive) to verify available budget headroom.
