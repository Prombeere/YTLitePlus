"""
Parst Game-Server-Responses (JSON, Protobuf, verschlüsselt).
Versucht mehrere Formate und extrahiert Spielerdaten.
"""

import json
import logging
import re
import time
from typing import Any, Optional

log = logging.getLogger("lw_parser")

# Mögliche Feldnamen für Spieler-Koordinaten (je nach Spielserver-Implementierung)
_COORD_X_KEYS = {"x", "coord_x", "pos_x", "posX", "mapX", "tile_x", "tileX", "cx"}
_COORD_Y_KEYS = {"y", "coord_y", "pos_y", "posY", "mapY", "tile_y", "tileY", "cy"}
_NAME_KEYS    = {"name", "player_name", "playerName", "nick", "nickname", "username"}
_ALLIANCE_KEYS = {"alliance", "alliance_name", "allianceName", "guild", "clan", "tag"}
_POWER_KEYS   = {"power", "might", "strength", "total_power", "totalPower", "bp"}
_SHIELD_KEYS  = {"shield", "shield_expire", "shieldExpire", "shield_end", "shieldEnd",
                 "protect", "protect_expire", "protectEnd", "immune", "immune_end",
                 "bubble", "bubble_expire", "peace_shield", "peaceshield"}


class ResponseParser:
    def parse(self, body: bytes, content_type: str = "") -> Optional[Any]:
        """Versucht den Response-Body zu parsen."""
        # 1. JSON direkt
        result = self._try_json(body)
        if result is not None:
            return result

        # 2. JSON nach URL-Decode
        result = self._try_json(body, url_decode=True)
        if result is not None:
            return result

        # 3. Protobuf – gib Raw-Bytes als Hex zurück für manuelle Analyse
        result = self._try_protobuf(body)
        if result is not None:
            return result

        # 4. Komprimiert (gzip/zlib)
        result = self._try_decompress(body)
        if result is not None:
            return result

        return None

    def extract_players(self, data: Any) -> list[dict]:
        """Durchsucht rekursiv geparste Daten nach Spieler-Objekten."""
        players = []
        self._search(data, players)
        return players

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _try_json(self, body: bytes, url_decode: bool = False) -> Optional[Any]:
        try:
            text = body.decode("utf-8", errors="replace")
            if url_decode:
                from urllib.parse import unquote
                text = unquote(text)
            return json.loads(text)
        except Exception:
            return None

    def _try_protobuf(self, body: bytes) -> Optional[dict]:
        try:
            # Einfacher Protobuf-Decoder ohne Schema
            fields = {}
            i = 0
            while i < len(body):
                if i >= len(body):
                    break
                tag_byte = body[i]
                field_number = tag_byte >> 3
                wire_type = tag_byte & 0x07
                i += 1
                if wire_type == 0:  # varint
                    val, i = self._decode_varint(body, i)
                    fields[f"field_{field_number}"] = val
                elif wire_type == 2:  # length-delimited
                    length, i = self._decode_varint(body, i)
                    chunk = body[i:i + length]
                    i += length
                    try:
                        fields[f"field_{field_number}"] = chunk.decode("utf-8", errors="replace")
                    except Exception:
                        fields[f"field_{field_number}"] = chunk.hex()
                else:
                    break
            return {"_protobuf": fields} if fields else None
        except Exception:
            return None

    def _try_decompress(self, body: bytes) -> Optional[Any]:
        import zlib
        for wbits in (15, -15, 31):
            try:
                decompressed = zlib.decompress(body, wbits)
                return self._try_json(decompressed)
            except Exception:
                continue
        return None

    @staticmethod
    def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
        result = 0
        shift = 0
        while pos < len(data):
            b = data[pos]
            pos += 1
            result |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        return result, pos

    # ------------------------------------------------------------------
    # Player extraction
    # ------------------------------------------------------------------

    def _search(self, obj: Any, results: list, depth: int = 0):
        if depth > 20:
            return
        if isinstance(obj, dict):
            player = self._try_extract_player(obj)
            if player:
                results.append(player)
            else:
                for v in obj.values():
                    self._search(v, results, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                self._search(item, results, depth + 1)

    def _try_extract_player(self, obj: dict) -> Optional[dict]:
        """Prüft ob ein Dict ein Spieler-Objekt ist und extrahiert Felder."""
        keys_lower = {k.lower(): k for k in obj}

        has_name = any(k in keys_lower for k in _NAME_KEYS)
        has_pos = (
            any(k in keys_lower for k in _COORD_X_KEYS) or
            any(k in keys_lower for k in _COORD_Y_KEYS)
        )

        if not (has_name or has_pos):
            return None

        player = {}

        # Name
        for key in _NAME_KEYS:
            if key in keys_lower:
                player["name"] = obj[keys_lower[key]]
                break

        # Koordinaten
        for key in _COORD_X_KEYS:
            if key in keys_lower:
                player["coord_x"] = obj[keys_lower[key]]
                break
        for key in _COORD_Y_KEYS:
            if key in keys_lower:
                player["coord_y"] = obj[keys_lower[key]]
                break

        # Allianz
        for key in _ALLIANCE_KEYS:
            if key in keys_lower:
                player["alliance"] = obj[keys_lower[key]]
                break

        # Power
        for key in _POWER_KEYS:
            if key in keys_lower:
                player["power"] = obj[keys_lower[key]]
                break

        # Shield / Bubble – das Interessante
        for key in _SHIELD_KEYS:
            if key in keys_lower:
                raw_val = obj[keys_lower[key]]
                player["shield_raw_key"] = key
                player["shield_raw_value"] = raw_val
                # Timestamp oder boolean?
                if isinstance(raw_val, (int, float)) and raw_val > 1_000_000_000:
                    player["shield_expires"] = int(raw_val)
                    player["shield_active"] = int(raw_val) > time.time()
                elif isinstance(raw_val, bool):
                    player["shield_active"] = raw_val
                log.warning(
                    "SHIELD-DATEN GEFUNDEN! Key='%s' Value='%s' – "
                    "Server schickt Shield-Info an Client!",
                    key, raw_val,
                )
                break

        # Rohdaten anhängen für vollständige Analyse
        player["_raw"] = obj
        return player if len(player) > 1 else None
