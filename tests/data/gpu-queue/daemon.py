#!/usr/bin/env python3
"""Thor GPU successor queue daemon.

Owns one thing: the GPU never sits idle while named work exists, and a
finite job is never dispatched without a named successor behind it.

Rules (also stated in queue.json, where anyone opening the queue sees them):
  1. A finite job dispatches only if another job is queued behind it OR
     the standing feeder is enabled. Otherwise it holds, and the hold is
     recorded against its lane.
  2. A running job is never interrupted.
  3. If a job fails to START twice (dies inside the start grace with a
     nonzero exit), dispatching halts: the GPU is left idle, the job's
     output is preserved, and the failure is recorded for the report.
  4. Idle time (no queue job running, GPU utilisation at or below the
     idle threshold) is logged as intervals with start, end, duration.
     Foreign work on the GPU (utilisation high, not ours) closes an idle
     interval as foreign work — the GPU was busy, just not for the queue.
  5. Only jobs named by existing lanes run here. The daemon adds nothing
     of its own except feeder instances, which are the lane's own
     standing job (foundry-loop variant generation) materialised one at
     a time.

State files (this directory):
  queue.json   the queue: meta (rules + feeder config) and jobs[]
  status.json  the live picture, rewritten every loop
  idle.jsonl   one line per closed idle interval
  events.jsonl one line per dispatch / finish / hold / halt / failure
  job-logs/    one log per job run, kept on failure
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "queue.json")
STATUS = os.path.join(HERE, "status.json")
IDLE = os.path.join(HERE, "idle.jsonl")
EVENTS = os.path.join(HERE, "events.jsonl")
LOGDIR = os.path.join(HERE, "job-logs")

POLL_S = 20
UTIL_IDLE = 15        # percent; at or below, the GPU counts as not working
START_GRACE_S = 25    # a nonzero exit inside this window = a start failure
MAX_START_ATTEMPTS = 2


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts))


def load_queue():
    with open(QUEUE) as f:
        return json.load(f)


def save_queue(q):
    tmp = QUEUE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(q, f, indent=1)
    os.replace(tmp, QUEUE)


def append_jsonl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")


def event(kind, **kw):
    rec = {"ts": iso(time.time()), "event": kind}
    rec.update(kw)
    append_jsonl(EVENTS, rec)


def gpu_util():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15)
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return -1


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class Daemon:
    def __init__(self):
        os.makedirs(LOGDIR, exist_ok=True)
        self.proc = None            # subprocess.Popen for the running job
        self.running_id = None
        self.running_since = None
        self.reattached = False
        self.idle_since = None      # ts when the current idle interval opened
        self.idle_annot = None      # annotation for the open interval
        q = load_queue()
        # Reattach to a job that was running when the daemon last stopped
        # (unit uses KillMode=process, so the job survives us).
        for j in q["jobs"]:
            if j["status"] == "running" and j.get("pid") and pid_alive(j["pid"]):
                self.running_id = j["id"]
                self.running_since = j.get("started_ts") or time.time()
                self.reattached = True
                event("reattached", job=j["id"], pid=j["pid"])
                break
            if j["status"] == "running":
                j["status"] = "done"
                j["finished"] = iso(time.time())
                j["exit"] = "unknown (daemon restarted, process gone)"
        save_queue(q)

    # ------------------------------------------------ idle bookkeeping
    def open_idle(self, annot):
        if self.idle_since is None:
            self.idle_since = time.time()
            self.idle_annot = annot

    def close_idle(self, reason):
        if self.idle_since is None:
            return
        end = time.time()
        append_jsonl(IDLE, {
            "start": iso(self.idle_since), "end": iso(end),
            "duration_s": round(end - self.idle_since, 1),
            "closed_by": reason, "note": self.idle_annot})
        self.idle_since = None
        self.idle_annot = None

    # ------------------------------------------------ job lifecycle
    def start_job(self, q, job):
        logpath = os.path.join(
            LOGDIR, "%s-%s.log" % (job["id"], int(time.time())))
        logf = open(logpath, "ab")
        proc = subprocess.Popen(
            job["cmd"], shell=True, stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True, cwd=job.get("cwd") or None)
        job["status"] = "running"
        job["pid"] = proc.pid
        job["started"] = iso(time.time())
        job["started_ts"] = time.time()
        job["log"] = logpath
        job["attempts"] = job.get("attempts", 0) + 1
        self.proc = proc
        self.running_id = job["id"]
        self.running_since = time.time()
        self.reattached = False
        self.close_idle("job started: " + job["name"])
        event("dispatch", job=job["id"], name=job["name"],
              lane=job["lane"], pid=proc.pid, attempt=job["attempts"])
        save_queue(q)

    def finish_running(self, q, rc):
        job = next(j for j in q["jobs"] if j["id"] == self.running_id)
        ran_s = time.time() - (self.running_since or time.time())
        job["finished"] = iso(time.time())
        job["pid"] = None
        job.pop("started_ts", None)
        if rc is None:
            job["status"] = "done"
            job["exit"] = "unknown (reattached after daemon restart)"
            event("finish", job=job["id"], exit=job["exit"],
                  ran_s=round(ran_s, 1))
        elif rc == 0:
            job["status"] = "done"
            job["exit"] = 0
            event("finish", job=job["id"], exit=0, ran_s=round(ran_s, 1))
        elif ran_s <= START_GRACE_S and not self.reattached:
            # Start failure: retry once, then halt the whole queue.
            job["exit"] = rc
            if job.get("attempts", 1) < MAX_START_ATTEMPTS:
                job["status"] = "queued"
                event("start_failure_retry", job=job["id"], exit=rc,
                      attempt=job["attempts"], log=job.get("log"))
            else:
                job["status"] = "failed"
                q["meta"]["halted"] = (
                    "job %s (%s) failed to start %d times; last exit %s; "
                    "log preserved at %s" % (
                        job["id"], job["name"], job["attempts"], rc,
                        job.get("log")))
                event("start_failure_halt", job=job["id"], exit=rc,
                      attempts=job["attempts"], log=job.get("log"))
        else:
            job["status"] = "failed"
            job["exit"] = rc
            event("job_failed", job=job["id"], exit=rc,
                  ran_s=round(ran_s, 1), log=job.get("log"))
        self.proc = None
        self.running_id = None
        self.running_since = None
        self.reattached = False
        save_queue(q)

    # ------------------------------------------------ feeder
    def materialise_feeder(self, q):
        f = q["meta"]["feeder"]
        idx = f["next_index"]
        arch = f["rotation"][idx % len(f["rotation"])]
        seed_start = f["seed_cursor"]
        f["seed_cursor"] = seed_start + f["seed_step"]
        f["next_index"] = idx + 1
        job = {
            "id": "feeder-%d" % (idx + 1),
            "name": "Foundry feeder: %s family x%d, seeds %d+" % (
                arch, f["count"], seed_start),
            "lane": f["lane"], "kind": "feeder",
            "cmd": ("cd /home/caseydigennaro/foundry && python3 mint.py "
                    "family --archetype %s --count %d --seed-start %d" % (
                        arch, f["count"], seed_start)),
            "status": "queued", "attempts": 0,
            "added": iso(time.time())}
        q["jobs"].append(job)
        save_queue(q)
        return job

    # ------------------------------------------------ main loop
    def loop(self):
        while True:
            try:
                self.tick()
            except Exception as e:  # never die on a bad tick
                event("daemon_error", error=repr(e))
            time.sleep(POLL_S)

    def tick(self):
        q = load_queue()
        meta = q["meta"]
        util = gpu_util()

        # Poll the running job.
        if self.running_id is not None:
            if self.proc is not None:
                rc = self.proc.poll()
                if rc is not None:
                    self.finish_running(q, rc)
                    q = load_queue()
            elif not pid_alive_for(q, self.running_id):
                self.finish_running(q, None)
                q = load_queue()

        running = self.running_id is not None
        queued = [j for j in q["jobs"] if j["status"] == "queued"]
        feeder_on = bool(meta.get("feeder", {}).get("enabled"))
        halted = meta.get("halted")

        annot = None
        if not running:
            if halted:
                annot = "halted: " + str(halted)
                self.open_idle(annot)
            elif util > UTIL_IDLE:
                self.close_idle("foreign work on GPU")
            elif queued:
                nxt = queued[0]
                has_successor = len(queued) > 1 or feeder_on
                if has_successor:
                    if util >= 0:
                        self.start_job(q, nxt)
                        q = load_queue()
                else:
                    # THE successor rule: last job, nothing behind it.
                    holds = meta.setdefault("no_successor_holds", {})
                    key = nxt["lane"]
                    if holds.get(key, {}).get("job") != nxt["id"]:
                        holds[key] = {"job": nxt["id"],
                                      "since": iso(time.time())}
                        save_queue(q)
                        event("no_successor_hold", job=nxt["id"],
                              lane=nxt["lane"])
                    annot = ("held: %s has no successor behind it"
                             % nxt["name"])
                    self.open_idle(annot)
            elif feeder_on:
                job = self.materialise_feeder(q)
                if util >= 0 and util <= UTIL_IDLE:
                    self.start_job(q, job)
                    q = load_queue()
                else:
                    self.open_idle("feeder queued; GPU busy with foreign work")
            else:
                annot = "queue empty, feeder off"
                self.open_idle(annot)

        self.write_status(q, util)

    def write_status(self, q, util):
        queued = [j for j in q["jobs"] if j["status"] == "queued"]
        idle_total = 0.0
        idle_count = 0
        if os.path.exists(IDLE):
            with open(IDLE) as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        idle_total += float(rec.get("duration_s", 0))
                        idle_count += 1
                    except Exception:
                        pass
        if self.idle_since is not None:
            idle_total += time.time() - self.idle_since
        st = {
            "ts": iso(time.time()),
            "gpu_util_pct": util,
            "running": None,
            "queued": [{"id": j["id"], "name": j["name"], "lane": j["lane"]}
                       for j in queued],
            "feeder_enabled": bool(q["meta"].get("feeder", {})
                                   .get("enabled")),
            "feeder_next_index": q["meta"].get("feeder", {})
                                  .get("next_index"),
            "halted": q["meta"].get("halted"),
            "no_successor_holds": q["meta"].get("no_successor_holds", {}),
            "idle_open_since": iso(self.idle_since)
                               if self.idle_since else None,
            "idle_intervals_logged": idle_count,
            "idle_total_s_including_open": round(idle_total, 1),
            "jobs_done": sum(1 for j in q["jobs"]
                             if j["status"] == "done"),
            "jobs_failed": sum(1 for j in q["jobs"]
                               if j["status"] == "failed"),
        }
        if self.running_id is not None:
            job = next((j for j in q["jobs"]
                        if j["id"] == self.running_id), None)
            if job:
                st["running"] = {
                    "id": job["id"], "name": job["name"],
                    "lane": job["lane"], "pid": job.get("pid"),
                    "started": job.get("started"),
                    "ran_s": round(time.time() - self.running_since, 1)
                    if self.running_since else None}
        tmp = STATUS + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f, indent=1)
        os.replace(tmp, STATUS)


def pid_alive_for(q, job_id):
    job = next((j for j in q["jobs"] if j["id"] == job_id), None)
    return bool(job and job.get("pid") and pid_alive(job["pid"]))


if __name__ == "__main__":
    Daemon().loop()
