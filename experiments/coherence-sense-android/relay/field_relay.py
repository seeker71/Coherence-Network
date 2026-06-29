#!/usr/bin/env python3
# field_relay.py — the Mac-side cross-device relay (NAMED HOST CARRIER, not body).
#
# HONEST LABEL: this is a host stand-in for the in-fkwu native TCP server. The
# C-bootstrapped fkwu (driver.fk, line ~1525) HAS a native host-net serve loop
# (socket/bind/listen/accept/fork + read request into fk_src + fk_walk a Form
# recipe with stdout dup'd to the client). Wiring that recipe's roster STATE across
# fork-per-connection (children can't write heap back to the parent) is the deep
# piece deferred for one pass. So the SOCKET ACCEPT here is host Python — but the
# RELAY DECISION is field-relay.fk's law: CONTENT-BLIND (we read from/kind metadata,
# never inspect the sensing payload's meaning) and CONSENT IS THE ONE GATE (a cell
# is reachable only through the signal-kind "sense" it offers; the relay polices no
# identity). The roster is the append-only board fr-route names (QUEUE 2).
#
# The fusion/trust/surprise MATH is NOT here — that runs in native fkwu on each
# device. This carrier only moves opaque readings between cells.
#
# Endpoints:
#   POST /reading   body: device|present|luma|surprise|kind   -> stores, returns roster
#   GET  /roster                                              -> roster of recent readings
#
# Roster line: device|present|luma|surprise|kind|age_ms

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8777

# The registry's one offered signal-kind. fr-consent-ok?: a reading whose kind is
# not in the offered interface is DENY (3). Every cell offers "sense".
OFFERED_KINDS = {"sense"}
STALE_MS = 30_000  # readings older than this are composted from the roster

# roster: device_id -> dict(present, luma, surprise, kind, at_ms)
_roster = {}


def fr_route(reading):
    # field-relay.fk fr-route, content-blind: reads kind only, never the payload.
    kind = reading.get("kind", "")
    if kind not in OFFERED_KINDS:
        return 3  # DENY — kind not offered
    return 1      # DELIVER (relay forwards to the roster all connected cells read)


def _prune(now_ms):
    dead = [d for d, r in _roster.items() if now_ms - r["at_ms"] > STALE_MS]
    for d in dead:
        del _roster[d]


def _roster_lines(exclude=None, now_ms=None):
    now_ms = now_ms or int(time.time() * 1000)
    _prune(now_ms)
    out = []
    for dev, r in _roster.items():
        if dev == exclude:
            continue
        age = now_ms - r["at_ms"]
        out.append(f"{dev}|{r['present']}|{r['luma']}|{r['surprise']}|{r['kind']}|{age}")
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet; the body's witness is the roster, not access logs

    def _send(self, code, text):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/roster"):
            dev = None
            if "?" in self.path:
                q = self.path.split("?", 1)[1]
                for kv in q.split("&"):
                    if kv.startswith("self="):
                        dev = kv[5:]
            lines = _roster_lines(exclude=dev)
            self._send(200, "\n".join(lines) if lines else "")
        else:
            self._send(404, "no such door")

    def do_POST(self):
        if not self.path.startswith("/reading"):
            self._send(404, "no such door")
            return
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode(errors="replace").strip()
        # reading wire shape: device|present|luma|surprise|kind
        parts = raw.split("|")
        if len(parts) < 5:
            self._send(400, "malformed reading")
            return
        reading = {
            "device": parts[0],
            "present": parts[1],
            "luma": parts[2],
            "surprise": parts[3],
            "kind": parts[4],
        }
        decision = fr_route(reading)
        if decision == 3:
            self._send(403, "DENY|kind-not-offered")
            return
        now_ms = int(time.time() * 1000)
        _roster[reading["device"]] = {
            "present": reading["present"],
            "luma": reading["luma"],
            "surprise": reading["surprise"],
            "kind": reading["kind"],
            "at_ms": now_ms,
        }
        # DELIVER: hand back the roster of the OTHER cells (content-blind forward).
        lines = _roster_lines(exclude=reading["device"], now_ms=now_ms)
        self._send(200, "\n".join(lines) if lines else "")


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"field-relay (host carrier) on 127.0.0.1:{PORT} — offered kinds {sorted(OFFERED_KINDS)}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
