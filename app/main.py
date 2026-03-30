"""
LIMA — Ligue d'Improvisation du Maine-et-Loire
FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    auth,
    alignments,
    commissions,
    events,
    members,
    seasons,
    settings as settings_router,
    show_plans,
    venues,
)

app = FastAPI(
    title="LIMA API",
    description="API backend de la Ligue d'Improvisation du Maine-et-Loire",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
origins = settings.CORS_ORIGINS
if origins == ["*"]:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(members.router)
app.include_router(seasons.router)
app.include_router(events.router)
app.include_router(venues.router)
app.include_router(alignments.router)
app.include_router(commissions.router)
app.include_router(show_plans.router)
app.include_router(settings_router.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health_check():
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "version": "0.1.0"}
