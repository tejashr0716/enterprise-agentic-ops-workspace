import pytest
import asyncio
from decimal import Decimal
from integrations.pii_firewall_adapter import pii_firewall
from integrations.sap_adapter import sap_adapter
from integrations.mcp_client import mcp_client
from src.rag.hybrid_retriever import policy_retriever
from src.agents.graph import compute_payload_hash, triage_node, policy_rag_node, systems_node, supervisor_node
from src.agents.state import AgentState
from src.models import AccessTier, UserRole, ProposedAction
from src.storage.database import db


# -------------------------------------------------------------
# 1. PII Financial Leakage Firewall Unit Tests
# -------------------------------------------------------------
def test_pii_firewall_redacts_valid_pan():
    # 4532015000000007 is a mathematically valid Luhn Visa PAN
    sample = "Please purchase with card 4532015000000007 for expediting."
    sanitized, findings = pii_firewall.sanitize_text(sample)
    assert len(findings) > 0
    assert findings[0]["type"] == "CREDIT_CARD"
    assert "4532015000000007" not in sanitized
    assert "4532-XXXX-XXXX-0007" in sanitized


def test_pii_firewall_ignores_invalid_luhn():
    # 4532015000000001 fails Luhn check
    sample = "Inventory tracking serial number: 4532015000000001."
    sanitized, findings = pii_firewall.sanitize_text(sample)
    assert len(findings) == 0
    assert "4532015000000001" in sanitized


def test_pii_firewall_redacts_ssn_and_secrets():
    sample = "Contact John Doe SSN 123-45-6789 with secret sk_test_51Abcd1234567890abcdef1234."
    sanitized, findings = pii_firewall.sanitize_text(sample)
    assert len(findings) >= 2
    assert "123-45-6789" not in sanitized
    assert "sk_test_51Abcd1234567890abcdef1234" not in sanitized
    assert "XXX-XX-6789" in sanitized
    assert "sk_test_XXXX...XXXX" in sanitized


# -------------------------------------------------------------
# 2. SAP S/4HANA Adapter Unit Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_sap_search_supplier_quotes():
    quotes = await sap_adapter.search_supplier_quotes("workstation")
    assert len(quotes) >= 1
    assert quotes[0].sku == "WS-ERGO-01"
    assert quotes[0].unit_price == Decimal("250.00")
    assert quotes[0].vendor_id == "SAP-VEN-99104"


@pytest.mark.asyncio
async def test_sap_create_purchase_order():
    action = ProposedAction(
        action_id="act-test-po",
        action_type="SAP_CREATE_PURCHASE_ORDER",
        vendor_name="Dell Technologies India Ltd",
        vendor_id="SAP-VEN-99104",
        item_description="Ergonomic Modular Sit-Stand Workstation",
        sku="WS-ERGO-01",
        quantity=5,
        unit_price=Decimal("250.00"),
        total_amount=Decimal("1250.00"),
        currency="USD",
        cost_center="8820",
        policy_reference="Spending Matrix v5.1 Section 2.1",
        target_environment="LOCAL_SIMULATOR",
        payload_hash=""
    )
    po = await sap_adapter.create_purchase_order(action)
    assert po["status"] == "SUCCESS"
    assert po["sap_purchase_order"].startswith("PO-")
    assert po["total_amount"] == 1250.00


# -------------------------------------------------------------
# 3. Model Context Protocol (MCP) Tools Unit Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_mcp_tax_and_shipping():
    tax_res = await mcp_client.calculate_tax_and_shipping(amount=2000.00, currency="USD", country="IN")
    assert tax_res["currency"] == "USD"
    # GST rate for IN is 18% -> 2000 * 0.18 = 360.00
    assert tax_res["tax_amount"] == 360.00
    assert tax_res["freight_shipping_fee"] == 0.00  # Free shipping over $1000
    assert tax_res["grand_total"] == 2360.00


@pytest.mark.asyncio
async def test_mcp_budget_verification():
    budget_ok = await mcp_client.verify_budget(cost_center="8820", requested_amount=2360.00)
    assert budget_ok["is_budget_approved"] is True
    assert budget_ok["cost_center"] == "8820"

    budget_exceeded = await mcp_client.verify_budget(cost_center="8820", requested_amount=9999999.00)
    assert budget_exceeded["is_budget_approved"] is False


# -------------------------------------------------------------
# 4. Hybrid RAG (BM25 + Dense) & Access Tier Unit Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_hybrid_rag_initialization_and_retrieval():
    await policy_retriever.initialize()
    results = policy_retriever.retrieve(
        query="What are the approval thresholds for IT hardware and workstations?",
        user_access_tier=AccessTier.INTERNAL,
        top_k=2
    )
    assert len(results) >= 1
    top_doc = results[0]
    assert "IT Hardware" in top_doc.document_title or "Spending Matrix" in top_doc.document_title
    assert top_doc.relevance_score > 0.0


def test_hybrid_rag_access_tier_restrictions():
    # Contractor (PUBLIC tier) cannot access RESTRICTED documents
    assert not policy_retriever._tier_permits(AccessTier.PUBLIC, AccessTier.RESTRICTED)
    # Internal user cannot access RESTRICTED documents
    assert not policy_retriever._tier_permits(AccessTier.INTERNAL, AccessTier.RESTRICTED)
    # Executive (RESTRICTED tier) can access all tiers
    assert policy_retriever._tier_permits(AccessTier.RESTRICTED, AccessTier.PUBLIC)
    assert policy_retriever._tier_permits(AccessTier.RESTRICTED, AccessTier.INTERNAL)
    assert policy_retriever._tier_permits(AccessTier.RESTRICTED, AccessTier.RESTRICTED)


# -------------------------------------------------------------
# 5. Deterministic Payload Hash Unit Tests
# -------------------------------------------------------------
def test_compute_payload_hash_deterministic():
    payload1 = {
        "action_type": "SAP_CREATE_PURCHASE_ORDER",
        "vendor_id": "SAP-VEN-99104",
        "sku": "WS-ERGO-01",
        "quantity": 5,
        "unit_price": "250.00",
        "total_amount": "1250.00",
        "currency": "USD",
        "cost_center": "8820"
    }
    payload2 = {
        "cost_center": "8820",
        "quantity": 5,
        "unit_price": "250.00",
        "sku": "WS-ERGO-01",
        "total_amount": "1250.00",
        "currency": "USD",
        "vendor_id": "SAP-VEN-99104",
        "action_type": "SAP_CREATE_PURCHASE_ORDER"
    }
    # Key order should not affect canonical hash
    assert compute_payload_hash(payload1) == compute_payload_hash(payload2)

    # Tampering any parameter must alter hash
    tampered = dict(payload1)
    tampered["total_amount"] = "1251.00"
    assert compute_payload_hash(payload1) != compute_payload_hash(tampered)


# -------------------------------------------------------------
# 6. Multi-Agent Graph Node State Transitions Unit Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_triage_node_intent_classification():
    state: AgentState = {
        "input_text": "Please requisition 5 ergonomic workstations for IT engineering team.",
        "events": []
    }
    res = await triage_node(state)
    assert res["intent"] == "PROCUREMENT_REQUISITION"
    assert res["current_node"] == "triage"
    assert len(res["events"]) >= 1


@pytest.mark.asyncio
async def test_supervisor_node_spending_threshold():
    await db.init_db()

    # Requester with $0.00 limit attempting $1,250.00 requisition
    state: AgentState = {
        "run_id": "run-test-01",
        "conversation_id": "conv-test-01",
        "user_id": "usr-alice-01",
        "user_name": "Alice Chen",
        "user_role": "REQUESTER",
        "spending_limit_usd": 0.00,
        "proposed_action": {
            "action_id": "act-test-01",
            "action_type": "SAP_CREATE_PURCHASE_ORDER",
            "vendor_name": "Dell Technologies India Ltd",
            "vendor_id": "SAP-VEN-99104",
            "sku": "WS-ERGO-01",
            "item_description": "Ergonomic Sit-Stand Workstation",
            "quantity": 5,
            "unit_price": "250.00",
            "total_amount": "1250.00",
            "currency": "USD",
            "cost_center": "8820",
            "policy_reference": "Spending Matrix v5.1 Section 2.1",
            "target_environment": "LOCAL_SIMULATOR",
            "payload_hash": ""
        },
        "events": []
    }
    state["proposed_action"]["payload_hash"] = compute_payload_hash(state["proposed_action"])

    res = await supervisor_node(state)
    assert res["approval_required"] is True
    assert res["approval_status"] == "PENDING"
    assert res["status"] == "WAITING_APPROVAL"
