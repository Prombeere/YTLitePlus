"""
Zeigt alle gesammelten Daten aus der SQLite-Datenbank an.
Ausführen mit: python viewer.py

Zeigt alle Spieler, gefundene Shield-Daten und rohe Requests.
"""

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path("captured_data.db")


def fmt_time(ts):
    if not ts:
        return "?"
    remaining = ts - time.time()
    if remaining <= 0:
        return "ABGELAUFEN"
    h = int(remaining // 3600)
    m = int((remaining % 3600) // 60)
    return f"{h}h {m}m"


def show_players():
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT name, coord_x, coord_y, alliance, power, shield_expires, shield_active, ts FROM players ORDER BY ts DESC LIMIT 100"
        ).fetchall()

    if not rows:
        print("Keine Spieler-Daten bisher.")
        return

    print(f"\n{'SPIELER':<22} {'X':>6} {'Y':>6} {'ALLIANZ':<8} {'POWER':>10} {'SCHILD':<16} {'ERFASST'}")
    print("-" * 90)
    for name, x, y, alliance, power, shield_exp, shield_active, ts in rows:
        shield_str = fmt_time(shield_exp) if shield_exp else ("Aktiv" if shield_active else "Kein Schild")
        captured = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "?"
        print(f"{str(name):<22} {str(x):>6} {str(y):>6} {str(alliance):<8} {str(power):>10} {shield_str:<16} {captured}")


def show_shield_leaks():
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT ts, host, path, parsed FROM requests WHERE parsed LIKE '%shield%' OR parsed LIKE '%protect%' OR parsed LIKE '%bubble%' ORDER BY ts DESC LIMIT 20"
        ).fetchall()

    if not rows:
        print("\nKeine Shield-Daten im Traffic gefunden.")
        return

    print(f"\n{'=== SHIELD-DATENLECKS ==='}")
    for ts, host, path, parsed in rows:
        t = time.strftime("%H:%M:%S", time.localtime(ts))
        print(f"\n[{t}] {host}{path}")
        try:
            data = json.loads(parsed)
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
        except Exception:
            print(parsed[:500])


def show_all_hosts():
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT host, COUNT(*) as cnt FROM requests GROUP BY host ORDER BY cnt DESC"
        ).fetchall()
    print("\n=== GAME SERVER HOSTS ===")
    for host, cnt in rows:
        print(f"  {cnt:4d}x  {host}")


def show_raw_requests(limit: int = 5):
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT ts, host, path, method, resp_body FROM requests ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    print(f"\n=== LETZTE {limit} REQUESTS ===")
    for ts, host, path, method, body in rows:
        t = time.strftime("%H:%M:%S", time.localtime(ts))
        print(f"\n[{t}] {method} {host}{path}")
        print(f"  Response: {body[:300] if body else '(leer)'}")


if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"Datenbank nicht gefunden: {DB_PATH}")
        print("Starte zuerst: mitmdump -s interceptor.py")
        exit(1)

    show_players()
    show_shield_leaks()
    show_all_hosts()
    show_raw_requests()
