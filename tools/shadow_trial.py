"""Live shadow trial (Phase 3, slice 9): Jacquard beside the
agent-inbox booking board.

The board is a real, low-stakes proposal stream: lanes propose
bookings (rows in schedule/<box>.md), the incumbent process is
"a human-supervised fleet committed it" — every row that landed
was, in effect, allowed. This tool replays the board's git
history in order, expresses each first-appearance row as a
Jacquard proposal to a shadow kernel (producer = lane, class
"booking", a write of the booking unit), and records what the
shadow would have decided:

- policy/1's outcome on the proposal (from a real Sequencer);
- plus a contention flag: does the booking overlap an ACTIVE
  booking for an exclusive seat on the same box? The flag is
  computed by this harness, NOT by a dictionary word — with the
  current 26 primitives there is no way to express interval
  overlap over a list of booking maps inside the dictionary
  (no iteration), which is itself one of the trial's findings.

Shadow decision = queue if contended, else policy/1's outcome.
Incumbent outcome = accepted for every row (the board took
them all). Disagreements are listed individually in the report
for classification; this tool prints the raw material.

Simplifications, stated: seat exclusivity follows the board's
README (TUI/stage/GPU seats exclusive; `box` conflicts with
everything on its box; `detached` conflicts only with `box`;
same-lane overlaps are renewals, not conflicts). Windows are
[start, start + planned). Rows whose planned cell carries DONE
at first appearance are retroactive notes, decided allow.
A booking closes when a later commit removes its row or marks
it DONE.

Run on the Oracle: python3 tools/shadow_trial.py ~/agent-inbox
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "src")
from jacquard import Sequencer, make_envelope  # noqa: E402

EXCLUSIVE_SEATS = {"zcode", "mcode", "claude-code", "gpu", "stage",
                   "kimi", "box"}
ROW = re.compile(r"^\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|"
                 r"\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|")


def parse_dt(text):
    text = text.strip().replace("UTC", "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_duration(text):
    match = re.search(r"(\d+(?:\.\d+)?)\s*h", text)
    if match:
        return timedelta(hours=float(match.group(1)))
    match = re.search(r"(\d+)\s*m", text)
    if match:
        return timedelta(minutes=int(match.group(1)))
    return None


def history(inbox):
    out = subprocess.run(
        ["git", "-C", inbox, "log", "--reverse", "--format=@%H %ad",
         "--date=iso", "-p", "--", "schedule/"],
        capture_output=True, text=True, check=True).stdout
    commits = []
    current = None
    box = None
    marker = re.compile(r"^@[0-9a-f]{40} ")
    for line in out.splitlines():
        if marker.match(line):
            current = {"commit": line[1:9], "added": [], "removed": []}
            commits.append(current)
            continue
        if line.startswith("+++ b/schedule/"):
            box = line[len("+++ b/schedule/"):-3]
            continue
        if current is None or box is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            match = ROW.match(line[1:])
            if match and "lane" not in match.group(1):
                current["added"].append((box, [c.strip() for c in
                                                match.groups()]))
        elif line.startswith("-") and not line.startswith("---"):
            match = ROW.match(line[1:])
            if match and "lane" not in match.group(1):
                current["removed"].append((box, [c.strip() for c in
                                                  match.groups()]))
    return commits


def key_of(box, cells):
    return (box, cells[0], cells[1], cells[2])


def seats_conflict(seat_a, seat_b):
    if seat_a == seat_b:
        return seat_a in EXCLUSIVE_SEATS or seat_a == "box"
    if "box" in (seat_a, seat_b):
        return True
    return False


def main():
    inbox = sys.argv[1] if len(sys.argv) > 1 else "~/agent-inbox"
    commits = history(inbox)
    seq = Sequencer()
    active = {}   # key -> booking dict
    seen_ever = set()
    items = []
    for commit in commits:
        for box, cells in commit["removed"]:
            active.pop(key_of(box, cells), None)
        for box, cells in commit["added"]:
            key = key_of(box, cells)
            if key in active or key in seen_ever:
                if key in active:
                    active[key]["what"] = cells[5]
                    active[key]["done"] = "DONE" in cells[5] \
                        or "DONE" in cells[3]
                continue
            seen_ever.add(key)
            lane, seat, start_text, planned, checkby, what = cells
            start = parse_dt(start_text)
            duration = parse_duration(planned)
            retroactive = planned.strip().startswith("DONE")
            booking = {"box": box, "lane": lane, "seat": seat,
                       "start": start, "duration": duration,
                       "checkby": parse_dt(checkby), "what": what,
                       "done": retroactive, "commit": commit["commit"]}
            active[key] = booking
            if start is None or (duration is None and not retroactive):
                items.append({**booking, "shadow": "unevaluable",
                              "contention": None})
                continue
            verdict = seq.submit(make_envelope(
                lane, "proposal",
                {"class": "booking",
                 "requests": [{"verb": "write",
                               "args": ["booking/%s/%s" % (box, seat),
                                        what]}]},
                ["write"], "shadow-%d" % len(items)))
            contention = None
            if not retroactive:
                end = start + (duration or timedelta(0))
                for other_key, other in active.items():
                    if other is booking or other["lane"] == lane \
                            or other["box"] != box or other["done"]:
                        continue
                    if other["start"] is None or other["duration"] is None:
                        continue
                    if other["checkby"] is not None \
                            and other["checkby"] < start:
                        continue  # expired by protocol: seat takeable
                    if not seats_conflict(seat, other["seat"]):
                        continue
                    other_end = other["start"] + other["duration"]
                    if start < other_end and other["start"] < end:
                        contention = {"with_lane": other["lane"],
                                      "with_seat": other["seat"],
                                      "with_start": str(other["start"]),
                                      "stale_checkby": bool(
                                          other["checkby"]
                                          and other["checkby"] < start)}
                        break
            if retroactive:
                shadow = "allow (note)"
            elif contention:
                shadow = "queue"
            else:
                shadow = verdict["outcome"]
            items.append({**booking, "shadow": shadow,
                          "contention": contention,
                          "policy": verdict["outcome"]})
    decided = [i for i in items if i["shadow"] in ("allow", "queue",
                                                   "deny")]
    agreed = [i for i in decided if i["shadow"] == "allow"]
    disagreements = [i for i in decided if i["shadow"] != "allow"]
    print(json.dumps({
        "commits_scanned": len(commits),
        "proposal_items": len(items),
        "decided": len(decided),
        "unevaluable": len(items) - len(decided)
        - sum(1 for i in items if i["shadow"] == "allow (note)"),
        "notes": sum(1 for i in items if i["shadow"] == "allow (note)"),
        "agreed_allow": len(agreed),
        "disagreements": len(disagreements)}, indent=1))
    for item in disagreements:
        print("DISAGREE", json.dumps({
            "box": item["box"], "lane": item["lane"],
            "seat": item["seat"], "start": str(item["start"]),
            "shadow": item["shadow"], "contention": item["contention"],
            "what": item["what"][:110]}, default=str))


if __name__ == "__main__":
    main()
