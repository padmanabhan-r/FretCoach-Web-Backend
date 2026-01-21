"""
FretCoach Dashboard API Server
FastAPI backend for the website dashboard with AI Coach
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env vars (local .env or Railway vars)
load_dotenv()

# Optional: Opik
if os.getenv("OPIK_API_KEY"):
    try:
        from opik import configure
        configure()
        print("[Opik] Configured successfully")
    except Exception as e:
        print(f"[Opik] Configuration skipped: {e}")

from routers import sessions, chat

app = FastAPI(
    title="FretCoach Dashboard API",
    description="API for the FretCoach web dashboard with AI Practice Coach",
    version="1.0.0"
)

# CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(chat.router, prefix="/api", tags=["chat"])

# Healthcheck
@app.get("/health")
def health():
    return {"status": "ok"}
