import logging
import uuid
from decimal import Decimal
from typing import List, Dict, Any, Optional
import httpx

from src.config import settings
from src.models import VendorQuote, ProposedAction

logger = logging.getLogger("sap_adapter")

# Pre-seeded official SAP catalog fixtures (DEMO DATA)
SAP_DEMO_CATALOG = [
    {
        "quote_id": "SQ-2026-9901",
        "vendor_id": "SAP-VEN-99104",
        "vendor_name": "Dell Technologies India Ltd",
        "sku": "WS-ERGO-01",
        "item_description": "Ergonomic Modular Sit-Stand Workstation 160x80cm Dual-Motor",
        "unit_price": Decimal("250.00"),
        "currency": "USD",
        "lead_time_days": 7,
        "category": "HARDWARE",
        "approved_vendor": True
    },
    {
        "quote_id": "SQ-2026-9902",
        "vendor_id": "SAP-VEN-99218",
        "vendor_name": "Hewlett Packard Enterprise (India)",
        "sku": "SRV-EDGE-X8",
        "item_description": "Enterprise Edge Compute Rack Server 64-Core 256GB ECC RAM",
        "unit_price": Decimal("4800.00"),
        "currency": "USD",
        "lead_time_days": 14,
        "category": "HARDWARE",
        "approved_vendor": True
    },
    {
        "quote_id": "SQ-2026-9903",
        "vendor_id": "SAP-VEN-99001",
        "vendor_name": "Microsoft India Enterprise Services",
        "sku": "SW-LANG-PRO",
        "item_description": "Multi-Agent Enterprise Orchestrator Developer Seat License (Annual)",
        "unit_price": Decimal("1200.00"),
        "currency": "USD",
        "lead_time_days": 1,
        "category": "SOFTWARE",
        "approved_vendor": True
    },
    {
        "quote_id": "SQ-2026-9904",
        "vendor_id": "SAP-VEN-99880",
        "vendor_name": "Prohibited Grey-Market Hardware Importer",
        "sku": "WS-GREY-CLONE",
        "item_description": "Unauthorized Uncertified Workstation Clone",
        "unit_price": Decimal("150.00"),
        "currency": "USD",
        "lead_time_days": 30,
        "category": "HARDWARE",
        "approved_vendor": False
    }
]


class SAPODataAdapter:
    """SAP S/4HANA Cloud OData integration adapter supporting Local Simulator and External Sandbox."""

    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or settings.sap_integration_mode
        self.base_url = settings.sap_odata_base_url
        self.api_key = settings.sap_api_key

    @property
    def catalog(self):
        return SAP_DEMO_CATALOG

    def get_environment_info(self) -> Dict[str, Any]:
        return {
            "adapter": "SAP S/4HANA OData v2/v4",
            "active_mode": self.mode.upper(),
            "target_url": self.base_url if self.mode == "sandbox" else "local://in-memory-sap-odata-simulator",
            "service_name": "API_PURCHASEORDER_PROCESS_SRV",
            "is_simulator": self.mode != "sandbox"
        }

    async def search_supplier_quotes(self, query: str) -> List[VendorQuote]:
        """Search SAP catalog for authorized supplier quotes matching query or SKU."""
        q = query.lower().strip()
        results = []

        for item in SAP_DEMO_CATALOG:
            # Check SKU or description match
            if q in item["sku"].lower() or q in item["item_description"].lower() or q in item["category"].lower() or any(w in item["item_description"].lower() for w in q.split()):
                results.append(VendorQuote(
                    quote_id=item["quote_id"],
                    vendor_id=item["vendor_id"],
                    vendor_name=item["vendor_name"],
                    sku=item["sku"],
                    item_description=item["item_description"],
                    unit_price=item["unit_price"],
                    currency=item["currency"],
                    lead_time_days=item["lead_time_days"],
                    source_system="SAP S/4HANA (LOCAL SIMULATOR)" if self.mode != "sandbox" else "SAP API Business Hub Sandbox"
                ))

        # Default fallback if query is broad
        if not results:
            # Return first approved item
            item = SAP_DEMO_CATALOG[0]
            results.append(VendorQuote(
                quote_id=item["quote_id"],
                vendor_id=item["vendor_id"],
                vendor_name=item["vendor_name"],
                sku=item["sku"],
                item_description=item["item_description"],
                unit_price=item["unit_price"],
                currency=item["currency"],
                lead_time_days=item["lead_time_days"],
                source_system="SAP S/4HANA (LOCAL SIMULATOR)"
            ))

        return results

    async def create_purchase_order(self, action: ProposedAction) -> Dict[str, Any]:
        """Execute purchase order creation against configured SAP environment."""
        po_id = f"PO-4500{uuid.uuid4().int % 900000 + 100000}"

        if self.mode == "sandbox" and self.api_key:
            # Real call to SAP Business Accelerator Hub Sandbox
            headers = {
                "APIKey": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            odata_payload = {
                "PurchaseOrderType": "NB",
                "CompanyCode": "1010",
                "PurchasingOrganization": "1010",
                "PurchasingGroup": "001",
                "Supplier": action.vendor_id.replace("SAP-VEN-", ""),
                "to_PurchaseOrderItem": {
                    "results": [
                        {
                            "PurchaseOrderItem": "10",
                            "Plant": "1010",
                            "OrderQuantity": str(action.quantity),
                            "PurchaseOrderQuantityUnit": "EA",
                            "NetPriceAmount": str(action.unit_price),
                            "DocumentCurrency": action.currency,
                            "Material": action.sku
                        }
                    ]
                }
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(f"{self.base_url}/A_PurchaseOrder", json=odata_payload, headers=headers)
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        return {
                            "status": "SUCCESS",
                            "environment": "SAP_SANDBOX",
                            "sap_purchase_order": data.get("d", {}).get("PurchaseOrder", po_id),
                            "vendor": action.vendor_name,
                            "total_amount": float(action.total_amount),
                            "currency": action.currency,
                            "raw_response": data
                        }
                    else:
                        logger.warning("SAP Sandbox returned status %d. Falling back to local simulator.", resp.status_code)
            except Exception as e:
                logger.error("Error communicating with SAP Sandbox: %s. Using local simulator.", e)

        # Local Simulator Mode (Compliant with OData v2 response wrapper format)
        return {
            "status": "SUCCESS",
            "environment": "LOCAL_SIMULATOR",
            "sap_purchase_order": po_id,
            "vendor": action.vendor_name,
            "vendor_id": action.vendor_id,
            "sku": action.sku,
            "quantity": action.quantity,
            "unit_price": float(action.unit_price),
            "total_amount": float(action.total_amount),
            "currency": action.currency,
            "cost_center": action.cost_center,
            "odata_metadata": {
                "uri": f"https://s4hana.internal.erp/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder('{po_id}')",
                "type": "API_PURCHASEORDER_PROCESS_SRV.A_PurchaseOrderType"
            }
        }


sap_adapter = SAPODataAdapter()
