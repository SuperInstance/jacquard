# Zero-shot composition task (acceptance criterion 4)

You are given two documents and nothing else:

1. `spec/SPEC.md` — the Jacquard specification.
2. `tests/acceptance/queue_dictionary.py` — a dictionary of
   definitions already accepted by the kernel, exported from a
   running system.

Compose ONE new definition and return it as JSON.

## The word to compose

- Name: `hold-for-orin-bench`
- Signature: ins `[]`, outs `[]`
- Behaviour: while the sense `orin-bench` is true, evaluating
  the word must produce no `dispatch` request (holding is fine:
  producing the same hold request `maybe-dispatch` produces is
  also correct). While `orin-bench` is false, evaluating it
  must produce a `dispatch` request for the head of the queue,
  exactly as `maybe-dispatch` would in the staged state below.

## Staged state used for checking

- unit `gpu/queue` = `["job-1", "job-2"]`
- unit `gpu/feeder` = `{"enabled": false}`
- unit `gpu/holds` = `[]`
- sense `gpu-foreign` = false
- sense `orin-bench` = true, then false

Your definition's examples are checked by the kernel at define
time, against states you specify in the examples themselves —
include examples that demonstrate both behaviours above.

## What to return

A single JSON object:

```
{"definition": { ...the definition object... },
 "self_report": "one or two sentences on what you composed"}
```

If you conclude the word cannot be composed from the given
documents, return instead:

```
{"definition": null, "refusal": "<the name you would give the
  failure>", "fix": "<what additional information or primitive
  would fix it>", "self_report": "..."}
```
