"""Typesafe Jev adapter for the decision-model provider seam
(SPEC section 13).

This file lives OUTSIDE the kernel package on purpose: the
kernel imports no provider-specific code. The adapter implements
jacquard.providers.DecisionModelProvider by shelling out to the
fleet's Jev CLI (bin/jev.py of the Typesafe connector); the CLI
path is a deployment detail, given by the JACQUARD_JEV_CLI
environment variable or the constructor.

Choices may carry criteria: "label — criteria text". The label
is what readings report; the criteria text is what the model
judges against. Two choices use Jev's probability judgement;
more use its choice judgement. Any failure (CLI missing, API
error, unparsable output) makes the provider decline (return
None) and records the reason on last_error: an advisor that is
down must never break, block, or alter a decision path.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard.providers import DecisionModelProvider  # noqa: E402

_DEFAULT_CLI = os.path.expanduser(
    "~/workspace/custom-connectors/custom.legacy-typesafe/bin/jev.py")
_CREDENTIALS_BIN = "/opt/muse/skills/custom-connector-setup/bin"


def _split(choice):
    label, _, criteria = choice.partition(" — ")
    return label.strip(), (criteria.strip() or label.strip())


class TypesafeJevProvider(DecisionModelProvider):
    name = "typesafe-jev"

    def __init__(self, cli=None, timeout=60):
        self.cli = cli or os.environ.get("JACQUARD_JEV_CLI", _DEFAULT_CLI)
        self.timeout = timeout
        self.last_error = None

    def _run(self, args):
        env = dict(os.environ)
        if os.path.isdir(_CREDENTIALS_BIN):
            env["PYTHONPATH"] = _CREDENTIALS_BIN + os.pathsep + \
                env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, self.cli] + args,
            capture_output=True, text=True, timeout=self.timeout, env=env)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "jev CLI failed")
        return json.loads(proc.stdout)

    def judge(self, text, question, choices):
        try:
            pairs = [_split(choice) for choice in choices]
            if len(pairs) == 2:
                (label_a, crit_a), (label_b, crit_b) = pairs
                out = self._run(["noul", text, question,
                                 "--true", crit_a, "--false", crit_b])
                probability = float(out["noul"])
                return {"choice": label_a if probability >= 0.5 else label_b,
                        "probability_bp": int(round(10000 * probability)),
                        "detail": "jev noul on %r" % question}
            options = ["%s=%s" % (label, crit) for label, crit in pairs]
            out = self._run(["choice", text, question] + options)
            first = pairs[0][0]
            probabilities = out.get("probabilities", {})
            return {"choice": out.get("choice"),
                    "probability_bp": int(round(
                        10000 * float(probabilities.get(first, 0.0)))),
                    "detail": "jev choice among %s" % [p[0] for p in pairs]}
        except Exception as exc:  # advisor failure = decline, never raise
            self.last_error = str(exc)
            return None
