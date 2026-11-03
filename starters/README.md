# Starter kits

One kit per proven use. Each kit is a guided first
deployment built from a real one — the deployments it
names are the evidence it works, and the commands are the
ones the deployments actually ran. Every kit ends with you
governing your own real task, and with a log whose counts
you can read back.

- [Job-queue governance](job-queue-governance.md) — a
  shared expensive queue: jobs reach it only if the kernel
  allowed them; holds wait for a batched decision; a
  sentinel stands last so finite jobs can run. (The Thor's
  gpu-queue, slices 22/25/30 and the slice-31 stranger
  run.)
- [Coding-agent supervision](coding-agent-supervision.md)
  — a coding agent's tool calls under kernel decision, with
  a batched operator queue. (The ZCode adapter, slices
  12/30/31.)
- [Anchored audit record](anchored-audit-record.md) — a
  record whose history a third party can verify without
  trusting you. (Slices 18/21: the public anchors repo.)
- [Batched approvals for a solo operator](batched-approvals-solo.md)
  — your own scripts and automations proposing, you
  deciding in batches, the log on your machine as the
  record. (The drill, generalised.)
