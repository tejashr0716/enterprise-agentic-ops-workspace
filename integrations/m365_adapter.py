import logging
from typing import List, Dict, Any, Optional
from src.config import settings
from src.models import AccessTier

logger = logging.getLogger("m365_adapter")

# Corporate Policy Documents Seed Data (DEMO DATA)
SHAREPOINT_POLICY_DOCUMENTS = [
    {
        "id": "doc-it-hardware-01",
        "title": "Global IT Hardware & Peripheral Procurement Policy",
        "version": "v4.2",
        "effective_date": "2026-01-15",
        "access_tier": AccessTier.INTERNAL,
        "source_url": "https://company.sharepoint.com/sites/Legal/Policies/IT-Hardware-Procurement-v4.2.pdf",
        "sections": [
            {
                "section": "Section 3.1 — Financial Thresholds for IT Peripherals",
                "content": "All peripheral and workstation equipment purchases exceeding $1,000.00 USD (or equivalent INR 80,000) require written pre-authorization from a designated Procurement Operations Approver prior to purchase order creation."
            },
            {
                "section": "Section 3.4 — High-Value Capital Expenditure Escalation",
                "content": "Capital expenditures exceeding $10,000.00 USD require dual executive sign-off from the Department Head and the Vice President of Operations."
            },
            {
                "section": "Section 4.2 — Approved OEM Supplier Whitelist",
                "content": "To maintain warranty coverage and ISO 27001 compliance, IT assets must be procured exclusively from authorized Tier-1 SAP vendor accounts (Dell Technologies India, Hewlett Packard Enterprise, Lenovo). Sourcing from unauthorized grey-market suppliers is prohibited."
            }
        ]
    },
    {
        "id": "doc-saas-software-02",
        "title": "Enterprise Cloud Software & SaaS Licensing Guidelines",
        "version": "v3.0",
        "effective_date": "2025-11-01",
        "access_tier": AccessTier.INTERNAL,
        "source_url": "https://company.sharepoint.com/sites/Legal/Policies/Cloud-Software-Licensing-v3.0.pdf",
        "sections": [
            {
                "section": "Section 2.1 — Individual Developer Seat Tooling",
                "content": "Individual AI and developer tooling seat licenses under $1,500.00 USD require Department Manager authorization. Enterprise-wide orchestrator licenses must undergo architectural review."
            },
            {
                "section": "Section 5.3 — Data Privacy & LLM Gateway Requirements",
                "content": "All cloud-based AI tools and multi-agent systems must route prompts through an approved DLP firewall to prevent exposure of customer PII, secret keys, and cardholder data."
            }
        ]
    },
    {
        "id": "doc-authority-matrix-03",
        "title": "Corporate Spending & Cost Center Authority Matrix",
        "version": "v5.1",
        "effective_date": "2026-01-01",
        "access_tier": AccessTier.RESTRICTED,
        "source_url": "https://company.sharepoint.com/sites/Finance/Governance/Spending-Authority-Matrix-v5.1.pdf",
        "sections": [
            {
                "section": "Section 1.2 — Cost Center Allocation Rules",
                "content": "Cost Center 8820 (IT Systems Engineering) is authorized for engineering workstations, cloud infrastructure, and operational tooling. Requisitions must include itemized vendor pricing."
            },
            {
                "section": "Section 2.4 — Prohibition of Self-Approval",
                "content": "In compliance with Sarbanes-Oxley (SOX) controls, individuals submitting purchase requisitions are strictly prohibited from approving their own purchase orders, regardless of delegated spending authority limits."
            }
        ]
    }
]


class M365SharePointAdapter:
    """Microsoft 365 SharePoint Graph API integration adapter supporting Local Simulator and Live Graph."""

    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or settings.m365_integration_mode
        self.tenant_id = settings.m365_tenant_id
        self.client_id = settings.m365_client_id
        self.client_secret = settings.m365_client_secret

    def get_environment_info(self) -> Dict[str, Any]:
        return {
            "adapter": "Microsoft Graph v1.0 (SharePoint Document Library)",
            "active_mode": self.mode.upper(),
            "target_url": f"https://graph.microsoft.com/v1.0/sites/{self.tenant_id}" if self.mode == "live" else "local://sharepoint-document-library-simulator",
            "is_simulator": self.mode != "live"
        }

    async def list_policy_documents(self, user_access_tier: AccessTier = AccessTier.INTERNAL) -> List[Dict[str, Any]]:
        """List documents from SharePoint with role-based access tier filtering."""
        accessible_docs = []
        tier_hierarchy = {
            AccessTier.PUBLIC: 1,
            AccessTier.INTERNAL: 2,
            AccessTier.RESTRICTED: 3
        }
        user_level = tier_hierarchy.get(user_access_tier, 1)

        for doc in SHAREPOINT_POLICY_DOCUMENTS:
            doc_level = tier_hierarchy.get(doc["access_tier"], 2)
            if user_level >= doc_level:
                accessible_docs.append(doc)

        return accessible_docs


m365_adapter = M365SharePointAdapter()
