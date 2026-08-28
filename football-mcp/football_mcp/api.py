"""Async client and response adapters for football-data.org API v4."""

from __future__ import annotations

from datetime import datetime
import os
import re
import unicodedata
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx


API_BASE_URL = "https://api.football-data.org/v4"

# The free football-data.org plan exposes these competitions. Put PL first so
# common lab requests such as Arsenal resolve with only one discovery request.
SUPPORTED_COMPETITIONS = ("PL", "PD", "BL1", "SA", "FL1", "CL")

LEAGUE_ALIASES = {
    "pl": "PL",
    "epl": "PL",
    "premier league": "PL",
    "english premier league": "PL",
    "pd": "PD",
    "la liga": "PD",
    "primera division": "PD",
    "primera división": "PD",
    "bl1": "BL1",
    "bundesliga": "BL1",
    "sa": "SA",
    "serie a": "SA",
    "fl1": "FL1",
    "ligue 1": "FL1",
    "cl": "CL",
    "ucl": "CL",
    "champions league": "CL",
    "uefa champions league": "CL",
}


class FootballDataError(RuntimeError):
    """Safe, user-facing error raised for configuration and upstream failures."""

    def __init__(self, code: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": self.code,
            "message": str(self),
            "status_code": self.status_code,
        }


def normalize_name(value: str) -> str:
    """Normalize accents, punctuation, and whitespace for human-entered names."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def resolve_league_code(league: str) -> str:
    normalized = normalize_name(league)
    code = LEAGUE_ALIASES.get(normalized)
    if code is None:
        supported = ", ".join(sorted({v for v in LEAGUE_ALIASES.values()}))
        raise FootballDataError(
            "unknown_league",
            f"Unsupported league '{league}'. Supported codes: {supported}.",
        )
    return code


class FootballDataClient:
    """Small football-data.org client with in-memory team discovery caching."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = API_BASE_URL,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("FOOTBALL_DATA_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport
        self._teams_by_competition: dict[str, list[dict[str, Any]]] = {}

    def _require_api_key(self) -> str:
        if not self.api_key:
            raise FootballDataError(
                "missing_api_key",
                "FOOTBALL_DATA_API_KEY is not configured.",
            )
        return self.api_key

    async def _request(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {"X-Auth-Token": self._require_api_key()}
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                code = "football_api_unauthorized"
                message = "Football Data API rejected the API token or subscription."
            elif status == 404:
                code = "football_api_not_found"
                message = "Football Data API could not find the requested resource."
            elif status == 429:
                code = "football_api_rate_limited"
                message = "Football Data API rate limit reached; retry in about one minute."
            else:
                code = "football_api_error"
                message = f"Football Data API returned HTTP {status}."
            raise FootballDataError(code, message, status) from exc
        except (httpx.RequestError, ValueError) as exc:
            raise FootballDataError(
                "football_api_unavailable",
                "Could not connect to or decode a response from Football Data API.",
            ) from exc

    async def _competition_teams(self, competition: str) -> list[dict[str, Any]]:
        if competition not in self._teams_by_competition:
            data = await self._request(f"/competitions/{competition}/teams")
            self._teams_by_competition[competition] = data.get("teams", [])
        return self._teams_by_competition[competition]

    @staticmethod
    def _team_search_keys(team: dict[str, Any]) -> set[str]:
        keys: set[str] = set()
        for field in ("name", "shortName", "tla"):
            value = team.get(field)
            if value:
                normalized = normalize_name(str(value))
                keys.add(normalized)
                keys.add(re.sub(r"\b(fc|afc|cf|ac|ssc)\b", "", normalized).strip())
        return {key for key in keys if key}

    async def resolve_team(self, team_name: str) -> dict[str, Any]:
        query = normalize_name(team_name)
        if not query:
            raise FootballDataError("invalid_team", "Team name must not be empty.")

        partial_matches: list[dict[str, Any]] = []
        for competition in SUPPORTED_COMPETITIONS:
            for team in await self._competition_teams(competition):
                keys = self._team_search_keys(team)
                if query in keys:
                    return team
                if any(query in key or key in query for key in keys):
                    partial_matches.append(team)

            if len(partial_matches) == 1:
                return partial_matches[0]
            if len(partial_matches) > 1:
                names = sorted({str(item.get("shortName") or item.get("name")) for item in partial_matches})
                raise FootballDataError(
                    "ambiguous_team",
                    f"Team name '{team_name}' is ambiguous: {', '.join(names[:5])}.",
                )

        raise FootballDataError(
            "unknown_team",
            f"Could not find team '{team_name}' in the supported free competitions.",
        )

    async def upcoming_matches(self, team_name: str, limit: int = 3) -> dict[str, Any]:
        if not 1 <= limit <= 10:
            raise FootballDataError("invalid_limit", "limit must be between 1 and 10.")

        team = await self.resolve_team(team_name)
        data = await self._request(
            f"/teams/{team['id']}/matches",
            {"status": "SCHEDULED", "limit": limit},
        )
        matches = sorted(data.get("matches", []), key=lambda item: item.get("utcDate", ""))
        return {
            "team": team.get("shortName") or team.get("name"),
            "team_id": team.get("id"),
            "matches": matches[:limit],
        }

    async def upcoming_matches_v1(self, team_name: str) -> dict[str, Any]:
        data = await self.upcoming_matches(team_name, limit=3)
        team_id = data["team_id"]
        compact: list[dict[str, Any]] = []
        for match in data["matches"]:
            home = match.get("homeTeam", {})
            away = match.get("awayTeam", {})
            opponent = away if home.get("id") == team_id else home
            compact.append({
                "opponent": opponent.get("shortName") or opponent.get("name"),
                "date": match.get("utcDate"),
            })
        return {"api_version": "1.0", "team": data["team"], "matches": compact}

    async def upcoming_matches_v2(
        self,
        team_name: str,
        limit: int = 3,
        timezone: str = "Asia/Bangkok",
    ) -> dict[str, Any]:
        try:
            timezone_info = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise FootballDataError(
                "invalid_timezone",
                f"Unknown IANA timezone '{timezone}'.",
            ) from exc

        data = await self.upcoming_matches(team_name, limit=limit)
        team_id = data["team_id"]
        detailed: list[dict[str, Any]] = []
        for match in data["matches"]:
            home = match.get("homeTeam", {})
            away = match.get("awayTeam", {})
            opponent = away if home.get("id") == team_id else home
            utc_date = match.get("utcDate")
            kickoff = utc_date
            if utc_date:
                kickoff = (
                    datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
                    .astimezone(timezone_info)
                    .isoformat()
                )
            detailed.append({
                "team": data["team"],
                "opponent": opponent.get("shortName") or opponent.get("name"),
                "kickoff": kickoff,
                "timezone": timezone,
                "competition": match.get("competition", {}).get("name"),
                "venue": match.get("venue"),
                "status": match.get("status"),
                "home_team": home.get("shortName") or home.get("name"),
                "away_team": away.get("shortName") or away.get("name"),
            })
        return {"api_version": "2.0", "team": data["team"], "matches": detailed}

    async def standings(self, league: str) -> dict[str, Any]:
        code = resolve_league_code(league)
        data = await self._request(f"/competitions/{code}/standings")
        standings = data.get("standings", [])
        total = next(
            (item for item in standings if item.get("type") == "TOTAL"),
            standings[0] if standings else {"table": []},
        )
        table = []
        for row in total.get("table", []):
            team = row.get("team", {})
            table.append({
                "position": row.get("position"),
                "team": team.get("shortName") or team.get("name"),
                "played": row.get("playedGames"),
                "won": row.get("won"),
                "draw": row.get("draw"),
                "lost": row.get("lost"),
                "goal_difference": row.get("goalDifference"),
                "points": row.get("points"),
            })
        season = data.get("season", {})
        competition = data.get("competition", {})
        return {
            "competition": competition.get("name"),
            "competition_code": competition.get("code") or code,
            "season": {
                "start_date": season.get("startDate"),
                "end_date": season.get("endDate"),
            },
            "current_matchday": season.get("currentMatchday"),
            "table": table,
        }

