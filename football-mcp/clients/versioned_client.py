"""Version-aware HTTP client proving v1 compatibility and v2 selection."""

from __future__ import annotations

import asyncio
import json
import os

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


load_dotenv()
PORT = int(os.getenv("PORT", "8086"))
SERVER_URL = f"http://localhost:{PORT}/mcp"


def _payload(result) -> object:
    if result.structuredContent:
        return result.structuredContent.get("result", result.structuredContent)
    return result.content[0].text if result.content else None


async def main_async() -> None:
    token = os.getenv("MCP_AUTH_TOKEN")
    if not token:
        raise SystemExit("MCP_AUTH_TOKEN is missing from .env")

    client = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"})
    async with client:
        async with streamable_http_client(SERVER_URL, http_client=client) as streams:
            read, write, _ = streams
            async with ClientSession(read, write) as session:
                await session.initialize()

                resource = await session.read_resource("server://info")
                metadata = json.loads(resource.contents[0].text)
                print(json.dumps(metadata, indent=2, ensure_ascii=False))

                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}

                legacy = await session.call_tool(
                    "get_upcoming_matches", {"team": "Arsenal"}
                )
                print("\nLegacy v1 still works:")
                print(json.dumps(_payload(legacy), indent=2, ensure_ascii=False))

                selected = (
                    "get_upcoming_matches_v2"
                    if "get_upcoming_matches_v2" in tool_names
                    else "get_upcoming_matches"
                )
                arguments = {"team": "Arsenal"}
                if selected.endswith("_v2"):
                    arguments.update({"limit": 1, "timezone": "Asia/Bangkok"})
                result = await session.call_tool(selected, arguments)
                print(f"\nVersion-aware client selected: {selected}")
                print(json.dumps(_payload(result), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main_async())

