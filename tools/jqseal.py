"""jqseal — sealed exports for Jacquard logs (spec 16).

    python3 tools/jqseal.py seal <log> --out <newlog>
        --field FIELD [--class CLASS] [--mode hash|keyed]
        [--producer P] [--redaction-key-env VAR]
    python3 tools/jqseal.py export <log> --out <export.json>
        [--length N]
    python3 tools/jqseal.py verify <export.json> --checkpoints DIR
        (--pubkey HEX | --keys REGISTRY) [--original <log>]
        [--redaction-key-env VAR]

`seal` copies the log to --out and appends ONE seal entry
committing to the redaction of `--field` (a dotted body path)
wherever it occurs — the source log is never modified. The
redaction key for `--mode keyed` is read as hex from the named
environment variable (default JACQUARD_REDACTION_KEY), never
from argv. `export` writes the redacted export document.
`verify` prints the section 16.3 result as JSON and exits 0 for
verified / verified_to_anchor, 1 for failed, 3 for unanchored.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard.anchor import (  # noqa: E402
    load_checkpoints, load_key_registry, load_entries, log_id_of,
    schedule_from_registry)
from jacquard.log import Log  # noqa: E402
from jacquard.sealing import (  # noqa: E402
    SealError, build_seals, export_bytes, load_export, make_export,
    targets_for_field, verify_export)

EXIT_CODES = {"verified": 0, "verified_to_anchor": 0,
              "failed": 1, "unanchored": 3}


def _redaction_key(args):
    raw = os.environ.get(args.redaction_key_env)
    if raw is None:
        return None
    try:
        return bytes.fromhex(raw.strip())
    except ValueError:
        raise SealError("%s does not hold hex" % args.redaction_key_env)


def cmd_seal(args):
    entries = load_entries(args.log)
    targets = targets_for_field(entries, args.field, args.cls)
    if not targets:
        raise SealError("field %r occurs in no entry body" % args.field)
    seals = build_seals(entries, targets, mode=args.mode,
                        redaction_key=_redaction_key(args))
    with open(args.log, "rb") as fh:
        data = fh.read()
    with open(args.out, "wb") as fh:
        fh.write(data)
    log = Log(path=args.out)
    entry = log.append("seal", {"producer": args.producer, "seals": seals})
    print(json.dumps({"sealed_fields": len(seals), "field": args.field,
                      "class": args.cls, "mode": args.mode,
                      "seal_entry_seq": entry["seq"], "out": args.out},
                     indent=1))
    return 0


def cmd_export(args):
    entries = load_entries(args.log)
    export = make_export(entries, exported_length=args.length)
    with open(args.out, "wb") as fh:
        fh.write(export_bytes(export))
    print(json.dumps({"out": args.out, "log_id": export["log_id"],
                      "exported_length": export["exported_length"],
                      "source_length": export["source_length"],
                      "seal_set_hash": export["seal_set_hash"]}, indent=1))
    return 0


def cmd_verify(args):
    export = load_export(args.export)
    envelopes, problems = load_checkpoints(args.checkpoints)
    if problems:
        print(json.dumps(
            {"outcome": "failed",
             "failure": {"stage": "history", "checkpoint_seq": None,
                         "detail": "checkpoint store problems: %s"
                                   % "; ".join(problems)}}, indent=1))
        return 1
    original = load_entries(args.original) if args.original else None
    if args.keys:
        registry = load_key_registry(args.keys)
        schedule = schedule_from_registry(registry, export["log_id"])
        pubkey = schedule[0][1]
    elif args.pubkey:
        schedule, pubkey = None, args.pubkey
    else:
        raise SealError("verify requires --pubkey or --keys")
    result = verify_export(export, envelopes, pubkey, schedule=schedule,
                           original_entries=original,
                           redaction_key=_redaction_key(args))
    print(json.dumps(result, indent=1))
    return EXIT_CODES[result["outcome"]]


def main():
    parser = argparse.ArgumentParser(prog="jqseal")
    sub = parser.add_subparsers(dest="command", required=True)

    seal = sub.add_parser("seal")
    seal.add_argument("log")
    seal.add_argument("--out", required=True)
    seal.add_argument("--field", required=True)
    seal.add_argument("--class", dest="cls", default="operator-identity")
    seal.add_argument("--mode", default="hash", choices=("hash", "keyed"))
    seal.add_argument("--producer", default="operator")
    seal.add_argument("--redaction-key-env",
                      default="JACQUARD_REDACTION_KEY")

    export = sub.add_parser("export")
    export.add_argument("log")
    export.add_argument("--out", required=True)
    export.add_argument("--length", type=int, default=None)

    verify = sub.add_parser("verify")
    verify.add_argument("export")
    verify.add_argument("--checkpoints", required=True)
    verify.add_argument("--pubkey", default=None)
    verify.add_argument("--keys", default=None)
    verify.add_argument("--original", default=None)
    verify.add_argument("--redaction-key-env",
                        default="JACQUARD_REDACTION_KEY")

    args = parser.parse_args()
    handler = {"seal": cmd_seal, "export": cmd_export,
               "verify": cmd_verify}[args.command]
    try:
        return handler(args)
    except SealError as exc:
        print("jqseal: %s" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
