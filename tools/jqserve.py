"""jqserve — run the Jacquard network service (Phase 5, slice 13).

    python3 tools/jqserve.py --log kernel.jsonl
    python3 tools/jqserve.py --log kernel.jsonl --port 8730
    JACQUARD_SERVICE_TOKEN=<secret> python3 tools/jqserve.py \\
        --log kernel.jsonl --host 192.168.0.10 --allow-remote

Binds 127.0.0.1 by default. A non-loopback bind requires
--allow-remote AND a bearer token in the JACQUARD_SERVICE_TOKEN
environment variable; without the token the service refuses to
start. There is no TLS — see the README's service section for
the honest auth story.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard.service import TOKEN_ENV, run  # noqa: E402


def main():
    parser = argparse.ArgumentParser(prog="jqserve")
    parser.add_argument("--log", required=True,
                        help="kernel log (JSONL)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8730)
    parser.add_argument("--allow-remote", action="store_true",
                        help="permit a non-loopback bind (requires "
                             "a bearer token in %s)" % TOKEN_ENV)
    args = parser.parse_args()
    token = os.environ.get(TOKEN_ENV) or None
    try:
        print("jacquard service: log %s, listening on %s:%d"
              % (args.log, args.host, args.port))
        run(args.log, host=args.host, port=args.port, token=token,
            allow_remote=args.allow_remote)
    except ValueError as problem:
        print("FAIL: %s" % problem)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
