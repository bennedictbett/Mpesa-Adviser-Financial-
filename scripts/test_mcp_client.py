"""
One-off diagnostic: connects to the running MCP server as a real
MCP client (using the mcp 2.x SDK's high-level Client) and calls
every tool, to verify they return correct data through the actual
protocol — not just that the endpoint exists.

Prerequisite: uvicorn must already be running
(uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload)

Run with: python -m scripts.test_mcp_client <session_id>
"""

import asyncio
import json
import sys

from mcp import Client

MCP_URL = "http://127.0.0.1:8001/mcp-server/mcp"


def extract_result(result):
    """
    mcp 2.x populates structured_content for tool return types it can
    generate a JSON schema from (Pydantic models, scalars). Some
    return types may still fall back to a TextContent JSON string in
    .content instead — handle both so this script works regardless.
    """
    if result.structured_content is not None:
        return result.structured_content
    if result.content and hasattr(result.content[0], "text"):
        return json.loads(result.content[0].text)
    return None


async def main(session_id: str):
    async with Client(MCP_URL) as client:
        tools = await client.list_tools()
        print("Available tools:")
        for tool in tools.tools:
            print(f"  - {tool.name}")
        print()

        calls = [
            ("spending_summary", {"session_id": session_id, "month": "2026-08"}),
            ("spending_by_category", {"session_id": session_id, "category": "Food", "month": "2026-08"}),
            ("category_breakdown", {"session_id": session_id, "month": "2026-08"}),
            ("budget_status", {"session_id": session_id, "category": "Food", "month": "2026-08"}),
        ]

        for tool_name, args in calls:
            print(f"Calling {tool_name}({args})...")
            result = await client.call_tool(tool_name, args)
            print(f"  -> {extract_result(result)}")
            print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.test_mcp_client <session_id>")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))