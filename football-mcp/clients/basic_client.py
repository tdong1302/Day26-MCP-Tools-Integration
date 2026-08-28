"""Basic stdio client: discovery plus real tool calls without LLM usage."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _result_payload(result) -> object:
    if result.structuredContent:
        return result.structuredContent.get("result", result.structuredContent)
    return result.content[0].text if result.content else None


async def run(team: str, league: str) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "football_mcp.server", "--transport", "stdio"],
        env=os.environ.copy(),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Discovered tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}")

            matches = await session.call_tool("get_upcoming_matches", {"team": team})
            print("\nUpcoming matches v1:")
            print(json.dumps(_result_payload(matches), indent=2, ensure_ascii=False))

            standings = await session.call_tool("get_team_standings", {"league": league})
            print("\nStandings:")
            print(json.dumps(_result_payload(standings), indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", default="Arsenal")
    parser.add_argument("--league", default="Premier League")
    args = parser.parse_args()
    asyncio.run(run(args.team, args.league))


if __name__ == "__main__":
    main()
