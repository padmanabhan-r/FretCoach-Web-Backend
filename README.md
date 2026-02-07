# FretCoach Hub - Web Backend

FastAPI backend powering FretCoach Hub analytics and AI coaching platform.

**Live Deployment:** Backend for [fretcoach.online](https://www.fretcoach.online)

---

## Overview

FretCoach Hub backend is a Python FastAPI service that provides REST APIs for practice session analytics and an AI-powered conversational coach. It uses LangGraph for intelligent agent orchestration, connecting to PostgreSQL for practice data and leveraging Google Gemini for natural language interactions.

**This is the backend component** — the Python API deployed to Railway. For the frontend React application, see [web-frontend/](../web-frontend/).

---

## Key Features

### 1. Sessions API
- **Fetch practice sessions** with filtering by date range, user, and limit
- **Aggregate statistics** including total sessions, practice time, average metrics
- **Session details** with complete metric breakdown and note statistics
- **CORS-configured** for production Vercel frontend and local development

### 2. AI Chat Coach (LangGraph)
- **Conversational AI** powered by Google Gemini 2.5 Flash
- **Database-grounded responses** using text-to-SQL capabilities
- **Tool-calling agent** with database schema introspection and SQL execution
- **Practice plan generation** in structured JSON format
- **Automatic fallback** to MiniMax 2.1 when Gemini rate limits are hit
- **Conversation persistence** with thread-based memory using LangGraph checkpointing

### 3. Observability & Tracing
- **Opik integration** for LLM call tracing and evaluation
- **Thread-level tracking** for multi-turn conversations
- **Tool call logging** for SQL queries and database access
- **Error monitoring** with detailed exception tracking

---

## Tech Stack

**Framework:**
- **Python 3.12+** — Modern async Python
- **FastAPI 0.109+** — High-performance async web framework
- **Uvicorn** — ASGI server with WebSocket support

**AI Orchestration:**
- **LangChain 0.1+** — LLM application framework
- **LangGraph 0.2+** — Agent workflow orchestration with stateful graphs
- **Google Gemini 2.5 Flash** — Primary LLM for coaching (via `langchain-google-genai`)
- **MiniMax 2.1** — Fallback LLM for rate limit scenarios (via `langchain-anthropic`)

**Database:**
- **PostgreSQL** — Production database (Supabase hosted)
- **psycopg2-binary** — PostgreSQL adapter for Python

**Observability:**
- **Comet Opik** — LLM tracing and evaluation platform

**Deployment:**
- **Railway** — Backend hosting with auto-deploy from GitHub

---

## Project Structure

```
web-backend/
├── routers/
│   ├── sessions.py           # Practice sessions API endpoints
│   ├── chat_langgraph.py     # AI coach chat endpoints (LangGraph)
│   └── __init__.py
│
├── tools/
│   ├── database_tools.py     # LangGraph tools for SQL execution
│   ├── plotting_tools.py     # Chart generation tools (planned)
│   └── __init__.py
│
├── ddl/
│   └── schema.sql            # Database schema definitions
│
├── main.py                   # FastAPI application entry point
├── langgraph_workflow.py     # LangGraph agent workflow definition
├── database.py               # Database connection utilities
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
└── test_langgraph.py         # LangGraph workflow tests
```

---

## Installation

### Prerequisites
- Python 3.12+
- PostgreSQL database (or Supabase account)
- Google Gemini API key
- Optional: MiniMax API key (for fallback)
- Optional: Opik API key (for observability)

### Setup

```bash
# Clone the repository
git clone https://github.com/padmanabhan-r/FretCoach.git
cd FretCoach/web/web-backend

# Install dependencies (using uv or pip)
uv sync
# OR
pip install -r requirements.txt

# Create .env file (see Environment Variables section)
cp .env.example .env
```

---

## Environment Variables

Create a `.env` file in the `web/web-backend/` directory:

```env
# Database Configuration
DATABASE_URL=postgresql://postgres.your-project-id:your-password@aws-region.pooler.supabase.com:5432/postgres

# Or use individual components
DB_USER=postgres.your-project-id
DB_PASSWORD=your-supabase-db-password
DB_HOST=aws-region.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres

# LLM Provider Configuration
GOOGLE_API_KEY=your-google-api-key
OPENAI_API_KEY=your-openai-api-key  # Optional: if using OpenAI
USE_OPENAI_MODEL=false               # Set to "true" to use OpenAI instead of Gemini
OPENAI_MODEL=gpt-4o-mini             # Model to use if USE_OPENAI_MODEL=true

# Fallback LLM (MiniMax via Anthropic wrapper)
ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic
ANTHROPIC_API_KEY=your-minimax-api-key

# Opik Observability (optional)
OPIK_API_KEY=your-opik-api-key
OPIK_PROJECT_NAME=FretCoach-Hub
OPIK_WORKSPACE=your-opik-workspace
OPIK_URL_OVERRIDE=https://www.comet.com/opik/api
```

**For production (Railway):**
- Set all environment variables in Railway dashboard
- `DATABASE_URL` from Supabase connection pooler
- `PORT` is automatically provided by Railway

---

## Development

```bash
# Start development server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Runs the API at **http://localhost:8000** with auto-reload on code changes.

**Testing the API:**
- **OpenAPI docs:** http://localhost:8000/docs (Swagger UI)
- **Alternative docs:** http://localhost:8000/redoc (ReDoc)
- **Health check:** http://localhost:8000/health

**Frontend Required:** For full testing, run the frontend at http://localhost:5173 and ensure `VITE_API_BASE_URL=http://localhost:8000` in frontend `.env`.

---

## Building for Production

Railway automatically builds and deploys using:

```bash
# Railway start command
uvicorn main:app --host 0.0.0.0 --port $PORT
```

No manual build step required — Railway handles Python environment setup and dependency installation.

---

## Deployment

### Railway (Recommended)

This project is configured for automatic deployment to Railway:

1. **Connect GitHub Repository:**
   - Import project in Railway dashboard
   - Link to your fork/repo

2. **Configure Start Command:**
   - Railway auto-detects Python and runs `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables:**
   - Add all variables from `.env.example` in Railway dashboard
   - Ensure `DATABASE_URL` points to Supabase connection pooler

4. **Deploy:**
   - Every push to `main` triggers auto-deployment
   - Health check endpoint: `GET /health`

**Production Backend URL:** Auto-generated Railway URL or custom domain

---

## API Endpoints

### Sessions API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | Fetch user practice sessions with optional date filtering |
| `/api/sessions/{session_id}` | GET | Get detailed session by ID |
| `/health` | GET | Health check for Railway monitoring |

**Sessions Query Parameters:**
- `user_id` (string, default: "default_user") — User identifier
- `limit` (int, default: 10, max: 50) — Number of sessions to return
- `include_aggregates` (bool, default: true) — Include summary statistics
- `start_date` (string, optional) — Filter from date (ISO format: "2024-01-01")
- `end_date` (string, optional) — Filter to date (ISO format: "2024-01-07")

**Sessions Response:**
```json
{
  "success": true,
  "sessions": [
    {
      "session_id": "uuid",
      "user_id": "default_user",
      "start_timestamp": "2024-01-15T10:30:00",
      "pitch_accuracy": 85.5,
      "scale_conformity": 92.3,
      "timing_stability": 78.9,
      "scale_chosen": "C Major",
      "duration_seconds": 300
    }
  ],
  "aggregates": {
    "total_sessions": 45,
    "total_practice_time": 13500,
    "avg_pitch_accuracy": 82.5,
    "avg_scale_conformity": 88.7,
    "avg_timing_stability": 75.3,
    "scales_practiced": ["C Major", "A Minor", "G Major"]
  }
}
```

---

### AI Chat API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send message to AI coach, get response with optional practice plan |

**Chat Request:**
```json
{
  "messages": [
    {"role": "user", "content": "What should I practice next?"}
  ],
  "user_id": "default_user",
  "thread_id": "optional-thread-uuid"
}
```

**Chat Response:**
```json
{
  "response": "Based on your recent sessions, I recommend practicing...",
  "thread_id": "thread-uuid",
  "data": [
    {"scale_chosen": "C Major", "pitch_accuracy": 85.5}
  ],
  "plan": {
    "plan_id": "plan-uuid",
    "focus_area": "Timing Stability",
    "current_score": 75.3,
    "suggested_scale": "G Major",
    "suggested_scale_type": "Pentatonic",
    "session_target": 85,
    "exercises": [
      "Practice with metronome at 80 BPM",
      "Focus on even note spacing"
    ]
  }
}
```

---

## LangGraph Agent Architecture

### Workflow Overview

The AI coach uses a **stateful LangGraph workflow** with tool-calling capabilities:

1. **Agent Node** — LLM receives user message and conversation history
2. **Tool Calling** — Agent can call `get_database_schema` or `execute_sql_query` tools
3. **Tool Execution Node** — SQL queries run against PostgreSQL
4. **Response Generation** — Agent synthesizes data into natural language response
5. **Memory Persistence** — Conversation saved using LangGraph checkpointing

### Agent State

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add]  # Full conversation history
    user_id: str                                     # User identifier for SQL filtering
    thread_id: Optional[str]                         # Conversation thread ID
    next_action: Optional[str]                       # Internal agent control
```

### Available Tools

**1. `get_database_schema`**
- Returns PostgreSQL schema for `fretcoach.sessions` and `fretcoach.ai_practice_plans` tables
- Helps agent understand available columns and data types

**2. `execute_sql_query`**
- Executes read-only SQL queries against the database
- Automatically filters by `user_id` for data isolation
- Returns JSON-serialized results

### Prompting Strategy

**Core System Prompt** (always included, ~150 tokens):
- Role definition: "AI guitar practice coach for FretCoach"
- Available tools and their purpose
- Key rules: user filtering, data-driven insights, JSON practice plan format

**Detailed Guidelines** (sent only on first message to save tokens):
- Database schema reference
- Example SQL queries
- Practice plan generation template
- Response formatting guidelines

### Fallback Mechanism

When Gemini 2.5 Flash hits rate limits (free tier: 20 requests/day):
1. Error detected: `RESOURCE_EXHAUSTED`, `429`, `RATE`, or `QUOTA`
2. Workflow automatically retries with MiniMax 2.1
3. User receives response from fallback model
4. Returns HTTP 503 if both models fail

---

## Database Schema

### Sessions Table

**Table:** `fretcoach.sessions`

| Column | Type | Description |
|--------|------|-------------|
| session_id | UUID | Primary key, unique session identifier |
| user_id | VARCHAR | User identifier |
| start_timestamp | TIMESTAMP | Session start time |
| end_timestamp | TIMESTAMP | Session end time |
| duration_seconds | INTEGER | Total practice duration |
| scale_chosen | VARCHAR | Scale practiced (e.g., "C Major") |
| scale_type | VARCHAR | Scale type (e.g., "Major", "Pentatonic") |
| pitch_accuracy | FLOAT | Pitch accuracy score (0-100) |
| scale_conformity | FLOAT | Scale conformity score (0-100) |
| timing_stability | FLOAT | Timing stability score (0-100) |
| total_notes_played | INTEGER | Total notes in session |
| correct_notes_played | INTEGER | Notes matching scale |
| bad_notes_played | INTEGER | Notes outside scale |
| sensitivity | FLOAT | Detection sensitivity setting |
| strictness | FLOAT | Evaluation strictness setting |
| ambient_light_option | VARCHAR | Smart bulb setting |

### Practice Plans Table

**Table:** `fretcoach.ai_practice_plans`

| Column | Type | Description |
|--------|------|-------------|
| practice_id | UUID | Primary key |
| user_id | VARCHAR | User identifier |
| generated_at | TIMESTAMP | Plan creation time |
| practice_plan | JSONB | Structured plan (scale, exercises, reasoning) |
| status | VARCHAR | "pending", "in_progress", or "completed" |
| session_id | UUID | Linked session when plan is completed |

---

## CORS Configuration

The backend allows requests from:

**Production:**
- `https://fretcoach.online`
- `https://www.fretcoach.online`
- `https://fret-coach-web-frontend.vercel.app`

**Development:**
- `http://localhost:5173` (Vite dev server)
- `http://localhost:8080`

CORS is configured in `main.py:39-45` for all HTTP methods and headers.

---

## Opik Observability

All LLM interactions are traced using **Comet Opik**:

**What gets traced:**
- Every chat API call (`POST /api/chat`)
- LangGraph workflow invocations
- Tool calls (SQL queries)
- Model responses (Gemini/MiniMax)
- Errors and exceptions

**Trace Attributes:**
- `thread_id` — Conversation identifier
- `user_id` — User making the request
- `model` — LLM used (gemini-2.5-flash or MiniMax-M2.1)
- `latency` — Response time
- `tool_calls` — SQL queries executed

**View traces:**
- Opik dashboard: https://www.comet.com/opik/
- Workspace: `padmanabhan-r-7119`
- Project: `FretCoach-Hub`

> **Detailed Opik documentation:** See [opik/opik-usage.md](../../opik/opik-usage.md)

---

## Testing

### Running Tests

```bash
# Run LangGraph workflow tests
pytest test_langgraph.py -v
```

### Manual API Testing

**Using curl:**
```bash
# Health check
curl http://localhost:8000/health

# Fetch sessions
curl "http://localhost:8000/api/sessions?user_id=default_user&limit=5"

# Chat with AI coach
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Show my recent sessions"}],
    "user_id": "default_user"
  }'
```

**Using OpenAPI UI:**
- Navigate to http://localhost:8000/docs
- Try out endpoints interactively

---

## Troubleshooting

### Database Connection Failed

**Issue:** `psycopg2.OperationalError: could not connect to server`

**Solutions:**
1. Verify `DATABASE_URL` in `.env` is correct
2. Check Supabase database is running and accessible
3. Ensure IP allowlist includes your location (Supabase → Settings → Database → Network)
4. Test connection: `psql $DATABASE_URL`

---

### AI Coach Not Responding

**Issue:** Chat endpoint returns 500 error or "Service Unavailable"

**Solutions:**
1. Check `GOOGLE_API_KEY` is valid and has quota remaining
2. Review backend logs for rate limit errors
3. Verify `ANTHROPIC_API_KEY` is set for fallback
4. Check Opik traces for detailed error context
5. Test LangGraph workflow: `python test_langgraph.py`

---

### CORS Errors

**Issue:** Frontend shows "CORS policy blocked" in browser console

**Solutions:**
1. Verify frontend origin is in `ALLOWED_ORIGINS` list (main.py:29-37)
2. Add development URL if testing locally: `http://localhost:5173`
3. Check browser console for exact blocked origin
4. Restart backend after updating CORS settings

---

### Slow API Responses

**Issue:** Requests take >5 seconds

**Solutions:**
1. Check database query performance (add indexes on `user_id`, `start_timestamp`)
2. Reduce session `limit` parameter in requests
3. Monitor Opik traces for slow tool calls
4. Check network latency to Supabase
5. Enable database connection pooling

---

## Production Repositories

**Note:** This is a monorepo reference implementation. The **production deployment** uses separate repositories:

- **Frontend:** [github.com/padmanabhan-r/FretCoach-Web-Frontend](https://github.com/padmanabhan-r/FretCoach-Web-Frontend)
- **Backend:** [github.com/padmanabhan-r/FretCoach-Web-Backend](https://github.com/padmanabhan-r/FretCoach-Web-Backend)

**Why separate?** Automated deployments to Vercel (frontend) and Railway (backend) via GitHub Actions.

---

## Documentation

For detailed architecture and usage:
- [Web Dashboard Guide](../../docs/web-dashboard.md)
- [AI Coach Agent Engine](../../docs/ai-coach-agent-engine.md)
- [System Architecture](../../docs/architecture.md#component-2-web-platform)
- [Environment Setup](../../docs/environment-setup.md)
- [Opik Observability](../../opik/opik-usage.md)

---

## Contributing

Contributions welcome! Please see [Contributing Guidelines](../../README.md#contributing) in the main README.

**Areas for Contribution:**
- Additional LangGraph tools (plotting, advanced analytics)
- Performance optimizations (query caching, connection pooling)
- Enhanced error handling and logging
- API endpoint expansion (export, sharing, leaderboards)

---

## License

Open source — see [LICENSE](../../LICENSE) in repository root.

---

**Built with FastAPI ⚡ | Powered by FretCoach 🎸**
