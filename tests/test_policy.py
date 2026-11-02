from jacquard.policy import POLICY_VERSION, decide


def test_version_pinned():
    assert POLICY_VERSION == "policy/1"


def test_plain_reads_allowed():
    assert decide("a", "proposal", {"reads"}, {}, None) == ("allow", [])


def test_protected_effects_queue_for_non_operator():
    for verb in ("send", "notify", "spend", "irreversible"):
        outcome, reasons = decide("a", "proposal", {verb}, {}, None)
        assert outcome == "queue"
        assert reasons == ["protected-effect:%s" % verb]


def test_operator_not_queued():
    outcome, _ = decide("operator", "proposal", {"send"}, {}, None)
    assert outcome == "allow"


def test_suspended_denied_even_for_reads():
    outcome, reasons = decide("a", "proposal", set(), {},
                              {"status": "suspended"})
    assert outcome == "deny"
    assert reasons == ["producer-suspended"]
