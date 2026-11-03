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
  gpu-queue, in production; deployment record in
  `docs/slice30-device-matrix.md`.)
- [Coding-agent supervision](coding-agent-supervision.md)
  — a coding agent's tool calls under kernel decision, with
  a batched operator queue. (The ZCode adapter, in
  production on workstation and front-room devices.)
- [Anchored audit record](anchored-audit-record.md) — a
  record whose history a third party can verify without
  trusting you. (The public
  `SuperInstance/jacquard-anchors` witness repo.)
- [Batched approvals for a solo operator](batched-approvals-solo.md)
  — your own scripts and automations proposing, you
  deciding in batches, the log on your machine as the
  record. (The drill, generalised.)
