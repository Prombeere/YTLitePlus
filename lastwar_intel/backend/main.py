from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import time
from pathlib import Path

from database import init_db, upsert_player, search_players, get_player, get_servers, get_stats

app = FastAPI(title="Last War Intel", docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

init_db()

STATIC = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


# ── Frontend routes ──────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

@app.get("/player/{server}/{name}")
def player_page(server: str, name: str):
    return FileResponse(STATIC / "player.html")


# ── API ──────────────────────────────────────────────────────────────

@app.get("/api/stats")
def stats():
    return get_stats()

@app.get("/api/servers")
def servers():
    return get_servers()

@app.get("/api/search")
def search(
    q: str = Query(""),
    server: str = Query(""),
    page: int = Query(0, ge=0),
    per_page: int = Query(50, le=100),
):
    players, total = search_players(q, server, page, per_page)
    return {"players": players, "total": total, "page": page, "per_page": per_page}

@app.get("/api/player/{server}/{name}")
def player(server: str, name: str):
    p = get_player(server, name)
    if not p:
        raise HTTPException(404, "Player not found")
    return p

@app.post("/api/ingest")
def ingest(players: list[dict]):
    """Called by the interceptor to submit captured player data."""
    saved = 0
    for p in players:
        if p.get("name") and p.get("server"):
            upsert_player(p)
            saved += 1
    return {"saved": saved}


# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
