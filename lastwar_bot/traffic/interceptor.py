"""
MITM-Proxy Addon für Last War: Survival Traffic-Analyse.

Setup:
  1. pip install mitmproxy
  2. Emulator-Proxy auf 127.0.0.1:8080 setzen
  3. mitmproxy CA-Zertifikat im Emulator installieren:
       - mitmproxy starten: mitmdump -s interceptor.py
       - Im Emulator Browser: http://mitm.it → Zertifikat herunterladen & installieren
  4. Emulator neu starten
  5. Last War starten und Map öffnen

Alles was das Spiel vom Server empfängt wird geloggt und analysiert.
"""

import json
import logging
import sqlite3
import time
from pathlib import Path

from mitmproxy import http
from parser import ResponseParser

log = logging.getLogger("lw_interceptor")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("traffic.log", encoding="utf-8"),
    ],
)

DB_PATH = Path("captured_data.db")
INTERESTING_KEYWORDS = [
    "shield", "protect", "expire", "timer",
    "coord", "position", "x", "y",
    "player", "user", "alliance",
    "power", "troop", "resource",
]


class LastWarInterceptor:
    def __init__(self):
        self.parser = ResponseParser()
        self._init_db()
        log.info("Interceptor gestartet. Warte auf Last War Traffic...")

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts       REAL,
                    host     TEXT,
                    path     TEXT,
                    method   TEXT,
                    req_body TEXT,
                    resp_body TEXT,
                    parsed   TEXT
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts          REAL,
                    name        TEXT,
                    coord_x     INTEGER,
                    coord_y     INTEGER,
                    alliance    TEXT,
                    power       INTEGER,
                    shield_expires INTEGER,
                    shield_active  INTEGER,
                    raw         TEXT
                )
            """)

    # ------------------------------------------------------------------
    # mitmproxy hooks
    # ------------------------------------------------------------------

    def response(self, flow: http.HTTPFlow):
        host = flow.request.pretty_host
        path = flow.request.path

        # Nur relevante Hosts verarbeiten
        if not self._is_game_traffic(host):
            return

        content_type = flow.response.headers.get("content-type", "")
        body_bytes = flow.response.content

        if not body_bytes:
            return

        parsed = self.parser.parse(body_bytes, content_type)
        self._log_request(flow, parsed)

        if parsed:
            players = self.parser.extract_players(parsed)
            if players:
                self._save_players(players)
                self._print_players(players)

    def request(self, flow: http.HTTPFlow):
        host = flow.request.pretty_host
        if not self._is_game_traffic(host):
            return
        log.debug("→ %s %s%s", flow.request.method, host, flow.request.path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_game_traffic(self, host: str) -> bool:
        # Last War nutzt eigene Server – alles was nicht Google/Apple/CDN ist
        skip = ["google", "apple", "gstatic", "googleapis", "firebase",
                "crashlytics", "adjust", "appsflyer", "cdn", "akamai"]
        return not any(s in host.lower() for s in skip)

    def _log_request(self, flow: http.HTTPFlow, parsed):
        try:
            with sqlite3.connect(DB_PATH) as con:
                con.execute(
                    "INSERT INTO requests (ts,host,path,method,req_body,resp_body,parsed) VALUES (?,?,?,?,?,?,?)",
                    (
                        time.time(),
                        flow.request.pretty_host,
                        flow.request.path,
                        flow.request.method,
                        flow.request.text[:4000] if flow.request.text else "",
                        flow.response.text[:4000] if flow.response.text else "",
                        json.dumps(parsed, ensure_ascii=False)[:4000] if parsed else None,
                    ),
                )
        except Exception as e:
            log.warning("DB-Fehler beim Loggen: %s", e)

    def _save_players(self, players: list[dict]):
        with sqlite3.connect(DB_PATH) as con:
            for p in players:
                con.execute(
                    """INSERT INTO players
                       (ts,name,coord_x,coord_y,alliance,power,shield_expires,shield_active,raw)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        time.time(),
                        p.get("name"),
                        p.get("coord_x"),
                        p.get("coord_y"),
                        p.get("alliance"),
                        p.get("power"),
                        p.get("shield_expires"),
                        p.get("shield_active"),
                        json.dumps(p, ensure_ascii=False),
                    ),
                )

    def _print_players(self, players: list[dict]):
        log.info("=" * 60)
        log.info("SPIELER-DATEN GEFUNDEN (%d):", len(players))
        for p in players:
            shield_info = ""
            if p.get("shield_expires"):
                remaining = p["shield_expires"] - time.time()
                if remaining > 0:
                    h = int(remaining // 3600)
                    m = int((remaining % 3600) // 60)
                    shield_info = f" | SCHILD: {h}h {m}m"
                else:
                    shield_info = " | KEIN SCHILD"
            log.info(
                "  %-20s Pos:(%s,%s) Allianz:%-6s Power:%-8s%s",
                p.get("name", "?"),
                p.get("coord_x", "?"),
                p.get("coord_y", "?"),
                p.get("alliance", "?"),
                p.get("power", "?"),
                shield_info,
            )
        log.info("=" * 60)


# mitmproxy erwartet eine Instanz als 'addon'
addon = LastWarInterceptor()
