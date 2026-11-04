# R4 inventory — elephant PanicDial (the second soft joint)

Read-only inventory pass, 2026-11-04, by the R4 battery-builder
seat for Jacquard Phase 16 slice 46 (amendment A1 joint).
No elephant code was modified.

Sources (SuperInstance/elephant @ 44e7363d304f8926632c0711c04637c1d110d9e8,
sparse checkout on the Thor, `elephant/` subtree only):
- `elephant/dials/panic.py` (md5 57e318bb706d96f3becdabc4cd397696)
- `elephant/dial.py`       (md5 3a3a09a8aabb05a94c1ae95b10307cc7)
- `elephant/room.py`       (md5 fb5059bfac02493301ce0b3f2d65f06c)

## Standalone runnability

The incumbent runs standalone, unmodified. On the Thor:

    git clone --filter=blob:none --sparse https://github.com/SuperInstance/elephant
    git sparse-checkout set elephant
    python -c "from elephant.dials.panic import PanicDial; ..."

imports the real `PanicDial`, `Room` and `Message` classes and
returns readings (smoke test: two messages "fire in the galley" /
"help now" 5 s apart read 0.5327). The top-level
`elephant/__init__.py` pulls `field`/`gesture`/`relaxation`, but
none of them need third-party packages on this path, so no shim
and no replication was needed. The baselines in this directory
import the real classes from that checkout; the dial's math is
nowhere reimplemented in the scoring path. (`run_incumbent.py`
also contains a `--selftest` that recomputes three hand-worked
readings against the imported dial to prove the runner builds
the Rooms it claims to build — the recomputation is a test of
the runner, not a second implementation used for scoring.)

## The incumbent computation (panic.py, `PanicDial.read`)

Input: a `Room` (see below). Output: float in [0, 1],
"0 calm .. 1 trampling". Empty room reads exactly 0.0.

Per message `m` (text lowercased first):

- `alarm_hits   += |{a in ALARM   : a is a substring of text}|`
- `urgency_hits += |{u in URGENCY : u is a substring of text}|`

  i.e. each lexicon entry counts **at most once per message**,
  however many times it occurs in that message, and counts again
  in every further message that contains it. Matching is raw
  substring (`a in text`), not word-boundary — see Defects.

- If a message contains any ALARM entry, it is a *trigger*
  message; `trigger_ripple = max` over trigger messages of
  `room.ripple(m)`.

Lexicons (verbatim, 21 + 11 entries):

- ALARM = fire, flood, breach, leak, alarm, emergency, evacuate,
  sinking, capsize, mayday, help, panic, stampede, crash,
  collision, man overboard, distress, code red, abandon, run
- URGENCY = now, immediately, hurry, fast, everyone, all hands,
  !!!, ???, now!, right now, go go go

Room-level terms:

- `density = room.density(window=30.0)` — messages per minute
  among messages within 30 s of the *last* message only
  (see room.py below); `density_norm = 1 - exp(-density/30)`.
- `word_count = sum(len(m.words))`, words = `\w+` tokens of the
  lowercased text (room.py `Message.words`).
- `alarm_norm   = min(1, alarm_hits / max(word_count/40, 1))`
- `urgency_norm = min(1, urgency_hits / 5)`
- `ripple_norm  = min(1, trigger_ripple / 20)`
- `panic = 0.40*alarm_norm + 0.25*urgency_norm
         + 0.20*ripple_norm + 0.15*density_norm`, clamped [0,1].

The spine (hard) is feature extraction: substring lexicon
counts, trailing-window density, reply/reaction cascade size.
The joint (soft, the judgement the spine cannot make) is the
**weighting**: every distinct lexicon hit in a message counts
equally — a negated "no fire", a quoted film line, a scheduled
drill notice and a genuine first report of fire each contribute
identically — and the four normalised terms are combined with
fixed weights 0.40/0.25/0.20/0.15 regardless of who is speaking,
whether the alarm is corroborated across the room, or whether
the words are even being used in their alarm sense.

## What a battery item must contain (room.py semantics)

- `Message(author: str, text: str, ts: float = 0.0,
  channel: str = "default", reactions: dict[str,int],
  replies: list[Message])`. A battery item is therefore a list
  of messages, each with author, text and a timestamp, plus —
  to exercise the ripple term at all — per-message reaction
  counts and reply structure.
- `Room(name, messages)` **sorts messages by `ts`** on
  construction. Timestamps are absolute floats in the source;
  the battery stores seconds relative to the first message,
  which is equivalent for every term the dial reads (density
  uses differences; gravity/reverberation are not read by
  PanicDial at all).
- `Room.density(window)`: takes messages with
  `latest_ts - ts <= window`; if fewer than 2 remain it returns
  0.0; otherwise `len(recent) / (last-first span in s) * 60`.
  PanicDial calls it with `window=30.0`, so density is decided
  entirely by the messages in the final 30 seconds: a room that
  talked slowly for ten minutes and bursts at the end reads the
  burst; a burst that ends more than 30 s before the last
  message is invisible to this term.
- `Room.ripple(msg, depth=3)`: `reaction_heat + len(replies)`
  plus the recursive ripple of each reply (depth 3).
  `reaction_heat = sum(reactions.values())`. Replies are full
  `Message` objects in the source. The battery represents a
  reply count `k` as `k` stub reply Messages (empty text, no
  reactions, no further replies) attached to the message: their
  contribution to ripple is exactly `k`, and, not being members
  of `room.messages`, they contribute nothing to the lexicon,
  word-count or density terms. This is stated here because it
  is a battery representation choice, not an elephant concept.
- `Message.words`: `re.findall(r"\w+", text.lower())` — this
  sets the `word_count` denominator of `alarm_norm`.

Consequence for scale: in the battery's short rooms
(3–12 messages, roughly 25–140 words), `max(word_count/40, 1)`
is between 1 and ~3.5, so **one or two distinct alarm hits
already saturate `alarm_norm` at 1.0**, contributing the full
0.40 — above the 1/3 calm/alarmed threshold on the alarm term
alone, before urgency, ripple or density add anything.

## Class form (pre-stated, untuned)

The dial's [0,1] reading is mapped to the battery's 3 classes
with FIXED equal-thirds thresholds, stated in advance and
never tuned (the E7 treatment of its incumbent):

    reading < 1/3  -> calm
    reading < 2/3  -> alarmed
    otherwise      -> stampede

## Defects found in the incumbent (reported, not fixed)

Quantification method: `defect_scan.py` in this directory
counts occurrences over the R4 battery itself; the numbers
below are its output on the shipped battery (see R4-BATTERY.md
for the battery). Defects are properties of panic.py / room.py
as written.

D1. **Substring lexicon matching (no word boundaries).**
    `a in text` fires inside unrelated words. Live examples in
    ordinary English the lexicons trip on: URGENCY "now" inside
    "know" / "snow" / "nowhere"; URGENCY "fast" inside
    "breakfast" / "fasten"; ALARM "run" inside "running",
    "rerun", "overrun" and "runway"; ALARM "help" inside
    "helpful" / "helping", ALARM "fire" inside "fireplace" /
    "bonfire" / "firewood", ALARM "crash" is a whole word that
    is polysemous rather than a substring trap. Every such hit
    counts exactly like a genuine alarm word.

D2. **No negation, quotation or modality handling.** "no fire",
    "false alarm, stand down", "the film ends with a fire",
    "fire drill on Tuesday" all add alarm hits identically to a
    genuine report. This is the joint's core blindness and the
    battery's largest boundary family.

D3. **Distinct-per-message counting flattens intensity inside a
    message and multiplies it across messages.** "FIRE FIRE
    FIRE" in one message = 1 hit for "fire"; the same word in
    five one-word messages = 5 hits. A single long careful
    report is systematically under-counted against a room
    repeating one word.

D4. **Density window edge effects.** Density is read over the
    trailing 30 s only and returns 0.0 when fewer than 2
    messages fall in that window — a stampede that pauses for
    31 s before a final message reads density 0; conversely two
    messages 1 s apart at the end of a quiet room read
    120 msgs/min (`density_norm` ≈ 0.98).

D5. **Ripple is gated on alarm substrings and is content-blind.**
    A cascade under a message with no ALARM substring (a purely
    technical emergency report) contributes no ripple at all,
    while reactions/replies on a joking "fire" message count in
    full. Ripple also counts reactions on the trigger message
    regardless of what the reactions mean.

D6. **`alarm_norm` saturates at battery scale** (see above):
    the normaliser `word_count/40` was presumably written for
    longer rooms. Measured on this battery (defect_scan):
    room word counts run 42–122 (median 75), so the
    denominator runs 1.05–3.05 (median 1.875) and **two
    distinct alarm hits already saturate the alarm term** in a
    median room. The dial cannot express "one or two alarm
    words, merely mentioned" at low weight in a short room.

Measured defect totals over the shipped battery
(`defect_scan.py`, lexicons imported from the real panic.py;
300 items, 1,721 messages):
- D1 substring traps: **62 messages** carry at least one
  lexicon entry that matches only as a substring inside a
  larger word (no word-boundary match). By entry: URGENCY
  "now" 14 (e.g. inside "know"), ALARM "crash" 11 (inside
  "crashed"), ALARM "flood" 9 (inside "flooded"), ALARM "run"
  8 (inside "running"), URGENCY "fast" 7, ALARM "fire" 6
  (inside "fire"-compounds/inflections), ALARM "panic" 4
  (inside "panics"), ALARM "abandon" 2, ALARM "capsize" 1.
- D3 flattening: **32 hits are lost** to distinct-per-message
  counting (an entry occurring >= 2 times in one message
  counts once): ALARM "fire" loses 12, "crash" 8, "run" 4,
  "flood" 3, URGENCY "now" 3, ALARM "alarm" 2.
- Stampede-band reachability (measured, baseline run): with
  these weights a room needs essentially saturated alarm AND
  urgency terms to cross 2/3; on this battery **no
  gold-stampede item in either main split reaches 2/3** (max
  0.623 / 0.635), while `single_loud_voice` items — one
  uncorroborated author — read 0.50–0.67 on ripple/urgency
  saturation alone, and `technical_cascade` items (room-wide
  genuine action, technical vocabulary) read 0.13–0.19.

D7. (Minor, dial.py) `DialBank.__init__` annotates
    `Optional[Iterable[Dial]]` but dial.py never imports
    `Iterable`; harmless only because `from __future__ import
    annotations` keeps the annotation unevaluated. Not a
    PanicDial defect; recorded for completeness, not counted
    against the joint.
