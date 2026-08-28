"""HTTP auth evidence: valid, invalid, and missing bearer token cases."""

from __future__ import annotations

import asyncio
import os

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


load_dotenv()
PORT = int(os.getenv("PORT", "8086"))
SERVER_URL = f"http://localhost:{PORT}/mcp"


async def probe(token: str | None) -> int:
    headers = {"Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "auth-probe", "version": "1.0"},
        },
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(SERVER_URL, headers=headers, json=body)
        return response.status_code


async def call_with_valid_token(token: str) -> None:
    client = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"})
    async with client:
        async with streamable_http_client(SERVER_URL, http_client=client) as streams:
            read, write, _ = streams
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                print("Valid token discovered:", ", ".join(t.name for t in tools.tools))
                result = await session.call_tool(
                    "get_upcoming_matches_v2",
                    {"team": "Arsenal", "limit": 1},
                )
                print("Valid token tool call:", "OK" if not result.isError else "FAILED")


async def main_async() -> None:
    token = os.getenv("MCP_AUTH_TOKEN")
    if not token:
        raise SystemExit("MCP_AUTH_TOKEN is missing from .env")

    valid_status = await probe(token)
    invalid_status = await probe(token + "-invalid")
    missing_status = await probe(None)
    print(f"Valid token   -> HTTP {valid_status}")
    print(f"Invalid token -> HTTP {invalid_status}")
    print(f"Missing token -> HTTP {missing_status}")

    if valid_status != 200:
        raise SystemExit("Valid token did not receive HTTP 200")
    if invalid_status not in (401, 403) or missing_status not in (401, 403):
        raise SystemExit("Invalid/missing tokens were not rejected")
    await call_with_valid_token(token)


if __name__ == "__main__":
    asyncio.run(main_async())

