"""Unit tests use httpx.MockTransport, so they never consume live API quota."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from football_mcp.api import FootballDataClient
from football_mcp.api import FootballDataError
from football_mcp.api import resolve_league_code


ARSENAL = {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal", "tla": "ARS"}
LIVERPOOL = {"id": 64, "name": "Liverpool FC", "shortName": "Liverpool", "tla": "LIV"}


def run(coro):
    return asyncio.run(coro)


def mock_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/competitions/PL/teams"):
        return httpx.Response(200, json={"teams": [ARSENAL, LIVERPOOL]})
    if request.url.path.endswith("/teams/57/matches"):
        return httpx.Response(
            200,
            json={
                "matches": [
                    {
                        "utcDate": "2026-09-01T19:00:00Z",
                        "status": "SCHEDULED",
                        "venue": "Emirates Stadium",
                        "competition": {"name": "Premier League"},
                        "homeTeam": ARSENAL,
                        "awayTeam": LIVERPOOL,
                    }
                ]
            },
        )
    if request.url.path.endswith("/competitions/PL/standings"):
        return httpx.Response(
            200,
            json={
                "competition": {"name": "Premier League", "code": "PL"},
                "season": {
                    "startDate": "2026-08-01",
                    "endDate": "2027-05-31",
                    "currentMatchday": 3,
                },
                "standings": [
                    {
                        "type": "TOTAL",
                        "table": [
                            {
                                "position": 1,
                                "team": ARSENAL,
                                "playedGames": 3,
                                "won": 3,
                                "draw": 0,
                                "lost": 0,
                                "goalDifference": 7,
                                "points": 9,
                            }
                        ],
                    }
                ],
            },
        )
    return httpx.Response(200, json={"teams": []})


def make_client(handler=mock_handler) -> FootballDataClient:
    return FootballDataClient(
        "test-token",
        transport=httpx.MockTransport(handler),
    )


def test_league_aliases() -> None:
    assert resolve_league_code("Premier League") == "PL"
    assert resolve_league_code("EPL") == "PL"
    assert resolve_league_code("Champions League") == "CL"


def test_v1_and_v2_are_backward_compatible() -> None:
    client = make_client()
    v1 = run(client.upcoming_matches_v1("Arsenal"))
    v2 = run(client.upcoming_matches_v2("Arsenal", 1, "Asia/Bangkok"))

    assert v1["api_version"] == "1.0"
    assert v1["matches"][0] == {
        "opponent": "Liverpool",
        "date": "2026-09-01T19:00:00Z",
    }
    assert v2["api_version"] == "2.0"
    assert v2["matches"][0]["venue"] == "Emirates Stadium"
    assert v2["matches"][0]["kickoff"].endswith("+07:00")


def test_standings_shape() -> None:
    result = run(make_client().standings("PL"))
    assert result["competition"] == "Premier League"
    assert result["current_matchday"] == 3
    assert result["table"][0]["team"] == "Arsenal"
    assert result["table"][0]["points"] == 9


def test_unknown_team_is_clear_error() -> None:
    with pytest.raises(FootballDataError, match="Could not find team"):
        run(make_client().resolve_team("Definitely Not A Club"))


def test_rate_limit_is_sanitized() -> None:
    def rate_limited(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "too many requests"})

    with pytest.raises(FootballDataError) as error:
        run(make_client(rate_limited).standings("PL"))
    assert error.value.code == "football_api_rate_limited"
    assert "test-token" not in str(error.value)

