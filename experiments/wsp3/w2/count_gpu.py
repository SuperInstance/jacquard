import json, collections, re, hashlib
jobs=json.load(open("/home/caseydigennaro/gpu-queue/queue.json"))["jobs"]
ev=[json.loads(l) for l in open("/home/caseydigennaro/gpu-queue/events.jsonl")]
out={}
out["events_total"]=len(ev)
out["events_by_type"]=dict(collections.Counter(e["event"] for e in ev))
out["events_range"]=[min(e["ts"] for e in ev), max(e["ts"] for e in ev)]
out["jobs_total"]=len(jobs)
out["jobs_by_kind"]=dict(collections.Counter(j.get("kind") for j in jobs))
out["jobs_by_status"]=dict(collections.Counter(j["status"] for j in jobs))
out["jobs_by_exit"]=dict(collections.Counter(str(j.get("exit")) for j in jobs))
out["jobs_by_lane"]=dict(collections.Counter(j.get("lane") for j in jobs))
# archetype from cmd --archetype
def arch(j):
 m=re.search(r"--archetype (\w+)", j["cmd"]); return m.group(1) if m else None
out["jobs_by_archetype"]=dict(collections.Counter(arch(j) for j in jobs))
out["feeder_by_archetype"]=dict(collections.Counter(arch(j) for j in jobs if j.get("kind")=="feeder"))
# distinct cmd templates (digits normalised)
def tmpl(s): return re.sub(r"\d+","N",s)
out["distinct_cmd_templates"]=len(set(tmpl(j["cmd"]) for j in jobs))
out["distinct_name_templates"]=len(set(tmpl(j["name"]) for j in jobs))
out["cmd_template_counts"]=collections.Counter(tmpl(j["cmd"]) for j in jobs).most_common(10)
fin=[e for e in ev if e["event"]=="finish"]
out["finish_exit"]=dict(collections.Counter(str(e.get("exit")) for e in fin))
out["finish_ran_s_le_60"]=sum(1 for e in fin if e.get("ran_s",999)<=60)
# temporal: sorted jobs by added; earliest70/latest30 kind mix
js=sorted(jobs, key=lambda j:(j["added"], j["id"]))
cut=int(len(js)*0.7)
for nm,part in [("diag",js[:cut]),("held",js[cut:])]:
 out[nm]={"n":len(part),"range":[part[0]["added"],part[-1]["added"]],
  "kind":dict(collections.Counter(j.get("kind") for j in part)),
  "archetype":dict(collections.Counter(arch(j) for j in part)),
  "status":dict(collections.Counter(j["status"] for j in part))}
# near-duplicate: token jaccard of message (name+cmd) across a sample cross-split pairs: exact template match rate in held whose digit-normalised template seen in diag
diag_t=set(tmpl(j["name"]+" "+j["cmd"]) for j in js[:cut])
out["held_template_already_in_diag"]=sum(1 for j in js[cut:] if tmpl(j["name"]+" "+j["cmd"]) in diag_t)
out["held_n"]=len(js[cut:])
# job-logs count
import glob; out["job_logs"]=len(glob.glob("/home/caseydigennaro/gpu-queue/job-logs/*"))
out["idle_lines"]=sum(1 for _ in open("/home/caseydigennaro/gpu-queue/idle.jsonl"))
print(json.dumps(out,indent=1,default=str))
