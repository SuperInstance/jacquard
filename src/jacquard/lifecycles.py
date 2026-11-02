"""The seven lifecycle machines (SPEC section 10).

These are profile definitions, written in the machine profile's
text format and submitted to a kernel like any other machine
definition (producer: operator). A kernel that has them installed
runs its proposal, action, approval and standing lifecycles
through the machines, so the log shows transitions, not just
outcomes. Where a lifecycle has no guard, the transitions are
plain: the machine records the path; policy decides it.
"""
from .envelope import make_envelope

PROPOSAL = """\
machine proposal
initial: received
terminal: closed, refused
events: submit, hold, decide, commit, close, refuse
received -> validated : submit
received -> refused : refuse
validated -> tentative : hold
validated -> decided : decide
validated -> refused : refuse
tentative -> decided : decide
tentative -> refused : refuse
decided -> committed : commit
committed -> closed : close
ignore submit in *
ignore hold in *
ignore decide in *
ignore commit in *
ignore close in *
ignore refuse in *
"""

ACTION = """\
machine action
initial: proposed
terminal: confirmed, compensated, rejected
events: approve, dispatch, confirm, fail, compensate, reject
proposed -> approved : approve
proposed -> rejected : reject
approved -> dispatched : dispatch
dispatched -> confirmed : confirm
dispatched -> failed : fail
failed -> compensated : compensate
ignore approve in *
ignore dispatch in *
ignore confirm in *
ignore fail in *
ignore compensate in *
ignore reject in *
"""

STANDING_RULE = """\
machine standing-rule
initial: candidate
terminal: revoked
events: evaluate, deploy, promote, activate, regress, quarantine, resubmit, revoke
candidate -> evaluated : evaluate
evaluated -> shadow : deploy
shadow -> canary : promote
canary -> active : activate
canary -> demoted : regress
active -> demoted : regress
active -> quarantined : quarantine
shadow -> quarantined : quarantine
demoted -> shadow : resubmit
quarantined -> shadow : resubmit
candidate -> revoked : revoke
evaluated -> revoked : revoke
shadow -> revoked : revoke
canary -> revoked : revoke
active -> revoked : revoke
demoted -> revoked : revoke
quarantined -> revoked : revoke
ignore evaluate in *
ignore deploy in *
ignore promote in *
ignore activate in *
ignore regress in *
ignore quarantine in *
ignore resubmit in *
ignore revoke in *
"""

PRODUCER_STANDING = """\
machine producer-standing
initial: normal
terminal: none
events: degrade, limit, suspend, reinstate, resume
normal -> degraded : degrade
normal -> quota_limited : limit
normal -> suspended : suspend
degraded -> quota_limited : limit
degraded -> suspended : suspend
degraded -> normal : resume
quota_limited -> suspended : suspend
quota_limited -> normal : resume
suspended -> reinstated : reinstate
reinstated -> normal : resume
ignore degrade in *
ignore limit in *
ignore suspend in *
ignore reinstate in *
ignore resume in *
"""

COMMIT_BATCH = """\
machine commit-batch
initial: open
terminal: folded, aborted
events: seal, fold, abort
open -> sealed : seal
open -> aborted : abort
sealed -> folded : fold
sealed -> aborted : abort
ignore seal in *
ignore fold in *
ignore abort in *
"""

APPROVAL = """\
machine approval
initial: pending
terminal: approved, denied, expired
events: present, approve, deny, expire
pending -> presented : present
pending -> expired : expire
presented -> approved : approve
presented -> denied : deny
presented -> expired : expire
ignore present in *
ignore approve in *
ignore deny in *
ignore expire in *
"""

WORKER = """\
machine worker
initial: starting
terminal: stopped
events: start, fail, restart, degrade, recover, stop
starting -> running : start
starting -> stopped : stop
running -> restarting : fail
running -> degraded : degrade
running -> stopped : stop
restarting -> running : start
restarting -> degraded : degrade
restarting -> stopped : stop
degraded -> running : recover
degraded -> stopped : stop
ignore start in *
ignore fail in *
ignore restart in *
ignore degrade in *
ignore recover in *
ignore stop in *
"""

LIFECYCLES = {
    "proposal": PROPOSAL,
    "action": ACTION,
    "standing-rule": STANDING_RULE,
    "producer-standing": PRODUCER_STANDING,
    "commit-batch": COMMIT_BATCH,
    "approval": APPROVAL,
    "worker": WORKER,
}


def install_lifecycles(sequencer, producer="operator"):
    """Submit the seven lifecycle machine definitions to a kernel.
    Side-effect free for kernels that never install them: lifecycle
    stepping in the sequencer applies only to machines present in
    the kernel's registry."""
    verdicts = {}
    for name, text in LIFECYCLES.items():
        verdicts[name] = sequencer.submit(make_envelope(
            producer, "machine", {"text": text}, [], "machine-" + name))
    return verdicts
