"""jqanchor — chain-head anchoring for Jacquard logs (spec 15).

    python3 tools/jqanchor.py keygen [--key PATH]
    python3 tools/jqanchor.py pubkey [--key PATH]
    python3 tools/jqanchor.py anchor <log> --label LABEL
        [--length N] [--checkpoints DIR] [--key PATH]
        [--commit] [--push]
    python3 tools/jqanchor.py verify <log> --checkpoints DIR
        (--pubkey HEX [--rotation-seq N --rotated-pubkey HEX]
         | --keys REGISTRY)
    python3 tools/jqanchor.py rotate --checkpoints DIR
        [--key OLD] [--new-key PATH]

From spec 0.6 the private key is passphrase-encrypted at rest:
`keygen` and `rotate` require a passphrase, taken from the
JACQUARD_ANCHOR_PASSPHRASE environment variable or an interactive
terminal prompt — never from argv, never printed. `rotate`
generates the successor key (encrypted) and updates the
transport's keys.json registry: the old key's signs_until is set,
per log, to the last checkpoint it signed, and the successor's
signs_from to the next sequence. Publish the registry, a README
rotation note and pubkey.txt as one commit, then `anchor` with
--history-keys REGISTRY so the first successor checkpoint
authenticates the old history under the published schedule.

`keygen` creates the operator keypair once, at
~/.jacquard/anchor-key.ed25519 (mode 0600, outside every repo);
it refuses to overwrite an existing key. The private key is never
printed. `pubkey` prints the public key hex for publication.

`anchor` computes the log's length and head at `--length`
(default: the full log), builds and signs the next checkpoint in
the log's checkpoint sequence, and stores it under
--checkpoints (default: ./checkpoints) at
<log_id>/<checkpoint_seq>.json. With --commit, the new file is
committed in the git repository that contains the checkpoints
directory (one commit, adds only); --push also pushes. The
publisher discipline of spec 15.4 — adds only, never amend,
rebase or force-push — is the operator's, enforced here by only
ever adding one file per run.

`verify` needs only the public key, a checkpoint history and a
presented log. It prints the result as JSON and exits 0 for
`verified` / `verified_to_anchor`, 1 for `failed`, 3 for
`unanchored`. The JSON always carries `anchored_length` and
`unanchored_tail` as distinct numbers; a failure names the first
divergent checkpoint (or the history / internal stage).
"""
import argparse
import getpass
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard.anchor import (  # noqa: E402
    AnchorError, DEFAULT_KEY_PATH, PASSPHRASE_ENV, anchor_entries,
    generate_key, history_for, key_is_encrypted, load_checkpoints,
    load_entries, load_key_registry, load_private_key, log_id_of,
    public_key_hex, registry_file_bytes, schedule_from_registry,
    verify_entries, REGISTRY_FORMAT_V2)

EXIT_CODES = {"verified": 0, "verified_to_anchor": 0,
              "failed": 1, "unanchored": 3}


def _git_root_of(path):
    proc = subprocess.run(
        ["git", "-C", path, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _passphrase(confirm=False):
    """The run-time passphrase (SPEC 15.3): environment variable
    first, else an interactive tty prompt. Never argv."""
    env = os.environ.get(PASSPHRASE_ENV)
    if env:
        return env
    if sys.stdin.isatty():
        first = getpass.getpass("anchor key passphrase: ")
        if confirm:
            if getpass.getpass("confirm passphrase: ") != first:
                raise AnchorError("passphrases do not match")
        return first
    return None


def cmd_keygen(args):
    pub = generate_key(args.key, passphrase=_passphrase(confirm=True))
    print(json.dumps({"key": args.key, "pubkey": pub,
                      "encrypted": key_is_encrypted(args.key)}, indent=1))
    return 0


def cmd_pubkey(args):
    print(public_key_hex(load_private_key(
        args.key, passphrase=_passphrase())))
    return 0


def cmd_rotate(args):
    old_key = load_private_key(args.key, passphrase=_passphrase())
    old_pub = public_key_hex(old_key)
    new_pub = generate_key(args.new_key,
                           passphrase=_passphrase(confirm=True))
    registry_path = os.path.join(args.checkpoints, "keys.json")
    if os.path.exists(registry_path):
        registry = load_key_registry(registry_path)
        # A rotation republishes the registry under the current
        # grammar (/2, SPEC 15.3 erratum 2): windows it records
        # are per-log by construction, which /2 reads exactly.
        registry["format"] = REGISTRY_FORMAT_V2
    else:
        registry = {"format": REGISTRY_FORMAT_V2,
                    "keys": [{"pubkey": old_pub, "status": "active",
                              "signs_from": {}, "signs_until": {}}]}
    envelopes, problems = load_checkpoints(args.checkpoints)
    if problems:
        raise AnchorError("checkpoint store has problems: %s"
                          % "; ".join(problems))
    log_ids = sorted({e["body"]["log_id"] for e in envelopes
                      if isinstance(e.get("body"), dict)})
    by_old = [e for e in registry["keys"] if e["pubkey"] == old_pub]
    if not by_old:
        raise AnchorError("the old key %s is not in the registry"
                          % old_pub)
    old_entry = by_old[0]
    old_entry["status"] = "retired"
    boundaries = {}
    for log_id in log_ids:
        history = history_for(envelopes, log_id)
        signed = [e["body"]["checkpoint_seq"] for e in history
                  if e["pubkey"] == old_pub]
        if signed:
            old_entry.setdefault("signs_until", {})[log_id] = max(signed)
            boundaries[log_id] = max(signed) + 1
    new_entry = {"pubkey": new_pub, "status": "active",
                 "signs_from": dict(boundaries), "signs_until": {}}
    registry["keys"].append(new_entry)
    with open(registry_path, "wb") as fh:
        fh.write(registry_file_bytes(registry))
    print(json.dumps({"old_pubkey": old_pub, "new_pubkey": new_pub,
                      "new_key": args.new_key,
                      "registry": registry_path,
                      "signs_from": boundaries}, indent=1))
    return 0


def cmd_anchor(args):
    entries = load_entries(args.log)
    key = load_private_key(args.key, passphrase=_passphrase())
    history_schedule = None
    if args.history_keys:
        registry = load_key_registry(args.history_keys)
        history_schedule = schedule_from_registry(
            registry, log_id_of(entries))
    envelope, path = anchor_entries(
        entries, key, args.label, args.checkpoints,
        log_length=args.length, history_schedule=history_schedule)
    body = envelope["body"]
    published = None
    if args.commit or args.push:
        root = _git_root_of(os.path.dirname(path))
        if root is None:
            raise AnchorError("--commit given but %s is not inside a "
                              "git repository" % path)
        subprocess.run(["git", "-C", root, "add", path],
                       check=True)
        message = ("anchor %s seq %d length %d"
                   % (body["label"], body["checkpoint_seq"],
                      body["log_length"]))
        subprocess.run(["git", "-C", root, "commit", "-m", message],
                       check=True, capture_output=True, text=True)
        head = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        published = {"repo": root, "commit": head}
        if args.push:
            subprocess.run(["git", "-C", root, "push"], check=True)
            published["pushed"] = True
    print(json.dumps({"checkpoint": path, "body": body,
                      "checkpoint_file": os.path.relpath(path),
                      "published": published}, indent=1))
    return 0


def cmd_verify(args):
    entries = load_entries(args.log)
    envelopes, problems = load_checkpoints(args.checkpoints)
    if problems:
        print(json.dumps(
            {"outcome": "failed",
             "failure": {"stage": "history", "checkpoint_seq": None,
                         "detail": "checkpoint store problems: %s"
                                   % "; ".join(problems)}},
            indent=1))
        return 1
    if args.keys:
        registry = load_key_registry(args.keys)
        schedule = schedule_from_registry(registry, log_id_of(entries))
        result = verify_entries(entries, envelopes, schedule[0][1],
                                schedule=schedule)
        print(json.dumps(result, indent=1))
        return EXIT_CODES[result["outcome"]]
    if not args.pubkey:
        raise AnchorError("verify requires --pubkey or --keys")
    schedule = [(0, args.pubkey)]
    if args.rotation_seq is not None:
        if not args.rotated_pubkey:
            raise AnchorError("--rotation-seq requires "
                              "--rotated-pubkey")
        schedule = [(0, args.pubkey),
                    (args.rotation_seq, args.rotated_pubkey)]
    result = verify_entries(entries, envelopes, args.pubkey,
                            schedule=schedule)
    print(json.dumps(result, indent=1))
    return EXIT_CODES[result["outcome"]]


def main():
    parser = argparse.ArgumentParser(prog="jqanchor")
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen")
    keygen.add_argument("--key", default=DEFAULT_KEY_PATH)

    pubkey = sub.add_parser("pubkey")
    pubkey.add_argument("--key", default=DEFAULT_KEY_PATH)

    anchor = sub.add_parser("anchor")
    anchor.add_argument("log")
    anchor.add_argument("--label", required=True)
    anchor.add_argument("--length", type=int, default=None)
    anchor.add_argument("--checkpoints", default="checkpoints")
    anchor.add_argument("--key", default=DEFAULT_KEY_PATH)
    anchor.add_argument("--history-keys", default=None)
    anchor.add_argument("--commit", action="store_true")
    anchor.add_argument("--push", action="store_true")

    verify = sub.add_parser("verify")
    verify.add_argument("log")
    verify.add_argument("--checkpoints", required=True)
    verify.add_argument("--pubkey", default=None)
    verify.add_argument("--keys", default=None)
    verify.add_argument("--rotation-seq", type=int, default=None)
    verify.add_argument("--rotated-pubkey", default=None)

    rotate = sub.add_parser("rotate")
    rotate.add_argument("--key", default=DEFAULT_KEY_PATH)
    rotate.add_argument("--new-key", required=True)
    rotate.add_argument("--checkpoints", default="checkpoints")

    args = parser.parse_args()
    handler = {"keygen": cmd_keygen, "pubkey": cmd_pubkey,
               "anchor": cmd_anchor, "verify": cmd_verify,
               "rotate": cmd_rotate}[args.command]
    try:
        return handler(args)
    except AnchorError as exc:
        print("jqanchor: %s" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
