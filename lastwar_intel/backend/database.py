import sqlite3
import time
from pathlib import Path

DB_PATH = Path("data/players.db")


def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    with get_db() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                server        TEXT NOT NULL,
                name          TEXT NOT NULL,
                power         INTEGER,
                level         INTEGER,
                army_kills    INTEGER,
                vip_level     INTEGER,
                vip_score     INTEGER,
                alliance      TEXT,
                alliance_rank TEXT,
                career_level  INTEGER,
                gift_level    INTEGER,
                coord_x       INTEGER,
                coord_y       INTEGER,
                shield_active INTEGER DEFAULT 0,
                shield_expires INTEGER,
                last_seen     REAL,
                created_at    REAL DEFAULT (unixepoch()),
                UNIQUE(server, name)
            );
            CREATE INDEX IF NOT EXISTS idx_server ON players(server);
            CREATE INDEX IF NOT EXISTS idx_name   ON players(name COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_power  ON players(power DESC);
            CREATE INDEX IF NOT EXISTS idx_alliance ON players(alliance COLLATE NOCASE);
        """)


def upsert_player(data: dict):
    data["last_seen"] = time.time()
    fields = [k for k in data if k in {
        "server","name","power","level","army_kills","vip_level","vip_score",
        "alliance","alliance_rank","career_level","gift_level",
        "coord_x","coord_y","shield_active","shield_expires","last_seen"
    }]
    placeholders = ",".join(f":{f}" for f in fields)
    updates = ",".join(f"{f}=excluded.{f}" for f in fields if f not in ("server","name"))
    sql = f"""
        INSERT INTO players ({','.join(fields)}) VALUES ({placeholders})
        ON CONFLICT(server,name) DO UPDATE SET {updates}
    """
    with get_db() as con:
        con.execute(sql, {f: data.get(f) for f in fields})


def search_players(query: str = "", server: str = "", page: int = 0, per_page: int = 50):
    conditions, params = [], {}
    if server:
        conditions.append("server = :server")
        params["server"] = server
    if query:
        conditions.append("(name LIKE :q OR alliance LIKE :q)")
        params["q"] = f"%{query}%"
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params["limit"] = per_page
    params["offset"] = page * per_page
    with get_db() as con:
        rows = con.execute(
            f"SELECT * FROM players {where} ORDER BY power DESC LIMIT :limit OFFSET :offset",
            params
        ).fetchall()
        total = con.execute(f"SELECT COUNT(*) FROM players {where}", params).fetchone()[0]
    return [dict(r) for r in rows], total


def get_player(server: str, name: str):
    with get_db() as con:
        row = con.execute(
            "SELECT * FROM players WHERE server=? AND name=? COLLATE NOCASE",
            (server, name)
        ).fetchone()
    return dict(row) if row else None


def get_servers():
    with get_db() as con:
        rows = con.execute(
            "SELECT server, COUNT(*) as count FROM players GROUP BY server ORDER BY count DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats():
    with get_db() as con:
        total = con.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        servers = con.execute("SELECT COUNT(DISTINCT server) FROM players").fetchone()[0]
        last = con.execute("SELECT MAX(last_seen) FROM players").fetchone()[0]
    return {"total_players": total, "total_servers": servers, "last_update": last}
