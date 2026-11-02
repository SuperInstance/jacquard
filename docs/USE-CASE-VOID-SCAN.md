# USE-CASE / VOID SCAN — Jacquard

*Commissioned by Casey, 2026-11-02: development should aim at real
use cases and at voids in what the world already offers —
uniqueness first, usefulness second (his standing extraction
rules, applied to Jacquard itself). This is a research-and-analysis
document. It does not modify the repo.*

*Method: the incumbent survey was run as four parallel research
passes over PRIMARY documentation only (official docs sites,
official GitHub repos, PyPI) on 2026-11-02. Vendor claims are
treated as testimony: a capability counts as SHIPPED only when
product documentation describes the mechanism concretely;
blog/landing claims are labelled MARKETING; a capability searched
for and not found in the docs is labelled NOT-FOUND (absence in
docs is a finding about the documented product, not proof about
unreleased code). Jacquard's side of the comparison uses ONLY what
is in v0.2.0, verified the same day against the repo on the Oracle
(main@3ce55ff, tag v0.2.0, spec 0.2, suite re-run: 128 passed;
TypeScript conformance 7 PASS + 2 declared SKIPs). Known limit of
Jacquard's own evidence base: its live-world proof so far is one
shadow trial over one real workflow's history (the fleet booking
board: 68 items, 52 decidable, 88% agreement) plus a replay of a
real GPU job-queue record. That is thin, local evidence and the
beachheads below are sized accordingly.*

*Scope of the survey: 16 products in four clusters — agent
frameworks (LangGraph, CrewAI, AutoGen/AG2, OpenAI Agents SDK),
durable execution (Temporal, Inngest, Trigger.dev, Restate),
policy/guardrails (OPA, Guardrails AI, NeMo Guardrails,
HumanLayer), observability/governance (LangSmith, Langfuse,
Microsoft Entra Agent ID / Agent 365 / Purview / Foundry,
Anthropic Claude Code). NOT surveyed in this pass (named so the
gaps are visible): standalone authorisation services (Permit.io,
Cerbos, OpenFGA), agent-security startups (e.g. Noma, WitnessAI),
eval/observability beyond the two above (Arize, Galileo,
AgentOps), sandbox providers (E2B), and agent protocols (MCP/A2A
governance layers). Conclusions are about the surveyed set.*

---

## 1. What the world offers — the five questions, by cluster

Every product was asked the same five questions: (1) how does it
gate untrusted agent actions before they execute? (2) what is its
human-approval pattern — blocking, batched, none? (3) can you
reconstruct WHY a decision happened from a tamper-evident record?
(4) can recurring patterns become standing rules with staged
deployment and rollback? (5) can state/rules move between systems
or providers?

### 1.1 Agent frameworks (LangGraph, CrewAI, AutoGen, OpenAI Agents SDK)

- **Gating exists everywhere, and is developer code everywhere.**
  LangGraph: `interrupt()` before a tool runs, or middleware with
  an argument predicate (`interrupt_on`); checks are code you
  write, no policy language or store
  (https://docs.langchain.com/oss/python/langgraph/interrupts,
  https://docs.langchain.com/oss/python/deepagents/human-in-the-loop).
  CrewAI: pre-tool hooks can block (`HookAborted`) — with the docs'
  own caveat that any *other* exception in a hook is swallowed,
  i.e. fail-open
  (https://docs.crewai.com/v1.15.31/en/learn/tool-hooks).
  AutoGen: an `approval_func` exists only for code execution, and
  the default (`None`) auto-approves everything; no general
  function-tool gate was found
  (https://microsoft.github.io/autogen/stable/_modules/autogen_agentchat/agents/_code_executor_agent.html).
  (Status note: Microsoft has archived AutoGen — "no longer
  maintained," production use advised against, users directed to
  Microsoft Agent Framework: https://github.com/microsoft/autogen.)
  OpenAI Agents SDK: tool guardrails + `needs_approval`; documented
  footgun — input guardrails default to parallel mode, in which
  tools may already have executed before cancellation; tool
  guardrails don't cover hosted tools, handoffs, or `Agent.as_tool()`
  (https://openai.github.io/openai-agents-python/guardrails/,
  https://openai.github.io/openai-agents-python/human_in_the_loop/).
- **Approval = blocking, per item, in all four.** LangGraph's
  interrupt waits indefinitely; parallel tool calls batch into one
  interrupt, but surfacing/queuing pending interrupts across runs
  is application code. OpenAI's `RunState` serialises the wait so
  an app *can* build a queue — the SDK ships the pause, not the
  queue. CrewAI is the partial exception: a custom
  `HumanFeedbackProvider` can make feedback non-blocking with
  persisted resume (https://docs.crewai.com/v1.15.28/en/learn/human-feedback-in-flows)
  — a paused-flow resume mechanism, not a managed multi-item
  review queue. AutoGen's `UserProxyAgent` blocks the team and the
  docs warn the blocked state "cannot be saved or resumed"
  (https://microsoft.github.io/autogen/0.5.4//user-guide/agentchat-user-guide/tutorial/human-in-the-loop.html).
- **Audit/replay: state snapshots and traces, never
  tamper-evident.** LangGraph checkpoint replay re-executes nodes
  including LLM calls, which the docs note "may produce different
  results" — replay is not deterministic re-derivation
  (https://docs.langchain.com/oss/python/langgraph/use-time-travel).
  CrewAI checkpoints + OpenTelemetry tracing; OpenAI SDK tracing to
  its dashboard or custom processors. No hash chain, no signing,
  no policy-version-stamped decision record in any of the four.
- **Learned behaviour: essentially absent.** CrewAI alone ships a
  narrow form: `@human_feedback(learn=True)` distils feedback into
  memory "lessons" an LLM recalls to pre-review future output —
  memory applied by a model, not a standing rule; no scoring, no
  shadow/canary, no demotion. The other three: NOT-FOUND.
- **Portability: within-ecosystem only.** AutoGen's JSON component
  dump/load is the best declarative story (with documented holes:
  tools not serialisable, `selector_func` silently dropped).
  Definitions are otherwise framework code; no cross-framework
  export format was found in any docs.

### 1.2 Durable execution (Temporal, Inngest, Trigger.dev, Restate)

- **Gating: NOT-FOUND as policy in all four.** Workflow code just
  runs activities/steps; the only pre-execution hooks are
  developer code (Temporal interceptors/update validators,
  Inngest middleware — https://docs.temporal.io/develop/python/workers/interceptors,
  https://www.inngest.com/docs/durable-execution/guides-and-advanced/middleware)
  or a human: Trigger.dev's chat tools have `needsApproval`
  (https://trigger.dev/docs/ai-chat/patterns/human-in-the-loop)
  and Restate's documented pattern for "dangerous actions" is code
  that pauses for a human via an awakeable
  (https://github.com/restatedev/docs-restate/blob/HEAD/docs/ai/patterns/human-in-the-loop.mdx).
  Nothing evaluates a proposed action's *effects*.
- **Approval = per-item blocking waits in all four** (Temporal
  Signals/`wait_condition`, Inngest `step.waitForEvent()`,
  Trigger waitpoint tokens, Restate signals/awakeables/promises).
  Other work continues (independent executions), but each item's
  approval is its own wait. Temporal's one batch mechanism is CLI
  bulk-*signalling* — the same payload to many executions, an
  operator broadcast, not a review queue of distinct items
  (http://docs.temporal.io/design-patterns/batch-processing-patterns).
  Trigger's `wait.listTokens` gives the raw material for a queue;
  completion is still per-token; no bulk approve is documented.
- **Audit/replay: the strongest logs in the survey, and still not
  tamper-evident.** Temporal's Event History is append-only,
  durably persisted, attributed (who started/signalled), and
  deterministically replayable — an exported history can be
  replayed locally with the SDK Replayer. But no hash chain or
  signature is documented anywhere; on Cloud the vendor controls
  the log, and an export carries no proof it wasn't altered
  (https://docs.temporal.io/workflow-execution/event).
  Restate's journal is SQL-inspectable — and operator-*editable*
  via `restate state edit`, the opposite of tamper-evidence
  (https://docs.restate.dev/services/introspection).
  Trigger.dev durability is CRIU checkpoint-resume, not replay —
  the vendor's own comparison table says "Replay behavior: None"
  (https://trigger.dev/vs/inngest). Inngest: traces + memoised
  step results, history in the vendor cloud.
- **Learned behaviour: NOT-FOUND.** Rollout machinery exists for
  *code* (Temporal worker versioning, Restate immutable
  deployments). Inngest is closest in spirit: Agent Evals
  (beta) score runs, and `group.experiment()` canaries
  developer-coded variants on live traffic — but rollout is
  manual ("read the results and roll out"), variants are code,
  nothing mines patterns into rules
  (https://www.inngest.com/docs/agent-evals/experiments).
- **Portability: within-product.** Temporal is strongest
  (self-host ↔ Cloud replication; closed histories export to your
  S3/GCS/Azure in protobuf for "compliance and audit trails" —
  https://docs.temporal.io/cloud/export). No product documents
  importing a history into a different engine, or a third party
  verifying one.

### 1.3 Policy / guardrails (OPA, Guardrails AI, NeMo Guardrails, HumanLayer)

- **Gating: all four check declarations, none verifies effects.**
  OPA decides over the JSON the caller supplies; Rego can compute
  compositionally over that declared artefact (functions,
  comprehensions), but OPA has no semantics of any action and no
  check that reality matches the input — a lying enforcement point
  defeats it (https://www.openpolicyagent.org/docs/policy-language).
  Guardrails AI validates input/output *text and values* with Hub
  validators (`on_fail` ∈ reask/fix/filter/refrain/…)
  (https://github.com/guardrails-ai/guardrails/blob/HEAD/README.md).
  NeMo's execution rails validate tool-call *structure* (allowed
  tool name + JSON-Schema-conformant args; the IORails engine
  "does not execute tools… validate[s] the request and response
  boundary") (https://docs.nvidia.com/nemo/guardrails/configure-guardrails/guardrail-catalog/tool-calling).
  HumanLayer (legacy SDK — see status note below) gates on a human
  judging the declared call; its one real strength is that
  `@hl.require_approval()` is baked into the tool itself, so the
  gate fires even if the model never asks
  (https://pypi.org/project/humanlayer/0.5.1/).
- **Approval: only HumanLayer has one, and it blocks per call**
  (Slack/email/Discord routing; denial feedback returns to the
  model). Batched queue: NOT-FOUND. OPA: NOT-FOUND (a decision
  *could* return "requires_approval" — your code builds the rest).
  NeMo: explicitly disclaimed — the docs say not to assume
  "approval workflows"
  (https://docs.nvidia.com/nemo/guardrails/resources/runtime-security-faq).
  *Product-status finding:* HumanLayer has pivoted — its docs and
  repo now describe a coding-agent IDE/control plane; the approval
  SDK survives as legacy packages. "Audit Logs" appears on the
  current site only as an Enterprise pricing line with no
  documented format (https://humanlayer.dev/docs).
- **Audit/replay: OPA is best and still unsigned.** OPA decision
  logs carry the full input, result, decision_id and the exact
  bundle revision; `nd_builtin_cache` exists expressly for
  "debugging and decision replay," so decisions are re-derivable
  offline *if* you kept the event and that bundle revision.
  Caveats from the same docs: input masking can remove fields
  before logging, breaking exact replay; signing exists for policy
  *bundles*, not for decision records
  (https://www.openpolicyagent.org/docs/management-decision-logs,
  https://www.openpolicyagent.org/docs/management-bundles).
  NeMo's FAQ is unusually honest: "Do not assume that every
  decision automatically includes a reason code, policy version,
  tenant ID, or replayable event schema"
  (https://docs.nvidia.com/nemo/guardrails/resources/runtime-security-faq).
  Guardrails AI keeps a mutable in-process history object.
- **Learned behaviour: NOT-FOUND in all four.** Policies are
  hand-authored (Rego, validators, Colang). HumanLayer's site
  claims "agents get smarter over time" — MARKETING, no pipeline
  documented.
- **Portability: OPA strongest** (Rego bundles are git-able
  policy-as-code, runnable anywhere OPA runs, compilable to
  wasm). The decision record is portable JSON but not
  self-verifying — verification means re-running OPA.

### 1.4 Observability / governance (LangSmith, Langfuse, Microsoft, Claude Code)

- **Gating: the observability products don't gate at all.**
  LangSmith automations act on traces *after* ingestion; Langfuse
  is tracing/prompt/eval, capture asynchronous and out of the
  request path (https://docs.langchain.com/langsmith/rules,
  https://langfuse.com/resources/engineering/clarifications).
  Microsoft's bundle gates narrowly in three places, none of them
  a per-action policy engine: Entra Conditional Access at token
  issuance for an agent identity; Foundry guardrails (Preview)
  doing annotate-and-block on content-safety categories at tool
  call; Purview DLP blocking Copilot processing of labelled data
  (https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview,
  https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/agent-identity).
  Per-action approval exists only in Microsoft's *developer
  framework* (`ApprovalRequiredAIFunction`), not the governance
  plane (https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/sequential).
- **Claude Code is the strongest per-action gating surface in the
  whole survey**: deny → ask → allow rules in `Tool(specifier)`
  form, enforced by the harness not the model; `PreToolUse` hooks
  can allow/deny/ask/defer and a hook deny holds in every mode
  (https://code.claude.com/docs/en/permissions,
  https://code.claude.com/docs/en/hooks-guide). Approval is a
  synchronous in-session per-action prompt. Async/batched queue:
  NOT-FOUND.
- **Audit/replay: rich vendor logs, zero verifiable records.**
  LangSmith/Langfuse traces are exportable (OTel, Parquet/blob) —
  telemetry, not decision records; Langfuse's separate platform
  audit logs are about changes *in Langfuse*. Microsoft retains
  Purview audit 180 days, searchable/exportable, stored in the
  tenant — no signed/hash-chained artifact, no policy-version
  binding, coverage uneven (some records omit prompt/response
  text) (https://learn.microsoft.com/en-us/purview/audit-standard-setup).
  Claude Code exports OpenTelemetry to your backend; decisions are
  not signed, not policy-version-stamped, no replay procedure
  documented (https://code.claude.com/docs/en/monitoring-usage).
- **Learned behaviour: NOT-FOUND as governed rules.** Microsoft's
  Entra ID Protection scores agent *risk* continuously, and a
  human-written Conditional Access policy can block on high risk —
  the learning feeds a signal, not a rule pipeline.
  Claude Code's one real history→rule mechanism is "don't ask
  again": it instantly writes a permanent allow rule to
  `.claude/settings.local.json` — immediate effect, no scoring,
  no shadow/staging, rollback = edit the file
  (https://code.claude.com/docs/en/permissions).
  Langfuse's genuinely staged artefact is *prompts* (labels,
  promotion/rollback) — prompts don't gate actions.
- **Portability: Langfuse strongest** (MIT, self-host/air-gapped,
  OTLP, blob export); Claude Code's rules are plain files in VCS
  but a proprietary syntax; Microsoft's identity/policies are
  Entra/M365-bound, log export (CSV) the only egress.

### Disagreements with vendor framing (recorded per the brief)

- "Replay" means three different things in vendor docs: Temporal =
  deterministic re-execution against a durable history (real);
  LangGraph = re-run from a snapshot, non-deterministic by the
  docs' own admission; Trigger.dev = start a *new* run (dashboard
  "replay"), durability being process checkpointing. Only the
  first is replay in the audit sense.
- "Guardrails" (NeMo, OpenAI) mostly guard *content and
  structure* — text in/out, tool name + arg schema — not what an
  action will do. The word invites an effects reading the
  mechanisms don't support.
- "Governance" (Microsoft) is identity + content safety + data
  loss prevention. It governs *who the agent is* and *what content
  flows*, not *which decisions the agent may take and why*.
- "Learning" claims (CrewAI lessons, HumanLayer's "agents get
  smarter") describe model-mediated memory, not governed rule
  deployment. The mechanisms are real; the framing overstates the
  discipline by exactly the stages that are missing (scoring,
  shadow, demotion).

---

## 2. The voids

Each void is stated as a need a real user plausibly has, with the
survey evidence that the surveyed offerings do not cover it.

**V1 — Verified-effects gating for composed behaviour.**
Need: before an agent's action runs, know what it will actually
do — including when the action is a composition (a script, a
defined workflow, a tool chain) whose effects are not visible in
its name or arguments. Evidence: across all 16 products, gates
evaluate declared artefacts — OPA reasons over supplied JSON and
cannot detect a mis-declaring caller (§1.3); NeMo validates
tool-call structure only; framework hooks/guardrails run developer
code over declared args; HumanLayer shows declared args to a
human. No surveyed product computes a composite action's effects
from its parts and refuses mechanically when the computation
exceeds what was declared. The gap is sharpest exactly where
agents are heading: agents that *write* the procedures they then
execute.

**V2 — Batched, non-blocking human approval.**
Need: a supervisor of many agents (or one busy human) cannot be a
synchronous prompt. Approvals should accumulate as a queue of
distinct items, decidable in one pass, with the rest of the work
continuing — and the approval should bind to exactly the item
reviewed. Evidence: every shipped approval mechanism surveyed
blocks the item's run — LangGraph interrupts, OpenAI
interruptions, HumanLayer's blocking call, Temporal/Inngest/
Trigger/Restate waits, Claude Code's in-session prompt (§§1.1,
1.2, 1.3, 1.4). The near misses prove the shape is missing rather
than the parts: OpenAI ships a serialisable pause and leaves the
queue to you; CrewAI ships async resume and leaves the queue to
you; Temporal ships bulk *broadcast*, not review. No surveyed
product documents hash-bound approval (approve a changed item →
fail), which is the property that makes batch review safe.

**V3 — A "why was this allowed" record an auditor can verify
without trusting the vendor.**
Need: regulated or simply careful operators must reconstruct a
decision — proposal, computed/declared effects, policy version,
evidence, outcome — from a record whose integrity doesn't rest on
the platform's own database. Evidence: zero of 16 products
documents a hash-chained or signed decision record. The two
closest (OPA decision logs, Temporal event histories) are
replayable but unsigned; OPA's masking can break replay; NeMo's
FAQ explicitly disclaims policy-version/replay guarantees;
Microsoft's audit is a tenant log you trust as stored; Restate's
journal is operator-editable. Independent verification by a third
party — re-deriving the decision from an exported artifact with
different code — is not a documented capability anywhere in the
survey.

**V4 — Approval history and outcomes compiling into governed
standing rules.**
Need: a supervisor approves the same shape of action forty times;
the fortieth approval should be a candidate rule, deployed the
way production changes should be: evaluated offline, shadow-run
against live traffic, activated in stages, scored, auto-demoted
on regression, revocable in one action. Evidence: NOT-FOUND in
all 16 products for gating rules. The four partial mechanisms
each miss different stages — CrewAI lessons (no rule, no
scoring/staging), Inngest experiments (scored canary of
hand-coded variants, manual rollout), Claude Code "don't ask
again" (a rule, instantly permanent, no scoring/shadow/rollback),
Langfuse prompt labels (staged, but prompts don't gate). The void
is precisely the composition of stages; note this is also the
void in the fleet's own current practice (per-case approvals
that never compound).

**V5 — Governance state that travels with trust reset.**
Need: move an agent's accumulated rules/definitions between
machines, providers, or organisations without either (a)
rebuilding trust from zero or (b) importing unearned trust.
Evidence: portability in the survey is within-product (Temporal
self-host↔Cloud, OPA bundles, Langfuse self-hosting) — code and
config move; *earned standing* does not move at all, and nothing
documents rules arriving unproven and re-earning activation in
the new environment, or authority/credentials being refused at
the border by construction. Cross-implementation verification of
a decision record (V3) is likewise absent, so even the record
doesn't travel as evidence.

**V6 — Fair contention between untrusted producers for shared
scarce resources.** *(Absence-based; partially unverified.)*
Need: several agents share one GPU, one executor pool, one
human's attention; allocation should be fair (no starvation),
resistant to flooding/capture, and accounted in the same record
as the decisions. Evidence: none of the surveyed docs describes
allocation across competing producers as a governed, priced,
fair-queued resource tied to the gate — workflow platforms offer
concurrency/rate limits as operational knobs (this specific area
was not exhaustively read for every product; mark the rate-limit
details UNVERIFIED), and observability products don't allocate.
The fleet's own booking-board history shows the failure mode is
real and mundane: exclusive resources double-booked by an
ungoverned process (see §4, beachhead 1/3 evidence).

---

## 3. Jacquard v0.2.0 mapped onto the voids — built properties only

| Void | Jacquard v0.2.0 (verified in repo) | Coverage |
|---|---|---|
| V1 verified effects | Dictionary definitions composed from 26 primitives; a definition's effects are **computed** as the union over its expansion (spec §§4–6); policy gates on computed effects; a definition cannot hide an effect, including transitively (Phase 1 acceptance C2, in the test suite) | **Partial, honestly bounded:** computed effects cover *dictionary-defined* behaviour. Raw (non-dictionary) proposals carry *declared* effects; their honesty rests on the sandboxed executor (bwrap adapter, spec §10.5) enforcing the declared envelope at runtime plus producer records — design gap GAP-3 in the design record, not hidden |
| V2 batched approval | Policy returns require(approval) → item enters a **decision queue**; all other work continues (Casey's ruling, spec §7); operator CLI (`tools/jq.py`) presents the queue and decides in batch; approvals are **hash-bound** — approving a changed item fails with binding mismatch and changes nothing (§10 slice, cold-agent drill passed from README alone) | Covered at kernel/CLI scale. No UI, no notification channels (no Slack/email), no multi-operator assignment — the queue is a local CLI surface today |
| V3 verifiable record | Append-only **hash-chained log**; state = fold; envelopes seal the spec version into every entry id; decisions record policy version; replay re-derives any proposal's full history (operator CLI `replay`). Third-party verification is demonstrated, not just claimed: an independent TypeScript implementation written from the spec alone folded the 3,295-entry real replay log to the identical state hash (conformance: 7 PASS, 2 SKIP — definitions/state vectors not yet ported) | Covered as *tamper-evidence + independent re-derivation*. Honest bound: a hash chain proves tampering only against an anchored head hash; v0.2.0 has no external anchoring/notarisation, no key management, and the audit story is a spec + two implementations, not a compliance product |
| V4 learned rules, governed | Learner (spec §12): mines repeated decision shapes → candidate definitions with computed effects → offline evaluation on a held-out slice → **shadow** → canary → active, each promotion scored against policy/1's *recorded outcomes* (never against the rule itself) → **auto-demotion** on regression (planted-regression test) → one-call revocation, all as machine transitions in the log | Covered as a mechanism, demonstrated on the GPU-queue record + synthetics. Honest bounds: never yet run against live traffic over time; quarantine stage exists as an operator lever with nothing driving it yet; learner quality bounded by the similarity index and evaluation-set quality (GAP-4) |
| V5 portable governance | State export bundles (spec §14): config/definitions/machines travel; definitions' effects are **recomputed at import** (a bundle claiming effects is refused); standing rules **re-enter at shadow** with export stage as provenance only and must re-earn activation on the destination's record; budgets, standing, credentials, authority **never travel** — smuggling attempts refused by name; re-import idempotent | Covered between Jacquard kernels. Not covered: import from any other system's format (no OPA/framework adapters exist), and no other system can consume a Jacquard bundle |
| V6 contention | One WFQ scheduler (spec §11) arbitrates sequencer admission, executor slots and **decision-queue attention**; weights purchasable from budgets, decaying to baseline, aging prevents starvation (acceptance tests: quiet flow served under a 57-item flood; weight-4 buyer lands share without capture); budgets + posted prices in one accounting unit, spends replayable from the log | Covered as a mechanism on one kernel. Honest bound: single sequencer is a single point of failure by design choice (GAP-5; hot standby in scope, multi-master never); scale is a Python reference implementation's scale |

**The combination is the differentiator, not any row.** Each row
individually has a partial incumbent analogue somewhere (OPA's
replayable logs, HumanLayer's deterministic gate placement,
Inngest's scored experiments, Claude Code's saved allow rules,
Temporal's durable history). No surveyed product holds more than
two of the six properties at once, and the properties compose in
Jacquard because they share one substrate: the same log that
makes decisions auditable (V3) is what rules are scored against
(V4), what bundles are folded from (V5), and what spends replay
from (V6); the same computed effects that gate definitions (V1)
are what batch approval presents to the human (V2). That
composition — not a feature checklist — is the void-shaped thing.

## 4. Where Jacquard is NOT differentiated (honest list)

- **Pre-execution gating as such is crowded and Jacquard is not
  first or best-resourced there.** Claude Code's permission/hook
  system is a shipped, polished, per-action gate in the hands of
  every user today; OpenAI's SDK and LangGraph ship real
  interruption machinery. Jacquard's claim is narrower: gating on
  *computed* effects with a verifiable record. Anyone who only
  needs "ask me before it runs" is already served.
- **Observability: Jacquard is not a competitor at all.**
  LangSmith/Langfuse offer tracing, evals, annotation, dashboards
  and hosted polish; Jacquard has a log, a CLI, and no UI. It
  would sit *under* such tools, not replace them.
- **Durable execution at scale: Temporal wins outright** —
  distribution, versioning, operational maturity, ecosystems.
  Jacquard's sequencer is deliberately single-writer and its
  implementation is a Python reference; it is a decision kernel,
  not a workflow platform (the design's own non-goals say so).
- **Policy-language maturity: OPA/Rego is far more general and
  battle-tested** as a language, with an ecosystem (Styra,
  integrations everywhere). Jacquard's policy + dictionary is
  narrower by design; teams whose need is "evaluate this JSON
  against rules" should use OPA.
- **Identity and access governance: Microsoft owns the
  enterprise surface** (Entra Agent ID, Conditional Access,
  Purview). Jacquard authenticates producers at the sequencer but
  has no enterprise identity story, no SCIM/RBAC product surface,
  no compliance certifications.
- **Content safety: not Jacquard's category at all** (NeMo,
  Foundry guardrails, Guardrails AI validators). Nothing in
  Jacquard checks content harm categories.
- **Maturity, support, distribution:** every incumbent wins.
  Jacquard v0.2.0 is a spec, a reference implementation, and a
  conformance suite built in days, with exactly one shadow trial
  of external evidence. Its README's own status section says what
  is not built: no network service, no packaging beyond the repo,
  interval contention (F1) and conditional starts/authority
  priority (F2) not yet expressible — the Phase 4 probes on those
  are in flight as of this writing.
- **Human-approval *channels*:** HumanLayer's Slack/email
  delivery and Trigger.dev's approve/deny buttons meet users
  where they are; Jacquard's queue is a CLI on one machine.

## 5. Beachheads, ranked

### 1. The supervision layer for coding-agent fleets run by small teams and solo operators

- **Who exactly:** a technical lead (or solo builder) running
  several coding agents — Claude Code / Codex-class — across a
  few machines, where agents push code, run deploys, spend API
  budget, and contend for shared resources (the fleet Casey
  himself runs is the archetype; the shape generalises to any
  small team that has given agents real credentials).
- **Pain:** supervision today is a synchronous prompt (Claude
  Code) — the human is the bottleneck and either babysits or
  flips to "don't ask again," minting permanent allow rules with
  no review, no scoring, and no record of why. Observability
  (LangSmith-class) reports afterwards. Nothing batches the
  decisions, binds them to what was reviewed, or compounds forty
  identical approvals into a governed rule.
- **Why incumbents fail them:** V2 + V4 + V3 simultaneously —
  blocking approvals, no governed learning, no verifiable record.
  This is the one audience for whom all three failures bite daily.
- **Proof that would demonstrate fit:** Jacquard interposed as
  the approval/decision layer over one real fleet for a fixed
  window (the natural harness: a `PreToolUse`-hook-shaped adapter
  emitting proposals). Metrics: operator minutes per 100 agent
  actions vs the interactive baseline; % of actions decided by
  learned rules with **zero regretted approvals** on replay
  audit; queue drain in one or two batched passes per day.
- **What Jacquard still lacks for it:** any live adapter to a
  real coding agent (none exists — the executor runs sandboxed
  commands, but no hook integration has been built); a network
  service (the queue is local CLI); notification channels; the
  F1/F2 expressiveness gaps matter here (resource contention and
  "start when the build lands" are daily shapes in this world;
  Phase 4 probes are deciding the minimal fix).

### 2. "Why was this allowed" evidence for small regulated operators piloting agents

- **Who exactly:** small operators in audited environments —
  a finance-ops team letting an agent prepare/post transactions,
  a clinic's admin agents touching records, a legal practice's
  document agents — too small for enterprise governance suites,
  but with an external auditor or regulator who will ask for
  decision evidence.
- **Pain:** their current stack produces vendor-stored logs an
  auditor must take on trust (or, per NeMo's FAQ, logs that don't
  even guarantee a policy version). When an agent does something
  wrong, "the platform's dashboard shows a trace" is not
  evidence; and nothing lets the auditor re-derive the decision
  independently.
- **Why incumbents fail them:** V3, with V1 behind it (the
  auditor also wants to know the action's effects were checked,
  not just its text). Microsoft's bundle answers with tenant logs
  and enterprise gravity — priced and shaped for enterprises,
  and still not independently verifiable.
- **Proof that would demonstrate fit:** an audit drill — export
  the log from a live pilot; hand an independent party the spec,
  the golden vectors, and the export; they re-derive 100% of a
  sampled decision set byte-identically with the second
  implementation (the conformance suite already demonstrates the
  mechanism on a real 3,295-entry record; the drill makes it a
  decision-level audit on pilot data). Metric: sampled decisions
  re-derived exactly, policy version bound per decision, zero
  decisions whose record depends on the operator's database.
- **What Jacquard still lacks for it:** external anchoring of the
  chain head (without it, tamper-evidence is relative to whoever
  holds the head hash); key management/signing of entries;
  PII/data-handling story (the log records everything — a
  liability as much as an asset without redaction policy);
  any compliance mapping (SOC 2 / HIPAA language); multi-operator
  roles. This beachhead is real but further away than #1 —
  ranked second because the missing pieces are product, not
  mechanism.

### 3. One shared expensive resource, many agents: home/lab and small-team compute governance

- **Who exactly:** labs, studios, and serious home setups where
  several agents/producers share one scarce resource — a GPU
  workstation, a render box, a test bench — and a human who wants
  silence unless something matters (the Confluence shape in the
  design record).
- **Pain:** ungoverned sharing double-books exclusive resources
  and starves quiet work; unjudged automation churns (Casey's
  feeder: 13,080 outputs, downstream use 0.0 — a reading Jacquard
  computed from records in its Phase 1 acceptance). Incumbent
  workflow engines run the jobs but don't govern competing
  producers, price attention, or demote churn rules.
- **Why incumbents fail them:** V6 + V4 — no fair contention with
  accounting, no governed rule demotion. This audience is small
  in count but exact in fit, and it is where Jacquard's only real
  datasets already live.
- **Proof that would demonstrate fit:** run Jacquard *live* (not
  shadow) over the booking board + GPU queue for a fixed window.
  Metrics: zero double-bookings of exclusive seats (the incumbent
  process produced 3 in 52 decidable items); starvation bound
  held for the quietest flow; a churn reading generated from
  records alone leading to a rule demotion.
- **What Jacquard still lacks for it:** F1 is this beachhead's
  core check — interval contention is currently inexpressible in
  the kernel and lived in the shadow trial's harness; the
  beachhead is gated on the Phase 4 outcome. Also: no network
  service (multi-machine means several kernels or a service that
  doesn't exist yet), one executor on one host.

**Ranking logic:** beachhead 1 needs the least new machinery
(adapters + a service surface) against the sharpest daily pain
and has a measurable baseline (interactive prompting) to beat;
beachhead 2 has the clearest willingness-to-pay shape but the
longest product tail; beachhead 3 is the most proven fit and the
smallest market — it is the demonstration garden for 1 and 2
more than a destination.

## 6. Process record (how this scan was made)

- 2026-11-02: four parallel research passes (frameworks /
  durable execution / policy+guardrails / observability+
  governance), each restricted to official docs and repos, each
  answering the same five questions with SHIPPED / MARKETING /
  NOT-FOUND labels and URLs; their product-level findings are
  folded into §1 with citations inline. Cross-pass agreement was
  notable: all four passes independently returned "no
  tamper-evident decision record" and "no governed learned rules"
  for their entire clusters.
- Jacquard claims were re-verified against the repo the same day
  rather than taken from the design record: README status
  section, spec section list (§§1–14 + §10.5 executor), module
  inventory, and a suite re-run (128 passed). Where the design
  record itself names a gap (GAP-3 raw-proposal effect honesty,
  GAP-4 learner bounds, GAP-5 single sequencer, F1/F2), the gap
  is carried into §3/§5 rather than smoothed over.
- Two vendor-framing disagreements worth Casey's attention beyond
  §1's list: (a) HumanLayer — the canonical "approval as a
  service" reference — has pivoted away from that product; the
  approval SDK is legacy. The void in V2 is therefore *widening*,
  not closing. (b) Microsoft's "agent governance" is the loudest
  marketing in the space and, per its own docs, is identity +
  content + DLP; the decision-governance layer (V2/V3/V4) is
  simply not what it sells.
- Unverified / open: rate-limit and quota specifics for the
  durable-execution cluster (V6 rests on absence in the docs
  read, not an exhaustive quota audit); the unsurveyed categories
  listed in the preamble could contain partial coverage of V1–V5
  (standalone authorisation services in particular were out of
  scope — a follow-up pass on Permit.io/Cerbos/OpenFGA and the
  agent-security startups is the obvious next scan if Casey wants
  the void claims hardened).

---

## 7. ADDENDUM — hardening pass (2026-11-02): authorisation services + agent-security products

*Appended 2026-11-02, the same day as the main scan, at Casey's
direction ("Great, go"). This section does not rewrite §§1–6. Where
a claim above must change, a dated correction note below names the
section it amends. Method identical to the main scan: PRIMARY
documentation only (official docs sites, official product pages,
the AARM conformance registry where a vendor's claims are
reproduced verbatim), read 2026-11-02; SHIPPED = mechanism
described concretely in product documentation; MARKETING = claim
on a product/blog page with no mechanism documentation;
NOT-FOUND = searched for in the docs read and absent (a finding
about the documented product). Nine more products: standalone
authorisation — Permit.io, Cerbos, OpenFGA, Oso, AuthZed/SpiceDB;
agent security/governance — Noma Security, WitnessAI, Zenity, and
Lasso Security (see its verification note). Surveyed total is now
25 products. Two honesty notes up front: Noma and WitnessAI have
no public product-documentation site that could be found — their
findings rest on vendor product/blog pages and are labelled
accordingly (weaker evidence than a docs site); and a PyPI project
named "LASSO" (a sandbox orchestrator) is NOT Lasso Security the
company and is treated separately, once, in §7.3.*

### 7.1 Standalone authorisation services

The cluster's shared shape, stated once: all five are policy
decision points over **declared** artefacts — a subject, an
action, a resource, and caller-supplied attributes/tuples/facts.
None has any semantics of what an action will *do*; enforcement
is the caller's job. That is the OPA shape (§1.3) with better
product surfaces, and it decides most of the five answers before
the per-product detail.

**Permit.io** (PDP = OPA or Cedar under a managed control plane;
OPAL syncs policy/data; decision logs with human-readable reasons,
exportable to SIEM —
https://docs.permit.io/overview/how-does-it-work/,
https://docs.permit.io/concepts/differentiator-checklist).
- Q1 gating: SHIPPED as declared-artefact checks (`permit.check()`
  over identity/action/resource/attributes). For agents, the MCP
  Gateway checks every MCP tool call against policy/trust level
  before it runs (https://docs.permit.io/permit-mcp-gateway/guide/).
  Computed effects of a composed action: NOT-FOUND — the gateway
  evaluates the declared tool + arguments, and its "Agent
  Interrogation" compares an agent's *declared* intent/tools
  against observed calls (drift detection), which is
  declaration-vs-behaviour, not effect computation
  (https://docs.permit.io/permit-mcp-gateway/advanced-features/).
- Q2 approval: **SHIPPED, and it changes V2 — see the correction
  in §7.4.** Two mechanisms. (a) MCP Gateway HITL (Enterprise):
  a gated tool call is paused and an approval request created;
  admins work an **Approvals queue** (Pending/History tabs,
  per-card tool/server/identity/exact arguments), with **batch
  approve/reject** via checkboxes, email/Slack/browser
  notifications, and a trusted-agent bypass. Bounds, from the
  same docs: the MCP client *waits*; default timeout 5 minutes;
  timeout = reject
  (https://docs.permit.io/permit-mcp-gateway/human-in-the-loop/).
  (b) Access Request MCP + Elements: non-blocking stored requests
  — an agent creates an access request or operation approval, a
  reviewer decides later in an embedded element or via API; on
  approval Permit *assigns a role* (`_Approved_`) on the resource
  instance, and one-timeness is the calling tool's responsibility
  ("your tool unassigns the `_Approved_` role after the action
  succeeds") (https://docs.permit.io/ai-security/access-request-mcp/overview/).
  Hash-bound approval (approval fails if the item changed):
  NOT-FOUND in either mechanism — approval binds to a displayed
  card or to a role grant, not to a hash of the exact item.
- Q3 record: decision logs record user/action/resource/tenant,
  decision, deciding policy and a human-readable reason, and can
  be forwarded to your SIEM (docs above). Hash chain, signing of
  decision records, independent re-derivation procedure:
  NOT-FOUND. "Permission Receipts" (who approved a grant, agent,
  server, tools, trust level, expiry) are exportable — an
  exported *record*, still vendor-asserted
  (https://docs.permit.io/permit-mcp-gateway/advanced-features/).
- Q4 learned rules: NOT-FOUND. Approval *history* is a list;
  nothing documents mining it into candidate rules, shadow
  scoring, staged activation, or demotion. Policies are authored
  (UI/API/Terraform) and synced by OPAL.
- Q5 portability: policy-as-code is genuinely portable as
  *configuration* (Terraform provider, Git-backed OPAL, engine
  choice of OPA/Cedar). Governance *standing* — trust levels,
  consent windows, receipts — lives inside Permit; rules arriving
  unproven and re-earning activation, or authority refused at
  import: NOT-FOUND.

**Cerbos** (open-source PDP, YAML policies with CEL conditions,
GitOps; Cerbos Hub = control plane: compilation, testing, signed
versioned bundle distribution, central audit collection; Synapse
= context-enriching proxy —
https://docs.cerbos.dev/cerbos-hub/decision-points,
https://docs.cerbos.dev/cerbos-hub/audit-log-collection).
- Q1 gating: SHIPPED as declared-artefact checks
  (`CheckResources`: principal/action/resource + supplied
  attributes), down to tool-call arguments for agents — including
  a **shipped Claude Code adapter**: Synapse's built-in hook
  handler converts Claude Code PreToolUse events into Cerbos
  checks against central policy, outside the agent's control
  (https://www.cerbos.dev/blog/governing-ai-coding-agents-with-cerbos-synapse).
  Computed effects: NOT-FOUND. Cerbos's own framing is explicit
  that it does not judge intent — "It decides what the agent is
  allowed to do at the moment it acts"
  (https://www.cerbos.dev/blog/cerbos-vs-plainid). `PlanResources`
  computes a *data-filter plan* from policy — a query artefact,
  not an action's effects.
- Q2 approval: NOT-FOUND. No human-approval mechanism (blocking,
  batched, or otherwise) is documented; Cerbos returns allow/deny
  (and obligations) only.
- Q3 record: **the strongest decision-log content in either pass,
  alongside OPA.** Every PDP emits access + decision entries with
  the full evaluation inputs, outputs and matched policy; Hub
  collects them centrally, searchable/exportable, and the vendor
  pairs them with the Git history of policy changes and Hub's
  record of which signed bundle build was live — "show me the
  policy that was in effect at the time" is a search, not a
  reconstruction (https://www.cerbos.dev/blog/cerbos-vs-plainid,
  https://docs.cerbos.dev/synapse/latest/quickstart). Bounds:
  signing covers policy *bundles*, not decision records; no hash
  chain or independent re-derivation procedure is documented —
  the log is complete but vendor/operator-held, exactly the
  trust position of OPA's logs in §1.3. (Cerbos marketing calls
  the trails "tamper-resistant" —
  https://www.cerbos.dev/blog/ai-coding-agent-deleted-a-production-database-in-9-seconds
  — MARKETING; no mechanism is documented.)
- Q4 learned rules: NOT-FOUND as approval-history compilation.
  Two adjacent partials, each missing the same stages as the
  §1 partials: Hub tests policies and *blocks deployment of
  failing bundles* (an offline-evaluation stage for hand-authored
  policy), and the vendor's own rollout advice is "Start in
  observe mode. Then write policy against what you actually see"
  (observe → enforce for hand-written rules; no scoring of
  candidate rules against recorded outcomes, no shadow stage for
  a *rule*, no demotion).
- Q5 portability: policies are YAML in Git — portable
  configuration, runnable anywhere Cerbos runs. Standing/trust
  reset semantics: NOT-FOUND.

**OpenFGA** (Okta/Auth0-origin, CNCF; Zanzibar ReBAC: an
authorization *model* + relationship *tuples*; Check/ListObjects/
ListUsers queries — https://openfga.dev/docs/concepts,
CNCF self-assessment at
https://tag-security.cncf.io/community/assessments/projects/openfga/self-assessment/).
- Q1 gating: SHIPPED only in the narrowest sense — a Check
  answers whether a tuple-relationship holds for a declared
  (user, relation, object). It is a relationship store with a
  query engine, not an action gate: no policy over action
  arguments or context beyond CEL conditions on tuples, and no
  effects semantics. NOT-FOUND for anything beyond that.
- Q2 approval: NOT-FOUND (no approval concept exists in the
  model).
- Q3 record: the datastore keeps a **changelog of tuple changes**
  (`ReadChanges`, used for cache invalidation) — a change feed
  for grants/revocations, not a decision record: Check calls
  themselves leave no documented decision log with inputs/policy
  version/outcome. Hash chain/signing: NOT-FOUND.
- Q4 learned rules: NOT-FOUND.
- Q5 portability: models are immutable, versioned artefacts
  (ULID-identified) and stores can be exported/imported via the
  CLI (`fga store import`) — configuration portability again.
  Earned standing has no representation at all, so trust-reset
  portability is NOT-FOUND by construction.

**Oso** (Polar policy language; Oso Cloud hosted engine + the
open-source library; status note: Oso Cloud was acquired by Tiny,
announced 2026-10-06, per Permit's migration guide — "Oso Cloud
keeps running" — https://www.permit.io/blog/migrate-from-oso-to-permit;
docs at https://www.osohq.com/docs/quickstart).
- Q1 gating: SHIPPED as declared-artefact checks (Polar rules over
  actor/action/resource + facts; field-level and list-filtering
  variants). No agent-specific gate and no effects semantics:
  NOT-FOUND beyond the general engine.
- Q2 approval: NOT-FOUND.
- Q3 record: Oso Cloud Logs record every authorization request
  with its inputs and result, and **Explain** re-runs a logged
  query showing the facts and rules that decided it — genuine
  "why" tooling, but Explain replays against *current* policy and
  facts (the debugging docs use it to find model bugs), so it is
  re-derivation against today's state, not verification of the
  decision as made; no signing/hash chain documented
  (https://www.osohq.com/docs/develop/troubleshooting/debugging).
- Q4 learned rules: NOT-FOUND. Nearest partial: "Oso Migrate"
  runs a new engine in shadow parallel to a legacy one during
  migrations (https://www.osohq.com/post/launching-oso-migrate) —
  shadow execution as migration tooling, not as a stage in a
  rule's governed lifecycle.
- Q5 portability: Polar policies are files in version control;
  the library embeds anywhere. Standing/trust reset: NOT-FOUND.

**AuthZed / SpiceDB** (Zanzibar permissions database; schema +
relationships + Caveats; ZedToken consistency —
https://authzed.com/docs/spicedb/concepts/consistency,
https://authzed.com/docs/spicedb/modeling/access-control-audit).
- Q1 gating: SHIPPED in the OpenFGA sense — relationship checks
  over declared (subject, relation, object), plus an "Agentic AI
  Authorization Model" (functionality control, inherited user
  permissions, "autonomy oversight") whose approval element is a
  model pattern, not a shipped approval product
  (https://authzed.com/blog/authzed-announces-support-for-ai-by-providing-permissions-aware-ai).
  Effects semantics: NOT-FOUND.
- Q2 approval: NOT-FOUND as a mechanism (see above — a modelling
  suggestion in a blog post is MARKETING, not a queue).
- Q3 record: SpiceDB deliberately does **not** keep the record:
  the Watch API streams relationship changes but "the application
  developer is responsible for persisting the audit history,"
  with 24 hours of change history held by default; SpiceDB
  "does not offer an API to determine what API calls it has
  received" (docs above). AuthZed's hosted tiers add audit logs
  as a platform feature (https://authzed.com/spicedb) — vendor-
  held, format/mechanism NOT-FOUND in the docs read. No signing
  or hash chain documented.
- Q4 learned rules: NOT-FOUND. (Materialize — incremental
  permission views, early access — is a query accelerator, not
  rule learning.)
- Q5 portability: schema is a portable artefact; deployments span
  self-hosted/Cloud/Dedicated. Standing/trust reset: NOT-FOUND.

### 7.2 Agent-security / agent-governance products

The cluster's shared shape: discovery + posture + **runtime
detection/enforcement over observed traffic and behaviour**
(prompt injection, data leakage, intent drift, tool misuse).
Enforcement is real and pre-execution in the leaders — but what
is evaluated is *signals about* the action (content, intent
scores, identity, session history), never a computation of the
action's effects from its parts; and the governance record is a
platform log, not a verifiable decision record. None of the four
publishes a documentation site with mechanism-level detail
comparable to §7.1's products; findings below lean on vendor
product pages and are labelled accordingly.

**Noma Security** (AI-SPM + Agent Access Control + AI-DR runtime
detection/response + red teaming; sources: vendor pages and
announcements — https://noma.security/blog/operationalizing-iso-iec-42001-how-to-generate-continuous-technical-evidence-for-ai-governance-and-compliance,
https://www.prnewswire.com/news-releases/noma-extends-agent-security-and-governance-to-the-employee-endpoint-302890925.html;
AARM conformance listing reproducing vendor claims at
https://github.com/hermanerr/docs/blob/HEAD/builders/noma.mdx).
*No public product-documentation site was found; mechanism-level
detail is UNVERIFIED beyond the claims below.*
- Q1 gating: SHIPPED as a category, per vendor: AI-DR evaluates
  agent actions before execution (proxy/hooks/gateway) with
  verdicts allow / block / mask / steer / escalate, using
  identity, permissions, policy and behaviour context — including
  session-scoped *accumulated intent*, the nearest conceptual
  neighbour to composition-awareness in either pass. It is
  detection over signals, not effect computation: nothing
  documents deriving a composite action's effects or refusing on
  under-declaration. The AARM listing's ALLOW/BLOCK/DEFER/
  REDACT/ESCALATE vocabulary is a conformance claim (third-party
  registry, vendor-supplied description), labelled MARKETING for
  mechanism purposes.
- Q2 approval: a human-approval response exists in the runtime
  repertoire (AI-DR can "require human approval"; registry/agent
  approval statuses — approved / needs review / blocked — govern
  *assets*, from the PR above). An approval *queue* — batched,
  non-blocking, hash-bound: NOT-FOUND in everything read; the
  documented pattern is a synchronous runtime response.
- Q3 record: Noma's own blog promises a "timestamped, unalterable
  record" from AI-DR and the AARM listing claims "Immutable,
  tamper-evident records of all authorization decisions… written
  to an immutable audit log before the action result is
  returned." These are the strongest immutability *claims* in
  either pass — and no mechanism (hash chain, signing scheme,
  WORM store, export format, verification procedure) is
  documented anywhere readable. Claim: MARKETING. Verifiable
  without trusting Noma: NOT-FOUND.
- Q4 learned rules: partial, MARKETING-grade: "posture context
  informs what gets tested, test results become runtime defenses,
  and runtime intelligence reshapes posture priorities" (AARM
  listing); red-team findings feeding runtime policies is the
  vendor's stated loop. No stage of the V4 pipeline is documented
  as a mechanism — no candidate rules mined from approvals, no
  shadow scoring, no staged activation, no demotion. NOT-FOUND
  as a governed pipeline.
- Q5 portability: NOT-FOUND (platform-internal across SaaS /
  homegrown / endpoint estates is coverage, not governance-state
  export with trust reset).

**WitnessAI** (network-level Observe / Control / Protect;
sources: vendor site and blogs only — no public docs site found:
https://witness.ai/blog/mcp-server-security/,
https://witness.ai/blog/claude-ai-security-risks/,
https://witness.ai/for-developers/).
- Q1 gating: Agentic Control (launched 2026-06-17, per vendor)
  does "pre-execution blocking of unauthorized tool calls"
  against an allow-list of approved agents/tools/MCP servers,
  under intent-based policy (allow / warn / block / route).
  Enforcement over declared identity + classified intent:
  SHIPPED-as-claimed on product pages, mechanism documentation
  NOT-FOUND. Effects computation: NOT-FOUND.
- Q2 approval: NOT-FOUND (warn is a synchronous enforcement
  action, not an approval flow; no queue documented).
- Q3 record: "granular audit trails" everywhere; one blog lists
  "Tamper-resistant, attributable logs" among enterprise
  controls, and a third-party comparison credits "immutable
  audit trails" mapped to EU AI Act / ISO 42001 / NIST AI RMF /
  PCI DSS 4.0.1 (https://www.kosmoy.com/resources/blog/noma-security-vs-witnessai/
  — a competitor's comparison page, weakest evidence class).
  Mechanism, format, signing, verification: NOT-FOUND. The audit
  trail is a compliance-reporting feature of the platform.
- Q4 learned rules: NOT-FOUND (intent models are the vendor's
  ML, not customer governance rules with a lifecycle).
- Q5 portability: NOT-FOUND.

**Zenity** (agent inventory/posture + "Boundaries" runtime
enforcement + observability; sources: vendor product pages —
https://zenity.io/platform/runtime-boundaries,
https://zenity.io/academy/agentic-ai-security).
- Q1 gating: SHIPPED-as-claimed: Boundaries "evaluates every
  agent action in real time against rules… decides to let it
  through, block it, or shut the agent down," with session
  semantics (who's acting, who for, what already happened).
  Rules are hand-authored from a prebuilt library or via an AI
  policy assistant (plain language → rule, human reviews before
  activation — AI-assisted *authoring*, not learning from
  approvals). One phrase deserves naming: the academy page
  describes a "**decision budget**: a cap on the aggregate effect
  of a delegation chain, so it never exceeds what a human
  authorized at the outset" — the closest any surveyed vendor
  comes to V1/V6 vocabulary. It appears on an academy explainer
  with no mechanism documentation behind it: MARKETING.
  Effects computed from composition: NOT-FOUND.
- Q2 approval: NOT-FOUND (steer/block/kill are automated
  responses; no human approval queue documented).
- Q3 record: observability and audit are product surfaces, but
  no format, signing, hash chain, or verification procedure is
  documented on the pages read: NOT-FOUND for tamper-evidence.
- Q4 learned rules: one MARKETING sentence — Protect catches
  what slips through "and turn[s] it into a sharper policy."
  No pipeline stages documented: NOT-FOUND.
- Q5 portability: NOT-FOUND (one rule "enforced everywhere" the
  agent runs *within Zenity's coverage* is propagation inside
  the product).

**Lasso Security** — **UNVERIFIED as a product in this pass.**
Its public surface is marketing pages (intent-layer detection,
MCP traffic inspection, "persistent audit logs of every
autonomous decision" — https://www.lasso.security/use-cases/ai-agents-security,
https://www.lasso.security/blog/securing-mcp-workflows) with no
readable mechanism documentation found for any of the five
questions. It is recorded here so the gap is visible, and no
void conclusion below rests on it. (Disambiguation: "LASSO — the
Layered Agent Sandbox Security Orchestrator" on PyPI is a
separate open-source sandbox tool, not this company; see §7.3.)

### 7.3 One out-of-cluster data point for V3

The PyPI project **LASSO (lasso-sandbox)** — sandboxed execution
for coding agents — documents "a tamper-evident, **HMAC-signed
audit log**" of sandbox actions in its package documentation
(https://pypi.org/project/lasso-sandbox/0.5.1/). It is a small
open-source sandbox tool, not a decision-governance product: the
signed log records sandbox/command actions, with no documented
policy-version binding, decision inputs, or third-party
re-derivation procedure. It shows signing an action log is
buildable and shipped *somewhere* — at the sandbox layer, for a
different artefact than a policy decision. V3's claim is about
decision records; this does not close it, and it is recorded so
the "nobody signs anything" version of the claim is never made.

### 7.4 Void-by-void verdicts after hardening

**V1 (verified-effects gating) — STANDS, reinforced.**
The authorisation cluster is the declaration shape in its purest
form: Permit literally evaluates with OPA/Cedar over supplied
attributes; OpenFGA/SpiceDB answer relationship questions;
Cerbos checks declared tool-call arguments and says plainly it
does not judge more than the request in front of it. The agent-
security cluster evaluates *signals* (content, intent, behaviour,
session accumulation) — Noma's accumulated-intent context and
Zenity's "decision budget" phrase are the nearest neighbours,
and neither computes a composite action's effects from its parts
nor refuses mechanically on under-declaration. No correction to
§2 V1 is required; this pass adds five PDPs and four security
platforms to its evidence base.

**V2 (batched, non-blocking approval) — SHRINKS; one correction
required; does not close.**
*Correction (2026-11-02) to §2 V2 and to §1.3's "Batched queue:
NOT-FOUND" (written of HumanLayer/OPA):* Permit.io's MCP Gateway
HITL is a shipped, documented **approval queue with batch
actions** — pending cards with exact arguments, checkbox batch
approve/reject, history, notifications (Enterprise plan;
https://docs.permit.io/permit-mcp-gateway/human-in-the-loop/).
"Every shipped approval mechanism is a bare synchronous prompt"
is no longer a safe sentence. What keeps the void open, from the
same documentation: (1) the item still **blocks** — the MCP
client waits on the paused call, the default timeout is 5
minutes, and timeout rejects; batching serves the *reviewer's*
pass, while Jacquard's queue lets the item wait indefinitely
with all other work — including the same producer's — continuing
and no timeout death; (2) **hash-bound approval remains
NOT-FOUND in all 25 products** — Permit's approval binds to the
displayed card, and its non-blocking variant (Access Request
MCP) binds approval to a *role grant on a resource instance*,
with one-timeness delegated to the calling tool, so the approved
artefact is still not the exact item reviewed. V2 as restated —
*batched review of distinct queued items that neither blocks the
producer nor expires, with approval bound to the item's hash* —
stands; V2 as originally evidenced ("no queue exists") is
narrowed to the reviewer-side queue now existing in exactly one
surveyed product, behind an Enterprise plan, for MCP tool calls.

**V3 (verifiable "why" record) — STANDS, with a wording
correction.**
*Correction (2026-11-02) to §2 V3's implication:* immutability is
now **claimed** in this cluster — Noma ("immutable, tamper-
evident records"), WitnessAI ("tamper-resistant" logs), Cerbos
("tamper-resistant audit trails"). The original sentence survives
only in its precise form: **zero of 25 products documents a
mechanism** — a hash chain, a signature scheme over decision
records, or a procedure by which a third party re-derives a
decision from an exported artefact without trusting the vendor.
Cerbos is the pass's strongest incumbent (decision entries with
full inputs + matched policy, signed policy *bundles*, Git
history of policy changes, Hub's bundle-version record) and it
lands exactly where OPA landed in §1.3: complete, replayable-in-
principle, vendor-held. Oso's Explain is the same shape one step
weaker (re-derivation against current, not as-decided, state).
The §7.3 sandbox signs its action log with HMAC and still is not
a decision record. The void — verification *without trusting the
vendor* — is untouched; anyone quoting this scan should say
"mechanism not documented," never "nobody claims immutability."

**V4 (approval history → governed standing rules) — STANDS.**
This pass adds partials, and every partial misses the same
stages as §1's four: Cerbos Hub's test-gated bundle deployment
(offline evaluation, hand-authored policy) and observe-mode
rollout advice; Oso Migrate's shadow parallel run (migration
tooling); Noma's red-team-findings→runtime-policies loop and
Zenity's "sharper policy" sentence (both MARKETING-grade, no
stages documented); Permit keeps an approval *history* and
compiles none of it. **Approval history mining into candidate
rules: NOT-FOUND in all 25 products.** The composition — mine →
evaluate offline → shadow → staged activation → scoring →
auto-demotion → one-action revocation — remains unsold by
anyone surveyed.

**V5 (governance state travels with trust reset) — STANDS.**
The authorisation cluster strengthens the *configuration* half
of the evidence (Cerbos YAML-in-Git, Permit Terraform/OPAL,
OpenFGA versioned model files + store import, SpiceDB schema) —
which §2 already granted: code and config move. The void's
other half is untouched and, in OpenFGA/SpiceDB, unrepresentable:
earned standing has no artefact to export; Permit's trust levels
and consent live and die inside Permit; **no product in either
pass documents rules arriving unproven in a new environment and
re-earning activation there, or authority/credentials being
refused at the border by construction.** NOT-FOUND across 25.

**V6 (fair contention between untrusted producers) — STANDS,
evidence class unchanged.** Nothing in the nine documents fair,
priced, starvation-proof allocation across competing producers
tied to the gate. Nearest phrases: Zenity's "decision budget"
(a cap on one delegation chain's aggregate effect — a ceiling,
not an allocation between rivals) and Permit's trust levels
(gating priority, not fair queueing). Rate-limit/quota specifics
across all 25 products remain not exhaustively audited; the
partially-unverified flag from §2 stays on.

### 7.5 Effect on the beachhead ranking (§5)

**Ranking unchanged: 1, 2, 3 — but two margins narrow, and
beachhead 1's framing gets sharper.**

- **Beachhead 1 (coding-agent fleet supervision) stays #1, with
  a new competitive fact:** the adapter slot is now demonstrably
  occupied. Cerbos Synapse ships a Claude Code hook adapter with
  central, versioned, agent-proof policy and a decision log; the
  fleet's own §5 proof plan assumed "a PreToolUse-hook-shaped
  adapter" would be novel plumbing — it is now a shipped
  incumbent pattern, and Permit owns the equivalent slot for MCP
  clients, approval queue included. Consequence: a Jacquard
  adapter that merely gates tool calls would be a me-too against
  Cerbos on day one. Jacquard's differentiation in this beachhead
  is exactly the composition the incumbents still lack —
  non-blocking hash-bound queue (V2 as restated), rules that
  compound from approvals (V4), a record a third party can
  re-derive (V3) — so the beachhead-1 build should be judged on
  those, and time-to-integrate is now a competitive variable,
  not a detail. Permit's 5-minute timeout also validates the
  pain from the other side: the incumbent queue *discards*
  undecided work on a timer, which is approval fatigue with a
  deadline — the failure mode beachhead 1 exists to remove.
- **Beachhead 2 ("why was this allowed" evidence) stays #2,
  margin narrowed:** Cerbos Hub is the strongest incumbent answer
  to this beachhead's question found in either pass (inputs +
  matched policy + signed bundle version + Git history, centrally
  searchable, marketed to regulated buyers). Jacquard's audit
  drill still wins on the one axis Cerbos doesn't contest —
  independent re-derivation without trusting the operator's
  store — but "the incumbent produces a dashboard trace" is no
  longer the right characterisation of the best incumbent; it's
  "a complete vendor-held evidence log." The beachhead's missing
  product pieces (anchoring, key management, PII story,
  compliance mapping) are unchanged, and Cerbos's presence raises
  the value of the anchoring piece specifically: it's the
  difference between Cerbos's record and Jacquard's.
- **Beachhead 3 (shared-resource governance) unchanged:** none
  of the nine touches fair contention (V6 stands), and nothing
  in this pass competes for the booking-board/GPU shape. It
  remains the demonstration garden, gated on Phase 4 as before.

**Net hardening result:** of the six voids, none closes; V2
shrinks on its reviewer side (one shipped batch queue) and is
restated more precisely; V3 keeps its substance and loses an
over-broad phrasing; V1, V4, V5, V6 stand with wider evidence.
The scan's central composition claim — no surveyed product holds
more than two of the six properties — survives the wider net:
the strongest newcomers hold at most two (Permit: partial V2 +
decision logs short of V3; Cerbos: record content short of V3 +
test-gated deployment short of V4), and the properties still do
not compose anywhere outside Jacquard, because no incumbent's
approval queue, rule lifecycle, and decision record share one
substrate.
