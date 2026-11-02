"""The network service (Phase 5, slice 13): every CLI verb over
HTTP, queue/replay byte-for-byte equal to the CLI on the same
log, hash-binding enforced over the wire, and the bind/auth
posture proven (non-loopback without a token refuses to start;
a wrong token changes nothing).
"""
import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log, Sequencer, make_envelope, publish_senses  # noqa: E402
from jacquard.service import check_bind, serve  # noqa: E402

JQ = os.path.join(os.path.dirname(__file__), "..", "tools", "jq.py")


def run_cli(log, *argv, expect=0):
    proc = subprocess.run(
        [sys.executable, JQ, "--log", str(log)] + list(argv),
        capture_output=True, text=True)
    assert proc.returncode == expect, (argv, proc.stdout, proc.stderr)
    return proc.stdout


class Client:
    def __init__(self, server, token=None):
        self.base = "http://127.0.0.1:%d" % server.server_address[1]
        self.token = token

    def call(self, method, path, payload=None, token="__default__"):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        use_token = self.token if token == "__default__" else token
        if use_token:
            headers["Authorization"] = "Bearer %s" % use_token
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode())


@pytest.fixture()
def running(tmp_path):
    log = tmp_path / "kernel.jsonl"
    server = serve(str(log), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield Client(server), log, server
    server.shutdown()
    server.server_close()


def test_every_verb_over_http(running):
    client, log, _server = running
    # seed through HTTP
    code, body = client.call("POST", "/seed-demo")
    assert code == 200 and body["ok"]
    queued = body["seed"]["queued"]
    assert len(queued) == 2
    # status
    code, body = client.call("GET", "/status")
    assert code == 200 and body["status"]["queue"] == 2
    assert body["text"] == run_cli(log, "status")
    # submit a new proposal through HTTP (carol-style dispatch is
    # allowed outright; alice-style notify queues)
    envelope = make_envelope(
        "dave", "proposal",
        {"requests": [{"verb": "notify", "args": ["ops", "via http"]}]},
        ["notify"], "http-1")
    code, body = client.call("POST", "/proposals", envelope)
    assert code == 200 and body["ok"]
    assert body["verdict"]["outcome"] == "queue"
    new_id = body["verdict"]["proposal_id"]
    # queue over HTTP presents it
    code, body = client.call("GET", "/queue")
    assert code == 200 and new_id in body["text"]
    # malformed proposal body is a clean 400
    code, body = client.call("POST", "/proposals",
                             {"not": "an envelope"})
    assert code == 200 and body["verdict"]["status"] == "REFUSED"
    # senses: nothing published yet -> empty map + 404 by name
    code, body = client.call("GET", "/senses")
    assert code == 200 and body["senses"] == {}
    code, _ = client.call("GET", "/senses/queue-depth")
    assert code == 404
    # unknown route / unknown replay
    code, _ = client.call("GET", "/nope")
    assert code == 404
    code, body = client.call("GET", "/replay/no-such-id")
    assert code == 404 and "no entries" in body["text"]


def test_published_senses_are_served_not_recomputed(running):
    client, log, _server = running
    run_cli(log, "seed-demo")
    seq = Sequencer(Log(str(log)))
    publish_senses(seq, ["queue-depth"])
    code, body = client.call("GET", "/senses")
    assert code == 200
    assert body["senses"]["queue-depth"]["value"] == 2
    assert "method" in body["senses"]["queue-depth"]
    code, body = client.call("GET", "/senses/queue-depth")
    assert code == 200 and body["reading"]["value"] == 2
    # Decide one item via HTTP; the published reading stays at
    # its as_of value (2) — the service serves the publication,
    # it does not recompute against the moved log.
    code, queue = client.call("GET", "/queue")
    item = queue["items"][0]
    code, _ = client.call("POST", "/decide",
                          {"action": "approve",
                           "proposal_id": item["proposal_id"],
                           "hash": item["binding"]})
    assert code == 200
    code, body = client.call("GET", "/senses/queue-depth")
    assert body["reading"]["value"] == 2


def test_drill_equivalence_full(tmp_path):
    log_cli = tmp_path / "cli.jsonl"
    log_http = tmp_path / "http.jsonl"
    run_cli(log_cli, "seed-demo")
    server = serve(str(log_http), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = Client(server)
    try:
        code, seed_body = client.call("POST", "/seed-demo")
        assert code == 200
        assert log_cli.read_bytes() == log_http.read_bytes()
        queued = seed_body["seed"]["queued"]
        (id_a, hash_a), (id_b, hash_b) = sorted(queued.items())

        code, body = client.call("GET", "/queue")
        assert body["text"] == run_cli(log_cli, "queue")

        # CLI decides on its log; HTTP decides the same on its log
        out_cli = run_cli(log_cli, "decide", "approve", id_a,
                          "--hash", hash_a)
        code, body = client.call("POST", "/decide",
                                 {"action": "approve",
                                  "proposal_id": id_a, "hash": hash_a})
        assert code == 200 and body["text"] == out_cli
        out_cli = run_cli(log_cli, "decide", "deny", id_b,
                          "--hash", hash_b)
        code, body = client.call("POST", "/decide",
                                 {"action": "deny",
                                  "proposal_id": id_b, "hash": hash_b})
        assert code == 200 and body["text"] == out_cli
        assert log_cli.read_bytes() == log_http.read_bytes()

        # queue (now empty) and status: byte-for-byte
        code, body = client.call("GET", "/queue")
        assert body["text"] == run_cli(log_cli, "queue")
        code, body = client.call("GET", "/status")
        assert body["text"] == run_cli(log_cli, "status")

        # replay of every drill proposal: byte-for-byte
        for pid in (id_a, id_b, seed_body["seed"]["dispatched"]):
            code, body = client.call("GET", "/replay/" + pid)
            assert code == 200
            assert body["text"] == run_cli(log_cli, "replay", pid), pid
    finally:
        server.shutdown()
        server.server_close()


def test_batch_decide_over_http(running):
    client, log, _server = running
    code, seed = client.call("POST", "/seed-demo")
    (id_a, hash_a), (id_b, hash_b) = seed["seed"]["queued"].items()
    code, body = client.call("POST", "/decide", {"decisions": [
        {"action": "approve", "proposal_id": id_a, "hash": hash_a},
        {"action": "deny", "proposal_id": id_b, "hash": hash_b}]})
    assert code == 200 and body["ok"]
    assert "approved %s" % id_a in body["text"]
    assert "denied %s" % id_b in body["text"]
    code, body = client.call("GET", "/queue")
    assert "empty" in body["text"]


def test_stale_hash_decide_over_http_changes_nothing(running):
    client, log, _server = running
    code, seed = client.call("POST", "/seed-demo")
    pid, _binding = next(iter(seed["seed"]["queued"].items()))
    before = log.read_bytes()
    code, body = client.call("POST", "/decide",
                             {"action": "approve", "proposal_id": pid,
                              "hash": "0" * 64})
    assert code == 409 and not body["ok"]
    assert "binding mismatch" in body["text"]
    assert log.read_bytes() == before
    assert pid in client.call("GET", "/queue")[1]["text"]
    # deciding an item that is not queued also fails clean
    code, body = client.call("POST", "/decide",
                             {"action": "approve",
                              "proposal_id": "no-such",
                              "hash": "0" * 64})
    assert code == 409 and "not in the decision queue" in body["text"]
    assert log.read_bytes() == before


def test_seed_demo_refuses_nonempty_log_over_http(running):
    client, log, _server = running
    assert client.call("POST", "/seed-demo")[0] == 200
    before = log.read_bytes()
    code, body = client.call("POST", "/seed-demo")
    assert code == 409 and "fresh log" in body["text"]
    assert log.read_bytes() == before


def test_non_loopback_bind_requires_opt_in_and_token(tmp_path):
    log = str(tmp_path / "k.jsonl")
    assert check_bind("192.0.2.1", allow_remote=False, token=None)
    assert check_bind("192.0.2.1", allow_remote=True, token=None)
    assert check_bind("192.0.2.1", allow_remote=False, token="t")
    assert check_bind("192.0.2.1", allow_remote=True, token="t") is None
    assert check_bind("127.0.0.1", allow_remote=False, token=None) is None
    with pytest.raises(ValueError, match="refusing to bind"):
        serve(log, host="192.0.2.1", port=0)
    with pytest.raises(ValueError, match="bearer token"):
        serve(log, host="192.0.2.1", port=0, allow_remote=True)


def test_token_checked_on_every_request(tmp_path):
    log = tmp_path / "k.jsonl"
    run_cli(log, "seed-demo")
    server = serve(str(log), port=0, token="s3cret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        anon = Client(server)
        good = Client(server, token="s3cret")
        before = log.read_bytes()
        # no token and wrong token: 401 on reads and writes alike
        for bad in (anon, Client(server, token="wrong")):
            assert bad.call("GET", "/queue")[0] == 401
            assert bad.call("GET", "/status")[0] == 401
            code, _ = bad.call("POST", "/decide",
                               {"action": "approve", "proposal_id": "x",
                                "hash": "0" * 64})
            assert code == 401
        assert log.read_bytes() == before  # nothing changed
        # the right token works
        assert good.call("GET", "/queue")[0] == 200
    finally:
        server.shutdown()
        server.server_close()
