"""
LIMA — Ligue d'Improvisation du Maine-et-Loire
FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.limiting import limiter
from app.middleware.activity_tracker import ActivityTrackerMiddleware
from app.routers import (
    admin,
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
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ActivityTrackerMiddleware)

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
app.include_router(admin.router, prefix="/api/admin")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health_check():
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "version": "0.1.0"}
