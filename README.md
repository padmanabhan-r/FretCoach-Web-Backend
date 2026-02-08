# FretCoach Hub - Web Backend

FastAPI backend powering analytics and AI coaching. Backend for [fretcoach.online](https://www.fretcoach.online)

## What is this?

Python API providing practice session data and a LangGraph-powered AI coach that queries your practice history and generates personalized recommendations.

## Tech Stack

- Python 3.12 + FastAPI + Uvicorn
- LangChain + LangGraph (AI orchestration)
- Google Gemini 3 Flash Preview (primary LLM)
- MiniMax 2.1 (fallback LLM)
- PostgreSQL via Supabase
- Comet Opik (observability)
- Deployed on Railway

## Quick Start

```bash
uv sync  # or pip install -r requirements.txt
cp .env.example .env  # Add your API keys and DATABASE_URL
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API docs at http://localhost:8000/docs

## Environment Variables

Required in `.env`:
- `DATABASE_URL` - PostgreSQL connection string (Supabase)
- `GOOGLE_API_KEY` - Google Gemini API key
- `ANTHROPIC_API_KEY` - MiniMax API key (fallback)
- `OPIK_API_KEY` - Opik tracing (optional)

## API Endpoints

- `GET /api/sessions` - Fetch practice sessions with filtering
- `POST /api/chat` - AI coach chat (LangGraph workflow)
- `GET /health` - Health check

## LangGraph Architecture

AI coach uses a stateful agent with:
- **Tools:** `get_database_schema`, `execute_sql_query`
- **Memory:** Thread-based conversation persistence
- **Fallback:** Auto-retry with MiniMax if Gemini rate limited

## Production

Deployed to Railway with auto-deploy from `main` branch.

**Production repo:** [github.com/padmanabhan-r/FretCoach-Web-Backend](https://github.com/padmanabhan-r/FretCoach-Web-Backend)

## Documentation

- [Web Dashboard Guide](../../docs/web-dashboard.md) - Full usage docs
- [Opik Observability](../../opik/opik-usage.md) - LLM tracing and monitoring
