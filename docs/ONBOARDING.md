# Onboarding — the concepts in meeting order

Jacquard has four ideas. This page introduces each one at
the moment an example forces it into existence, in the same
order `docs/QUICKSTART.md`'s drill makes you meet them. If
you have run the drill, you have already used all four;
this page names what you did.

## 1. A proposal — an agent asks

In the drill, `seed-demo` created proposals from two
producers, alice and bob. A **proposal** is the only way
anything enters Jacquard: a sealed envelope saying *who* is
asking, *what* they want to do (its **requests**), and —
computed, never declared — what that would **effect**:
write a file, send a message, spend a budget, dispatch a
job. Effects are computed from the definitions a proposal
is built from, out of a fixed set of 26 primitives, so a
proposal cannot hide what it does: a definition that sends
cannot be dressed as one that merely writes.

Real proposals you will meet in this repo: a coding agent's
tool call, translated by the ZCode adapter (a Bash command
becomes an `agent-shell` proposal); a GPU job submitted to
`tools/jqgpu.py`; a booking submitted to
`tools/jqbook.py`. Same envelope, same kernel.

## 2. A decision — policy answers

Every proposal is decided against **versioned policy**
before anything runs. The answer is one of:

- **allow** — it may proceed (alice's kind of action, when
  policy trusts the shape);
- **deny** — it may not, with a named reason (bob's spend,
  in the drill, once you deny it — or policy's own refusal:
  an unknown dictionary form is refused *by name*);
- **queue** — a human should look at this one. It waits,
  and *nothing else waits with it*: the producer's other
  work, and every other producer, keeps moving. This is
  the property the whole design exists for — approval is a
  batch, never a roadblock.

Decisions are not vibes: each is recorded with the policy
version that made it and the reasons it cites.

## 3. The queue — you decide a batch, hash-bound

The drill's `queue` listing showed each waiting item with
a **binding hash**. When you `decide approve <id> --hash
<binding>`, you are approving *the item you were shown* —
if the proposal changed after presentation, the binding
fails and nothing is decided. One approval authorises
exactly one execution of exactly that action; when the
producer retries the identical action, the approval is
**consumed** (recorded as a sense entry) and the action
runs once. A changed action is a new proposal and queues
again.

Over time, your decisions teach: shapes you keep releasing
are mined into candidate **standing rules**, which climb
an eval → shadow → canary → active ladder on scored
evidence, and can be revoked in one call. The queue
shrinks because your history compiled — not because anyone
widened a permission.

Two refinements you will meet in the profiles: when two
bookings contend for one seat, **contention** is a kernel
sense, and at equal authority rank the challenger *holds*
for you (the interim tie disposition) instead of silently
winning; and a job queue's jobs carry their outcomes back
into the same record (next section).

## 4. The record — everything replays

Every definition, proposal, decision, execution and sense
reading is an entry in an **append-only, hash-chained
log**. Committed state is a *fold* of that log — there is
no other state to trust or to lose. `replay <id>` walks
one proposal from submission to its final state; `counts`
re-derives a deployment's totals from the log alone; the
conformance suites prove three implementations fold the
same logs to the same hashes.

The chain proves the log is self-consistent. It cannot
prove the log wasn't rewritten wholesale — for that, the
log's head is **anchored**: signed checkpoints published
outside the kernel's store (the fleet's are in the public
`SuperInstance/jacquard-anchors` repo), so a forged history
fails verification at the first checkpoint it contradicts.
And when a record must be shared with fields withheld,
**sealed exports** redact under commitments recorded in
the log first — the anchored original is never altered,
and the export still verifies.

## Where each idea lives

| Idea | Spec | Start with |
|---|---|---|
| proposal, effects | §4–§5 | the drill (`tools/jq.py seed-demo`) |
| decision, policy | §6–§7 | `tools/jq.py queue` / `decide` |
| queue, standing rules | §7, §12 | `docs/proof-run-2-2026-11-02.md` |
| contention, authority | §11 | `tools/jqbook.py`, `docs/slice30-device-matrix.md` |
| the record, replay | §3, §8 | `tools/jq.py replay` |
| anchoring, sealed exports | §15–§16 | `tools/jqanchor.py`, `tools/jqseal.py` |

Then: `starters/` for a guided first deployment of each
proven use, `docs/DEVICES.md` for what differs per
machine, and `spec/SPEC.md` when you want the whole truth.
