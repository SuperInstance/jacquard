#!/usr/bin/env python3
"""Phase 10 slice 28 — Thor GPU-heavy flow inventory.

Run ON the Thor (read-only). Inventories every record store
that describes GPU work on the box — the gpu-queue's own
history (the standing dispatch path since 2026-10-27), the
image-studio gallery, the foundry portal builds, and the
foundry registry's use record — and reports, per class:
submission counts, measured durations, and the >= ~5
GPU-minute test the slice brief sets for an "expensive"
class. Prints JSON; the slice report quotes it.
"""
import json
import os
import sqlite3
import statistics

HOME = os.path.expanduser("~")
THRESHOLD_S = 300


def gpuq():
    events = [json.loads(l)
              for l in open(os.path.join(HOME, "gpu-queue",
                                         "events.jsonl"))]
    runs = {}
    for e in events:
        if e.get("event") == "finish" and "ran_s" in e:
            runs[e["job"]] = e["ran_s"]
    queue = json.load(open(os.path.join(HOME, "gpu-queue",
                                        "queue.json")))
    lanes = {}
    for j in queue["jobs"]:
        lane = lanes.setdefault(j["lane"], {
            "jobs": 0, "ran_s": [], "statuses": {}})
        lane["jobs"] += 1
        lane["statuses"][j["status"]] = \
            lane["statuses"].get(j["status"], 0) + 1
        if j["id"] in runs:
            lane["ran_s"].append(runs[j["id"]])
    out = {}
    for lane, d in lanes.items():
        rs = sorted(d.pop("ran_s"))
        d["finished"] = len(rs)
        if rs:
            d["median_s"] = round(statistics.median(rs), 1)
            d["max_s"] = round(rs[-1], 1)
            d["total_gpu_min"] = round(sum(rs) / 60, 1)
            d["jobs_ge_threshold"] = sum(
                1 for r in rs if r >= THRESHOLD_S)
        out[lane] = d
    return {"classes": out,
            "feeder_enabled": queue["meta"]["feeder"]["enabled"]}


def image_studio():
    db = os.path.join(HOME, "image-studio", "gallery.db")
    c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    by_model = [{"model": m, "kind": k, "n": n} for m, k, n in
                c.execute("select model, kind, count(*) from "
                          "images group by model, kind")]
    jobs = [{"status": s, "n": n} for s, n in
            c.execute("select status, count(*) from jobs "
                      "group by status")]
    return {"images_by_model": by_model, "jobs": jobs,
            "duration_record": "none in the gallery db; the "
            "portal's own build record (TOOLS.md, 2026-10-23) "
            "measured SDXL base at 13.7 s cold / 11.8 s warm "
            "for 1024x1024; every model present is a distilled "
            "or turbo variant of the same order"}


def foundry():
    pdb = os.path.join(HOME, "foundry", "portal", "portal.db")
    c = sqlite3.connect("file:%s?mode=ro" % pdb, uri=True)
    builds = []
    for (t,) in c.execute("select timings from bversions"):
        try:
            d = json.loads(t)
            builds.append({"total_s": d.get("total_s", 0),
                           "build_s": d.get("build_s", 0),
                           "brain_s": d.get("brain_s", 0)})
        except Exception:
            pass
    rdb = os.path.join(HOME, "foundry", "registry.db")
    r = sqlite3.connect("file:%s?mode=ro" % rdb, uri=True)
    total, used = r.execute(
        "select count(*), sum(case when use_count > 0 then 1 "
        "else 0 end) from assets").fetchone()
    return {"portal_builds": len(builds),
            "portal_build_max_total_s":
                max((b["total_s"] for b in builds), default=0),
            "portal_build_max_gpu_build_s":
                max((b["build_s"] for b in builds), default=0),
            "registry_assets": total,
            "registry_assets_ever_used": used,
            "registry_use_ratio_bp":
                round(10000 * used / total) if total else 0}


if __name__ == "__main__":
    print(json.dumps({"gpuq": gpuq(),
                      "image_studio": image_studio(),
                      "foundry": foundry()},
                     indent=1))
