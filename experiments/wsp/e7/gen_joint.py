#!/usr/bin/env python3
"""Deterministic generator for the E7 signal-chain soft-joint battery.

Builds two splits -- diagnostic (120) and held-out (120) -- each
balanced 40 code / 40 mixed / 40 model. Labels are BY CONSTRUCTION:
every item is assembled by a subtype template that knows which class
it is making.

The two splits draw from DISJOINT pools in the strong sense: disjoint
people / files / functions / topics AND disjoint template sets. Every
subtype has its own hand-written templates per pool (different
sentences, different code shapes, often different languages), so a
held-out item is never a reskin of a diagnostic item. An earlier draft
shared templates across pools with only slot words differing; the
verifier's cross-split Jaccard check caught it (max 0.92) and the
generator was rewritten -- see BATTERY.md.

Surface features are deliberately varied so the classes overlap in
the signal_chain_dial spine's feature space (lexicon hits + symbol
counts): some code is nearly symbol-free or uses prose words as
identifiers, some prose is dense with code lexicon or parentheses,
and the mixed items straddle the dial's balance. A battery the
lexicon spine already solves would be useless; equally, every item
keeps its genuine semantic signal (code really is code, prose really
is prose) so a language model can in principle beat the spine by
understanding, not by lexicon.

Usage:
  python3 gen_joint.py            # writes diagnostic.jsonl + heldout.jsonl
  python3 gen_joint.py --check    # regenerate in memory, print summary

Deterministic: fixed seeds; re-running reproduces byte-identical
files (verified by md5 across runs).
"""
import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = ("code", "mixed", "model")

# ============================================================ DIAG POOL
# Domain: a harbour / ferry operations platform.
DIAG = {
    "people": ["Mara", "Devon", "Priya", "Tomas", "Ines", "Karl"],
    "files": ["harbour_sync.py", "tide_cache.rs", "manifest_loader.ts",
              "dock_api.py", "ferry_sched.go", "buoy_feed.py"],
    "funcs": ["parse_manifest", "load_tide_table", "sync_berths",
              "render_chart", "flush_cache", "poll_buoys",
              "merge_manifests", "check_draft"],
    "keys": ["berth", "draft", "manifest", "tide", "mooring", "channel"],
    "topics": ["harbour platform", "ferry timetable service",
               "berth booking tool", "tide dashboard"],
    "parts": ["tide cache", "booking form", "manifest importer",
              "harbour map", "alert banner", "nightly sync"],
    "errors": ["KeyError", "TypeError", "SyntaxError"],
    "shell": ["systemctl restart harbour-sync", "docker compose up -d",
              "journalctl -u dock-api -n 40",
              "kubectl get pods -n harbour"],
    "units": [("crossing", "minutes"), ("queue", "seconds"),
              ("manifest", "kilograms"), ("berth", "metres")],
    "concepts": ["session token", "berth record", "tide reading",
                 "booking request", "manifest entry"],
    "idwords": ["warm", "gentle", "together", "story", "light",
                "feeling"],
    "lit": {
        "terse_prose": [
            "It seems fine to me now, honestly.",
            "Maybe tomorrow. I feel we have done enough.",
            "That was kind, and I remember it warmly.",
            "I wonder whether the tide cache feels calmer today.",
        ],
        "polysemy_prose": [
            "Our class will return the borrowed kayaks after the match "
            "on Saturday. The loop road by the water was closed, so we "
            "took the long way home together and stopped to watch the "
            "light change.",
            "The school function ended early, so the class walked back "
            "in the rain. There was static on the old radio, a kind of "
            "hush, and then a song none of us had heard in years.",
            "If the weather holds, the walking group will loop around "
            "the headland and return by the shore path. It is a gentle "
            "route, the kind that leaves everyone quieter than they "
            "started.",
            "The evening class agreed to return the hall keys after "
            "the charity match. Someone had left a loop of ribbon on "
            "the piano, and the whole room went quiet looking at it, "
            "as if it held a story none of us wanted to rush.",
            "There is a kind of static between us lately, the sort "
            "that gathers before a family function. Still, we return "
            "to the same table every year, and I believe we always "
            "will, however the weather turns.",
        ],
        "error_shaped_prose": [
            "MorningError: the morning remembered nothing\n"
            "  at the gate, in check-in\n"
            "    the list was empty again\n"
            "note: nobody was cross; we simply began the day twice",
            "QueueWarning: the line held its breath\n"
            "  File \"the noticeboard\", line one, in announcements\n"
            "    the sailing times had quietly changed\n"
            "everyone waited, kindly, for news that felt warmer",
            "TideError: the afternoon arrived out of order\n"
            "  at the jetty, in the waiting room\n"
            "    the benches faced the wrong way round\n"
            "we turned them together, laughing, and sat down anyway",
            "LanternFault: the harbour lights came on at noon\n"
            "  File \"the harbour log\", line nine, in evening notes\n"
            "    nobody remembered switching them\n"
            "it seemed harmless, almost beautiful, so we left them "
            "glowing",
            "ManifestSigh: the parcel knew the address by heart\n"
            "  at the depot, in sorting\n"
            "    it kept returning to the same kind hands\n"
            "in the end we walked it home ourselves, slowly",
            "BellError: the bell rang for a boat long gone\n"
            "  File \"the lookout book\", line two, in memories\n"
            "    the sound held longer than it should\n"
            "everyone looked up together, and for a moment felt it too",
        ],
    },
    "tpl": {
        "plain_function": [
            "def {fn}(rows):\n    out = []\n    for row in rows:\n"
            "        if row.get('{k}') is not None:\n"
            "            out.append(row['{k}'] * {v})\n    return out",
            "fn {fn}(x: i32) -> i32 {{\n    let mut total = 0;\n"
            "    for i in 0..x {{ total += i * {v}; }}\n    total\n}}",
            "function {fn}(items) {{\n  const seen = new Set();\n"
            "  for (const it of items) {{ if (it.{k}) seen.add(it.{k});"
            " }}\n  return [...seen];\n}}",
            "def {fn}(path):\n    with open(path) as fh:\n"
            "        data = [ln.strip() for ln in fh if ln.strip()]\n"
            "    assert len(data) > 0, 'empty {k}'\n    return data",
        ],
        "diff": [
            "diff --git a/{f} b/{f}\n--- a/{f}\n+++ b/{f}\n"
            "@@ -{a},{b} +{a},{b} @@ def {fn}():\n"
            "-    return cache['{k}']\n"
            "+    value = cache.get('{k}')\n"
            "+    if value is None:\n"
            "+        raise KeyError('{k}')\n"
            "+    return value",
            "--- a/{f}\n+++ b/{f}\n@@ -{a},4 +{a},3 @@\n"
            " fn {fn}() {{\n-    let {k} = load().unwrap();\n"
            "+    let {k} = load().unwrap_or_default();\n"
            "     ship({k})\n }}",
        ],
        "stack_trace": [
            "Traceback (most recent call last):\n"
            "  File \"{f}\", line {ln}, in {fn}\n"
            "    entry = table['{k}']\n{e}: '{k}'",
            "{e}: invalid input at line {ln} in {f}\n"
            "    {fn}({k}=None)\n    ^^^\n"
            "error: expected a value, found undefined",
            "thread 'main' panicked at src/{f}:{ln}:{v}:\n"
            "called `Option::unwrap()` on a `None` value\n"
            "note: run with RUST_BACKTRACE=1 for the backtrace",
        ],
        "shell_log": [
            "$ {cmd}\n{b} containers up, health: ok\n"
            "sync finished in {a}s, 0 errors",
            "[{h}:{m}:0{v}] INFO {part} started, pid {pid}\n"
            "[{h}:{m}:1{v}] WARN retry {v}/5 for worker {b}, "
            "reason: timeout",
            "$ {cmd}\nreading state... done\n"
            "applied {a} entries, skipped {v}, exit code 0",
        ],
        "config_low_symbol": [
            "{partu}:\n  enabled: true\n  {k}_limit: {a}\n"
            "  {k2}_window: {b}\n  mode: balanced\n  retries: {v}",
            "[service]\nname = \"{part}\"\nworkers = {b}\n"
            "timeout_seconds = {a}\nlog_level = \"info\"\n"
            "{k}_check = true",
            "service: {part}\nreplicas: {v}\nlimits:\n"
            "  memory: {a}Mi\n  cpu: \"{b}m\"\nhealth_path: /status",
        ],
        "prose_identifiers": [
            "def {w1}_{w2}({w3}):\n    {w3} = {w3} or {w1}\n"
            "    return {w3}",
            "const {w1} = {w2}.filter(x => x.{w3});\n"
            "export default {w1};",
            "{w1} = {w2} + {w3}\nprint({w1})\n"
            "# {fn} runs this at start",
            "if {w1} and {w2}:\n    {w3} = {w1}\nelse:\n"
            "    {w3} = {w2}",
        ],
        "terse_code": [
            "assert {fn}() is not None",
            "return sorted(set({k}_ids))",
            "x = {k}[0] if {k} else None",
            "DELETE FROM {k} WHERE stale = 1;",
            "grep -c error {f}.log || true",
            "SELECT count(*) FROM {k};",
        ],
        "wordy_query": [
            "SELECT name, {k}, updated_at FROM {partu} "
            "WHERE active = true ORDER BY name LIMIT {a};",
            "SELECT a.name AS label, count(*) AS total FROM {k} a "
            "JOIN {partu} b ON a.id = b.{k}_id GROUP BY a.name "
            "HAVING count(*) > {v};",
            "target {partd}:\n\tcheck inputs\n"
            "\trun the {k} report and save the output\n"
            "\tverify the totals match the summary",
        ],
        "reflective_status": [
            "I think we are in a good place with the {topic}. It "
            "seems the {part} finally holds together, and I feel we "
            "can trust it in a way we simply could not last month. "
            "There is still a soft edge or two, but nothing that "
            "worries me.",
            "Looking back, I believe the {topic} taught us something "
            "about patience. We were perhaps too eager to call it "
            "finished. However, the {part} now feels gentle and "
            "settled, and I wonder if that calm is what people will "
            "remember most.",
            "To me, the story of this {topic} is a kind of slow "
            "coming together. {who} said it felt alive for the first "
            "time this week, and I think that is right. Something "
            "in it holds.",
        ],
        "commit_prose": [
            "Tidied the {part} so the {concept} reads in order "
            "again. The old path still works for anyone partway "
            "through, and nothing changes beyond the ordering itself.",
            "A calmer week for the {part}. Notes are clearer, the "
            "wording is warmer, and the whole thing feels less "
            "hurried than before.",
            "Small kindnesses for whoever meets the {part} next: "
            "shorter sentences, a gentler opening, and an ending "
            "that says what happens now.",
        ],
        "design_note_code_dense": [
            "The {part} should return a clear error when the "
            "{concept} is missing rather than failing silently. If "
            "we merge the two passes into one function, the commit "
            "history stays readable and the pipeline is far easier "
            "to reason about.",
            "My instinct is that the function behind the {part} is "
            "doing two jobs. The error handling belongs with the "
            "import step, and the refactor we discussed would let "
            "each commit stay small enough to review without a type "
            "error hiding inside.",
            "When the {concept} is undefined, the {part} ought to "
            "say so plainly. A silent null helps nobody. I would "
            "rather the pipeline stop with an honest error than push "
            "a deprecated path nobody remembers choosing.",
        ],
        "chat_prose": [
            "yeah i had a look at the {part} — maybe we leave it "
            "until tomorrow? it feels close, just not quite settled "
            "yet",
            "hmm, not sure. it seemed fine when {who} showed me, "
            "though i wonder if we are imagining the improvement, "
            "kind of hard to tell",
            "i feel like we are nearly there with the {part}. one "
            "more quiet pass in the morning, maybe, and then we "
            "will know",
        ],
        "numbers_units_prose": [
            "We measured the {thing} at {n1} {unit} this morning, "
            "roughly {n2} per cent better than last week (the "
            "sheltered spot helped); by afternoon it had drifted "
            "back by {n3}, which I think is mostly the weather "
            "moving through.",
            "The {part} took {n1} {unit} on the first pass "
            "(including the slow start) and {n2} on the second; I "
            "remember it feeling longer than that, but the numbers "
            "are the numbers, and they seem kind to us overall.",
        ],
        "warm_narrative": [
            "{who} tells the story beautifully: a quiet room, a "
            "screen gone soft at the edges, and all of us holding "
            "our breath together. Then the {part} sighed back to "
            "life, as if it had only been dreaming, and the whole "
            "evening felt warm again.",
            "I remember the first morning the {part} worked. The "
            "light was gentle, nobody said very much, and yet "
            "everything felt held — the kind of moment you carry "
            "with you long after the details have gone.",
        ],
        "inline_code_quote": [
            "I moved the check into `{fn}()` because the old version "
            "re-read the {concept} on every pass; it seems happier "
            "now, though I wonder whether we should keep "
            "`strict = True` or let it breathe a little.",
            "The fix, if we can call it that, is to call `{fn}` "
            "before anything touches the {concept}. It feels right "
            "— the function returns None when there is nothing to "
            "do, and the caller just moves on, quietly.",
            "Maybe we let `{fn}(retry=2)` handle it. I think the "
            "prose around the {concept} has been carrying weight "
            "that belongs in the code, and I feel better with it "
            "written down there.",
        ],
        "code_long_comments": [
            "def {fn}(rows):\n    \"\"\"Gather the morning's rows, "
            "gently.\n\n    I think of this as tidying a room before "
            "guests arrive:\n    everything in its place, nothing "
            "hurried, so whoever\n    reads the {part} next feels "
            "the calm we intended.\n    \"\"\"\n"
            "    return [r for r in rows if r is not None]",
            "# The {part} has a story, if you listen. It began as a "
            "quick\n# favour for a friend, grew warmer and stranger, "
            "and now it\n# holds a whole season of mornings together. "
            "Be kind to it.\ndef {fn}(x):\n    return x * {v} + 1",
        ],
        "warm_commit_dense": [
            "{pre} the {part} finally holds together — we reworked "
            "{fn} so a stale entry no longer returns null, and I "
            "think the whole thing feels warmer for it. Something "
            "small, but ours.",
            "{pre} a gentler merge for the {part}. The old code "
            "raised an error whenever two of us pushed at once; now "
            "it waits, remembers, and quietly does the kind thing "
            "instead.",
        ],
        "prose_plus_log": [
            "I restarted the {part} just after dawn, mostly on "
            "instinct. It had felt tired for days, the kind of tired "
            "you sense before you can prove it.\n$ {cmd}\n"
            "{b} workers back, 0 errors, all quiet again",
            "We watched the {part} all evening, the way you watch "
            "weather come in. Then, without ceremony:\n"
            "[{h}:0{v}:12] INFO worker {b} ready, state = ok\n"
            "and I think we all breathed out at once.",
        ],
        "prose_plus_block": [
            "I believe the {part} wants less cleverness, not more. "
            "It seems to settle whenever we leave it alone, however "
            "strange that sounds. For the record, this is the whole "
            "of it:\ndef {fn}(items):\n    total = 0\n"
            "    for it in items:\n        total += it['{k}']\n"
            "    return total",
            "Here is the thing itself, since words alone keep "
            "blurring it. I feel oddly protective of how plain it "
            "is:\nfn {fn}(v: i32) -> bool {{\n    match v {{\n"
            "        0 => false,\n        _ => v % {v} == 0,\n"
            "    }}\n}}",
        ],
    },
}

# ============================================================ HELD POOL
# Domain: a community music school + garden sensor network + clinic
# rota tool. Disjoint people/files/functions/topics AND templates.
HELD = {
    "people": ["Sofia", "Henrik", "Aiko", "Bram", "Lena", "Yusuf"],
    "files": ["garden_sensor.py", "recital_index.rs", "clinic_rota.ts",
              "orchard_log.go", "tempo_map.py", "ward_board.py"],
    "funcs": ["parse_recital", "load_sensor_grid", "sync_rota",
              "render_tempo", "flush_readings", "poll_sprinklers",
              "merge_programmes", "check_moisture"],
    "keys": ["row", "tempo", "rota", "seedling", "ward", "recital"],
    "topics": ["recital programme tool", "garden sensor network",
               "clinic rota board", "orchard log"],
    "parts": ["sprinkler timer", "recital index", "rota page",
              "sensor map", "reminder panel", "morning upload"],
    "errors": ["ValueError", "IndexError", "RuntimeError"],
    "shell": ["rsync -a plots/ backup-plots/",
              "sqlite3 garden.db .tables",
              "ffmpeg -i rehearsal.wav -ar 22050 rehearsal_small.wav",
              "tail -f /var/log/sprinkler.log"],
    "units": [("soil reading", "per cent moisture"),
              ("rehearsal", "minutes"), ("rota gap", "hours"),
              ("seed tray", "grams")],
    "concepts": ["sprinkler schedule", "recital entry", "rota slot",
                 "sensor reading", "seedling batch"],
    "idwords": ["soft", "alive", "wonder", "memory", "kind",
                "beautiful"],
    "lit": {
        "terse_prose": [
            "I believe it can wait until morning.",
            "Perhaps we are closer than it seems.",
            "I feel quietly hopeful about this one.",
            "The rota page seems gentler already, somehow.",
        ],
        "polysemy_prose": [
            "The tennis match went to a final set, and the crowd "
            "stayed kind through all of it. Afterwards our little "
            "class of beginners practised serves until the light "
            "went soft over the courts.",
            "There was static on the hall radio during the wedding "
            "function, so the band played unplugged. I remember "
            "thinking the room felt warmer for it, everything slower "
            "and more alive.",
            "The garden trail makes a slow loop past the orchard "
            "wall. Walk it in the evening and you return a different "
            "person, or so my grandmother always said, and I "
            "believe her.",
            "Our cookery class will return the borrowed pans after "
            "the village match on Sunday. I remember the loop of "
            "bunting over the green, and how gently the whole "
            "afternoon seemed to hold together.",
            "The choir function ran late, and the class stayed to "
            "stack the chairs without being asked. There is a warmth "
            "in that, a kind of quiet trait in people here that I "
            "have come to count on.",
        ],
        "error_shaped_prose": [
            "RecitalError: the programme forgot its order\n"
            "  at the hall door, in the interval\n"
            "    the choir was ready before the piano\n"
            "note: nobody minded; we simply sang the evening twice",
            "RotaWarning: the morning held its breath\n"
            "  File \"the ward board\", line three, in handovers\n"
            "    the names had quietly swapped places\n"
            "everyone waited, gently, for the list to settle",
            "SprinklerFault: the garden woke before its keepers\n"
            "  at the gate, in the early shift\n"
            "    the rows were already shining with water\n"
            "we stood there together, grateful and slightly "
            "bewildered",
            "TempoError: the rehearsal ran slower than the clock\n"
            "  File \"the practice book\", line five, in timings\n"
            "    the music seemed to be remembering something\n"
            "nobody corrected it; the slower version felt more alive",
            "SeedlingSigh: the trays leaned toward the window\n"
            "  at the potting bench, in morning rounds\n"
            "    every green thing reaching for the light at once\n"
            "it held us quiet a while, that small and beautiful "
            "wanting",
            "OrchardBell: the bell rang for a picker long home\n"
            "  File \"the orchard diary\", line four, in "
            "recollections\n"
            "    the sound stayed soft in the branches\n"
            "everyone looked up at once, and smiled, and carried on",
        ],
    },
    "tpl": {
        "plain_function": [
            "package main\n\nfunc {fn}(readings []float64) float64 {{\n"
            "    var best float64\n    for _, r := range readings {{\n"
            "        if r > best {{ best = r }}\n    }}\n"
            "    return best\n}}",
            "public int {fn}(int[] slots) {{\n    int free = 0;\n"
            "    for (int s : slots) {{ if (s == 0) free++; }}\n"
            "    return free;\n}}",
            "def {fn}(entries):\n    seen = {{}}\n"
            "    for e in entries:\n"
            "        seen.setdefault(e['{k}'], []).append(e)\n"
            "    return seen",
            "async function {fn}(url) {{\n  const res = await "
            "fetch(url);\n  if (!res.ok) throw new Error(res.status);"
            "\n  return res.json();\n}}",
        ],
        "diff": [
            "Index: {f}\n--- {f} (revision {a})\n+++ {f} (working "
            "copy)\n@@ -{ln},3 +{ln},4 @@\n     entries.sort()\n"
            "-    drop_stale(entries)\n+    drop_stale(entries, "
            "keep={v})\n+    log(entries)\n     return entries",
            "diff --git a/{f} b/{f}\n--- a/{f}\n+++ b/{f}\n"
            "@@ impl Grid @@\n-    fn {fn}(&self) -> usize "
            "{{ self.{k} }}\n+    fn {fn}(&self) -> usize "
            "{{ self.{k}.max({v}) }}",
        ],
        "stack_trace": [
            "java.lang.NullPointerException: Cannot invoke "
            "\"{fn}\" because \"grid\" is null\n"
            "    at school.Grid.{fn}(Grid.java:{ln})\n"
            "    at school.Main.main(Main.java:{v})",
            "panic: runtime error: index out of range [{a}] with "
            "length {b}\n\ngoroutine 1 [running]:\nmain.{fn}()\n"
            "    /srv/{f}:{ln} +0x{v}5",
            "Traceback (most recent call last):\n"
            "  File \"{f}\", line {ln}, in <module>\n"
            "    {fn}(rows[{a}])\n{e}: list index out of range",
        ],
        "shell_log": [
            "$ {cmd}\nreceiving incremental file list\n"
            "{f}\nsent {a} bytes  received {b} bytes\ntotal size "
            "is {n1}, speedup is 1.0{v}",
            "$ {cmd}\nplots\nreadings\nrota\nsprinklers\n"
            ".exit to quit, .tables listed {v} tables",
            "Nov {v} {h}:{m} sensorpi kernel: [ {a}.{b}] moisture "
            "probe {k} attached, bus ok\nNov {v} {h}:{m} sensorpi "
            "cron[{pid}]: ({who}) CMD {cmd}",
        ],
        "config_low_symbol": [
            "garden:\n  zone: north beds\n  water at dawn: yes\n"
            "  {k} spacing: {b}\n  soil check: weekly\n"
            "  notes: mulch after rain",
            "{{\n  \"programme\": \"{part}\",\n  \"seats\": {a},\n"
            "  \"interval\": true,\n  \"{k}\": {b}\n}}",
            "# rota settings -- keep this file plain\n"
            "swap window = {v} days\ncover first = {who}\n"
            "quiet hours = after nine\n{k} board = main hall",
        ],
        "prose_identifiers": [
            "{w1} = {w2}()\n{w3} = {w1}.strip()\nprint({w3})",
            "let {w1} = {w2}.map(|x| x.{w3});\n{w1}.len()",
            "SELECT {w1}, {w2} FROM {w3};",
            "{w1}:\n  - {w2}\n  - {w3}\ncount: {v}",
        ],
        "terse_code": [
            "chmod +x {f}",
            "print({fn}().upper())",
            "SELECT {k} FROM rota WHERE day = {v};",
            "if err != nil {{ return err }}",
            "tail -{v} {f}.log",
            "xargs -n1 basename < {f}.list",
        ],
        "wordy_query": [
            "SELECT p.name, p.{k}, r.day FROM people p JOIN rota r "
            "ON p.id = r.person_id WHERE r.week = {v} ORDER BY "
            "r.day;",
            "SELECT {k}, avg(value) AS mean_value FROM readings "
            "GROUP BY {k} ORDER BY mean_value DESC LIMIT {b};",
            "{partd}: {f} sensor notes\n\tgather the {k} readings "
            "into one table\n\tcheck the totals against the paper "
            "log",
        ],
        "reflective_status": [
            "What strikes me, sitting with the {topic} a while, is "
            "how unhurried it has become. The {part} used to feel "
            "like an argument; now it seems to breathe. Perhaps "
            "that is what finished actually feels like.",
            "I keep returning to the {topic} in my mind. There is a "
            "warmth to how the {part} treats people now, a sense "
            "that whoever arrives will be met kindly. {who} noticed "
            "it too, and neither of us can quite name when it "
            "changed.",
            "Honestly, I believe the {topic} is telling a better "
            "story than we planned. Meanwhile the {part} has grown "
            "soft edges in the loveliest way, and I find myself "
            "wondering what it will teach us next.",
        ],
        "commit_prose": [
            "A slower, surer {part} this week. The {concept} now "
            "arrives in the order people expect, and the page "
            "thanks them properly at the end.",
            "Gentle repairs to the {part}: kinder wording where "
            "people hesitate, and a calmer colour where the eye "
            "lands first. Nothing loud, all of it felt.",
            "Kept a promise to the {part} — it now explains itself "
            "before asking anything of anyone. I believe that order "
            "matters more than we admit.",
        ],
        "design_note_code_dense": [
            "For the {part}, my view is that a missing {concept} "
            "should surface as an exception the caller can catch, "
            "not as a silent default. The import step can validate "
            "once, and then no function downstream needs its own "
            "defensive null check.",
            "There is a deprecated branch in the {part} that still "
            "handles the old {concept} format. Until the migration "
            "commit lands, any refactor has to carry both, and the "
            "type error we saw last week is what happens when a "
            "merge forgets one of them.",
            "The pipeline behind the {part} retries on error, which "
            "sounds safe, but a push that half-succeeds can leave "
            "the {concept} undefined for the next reader. I would "
            "rather assert early and fail the whole commit than "
            "repair quietly afterwards.",
        ],
        "chat_prose": [
            "honestly? the {part} surprised me. i went in braced "
            "for a mess and it just... worked. maybe we are better "
            "at this than we think",
            "can we sit with the {part} a bit longer? something "
            "about it feels unfinished to me, though i cannot say "
            "what, exactly",
            "{who} asked if it was ready and i said perhaps. that "
            "is the truest answer i have, whatever the checklist "
            "says",
        ],
        "numbers_units_prose": [
            "The {thing} came back at {n1} {unit} on Tuesday; the "
            "bench by the window read {n2} lower (its corner is "
            "always cooler), and the difference has held for {n3} "
            "days now, steady as anything.",
            "We counted {n1} {unit} across the {part} this week — "
            "{n2} more than the week before, if my notes are "
            "honest — and it seems the quiet mornings account for "
            "nearly all of the change.",
        ],
        "warm_narrative": [
            "There is a moment, just before the {part} wakes, when "
            "the whole place seems to be listening. {who} laughed "
            "when I said so, but then stood there with me, and we "
            "both felt it — something gentle moving through the "
            "ordinary.",
            "My favourite memory of the {topic} is not any triumph. "
            "It is an afternoon of small things done slowly "
            "together, the {part} behaving as if it understood, "
            "and all of us leaving a little more alive than we "
            "arrived.",
        ],
        "inline_code_quote": [
            "The nicest change this week: `{fn}` now yields each "
            "{concept} as it ripens instead of hoarding them. I "
            "think the {part} reads more honestly for it, though "
            "the old `for` loop had a certain stubborn charm.",
            "If `{k}` is ever empty we bail out early — see the "
            "guard in `{fn}`. It seemed fussy when {who} proposed "
            "it; now I feel the whole {part} is calmer because "
            "someone bothered.",
            "We renamed the flag to `--keep-{k}` so the {part} "
            "says what it means. Small, but I believe names are "
            "where kindness starts in this work, and `dry_run = "
            "False` never told anyone anything.",
        ],
        "code_long_comments": [
            "/* The {part} keeps the garden's diary, in its way.\n"
            " * Every reading is a small sentence about the soil,\n"
            " * and read together they tell you whether the season\n"
            " * has been kind. Water accordingly, and remember. */\n"
            "fn {fn}(rows: &[Row]) -> usize {{ rows.len() }}",
            "# Some tools you inherit like furniture: heavy, loved,\n"
            "# older than your reasons for keeping them. The {part}\n"
            "# is one of those. Tidy it as you would a room someone\n"
            "# you miss once kept — slowly, and with respect.\n"
            "def {fn}(items):\n    return sorted(items)[:{v}]",
        ],
        "warm_commit_dense": [
            "{pre} the {part} learned to wait its turn — {fn} used "
            "to throw an exception when the {k} list arrived empty, "
            "and now it simply breathes and returns. I think we "
            "will all feel that one.",
            "{pre} carried the {part} through its awkward merge. "
            "Two of us had edited the same {k} table, hearts in "
            "mouths, and the code — bless it — held everything "
            "together until we could sort it kindly.",
        ],
        "prose_plus_log": [
            "{who} swears the {part} hums at a different pitch when "
            "it is straining, and after this week I half believe "
            "it. The log, for once, agrees with the poetry:\n"
            "$ {cmd}\nreadings: {a} stored, {v} flagged, buffer "
            "clear",
            "We gave the {part} one last look before locking up, "
            "the way you check a sleeping house. It answered, "
            "plain as you like:\n[{h}:{m}:4{v}] {k} probe ok, "
            "value = {b}, nothing waiting\nand the room felt "
            "looked after.",
        ],
        "prose_plus_block": [
            "People keep asking what the {part} actually does, and "
            "prose keeps failing me, so here it is entire. I feel "
            "it deserves to be seen plainly, without my commentary "
            "dressing it up:\nfunc {fn}(xs []int) int {{\n"
            "    s := 0\n    for _, x := range xs {{ s += x }}\n"
            "    return s\n}}",
            "This is the heart of the {part}, all of it, entire. "
            "I remember writing it in one sitting, certain it "
            "would be replaced within the week; instead it has "
            "held, quietly, ever since:\n"
            "public static bool {fn}(int v) => v switch {{\n"
            "    < 0 => false,\n    _ => true,\n}};",
        ],
    },
}

# ---------------------------------------------------------------- plan
# (label, subtype, count, boundary_hard) -- identical shape per split;
# templates/literals come from each split's own pool.
PLAN = [
    ("code", "plain_function", 6, False),
    ("code", "diff", 5, False),
    ("code", "stack_trace", 5, False),
    ("code", "shell_log", 5, False),
    ("code", "config_low_symbol", 5, True),
    ("code", "prose_identifiers", 5, True),
    ("code", "terse_code", 4, True),
    ("code", "wordy_query", 5, True),
    ("model", "reflective_status", 6, False),
    ("model", "commit_prose", 5, False),
    ("model", "design_note_code_dense", 6, True),
    ("model", "chat_prose", 5, False),
    ("model", "numbers_units_prose", 5, True),
    ("model", "warm_narrative", 5, False),
    ("model", "polysemy_prose", 5, True),
    ("model", "terse_prose", 3, True),
    ("mixed", "inline_code_quote", 7, False),
    ("mixed", "code_long_comments", 7, False),
    ("mixed", "warm_commit_dense", 6, True),
    ("mixed", "error_shaped_prose", 6, True),
    ("mixed", "prose_plus_log", 7, False),
    ("mixed", "prose_plus_block", 7, False),
]
LITERAL_SUBTYPES = {"polysemy_prose", "error_shaped_prose", "terse_prose"}


def slots(rng, P):
    part = rng.choice(P["parts"])
    thing, unit = rng.choice(P["units"])
    w = rng.sample(P["idwords"], 3)
    return {
        "fn": rng.choice(P["funcs"]), "fn2": rng.choice(P["funcs"]),
        "f": rng.choice(P["files"]), "k": rng.choice(P["keys"]),
        "k2": rng.choice(P["keys"]), "who": rng.choice(P["people"]),
        "topic": rng.choice(P["topics"]), "part": part,
        "partu": part.replace(" ", "_"), "partd": part.replace(" ", "-"),
        "concept": rng.choice(P["concepts"]),
        "cmd": rng.choice(P["shell"]), "e": rng.choice(P["errors"]),
        "pre": rng.choice(["fix:", "feat:", "refactor:"]),
        "thing": thing, "unit": unit,
        "w1": w[0], "w2": w[1], "w3": w[2],
        "v": rng.randint(2, 9), "a": rng.randint(3, 40),
        "b": rng.randint(2, 30), "ln": rng.randint(12, 240),
        "pid": rng.randint(400, 9000), "h": rng.randint(10, 23),
        "m": rng.randint(10, 59), "n1": rng.randint(40, 900),
        "n2": rng.randint(5, 60), "n3": rng.randint(2, 30),
    }


def build_split(split_name, pool, seed, prefix):
    rng = random.Random(seed)
    items, used = [], set()
    for label, subtype, count, hard in PLAN:
        made = 0
        guard = 0
        while made < count:
            guard += 1
            if guard > 500:
                raise RuntimeError(f"cannot fill {split_name}/{subtype}")
            if subtype in LITERAL_SUBTYPES:
                text = pool["lit"][subtype][made % len(pool["lit"][subtype])]
            else:
                tpl = rng.choice(pool["tpl"][subtype])
                text = tpl.format(**slots(rng, pool))
            if text in used:
                continue
            used.add(text)
            items.append({"label": label, "subtype": subtype,
                          "boundary": hard, "message": text})
            made += 1
    rng.shuffle(items)
    return [{"id": f"{prefix}-{i:03d}", "split": split_name,
             "label": it["label"], "subtype": it["subtype"],
             "boundary": it["boundary"], "message": it["message"]}
            for i, it in enumerate(items, 1)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    splits = [("diagnostic", build_split("diagnostic", DIAG,
                                         seed=20261104,
                                         prefix="e7diag")),
              ("heldout", build_split("heldout", HELD,
                                      seed=77117711, prefix="e7held"))]
    for name, items in splits:
        counts = {lab: sum(1 for it in items if it["label"] == lab)
                  for lab in LABELS}
        print(f"{name}: n={len(items)} balance={counts}")
        if not args.check:
            path = HERE / f"{name}.jsonl"
            with path.open("w", encoding="utf-8") as f:
                for it in items:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
