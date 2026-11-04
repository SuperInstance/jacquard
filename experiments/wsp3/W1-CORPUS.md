# W1 corpus — how it was built

Phase 17 W1 shadow corpus: the fleet's real agent-message flow,
per CRITERIA.md's pre-established substitution (no live dial
consumers exist in the fleet; battery traffic is never reported
as live traffic — this corpus is labelled a substitution
wherever it is reported).

## Source

The agent-inbox repo on the Oracle (`~/agent-inbox`,
github.com/SuperInstance/agent-inbox), mined at its local HEAD
7504435 — the GitHub mirror is BEHIND the Oracle repo (156 vs
280 commits reachable), so mining ran against the Oracle repo
itself. 280 commits reachable from `--all` (main +
remotes kimi/main, origin/main).

Generator: `experiments/wsp3/build_corpus.py` (committed on
this branch; deterministic — commits visited in (date, hash)
order, paths sorted within a commit, first occurrence of a
content hash wins its provenance). Re-running it against the
same repo state reproduces `corpus.jsonl` byte-for-byte.
The corpus itself is committed as `corpus.jsonl.gz`
(9,221,644 bytes raw, 3,293,389 gzipped).

## Method

Every version of every file under `inbox/`, `claimed/`,
`done/`, `verdicts/`, `standing/` across all 280 commits:
16,366 blob-versions seen. Inclusion rules, stated in advance
of scoring:

- blob must decode as strict UTF-8 with no NUL byte (text
  only — this excludes the .onnx/.pt model binaries and .pyc
  files committed under done/017 and done/018);
- stripped text must be non-empty (excludes .gitkeep and
  empty files);
- deduplication by sha256 of the stripped text; each kept
  item's provenance is its FIRST occurrence: commit sha,
  path, commit date (ISO).

Out of 16,366 blob-versions: 15,330 were duplicate-content
occurrences, 279 binary occurrences, 601 empty occurrences,
leaving **156 distinct items** — every distinct text message
the full history contains under those directories.

## The count vs the target

CRITERIA.md targets >= 300 messages and states the fallback:
"if fewer exist, all of them, and the count is stated."
**156 exist. All of them are in the corpus.** The history is
shallow in distinct content because the inbox flow re-commits
the same files many times (moves inbox/ -> done/, status
edits, log appends).

## Provenance shape

First-occurrence top directory: standing 82, done 47,
inbox 22, verdicts 3, claimed 2. (A task that first appears
under inbox/ and is later moved to done/ keeps its inbox/
provenance; provenance records where a message entered the
flow, not where it ended.)

Dominance warning: **standing/prospector-log.md alone is 71
of 156 items (45.5%)** — an append-only log whose every
committed version is a distinct content (each version is a
prefix-extension of the previous). These are real versions
of a real agent log, kept per the mining rule, but any
corpus-level statistic is close to half prospector-log
snapshots by count. Per-provenance breakdowns accompany the
headline numbers in W1-SHADOW.md so this is visible, not
buried.

## Blind sample (for the teacher spot-check)

blind_sample.jsonl: 66 items (>= 60 required), drawn
from the 91 items both specialists scored, containing
ONLY id + text — no incumbent or specialist output.
Stratification, two levels, both stated: primary, by
the model/code incumbent's class, with strata of <= 5
items exhausted so the rare classes appear (sample
incumbent mix: code 63, mixed 2, model 1 — the mixed
and model strata are 2 and 1 items in the whole
universe); secondary, inside the dominant code
stratum, every item the panic specialist calls alarmed
(11) or stampede (3) is force-included so CRITERIA's
stampede watch is measurable on the sample (sample
panic-specialist mix: calm 46, alarmed 11, stampede 3,
no-label 6). All panic-alarmed/stampede items sit in
the code stratum, so the secondary rule does not
distort the primary mix. Draw is deterministic
(seed 17) in analyze_w1.py (run record on the Thor,
~/wsp-exp17/w1/). The panic incumbent's class cannot
stratify anything: it calls all 66 sample items calm,
as it does the whole corpus.

## Item shape vs battery shape

Corpus items are long: min 185 chars, median 7,048, max
544,423 (a tokenizer.json committed as a task artefact).
The E7/R4 battery items are short constructed messages
(tens to hundreds of chars). The specialists therefore read
far outside their battery surface in length alone; this is
part of what "in practice" measures, and the class-mix
caveat in W1-SHADOW.md applies throughout.

Specialist eligibility (stated, not silent): a specialist
scores an item only if its fixed harness prompt, chat-
templated exactly as the phase scorer builds it, tokenizes
to <= 8,192 tokens with the model's own tokenizer. Longer
items are recorded in scores.jsonl with specialist_class
null and note `prompt_too_long_cap_8192` — never truncated,
never chunked. Eligible: **91/156 for each specialist**
(65 items too long for both — the same set, since both
prompts wrap the same text and differ only by a short
instruction/transcript frame). The too-long set is mostly
the prospector-log snapshots plus the tokenizer artefact.
The incumbent dials (pure lexicon arithmetic) score all
156 items.

## Class mix under each incumbent (full corpus, n=156)

Measured by prepare_and_incumbents.py on the Thor;
incumbents.json is the record.

- Model/code dial (signal_chain_dial._score, equal-thirds
  mapping as in E7's baseline_joint.py): **code 153
  (98.1%), model 1, mixed 2.** Mechanism, visible in the
  _score source: model/code lexicon hits count DISTINCT
  words (a set), so their contribution saturates as a
  document grows, while the code-symbol count
  (braces/parens/brackets/semicolons/operators) counts
  EVERY occurrence and grows linearly with length. On
  battery-length messages the two terms are comparable;
  on real agent documents (median 7,048 chars) the symbol
  term swamps the lexicon and nearly everything reads
  code. The mixed class — the class the battery showed
  the incumbent already nearly blind to (held-out mixed
  3/40) — is effectively dead on live traffic: 2/156.
- Panic dial (elephant PanicDial, equal-thirds as in R4's
  run_incumbent.py; each item read as a single-message room —
  see W1-SHADOW.md for the adaptation and its consequence):
  **calm 156, alarmed 0, stampede 0.** The incumbent is a
  single-class instrument on this traffic: alarm_norm is
  divided by word_count/40, so on documents of ~1,000+
  words even a full lexicon of distinct alarm words cannot
  lift the reading across the 1/3 line, and the density and
  ripple terms are identically zero for a single-message
  room (density needs >= 2 messages in the window; ripple
  needs reactions/replies the corpus does not carry).
  Stampede is additionally unreachable in principle here:
  with density and ripple zeroed, the maximum possible
  reading is 0.40 + 0.25 = 0.65 < 2/3.
