#!/usr/bin/env python3
"""E2/E6 governance driver — thin orchestration over tools/jq.py.

The kernel decides; this driver only sequences the operator's
steps and keeps the stage bookkeeping in one place. Physical
acts (applying a patch to the serving copy, scoring, rollback)
happen OUTSIDE the kernel, performed by the coordinator between
driver steps; their receipts are hashed into the next stage's
evidence proposal — the same shape as the Phase 8 gpu bridge.

Usage (from the repo root, log = experiments/wsp/governance/kernel.jsonl):
  govern.py evidence <stage> <evidence.json>
      Submit a measurement record (producer wsp-harness,
      declared effect "record" — decided on submission).
  govern.py propose <stage> <manifest.json>
      Submit a deployment proposal (producer wsp-patcher,
      declared effect "irreversible" — queues for a decision).
      Manifest: {"patch_id": ..., "patch_sha256": ...,
                 "target": ..., "summary": ...}
  govern.py queue
  govern.py decide <proposal_id> <approve|deny>
  govern.py execute
  govern.py replay <proposal_id>
  govern.py status
"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
LOG = ROOT / "experiments" / "wsp" / "governance" / "kernel.jsonl"
JQ = ROOT / "tools" / "jq.py"


def jq(*args, inp=None):
    cmd = [sys.executable, str(JQ), "--log", str(LOG), *args]
    r = subprocess.run(cmd, input=inp, capture_output=True, text=True,
                       cwd=str(ROOT))
    out = (r.stdout or "") + (r.stderr or "")
    print(out.strip())
    return r.returncode, out


def submit(spec):
    return jq("submit", "-", inp=json.dumps(spec))


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    cmd = sys.argv[1]
    if cmd == "evidence":
        stage, path = sys.argv[2], sys.argv[3]
        ev = json.loads(pathlib.Path(path).read_text())
        spec = {"producer": "wsp-harness", "id": f"evidence-{stage}",
                "declared_effects": ["write"],
                "body": {"class": "measurement",
                         "requests": [{"verb": "write",
                                       "args": [f"wsp/evidence/{stage}",
                                                {"sha256": ev["sha256"],
                                                 "summary": ev["summary"]}]}]}}
        rc, _ = submit(spec); return rc
    if cmd == "propose":
        stage, path = sys.argv[2], sys.argv[3]
        m = json.loads(pathlib.Path(path).read_text())
        manifest = {"patch_sha256": m["patch_sha256"], "stage": stage,
                    "summary": m["summary"]}
        spec = {"producer": "wsp-patcher", "id": f"wsp-{stage}-{m['patch_id']}",
                "declared_effects": ["write", "send", "irreversible"],
                "body": {"class": "weight-patch-deployment",
                         "requests": [
                             {"verb": "write",
                              "args": [m["target"], manifest]},
                             {"verb": "send",
                              "args": [m["target"], manifest]}]}}
        rc, _ = submit(spec); return rc
    if cmd == "decide":
        pid, action = sys.argv[2], sys.argv[3]
        rc, out = jq("queue")
        binding = None
        lines = out.splitlines()
        for i, line in enumerate(lines):
            if pid in line and "binding" not in line:
                for nxt in lines[i + 1:i + 4]:
                    if "binding" in nxt:
                        binding = nxt.split("binding", 1)[1].strip()
                        break
        if binding is None:
            # queue output may be JSON; try to find the hash field
            try:
                data = json.loads(out[out.index("{"):])
                items = data if isinstance(data, list) else data.get("queue", [])
                for it in items:
                    if it.get("proposal_id") == pid or it.get("id") == pid:
                        binding = it.get("binding_hash") or it.get("hash")
            except Exception:
                pass
        if binding is None:
            print(f"could not find binding hash for {pid} in queue output")
            return 1
        rc, _ = jq("decide", action, pid, "--hash", binding)
        return rc
    if cmd in ("queue", "execute", "status"):
        rc, _ = jq(cmd); return rc
    if cmd == "replay":
        rc, _ = jq("replay", sys.argv[2]); return rc
    print(__doc__); return 2


if __name__ == "__main__":
    raise SystemExit(main())
