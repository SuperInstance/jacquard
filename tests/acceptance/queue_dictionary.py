"""The gpu-queue successor rule as dictionary definitions.

These definitions encode, as data, the dispatch policy of the
real gpu-queue daemon (daemon.py on the Thor, copied with the
dataset under tests/data/gpu-queue/):

- jobs dispatch strictly in queue order, one at a time;
- the head job dispatches only when another job is queued behind
  it, or the feeder is enabled (the feeder guarantees a
  successor); otherwise the job holds, and the hold is recorded;
- foreign work on the GPU pre-empts a dispatch (the tick is
  recorded as a hold);
- a job whose start fails twice halts dispatching: the
  bump-failures / should-halt? / apply-halt words carry that
  rule, and once gpu/halted is set, maybe-dispatch emits nothing.

There is no imperative policy code: the harness evaluates
maybe-dispatch and executes exactly the requests it returns.
Words assume the harness maintains the gpu/feeder unit and the
gpu-foreign sense; every word is checked against its examples
by the kernel at define time.

State layout:
- unit "gpu/queue": list of queued job ids, head first
- unit "gpu/feeder": {"enabled": bool}
- unit "gpu/halted": true once dispatching has halted
- unit "gpu/holds": list of job ids a hold was recorded for
- unit "gpu/start-failures": count of consecutive start failures
- sense "gpu-foreign": true while foreign work holds the GPU
"""

DEFINITIONS = [
    {"name": "feeder-on?",
     "signature": {"ins": [], "outs": ["bool"]},
     "body": [{"lit": "gpu/feeder"}, "get", {"lit": "enabled"}, "getf",
              {"lit": True}, "eq"],
     "examples": [
         {"args": [], "state": {"units": {"gpu/feeder": {"enabled": True}}},
          "expect": [True]},
         {"args": [], "state": {"units": {"gpu/feeder": {"enabled": False}}},
          "expect": [False]}]},

    {"name": "successor-exists?",
     "signature": {"ins": [], "outs": ["bool"]},
     "body": [{"lit": "gpu/queue"}, "get", "count", {"lit": 1}, "gt"],
     "examples": [
         {"args": [], "state": {"units": {"gpu/queue": ["a", "b"]}},
          "expect": [True]},
         {"args": [], "state": {"units": {"gpu/queue": ["a"]}},
          "expect": [False]}]},

    {"name": "foreign-work?",
     "signature": {"ins": [], "outs": ["bool"]},
     "body": [{"lit": "gpu-foreign"}, "sense", {"lit": True}, "eq"],
     "examples": [
         {"args": [], "state": {"senses": {"gpu-foreign": True}},
          "expect": [True]},
         {"args": [], "state": {}, "expect": [False]}]},

    {"name": "halted?",
     "signature": {"ins": [], "outs": ["bool"]},
     "body": [{"lit": "gpu/halted"}, "get", {"lit": True}, "eq"],
     "examples": [
         {"args": [], "state": {"units": {"gpu/halted": True}},
          "expect": [True]},
         {"args": [], "state": {}, "expect": [False]}]},

    {"name": "dispatchable?",
     "signature": {"ins": [], "outs": ["bool"]},
     "body": ["successor-exists?", "feeder-on?", "or",
              "foreign-work?", "not", "and"],
     "examples": [
         {"args": [],
          "state": {"units": {"gpu/queue": ["a", "b"],
                              "gpu/feeder": {"enabled": False}},
                    "senses": {"gpu-foreign": False}},
          "expect": [True]},
         {"args": [],
          "state": {"units": {"gpu/queue": ["a"],
                              "gpu/feeder": {"enabled": True}},
                    "senses": {"gpu-foreign": False}},
          "expect": [True]},
         {"args": [],
          "state": {"units": {"gpu/queue": ["a", "b"],
                              "gpu/feeder": {"enabled": False}},
                    "senses": {"gpu-foreign": True}},
          "expect": [False]},
         {"args": [],
          "state": {"units": {"gpu/queue": ["a"],
                              "gpu/feeder": {"enabled": False}},
                    "senses": {"gpu-foreign": False}},
          "expect": [False]}]},

    {"name": "dispatch-one",
     "signature": {"ins": ["val"], "outs": []},
     "body": [{"lit": {}}, "swap", {"lit": "job"}, "swap", "assoc",
              "dispatch"],
     "examples": [
         {"args": ["job-1"], "requests": ["dispatch"]}]},

    {"name": "do-dispatch",
     "signature": {"ins": [], "outs": []},
     "body": [{"lit": "gpu/queue"}, "get", "first", "dispatch-one"],
     "examples": [
         {"args": [], "state": {"units": {"gpu/queue": ["job-1", "job-2"]}},
          "requests": ["dispatch"]}]},

    {"name": "record-hold",
     "signature": {"ins": [], "outs": []},
     "body": [{"lit": "gpu/holds"}, {"lit": "gpu/holds"}, "get",
              {"lit": "gpu/queue"}, "get", "first", "snoc", "write"],
     "examples": [
         {"args": [],
          "state": {"units": {"gpu/holds": [], "gpu/queue": ["job-2"]}},
          "requests": ["write"]}]},

    {"name": "maybe-dispatch",
     "signature": {"ins": [], "outs": []},
     "body": ["halted?",
              {"if": [],
               "else": ["dispatchable?",
                        {"if": ["do-dispatch"],
                         "else": ["record-hold"]}]}],
     "examples": [
         {"args": [],
          "state": {"units": {"gpu/queue": ["job-1", "job-2"],
                              "gpu/feeder": {"enabled": False},
                              "gpu/holds": []},
                    "senses": {"gpu-foreign": False}},
          "requests": ["dispatch"]},
         {"args": [],
          "state": {"units": {"gpu/queue": ["job-2"],
                              "gpu/feeder": {"enabled": False},
                              "gpu/holds": []},
                    "senses": {"gpu-foreign": False}},
          "requests": ["write"]},
         {"args": [],
          "state": {"units": {"gpu/queue": ["job-1", "job-2"],
                              "gpu/feeder": {"enabled": False},
                              "gpu/holds": []},
                    "senses": {"gpu-foreign": True}},
          "requests": ["write"]},
         {"args": [],
          "state": {"units": {"gpu/queue": ["job-1", "job-2"],
                              "gpu/feeder": {"enabled": False},
                              "gpu/holds": [],
                              "gpu/halted": True},
                    "senses": {"gpu-foreign": False}},
          "requests": []}]},

    {"name": "bump-failures",
     "signature": {"ins": [], "outs": []},
     "body": [{"lit": "gpu/start-failures"},
              {"lit": "gpu/start-failures"}, "get", {"lit": 1}, "add",
              "write"],
     "examples": [
         {"args": [], "state": {"units": {"gpu/start-failures": 1}},
          "requests": ["write"]}]},

    {"name": "should-halt?",
     "signature": {"ins": [], "outs": ["bool"]},
     "body": [{"lit": "gpu/start-failures"}, "get", {"lit": 2}, "lt",
              "not"],
     "examples": [
         {"args": [], "state": {"units": {"gpu/start-failures": 2}},
          "expect": [True]},
         {"args": [], "state": {"units": {"gpu/start-failures": 1}},
          "expect": [False]}]},

    {"name": "apply-halt",
     "signature": {"ins": [], "outs": []},
     "body": ["should-halt?",
              {"if": [{"lit": "gpu/halted"}, {"lit": True}, "write"],
               "else": []}],
     "examples": [
         {"args": [], "state": {"units": {"gpu/start-failures": 2}},
          "requests": ["write"]},
         {"args": [], "state": {"units": {"gpu/start-failures": 1}},
          "requests": []}]},
]


def submit_all(seq, producer="operator"):
    """Submit every definition; return the list of verdicts."""
    from jacquard import make_envelope
    verdicts = []
    for i, defn in enumerate(DEFINITIONS):
        verdicts.append(seq.submit(make_envelope(
            producer, "definition", defn, [], "queue-dict-%d" % i)))
    return verdicts
