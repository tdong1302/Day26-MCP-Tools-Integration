"""Football MCP server: real tools, HTTP bearer auth, and version metadata."""

from __future__ import annotations

import argparse
import json
import logging
import os

from dotenv import load_dotenv
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from .api import FootballDataClient, FootballDataError


load_dotenv()
logging.getLogger("httpx").setLevel(logging.WARNING)

SERVER_VERSION = "2.0.0"
PORT = int(os.getenv("PORT", "8086"))
SERVER_URL = f"http://localhost:{PORT}"


class StaticTokenVerifier(TokenVerifier):
    """Validate the local demo bearer token without logging its value."""

    async def verify_token(self, token: str) -> AccessToken | None:
        expected = os.getenv("MCP_AUTH_TOKEN")
        if not expected or token != expected:
            return None
        return AccessToken(
            token=token,
            client_id="football-lab-client",
            scopes=["football:read"],
        )


mcp = FastMCP(
    "football-match-mcp",
    instructions=(
        "Football Match MCP Server v2.0.0. Use tools for factual match and "
        "standings data; never invent results or schedules."
    ),
    host="0.0.0.0",
    port=PORT,
    streamable_http_path="/mcp",
    token_verifier=StaticTokenVerifier(),
    auth=AuthSettings(
        issuer_url=SERVER_URL,
        resource_server_url=SERVER_URL,
        required_scopes=["football:read"],
    ),
)

football = FootballDataClient()


def _safe_error(exc: FootballDataError) -> dict:
    return exc.as_dict()


@mcp.tool()
async def get_upcoming_matches(team: str) -> dict:
    """[v1, deprecated] Get up to three upcoming matches for a football team.

    Args:
        team: Team name, short name, or abbreviation, for example Arsenal.
    """
    try:
        return await football.upcoming_matches_v1(team)
    except FootballDataError as exc:
        return _safe_error(exc)


@mcp.tool()
async def get_upcoming_matches_v2(
    team: str,
    limit: int = 3,
    timezone: str = "Asia/Bangkok",
) -> dict:
    """[v2] Get detailed upcoming matches for a football team.

    Args:
        team: Team name, short name, or abbreviation, for example Arsenal.
        limit: Number of matches to return, from 1 to 10.
        timezone: IANA timezone used for kickoff times, default Asia/Bangkok.
    """
    try:
        return await football.upcoming_matches_v2(team, limit, timezone)
    except FootballDataError as exc:
        return _safe_error(exc)


@mcp.tool()
async def get_team_standings(league: str) -> dict:
    """Get the current standings table for a supported football league.

    Args:
        league: League name or code, for example Premier League, EPL, or PL.
    """
    try:
        return await football.standings(league)
    except FootballDataError as exc:
        return _safe_error(exc)


@mcp.resource("server://info")
def server_info() -> str:
    """Return server capabilities, versions, and migration metadata."""
    return json.dumps(
        {
            "name": "football-match-mcp",
            "server_version": SERVER_VERSION,
            "capabilities": ["matches", "standings", "authentication", "versioning"],
            "tools": {
                "get_upcoming_matches": {
                    "version": "1.0.0",
                    "deprecated": True,
                    "replacement": "get_upcoming_matches_v2",
                },
                "get_upcoming_matches_v2": {
                    "version": "2.0.0",
                    "deprecated": False,
                },
                "get_team_standings": {
                    "version": "1.0.0",
                    "deprecated": False,
                },
            },
            "migration_guide": (
                "Keep get_upcoming_matches for legacy clients. New clients should "
                "use get_upcoming_matches_v2 for competition, venue, status, and "
                "timezone-aware kickoff fields."
            ),
        },
        ensure_ascii=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Football Match MCP Server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="stdio for basic lab; http for Streamable HTTP with bearer auth",
    )
    args = parser.parse_args()

    if args.transport == "http":
        print(f"Football MCP v{SERVER_VERSION}: {SERVER_URL}/mcp")
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
