# Football Match MCP Server

MCP Server cá nhân cho Day 26. Server biến việc mở web/app để tra lịch đấu và
bảng xếp hạng thành tools mà MCP client hoặc AI agent có thể tự khám phá và gọi.
Dữ liệu lấy trực tiếp từ [football-data.org API v4](https://www.football-data.org/documentation/quickstart),
không hard-code lịch đấu hay bảng xếp hạng.

## Use case

### Công việc hiện tại

Tôi thường xuyên tra cứu lịch thi đấu sắp tới của một đội bóng và bảng xếp hạng của các giải bóng đá.

### Tôi đang làm thủ công như thế nào

Hiện tại, khi muốn xem lịch thi đấu, tôi phải lên Google tìm kiếm tên đội bóng, sau đó mở từng trang web để tìm và kiểm tra các trận đấu sắp tới.

Tương tự, khi muốn xem bảng xếp hạng, tôi phải tiếp tục tìm kiếm trên Google, truy cập các trang cung cấp thông tin bóng đá và tự tìm bảng xếp hạng của giải đấu cần xem.

Quy trình này phải thực hiện thủ công qua nhiều bước và nhiều trang web. MCP Server giúp tự động hóa việc tra cứu để Claude Code, MCP client hoặc AI agent có thể gọi tool và lấy dữ liệu thật trực tiếp từ `football-data.org API v4`.

### Input

Tùy theo nhu cầu tra cứu:

- Tên đội bóng, ví dụ: `Arsenal`.
- Tên hoặc mã giải đấu, ví dụ: `Premier League`, `PL`.
- Với phiên bản v2 của tool tra lịch đấu có thể truyền thêm `limit` và `timezone`.

### Output

- Danh sách các trận đấu sắp tới của đội bóng.
- Thông tin trận đấu như đối thủ, thời gian, giải đấu, sân đấu, trạng thái và đội nhà/đội khách.
- Bảng xếp hạng gồm vị trí, đội bóng, số trận, thắng/hòa/thua, hiệu số và điểm.

### Các MCP tools

Server có **2 chức năng chính** và **3 MCP tools**:

1. **Tra lịch thi đấu**
   - `get_upcoming_matches(team)` — phiên bản v1.
   - `get_upcoming_matches_v2(team, limit=3, timezone="Asia/Bangkok")` — phiên bản v2 để minh họa versioning và backward compatibility.
2. **Tra bảng xếp hạng**
   - `get_team_standings(league)` — lấy bảng xếp hạng của giải đấu.

`get_upcoming_matches_v2` là phiên bản mở rộng của tool tra lịch, không phải một use case riêng.

## Kết quả của bài lab

- **Bài 1:** tools thật qua stdio và Python MCP client.
- **Bài 2:** Streamable HTTP + bearer token + `TokenVerifier`.
- **Bài 3:** giữ v1, thêm v2, resource `server://info`, client tự chọn version.
- **Agent demo:** Google ADK + OpenAI `gpt-4o-mini` + authenticated `McpToolset`.

```text
User / Python Client / ADK Agent
              |
              | MCP stdio hoặc Streamable HTTP + Bearer token
              v
       Football MCP Server
              |
              | X-Auth-Token
              v
       football-data.org v4
```

Server chỉ cần chạy trong lúc demo hoặc kiểm thử; bài lab không yêu cầu host
24/7.

## Tools và resource

### `get_upcoming_matches(team)` — v1, backward compatible

Input:

```json
{"team": "Arsenal"}
```

Output rút gọn:

```json
{
  "api_version": "1.0",
  "team": "Arsenal",
  "matches": [{"opponent": "Liverpool", "date": "2026-09-01T19:00:00Z"}]
}
```

### `get_upcoming_matches_v2(team, limit=3, timezone="Asia/Bangkok")`

Phiên bản v2 giữ chức năng tra lịch đấu nhưng trả thêm `competition`, `venue`, `status`, đội nhà/đội khách và giờ địa phương. `limit` nhận giá trị 1–10.

Input:

```json
{
  "team": "Arsenal",
  "limit": 3,
  "timezone": "Asia/Bangkok"
}
```

Output rút gọn:

```json
{
  "api_version": "2.0",
  "team": "Arsenal",
  "matches": [
    {
      "home_team": "Liverpool",
      "away_team": "Arsenal",
      "competition": "Premier League",
      "venue": "Anfield",
      "status": "TIMED",
      "utc_date": "2026-09-01T19:00:00Z",
      "local_date": "2026-09-02T02:00:00+07:00"
    }
  ]
}
```

### `get_team_standings(league)`

Hỗ trợ alias: Premier League/EPL/PL, La Liga/PD, Bundesliga/BL1, Serie A/SA,
Ligue 1/FL1 và Champions League/CL.

Input:

```json
{"league": "Premier League"}
```

Output rút gọn:

```json
{
  "league": "Premier League",
  "season": "2026",
  "current_matchday": 3,
  "standings": [
    {
      "position": 1,
      "team": "Arsenal",
      "played": 3,
      "won": 3,
      "draw": 0,
      "lost": 0,
      "goal_difference": 6,
      "points": 9
    }
  ]
}
```

Output đầy đủ gồm `season`, `current_matchday` và bảng `position/team/played/won/draw/lost/goal_difference/points`.

### `server://info`

Công bố version `2.0.0`, capabilities, deprecated tool và migration guide.
Client cũ tiếp tục dùng `get_upcoming_matches`; client mới đọc metadata rồi ưu
tiên `get_upcoming_matches_v2`.

## Cài đặt

Yêu cầu Python 3.12+ và `uv`.

```powershell
cd football-mcp
uv sync
Copy-Item .env.example .env
```

Điền `.env`:

```env
FOOTBALL_DATA_API_KEY=token_tu_football_data_org
MCP_AUTH_TOKEN=mot_token_local_do_ban_tu_chon
OPENAI_API_KEY=openai_api_key_co_credit
PORT=8086
```

Không commit `.env`. OpenAI API billing độc lập với gói ChatGPT.

## Bài 1 — chạy stdio

Client tự khởi động MCP server, khám phá tools và gọi dữ liệu thật:

```powershell
uv run python -m clients.basic_client --team Arsenal --league "Premier League"
```

Test thêm lỗi team:

```powershell
uv run python -m clients.basic_client --team "Definitely Not A Club"
```

### Đăng ký với Claude Code (stdio)

Trong thư mục gốc repository, tạo file `.mcp.json` cục bộ (không cần commit) với
đường dẫn `football-mcp` phù hợp máy của bạn:

```json
{
  "mcpServers": {
    "football-match": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "E:\\VIN_CODEEEEEEEEEEEEEEEEEEEEEEEEE\\codelab\\Day26-MCP-Tools-Integration\\football-mcp",
        "python",
        "-m",
        "football_mcp.server",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

Claude Code khởi chạy server trong `football-mcp`, nên server sẽ đọc các key từ
`football-mcp/.env`; không chép key vào `.mcp.json`. Reload/restart Claude Code,
sau đó hỏi tự nhiên: `Arsenal đá trận tiếp theo khi nào?` hoặc `Cho tôi bảng xếp
hạng Premier League.`. Nếu không có Claude Code/Claude subscription, các script
Python ở phần kiểm thử bên dưới vẫn là bằng chứng thay thế cho tool discovery và
tool call.

## Bài 2 — Streamable HTTP và Authentication

Terminal 1:

```powershell
uv run python -m football_mcp.server --transport http
```

Endpoint MCP là `http://localhost:8086/mcp`; không mở trực tiếp endpoint này
như một trang web.

Terminal 2:

```powershell
uv run python -m clients.auth_client
```

Kết quả mong đợi:

```text
Valid token   -> HTTP 200
Invalid token -> HTTP 401 hoặc 403
Missing token -> HTTP 401 hoặc 403
Valid token tool call: OK
```

## Bài 3 — Versioning

Giữ HTTP server đang chạy, sau đó:

```powershell
uv run python -m clients.versioned_client
```

Client sẽ đọc `server://info`, gọi v1 để chứng minh backward compatibility,
sau đó chọn v2 nếu server công bố tool đó.

## ADK Web với OpenAI gpt-4o-mini

OpenAI `gpt-4o-mini` hỗ trợ function calling theo
[OpenAI Docs](https://developers.openai.com/api/docs/models/gpt-4o-mini).
Agent dùng LiteLLM để kết nối model và gửi bearer token đến MCP server.

Giữ HTTP server ở Terminal 1. Terminal 2:

```powershell
uv run adk web
```

Mở `http://localhost:8000`, chọn `football_agent`, rồi hỏi:

```text
Arsenal đá trận tiếp theo khi nào?
Cho tôi bảng xếp hạng Premier League.
```

Nếu OpenAI key thiếu API credit, các Python clients vẫn kiểm thử đầy đủ MCP,
auth và versioning mà không cần LLM.

## Kiểm thử

Unit tests dùng `httpx.MockTransport`, không tốn quota API:

```powershell
uv run python -m pytest -q -p no:cacheprovider
```

## Checklist đối chiếu yêu cầu Day26

- [x] MCP Server tự xây cho một công việc thực tế.
- [x] Dữ liệu thật từ `football-data.org API v4`, không hard-code lịch đấu/BXH.
- [x] Có các MCP tools với input/output rõ ràng.
- [x] Chạy được qua `stdio`.
- [x] Có hướng dẫn đăng ký MCP Server với Claude Code.
- [x] Có câu hỏi ngôn ngữ tự nhiên để kiểm tra agent tự chọn tool.
- [x] Có phiên bản `Streamable HTTP`.
- [x] Có Bearer token và `TokenVerifier`.
- [x] Có hướng dẫn test token đúng, sai và thiếu token.
- [x] Có versioning v1/v2 và giữ backward compatibility.
- [x] Có resource `server://info`.
- [x] Client mới đọc metadata trước khi ưu tiên v2.
- [x] Có Python clients và unit tests để kiểm chứng tool chạy được.
- [x] Không đưa API key/token thật vào README; secret được đọc từ `.env`.

## Lỗi thường gặp

- `missing_api_key`: chưa cấu hình `FOOTBALL_DATA_API_KEY`.
- `football_api_unauthorized`: token Football Data sai hoặc giải không thuộc gói.
- `football_api_rate_limited`: gói Free giới hạn 10 request/phút; chờ một phút.
- HTTP 401/403: kiểm tra `Authorization: Bearer <MCP_AUTH_TOKEN>` và restart
  server sau khi đổi `.env`.
- HTTP 404 sau khi restart server: restart MCP client/ADK để tạo session mới.
- OpenAI 429: kiểm tra API credit/billing; ChatGPT và API là hai sản phẩm billing
  riêng.
