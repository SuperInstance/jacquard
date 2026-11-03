# Starter kit: batched approvals for a solo operator

**Use:** one human, one machine, local automations — your
scripts and agents propose, you decide in batches, the log
on your machine is the record. No server, no sharing.

**Proven by:** the drill in `docs/QUICKSTART.md`
(generalised) and the fleet's own operator practice.

## 1. Start with the drill

```
rm -f /tmp/kernel.jsonl
python3 tools/jq.py --log /tmp/kernel.jsonl seed-demo
python3 tools/jq.py --log /tmp/kernel.jsonl queue
python3 tools/jq.py --log /tmp/kernel.jsonl decide approve <id> --hash <binding>
python3 tools/jq.py --log /tmp/kernel.jsonl execute
python3 tools/jq.py --log /tmp/kernel.jsonl replay <id>
```

You now know the four ideas. Keep your real log under
your home directory (every tool takes `--log`).

## 2. Point an automation at the queue

Any script that does something consequential submits a
proposal file with `tools/jq.py submit` (or through the
loopback service, `tools/jqserve.py` — the README's
service section):

```
{"producer": "newsletter", "id": "send-2026-11-04",
 "declared_effects": ["send"],
 "body": {"class": "outbound",
          "requests": [{"verb": "send",
                        "args": ["https://example.org/post",
                                 "Harbor Notes #43 is out"]} ]}}
```

```
python3 tools/jq.py --log ~/kernel.jsonl submit proposal.json
```

The submission rule for your own automations: **the
consequential verb is a proposal**, never a direct call.
A script that spends, sends, deletes or publishes goes
through the log; a script that reads does not need to.

**What queues, and what doesn't.** Under the shipped
policy (`policy/1`), a proposal whose effects touch the
protected set — `send`, `notify`, `spend`, `irreversible`
— queues for your decision whenever the producer is not
the operator. There is no exemption class to declare: a
routine send queues the first time like any other.
Effects outside the protected set are decided on
submission. A class of routine items earns auto-decision
a different way — by repetition: shapes you keep
approving in the batch become standing rules (§4), and a
rule at its active stage decides the next one itself,
with the decision recorded as the rule's. If you need a
category to never queue from day one, that is a policy
change, not a configuration of this kit — the honest
shape of the tool is queue-first, then earned trust.

## 3. Decide in batches, on a cadence

Once a day (or once a sitting), present the queue and
decide it whole:

```
python3 tools/jq.py --log ~/kernel.jsonl queue
#    approve what you recognise, deny what you don't —
#    a denied action stays denied for that exact payload,
#    and a changed payload is a new proposal
```

Batching is the point: three passes a week beat thirty
interruptions a day, and every decision lands in a record
you can replay in a month when you ask "why was that
allowed".

## 4. Let the queue shrink

Shapes you keep approving become candidates for standing
rules (spec §12): evaluate, shadow, canary, active —
revocable in one call. Check what your rules are doing:

```
python3 tools/jq.py --log ~/kernel.jsonl status
```

If a rule starts releasing something you would now deny,
reject it once and the rejection counts against the rule.
That feedback is the learner's training signal.

## Limits, honestly

- One automation sending a handful of items a week is
  honestly served by a script and a file. This kit earns
  its keep when several automations propose against the
  same log, when your approvals should compile into
  standing rules, or when "why was that allowed" needs an
  answer you can replay.
- This kit governs your own machine's automations; it does
  not supervise other people's agents or shared state —
  those are the other three kits.
- The log records proposal contents verbatim: keep it out
  of shared repos and treat it as sensitive.
