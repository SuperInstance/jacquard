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

Any script that does something consequential can submit
through `tools/jq.py` (see the drill's shapes) or through
the loopback service (`tools/jqserve.py` — the README's
service section). The submission rule for your own
automations: **the consequential verb is a proposal**,
never a direct call. A script that spends, sends, deletes
or publishes goes through the log; a script that reads
does not need to.

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

- This kit governs your own machine's automations; it does
  not supervise other people's agents or shared state —
  those are the other three kits.
- The log records proposal contents verbatim: keep it out
  of shared repos and treat it as sensitive.
