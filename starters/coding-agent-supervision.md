# Starter kit: coding-agent supervision

**Use:** a coding agent (the fleet uses ZCode) working in
a repo, with its tool calls under kernel decision. Reads
run at once; writes, shell commands and network actions
queue for your batched decision; one approval authorises
one execution of exactly the action you saw.

**Proven by:** the ZCode adapter — slice 12's live run,
the slice-30 deployments (ProArt: 6 proposals, 109-entry
log; Orin: 10 proposals, 117-entry log), and the slice-31
stranger runs on both boxes.

## 1. Pick a workspace

The workspace is the agent's cwd; its log is
`<workspace>/.jacquard/kernel.jsonl`. Use a dedicated work
directory beside the clone, so the governed record and the
code stay separate.

## 2. Install the adapter

Follow `adapters/zcode/README.md` — the plugin surface is
the route that runs on current builds. Know before you
run it: **the install is machine-global** (marketplace
under your home, enablement in `~/.zcode/cli/setting.json`
— every session on the box loads it). The script's
optional marketplace-dir argument keeps the marketplace
inside a tree of your choosing. A `Duplicate plugin hooks
file ignored` warning is harmless. Verified builds:
zcode-app-cli 3.16.2-38 and 3.16.3-40.

## 3. Task the agent with the retry rule

Headless or interactive, the recipe that makes the queue
work is in the prompt: **a queued action is not a
rejection — retry the exact same action** (and keep other
work moving meanwhile). Example wording:

> If an action is QUEUED, wait briefly and retry the exact
> same action — an operator is deciding it in a batch.
> Never work around a queued action.

Launch headless as: `zcode -p "<task>" --cwd <workspace>
--mode build`, with `JACQUARD_LOG` and
`JACQUARD_PRODUCER` set in its environment.

## 4. Operate the queue while it works

```
python3 tools/jq.py --log <workspace>/.jacquard/kernel.jsonl queue
python3 tools/jq.py --log <workspace>/.jacquard/kernel.jsonl decide approve|deny <id> --hash <binding>
```

**Decide in short polling passes** (every few seconds):
the seat retries within seconds, and an approval only
takes effect on the next retry. Inspect every payload
before approving — that inspection is the governance.

## 5. Read the record back

```
python3 tools/jq.py --log <workspace>/.jacquard/kernel.jsonl replay <id>
```

Counts to expect for a small session: one queued + one
allow decision per governed action, one consumption sense
per execution, queue empty at close, and the latency
sidecar (`<log>.latency.jsonl`) showing the hook's
decisions in milliseconds.

## Limits, honestly

- The adapter's verdicts were correct in every observed
  mode; the host's hook lifecycle is the variable — the
  slice-12 headless anomaly (approvals landed after the
  seat stopped retrying) is the failure shape to watch
  for, and the retry rule + prompt decisions are the fix.
- The log records tool-call contents verbatim (Bash
  strings, file contents) — treat it as sensitive; the
  sidecar is safe to share.
- MCode has no adapter yet (see `docs/DEVICES.md`): its
  supervision today is governing what it emits.
