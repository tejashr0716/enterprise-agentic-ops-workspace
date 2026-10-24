"""Model Context Protocol (MCP 2.x) Enterprise Tools & Resources Server."""

from mcp.server.mcpserver import MCPServer
from typing import Dict, Any, List

# Initialize MCP 2.x Server
mcp_server = MCPServer("enterprise-agentic-ops-mcp")


@mcp_server.tool()
def mcp_get_approved_catalog(category: str = "ALL") -> List[Dict[str, Any]]:
    """Retrieve approved enterprise hardware and software SKUs from MCP catalog."""
    catalog = [
        {
            "sku": "WS-ERGO-01",
            "name": "Ergonomic Sit-Stand Workstation",
            "unit_price": 250.00,
            "currency": "USD",
            "category": "HARDWARE",
            "tier1_vendor": "Dell Technologies India"
        },
        {
            "sku": "SRV-EDGE-X8",
            "name": "Enterprise Edge Compute Server 64-Core",
            "unit_price": 4800.00,
            "currency": "USD",
            "category": "HARDWARE",
            "tier1_vendor": "Hewlett Packard Enterprise"
        },
        {
            "sku": "SW-LANG-PRO",
            "name": "Multi-Agent Orchestrator Developer Seat License",
            "unit_price": 1200.00,
            "currency": "USD",
            "category": "SOFTWARE",
            "tier1_vendor": "Microsoft India Enterprise"
        }
    ]
    if category.upper() == "ALL":
        return catalog
    return [item for item in catalog if item["category"] == category.upper()]


@mcp_server.tool()
def mcp_calculate_shipping_and_tax(amount: float, currency: str = "USD", country: str = "IN") -> Dict[str, Any]:
    """Calculate estimated freight logistics and statutory tax for procurement requisitions."""
    tax_rate = 0.18 if country.upper() == "IN" else 0.0825
    freight_fee = 50.00 if amount < 1000.0 else 0.00  # Free shipping over $1000

    tax_amount = round(amount * tax_rate, 2)
    grand_total = round(amount + tax_amount + freight_fee, 2)

    return {
        "base_amount": amount,
        "tax_rate_percent": round(tax_rate * 100, 2),
        "tax_amount": tax_amount,
        "freight_shipping_fee": freight_fee,
        "grand_total": grand_total,
        "currency": currency,
        "country": country.upper()
    }


@mcp_server.tool()
def mcp_verify_cost_center_budget(cost_center: str, requested_amount: float) -> Dict[str, Any]:
    """Verify quarterly budget allocation and headroom for specified cost center."""
    # Seeded budget limits (DEMO DATA)
    budgets = {
        "8820": {"dept": "IT Systems Engineering", "quarterly_budget": 50000.0, "spent": 18200.0},
        "7710": {"dept": "Human Resources", "quarterly_budget": 15000.0, "spent": 12400.0},
        "9900": {"dept": "Executive Operations", "quarterly_budget": 100000.0, "spent": 24500.0}
    }

    cc = budgets.get(cost_center, {"dept": "General Corporate", "quarterly_budget": 20000.0, "spent": 15000.0})
    remaining = cc["quarterly_budget"] - cc["spent"]
    is_sufficient = remaining >= requested_amount

    return {
        "cost_center": cost_center,
        "department": cc["dept"],
        "quarterly_budget": cc["quarterly_budget"],
        "already_spent": cc["spent"],
        "remaining_headroom": round(remaining, 2),
        "requested_amount": requested_amount,
        "is_budget_approved": is_sufficient
    }
