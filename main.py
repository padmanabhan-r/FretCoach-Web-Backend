"""
FretCoach Dashboard API Server
FastAPI backend for the website dashboard with AI Coach
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv, find_dotenv

# Load environment variables from backend/.env
backend_env = os.path.join(os.path.dirname(__file__), '..', '..', 'backend', '.env')
if os.path.exists(backend_env):
    load_dotenv(backend_env)
else:
    load_dotenv(find_dotenv())

# Initialize Opik
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

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(chat.router, prefix="/api", tags=["chat"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "fretcoach-dashboard-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


#cd web/server && uvicorn main:app --host 0.0.0.0 --port 8000 --reload 