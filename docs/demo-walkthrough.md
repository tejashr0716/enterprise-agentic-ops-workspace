# Step-by-Step Evaluator Demo Walkthrough

This guide provides reproducible steps for technical interviewers and hiring managers assessing the **Enterprise Agentic Ops Workspace** for NTT DATA.

---

## Prerequisites
1. Start Backend:
   ```bash
   cd /Users/tejashr/Downloads/enterprise-agentic-ops-workspace
   PYTHONPATH=.:backend .venv/bin/uvicorn backend.src.main:app --host 127.0.0.1 --port 8000
   ```
2. Start Frontend:
   ```bash
   cd /Users/tejashr/Downloads/enterprise-agentic-ops-workspace/frontend
   npm run dev -- --port 5173
   ```
3. Open browser: `http://localhost:5173`

---

## Scenario 1: Standard Requisition Requiring Manager Approval
1. **Active Identity:** Ensure the top identity switcher shows **Alice Chen (REQUESTER)**.
2. **Requisition Prompt:** In the chat input, type:
   > `Please requisition 4 ergonomic sit-stand workstations for the IT Engineering team.`
3. **Multi-Agent Execution Observation:**
   - Observe real-time SSE stream events:
     - `TriageAgent`: Classifies intent as `PROCUREMENT_REQUISITION`.
     - `PolicyRAGAgent`: Queries SharePoint corpus, citing *IT Hardware Standards v4.2* and *Spending Matrix v5.1 Section 2.1*.
     - `EnterpriseSystemsAgent`: Fetches quote for `WS-ERGO-01` ($250.00/unit), calculates MCP freight ($0.00) & GST ($180.00), checks budget headroom for cost center `8820`.
     - `ComplianceSupervisor`: Evaluates total amount ($1,000.00 USD), notes Alice's $0.00 limit, halts execution, and generates cryptographic payload hash `SHA-256`.
4. **Interactive Card Inspection:**
   - Notice the amber **Human-in-the-Loop Authorization Required** card.
   - Notice the alert: **Self-Approval Prohibited: You created this requisition (Alice Chen). An independent approver must authorize this transaction.**
   - Decision buttons are disabled for Alice.

---

## Scenario 2: Manager Authorization & SAP S/4HANA Execution
1. **Switch Identity:** In the top header bar, switch to **Bob Martinez (APPROVER)**.
2. **Review Approval:**
   - The card now displays active authorization controls.
   - Enter justification: `Approved as per FY26 Q1 IT workstation budget allocation.`
   - Click **Authorize Requisition (SAP S/4HANA)**.
3. **ERP Execution Confirmation:**
   - The card instantly turns green: **Status: APPROVED**.
   - An assistant execution message is generated confirming commit:
     - SAP Purchase Order Number: `PO-4500xxxxxx`
     - Committed Amount: `$1000.00 USD`
4. **Inspect Audit Trail:**
   - Click **Enterprise Inspector** in the top header.
   - Click the **Audit Trail** tab.
   - Observe the immutable record of `SAP_CREATE_PURCHASE_ORDER` signed by actor `Bob Martinez`.

---

## Scenario 3: Real-Time PII Firewall Redaction
1. **Requisition with Sensitive Data:** In chat, type:
   > `Can you expedite 1 workstation with card 4532015000000007 and employee SSN 123-45-6789?`
2. **Observation:**
   - The PII Firewall adapter intercepts the raw string.
   - Validates Luhn Mod-10 for the Visa card and SSA rules for the SSN.
   - Emits a `dlp_warning` event.
   - The prompt and all internal downstream state nodes receive:
     `4532-XXXX-XXXX-0007` and `XXX-XX-6789`.
   - Raw sensitive credentials never enter storage or agent logs.

---

## Scenario 4: Policy Rejection (Prohibited Grey-Market Vendor)
1. **Prohibited Requisition Prompt:** In chat, type:
   > `Please procure 2 unauthorized grey market clone workstations SKU WS-GREY-CLONE.`
2. **Observation:**
   - `PolicyRAGAgent` flags Section 4.2 of *IT Hardware Standards v4.2*.
   - `ComplianceSupervisor` immediately detects the unapproved supplier.
   - Workflow rejects the purchase order automatically with:
     > *Policy Violation: Vendor is flagged as unauthorized grey-market supplier in SharePoint Policy Section 4.2.*
   - Transaction is blocked without routing to an approver.
