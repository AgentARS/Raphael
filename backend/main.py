"""
Main FastAPI application for Raphael.

Sets up CORS, lifespan (DB init), routers, and health check.
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import entries, search, tasks, ideas, entities, chat, calendar, events


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database on startup."""
    await init_db()
    yield


app = FastAPI(
    title="Raphael",
    description="Personal AI Knowledge Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(entries.router)
app.include_router(search.router)
app.include_router(tasks.router)
app.include_router(ideas.router)
app.include_router(entities.router)
app.include_router(chat.router)
app.include_router(calendar.router)
app.include_router(events.router)


@app.get("/api/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }
