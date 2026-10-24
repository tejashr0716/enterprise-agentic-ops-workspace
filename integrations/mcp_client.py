"""Model Context Protocol (MCP 2.x) Client Adapter discovering and executing MCP tools."""

from typing import Dict, Any, List
from integrations.mcp_server import (
    mcp_get_approved_catalog,
    mcp_calculate_shipping_and_tax,
    mcp_verify_cost_center_budget
)


class MCPClientAdapter:
    """Discovers MCP tools and exposes them to LangGraph agent execution."""

    def __init__(self):
        self.protocol_version = "2024-11-05 (MCP 2.x)"

    def get_info(self) -> Dict[str, Any]:
        return {
            "protocol": "Model Context Protocol (MCP)",
            "sdk_version": "2.3.0",
            "protocol_version": self.protocol_version,
            "transport": "In-Memory Callable / STDIO Bridge",
            "tools_count": 3,
            "tools": [
                "mcp_get_approved_catalog",
                "mcp_calculate_shipping_and_tax",
                "mcp_verify_cost_center_budget"
            ]
        }

    async def get_catalog(self, category: str = "ALL") -> List[Dict[str, Any]]:
        return mcp_get_approved_catalog(category)

    async def calculate_tax_and_shipping(self, amount: float, currency: str = "USD", country: str = "IN") -> Dict[str, Any]:
        return mcp_calculate_shipping_and_tax(amount, currency, country)

    async def verify_budget(self, cost_center: str, requested_amount: float) -> Dict[str, Any]:
        return mcp_verify_cost_center_budget(cost_center, requested_amount)


mcp_client = MCPClientAdapter()
