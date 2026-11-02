"""The network service (Phase 5, slice 13).

A small HTTP JSON API exposing the same verbs as the operator
CLI (tools/jq.py) against one kernel log, so a second machine
can operate the kernel: submit proposals, read senses, present
and decide the decision queue (hash-bound, exactly as the CLI),
replay, and status. Standard library only — the repo is
zero-dependency and the service keeps it that way.

Posture (stated plainly; see the README's service section):

- Binds 127.0.0.1 by default.
- Binding a non-loopback address requires BOTH an explicit
  opt-in (`allow_remote=True` / `--allow-remote`) AND a bearer
  token; without the token the service refuses to start on a
  non-loopback bind.
- When a token is configured it is checked on EVERY request
  (`Authorization: Bearer <token>`); a missing or wrong token
  gets 401 and changes nothing.
- There is no TLS. The token is a shared secret against casual
  and unauthorised access on a trusted LAN; it is not
  encryption, not per-user identity, and not a substitute for
  a tunnel or a firewall. Loopback binding trusts every local
  user of the host.

Queue presentation and replay are rendered by
jacquard.present — the same code the CLI prints from — so the
two surfaces agree byte-for-byte by construction.

Senses are PUBLISHED readings: GET /senses returns what the
owning kernel has published into its log (folded state), never
a recomputation. A remote consumer reads the owning kernel's
readings; it does not recompute contention or any other sense
from someone else's record (Phase 4 findings addendum).
"""
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from .log import Log
from .present import (decide_one, queue_items, render_queue,
                      render_replay, render_status, seed_demo,
                      status_data)
from .sequencer import Sequencer

TOKEN_ENV = "JACQUARD_SERVICE_TOKEN"
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def is_loopback(host):
    return host in LOOPBACK_HOSTS


def check_bind(host, allow_remote, token):
    """Refuse an unsafe bind. Returns an error string, or None
    when the bind is allowed."""
    if is_loopback(host):
        return None
    if not allow_remote:
        return ("refusing to bind non-loopback address %s without "
                "the explicit remote opt-in (--allow-remote)" % host)
    if not token:
        return ("refusing to bind non-loopback address %s without a "
                "bearer token (set %s)" % (host, TOKEN_ENV))
    return None


class KernelService:
    """One kernel log behind HTTP. Every request opens the log
    fresh from disk, so the service always acts on the current
    record (including entries appended by the CLI between
    requests); mutations are serialised with a lock."""

    def __init__(self, log_path):
        self.log_path = log_path
        self.lock = threading.Lock()

    def open(self):
        return Sequencer(Log(self.log_path))


def _decide_entries(payload):
    """Normalise a /decide body to [(action, proposal_id, hash)].
    Returns (entries, error). Accepted shapes:

      {"action": "approve", "proposal_id": id, "hash": h}
      {"action": "approve", "batch": [{"proposal_id": id,
                                       "hash": h}, ...]}
      {"decisions": [{"action": "deny", "proposal_id": id,
                      "hash": h}, ...]}
    `binding` / `expect_hash` are accepted as aliases of `hash`.
    """
    def one(obj, default_action=None):
        if not isinstance(obj, dict):
            return None
        action = obj.get("action", default_action)
        proposal_id = obj.get("proposal_id") or obj.get("id")
        expect = obj.get("hash") or obj.get("binding") \
            or obj.get("expect_hash")
        if action not in ("approve", "deny") or not proposal_id \
                or not isinstance(expect, str):
            return None
        return (action, proposal_id, expect)

    if not isinstance(payload, dict):
        return None, "body must be a JSON object"
    if isinstance(payload.get("decisions"), list):
        entries = [one(d) for d in payload["decisions"]]
    elif isinstance(payload.get("batch"), list):
        entries = [one(d, payload.get("action"))
                   for d in payload["batch"]]
    else:
        entries = [one(payload)]
    if not entries or any(e is None for e in entries):
        return None, ("each decision needs action (approve|deny), "
                      "proposal_id and hash (the binding shown by "
                      "the queue)")
    return entries, None


def make_handler(service, token):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # -- plumbing -------------------------------------------
        def log_message(self, *args):  # keep stdout clean
            pass

        def _send(self, code, obj):
            raw = json.dumps(obj, indent=1, sort_keys=True) \
                .encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _authorised(self):
            if not token:
                return True
            header = self.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return False
            return hmac.compare_digest(header[len("Bearer "):], token)

        def _guard(self):
            if self._authorised():
                return True
            self._send(401, {"ok": False,
                             "error": "unauthorised: missing or "
                                      "wrong bearer token"})
            return False

        def _read_json(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None

        # -- verbs ------------------------------------------------
        def do_GET(self):
            if not self._guard():
                return
            path = urlparse(self.path).path
            seq = service.open()
            if path in ("/", "/health"):
                self._send(200, {"ok": True, "service": "jacquard"})
            elif path == "/status":
                self._send(200, {"ok": True,
                                 "text": render_status(seq) + "\n",
                                 "status": status_data(seq)})
            elif path == "/queue":
                self._send(200, {"ok": True,
                                 "text": render_queue(seq) + "\n",
                                 "items": queue_items(seq)})
            elif path == "/senses":
                self._send(200, {"ok": True,
                                 "senses": dict(seq.state.senses)})
            elif path.startswith("/senses/"):
                name = unquote(path[len("/senses/"):])
                if name in seq.state.senses:
                    self._send(200, {"ok": True, "name": name,
                                     "reading": seq.state.senses[name]})
                else:
                    self._send(404, {"ok": False,
                                     "error": "no published reading "
                                              "named %s" % name,
                                     "name": name})
            elif path.startswith("/replay/"):
                proposal_id = unquote(path[len("/replay/"):])
                found, text = render_replay(seq, proposal_id)
                self._send(200 if found else 404,
                           {"ok": found, "text": text + "\n",
                            "proposal_id": proposal_id})
            else:
                self._send(404, {"ok": False,
                                 "error": "no such route: %s" % path})

        def do_POST(self):
            if not self._guard():
                return
            path = urlparse(self.path).path
            payload = self._read_json()
            if payload is None:
                self._send(400, {"ok": False,
                                 "error": "request body is not JSON"})
                return
            if path == "/proposals":
                envelope = payload.get("envelope", payload) \
                    if isinstance(payload, dict) else None
                if not isinstance(envelope, dict):
                    self._send(400, {"ok": False,
                                     "error": "body must be an "
                                              "envelope object"})
                    return
                with service.lock:
                    verdict = service.open().submit(envelope)
                self._send(200, {"ok": verdict.get("status")
                                 != "REFUSED", "verdict": verdict})
            elif path == "/seed-demo":
                with service.lock:
                    seq = service.open()
                    ok, result = seed_demo(seq, service.log_path)
                if ok:
                    self._send(200, {"ok": True, "seed": result})
                else:
                    self._send(409, {"ok": False, "text": result + "\n",
                                     "error": result})
            elif path == "/decide":
                entries, error = _decide_entries(payload)
                if error:
                    self._send(400, {"ok": False, "error": error})
                    return
                results, lines = [], []
                with service.lock:
                    seq = service.open()
                    for action, proposal_id, expect in entries:
                        ok, line = decide_one(seq, action,
                                              proposal_id, expect)
                        results.append({"proposal_id": proposal_id,
                                        "action": action, "ok": ok,
                                        "text": line})
                        lines.append(line)
                all_ok = all(r["ok"] for r in results)
                self._send(200 if all_ok else 409,
                           {"ok": all_ok,
                            "text": "\n".join(lines) + "\n",
                            "results": results})
            else:
                self._send(404, {"ok": False,
                                 "error": "no such route: %s" % path})

    return Handler


def serve(log_path, host="127.0.0.1", port=8730, token=None,
          allow_remote=False):
    """Build (but do not start) the HTTP server. Raises
    ValueError when the bind posture is refused."""
    problem = check_bind(host, allow_remote, token)
    if problem:
        raise ValueError(problem)
    service = KernelService(log_path)
    server = ThreadingHTTPServer((host, port),
                                 make_handler(service, token))
    return server


def run(log_path, host="127.0.0.1", port=8730, token=None,
        allow_remote=False):
    server = serve(log_path, host, port, token, allow_remote)
    try:
        server.serve_forever()
    finally:
        server.server_close()
