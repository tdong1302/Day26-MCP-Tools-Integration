"""Google ADK agent using OpenAI gpt-4o-mini and authenticated MCP tools."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StreamableHTTPConnectionParams,
)


load_dotenv()
PORT = int(os.getenv("PORT", "8086"))
MCP_SERVER_URL = f"http://localhost:{PORT}/mcp"
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is missing from .env")
if not MCP_AUTH_TOKEN:
    raise RuntimeError("MCP_AUTH_TOKEN is missing from .env")

football_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=MCP_SERVER_URL,
        headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"},
        timeout=30.0,
    ),
    use_mcp_resources=True,
)

root_agent = Agent(
    name="football_agent",
    model=LiteLlm(model="openai/gpt-4o-mini"),
    instruction=(
        "Bạn là trợ lý bóng đá trả lời bằng tiếng Việt. Với mọi câu hỏi về lịch "
        "đấu hoặc bảng xếp hạng, bắt buộc dùng MCP tools và chỉ dựa trên dữ liệu "
        "tool trả về. Ưu tiên get_upcoming_matches_v2; không tự bịa trận đấu, "
        "thời gian, kết quả hay thứ hạng. Nếu tool báo lỗi, giải thích đúng lỗi đó."
    ),
    tools=[football_tools],
)
