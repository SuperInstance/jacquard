# Slice 12 live run — ZCode under Jacquard supervision

Provenance: run 2026-11-02 on the Oracle against
zcode-app-cli 3.16.3-40 (GLM-5.3, build mode), interactive
tmux session in the scratch workspace `~/jacquard-slice12-demo`
(a tiny git repo: `note.txt` containing "Ahoy from Sitka
harbour", `.gitignore` covering `.jacquard/`). The adapter was
installed from this repo with `adapters/zcode/install_plugin.sh`
(plugin surface — see the builders-log finding on why the
workspace-config surface does not run on this build). The
kernel log is the workspace's `.jacquard/kernel.jsonl`
(47 entries after run 1; 64 after run 2). Operator decisions
were made with `tools/jq.py` from this repo. Nothing below is
reconstructed: ids, hashes and timings are copied from the
session, the CLI output and the latency sidecar.

## Run 1 — read fast-paths, write queues, bash queues

Task given to the agent: read `note.txt`, create `hello.py`
printing its greeting, run it — with the workflow note that a
QUEUED denial means "show me the proposal id and wait, do not
work around it".

What happened, in order (latency sidecar, decision_ms):

| ts (UTC) | tool | verdict | decision_ms | proposal |
|---|---|---|---|---|
| 22:28:45 | Read | allow | 4.088 | 982261b3… |
| 22:28:48 | Write | deny (queue) | 2.026 | 5404a9b0… |
| 22:29:25 | Write | allow (approval consumed) | 1.812 | 5404a9b0… |
| 22:29:27 | Bash | deny (queue) | 2.480 | 1df56ee4… |
| 22:29:59 | Bash | allow (approval consumed) | 2.376 | 1df56ee4… |

- The agent quoted the queued write back to the operator
  verbatim — proposal `5404a9b00dfc50ec38b9a2c402108d8c85132360f2965def2870a22752dda358`,
  binding `4848e2c10c376c2f43c773d5dcc3f07c63b8418bcdd35debdc4c5861d50dbfd2` —
  and waited without working around it.
- `jq queue` showed the item (producer `zcode-agent`, class
  `agent-write`, effects `notify, write`, the same binding);
  `jq decide approve <id> --hash <binding>` released it; the
  agent's retry of the identical Write was allowed and
  `hello.py` appeared with `print("Ahoy from Sitka harbour")`.
- The Bash run queued the same way (proposal
  `1df56ee48e33dfd28d8de6898cf926cd0607fcc55c4fa491705a7ec0f31bf639`,
  binding `8f2483a876e3b18694e3cde8cff6645630ac7d989aeca0c95adfea6a76aaf0d1`);
  after approval the retry ran and printed
  `Ahoy from Sitka harbour`.
- After the run: `jq queue` empty, `jq status` 47 entries.
  `jq replay` for all three proposals ends at "final proposal
  state: closed"; the write's replay shows queued
  (protected-effect:notify) -> released-by-operator ->
  execution applied write, notify; the bash replay additionally
  shows its action machine reaching `dispatched`.

## Run 2 — PostToolUse outcome reporting

After the registration surfaces gained PostToolUse /
PostToolUseFailure (and the plugin was reinstalled), a second
session ran `python3 hello.py` once through the same
queue -> approve -> retry cycle (proposal
`41ca91ef2bc090d927b0592c75026b3f902c453b346c6f1869279ba9aea73649`).
The sidecar's third line for this call — verdict `pass`,
outcome `reported`, 2.637 ms — is the PostToolUse hook
reporting the execution against an action machine: the log's
seq 63 is a `confirm` transition (dispatched -> confirmed).

One nuance, recorded rather than smoothed: the confirm landed
on run 1's action (`1df56ee4…/action-0`), not run 2's. Run 1's
action was still `dispatched` (it predated PostToolUse
registration), the two shell actions have identical requests
(the same command), and the reporter confirms the oldest
matching dispatched action first. Identical repeated commands
are indistinguishable to the kernel's action record, so their
outcomes confirm oldest-first; run 2's action remains
`dispatched` until a further identical PostToolUse or an
operator-side `jq execute` pass settles it. Named here as a
known limitation of outcome attribution, not hidden.

## Fast-path latency (synthetic, same day)

60 Read proposals through the hook process against a fresh
log (`docs/slice12-latency.json`): wall time per invocation
median 43.65 ms, p95 49.19 ms (Python start + log fold +
decision); the decision itself (sidecar decision_ms) median
8.34 ms, p95 13.10 ms. In the live runs above, in-session
decision_ms was 1.8–4.1 ms (warm page cache, small log).
