"""
FretCoach Dashboard API Server
FastAPI backend for the website dashboard with AI Coach
"""
#uvicorn main:app --host 0.0.0.0 --port 8000

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env vars (local .env or Railway vars)
load_dotenv()

# Configure Opik
from opik import configure
configure()
print("[Opik] Configured successfully")

from routers import sessions, chat_langgraph

app = FastAPI(
    title="FretCoach Dashboard API",
    description="API for the FretCoach web dashboard with AI Practice Coach (LangGraph)",
    version="2.0.0"
)

# ✅ PRODUCTION CORS
ALLOWED_ORIGINS = [
    "https://fretcoach.online",
    "https://www.fretcoach.online",
    "https://fret-coach-web-frontend.vercel.app",

    # Local development
    "http://localhost:5173",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(chat_langgraph.router, prefix="/api", tags=["chat"])

# Healthcheck (Railway)
@app.get("/health")
def health():
    return {"status": "ok"}