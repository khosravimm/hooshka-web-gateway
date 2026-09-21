from pathlib import Path

import pytest

from core.discovery_orchestrator import (
    DiscoveryState,
    attach_baseline,
    attach_exploration,
    attach_research,
    begin_certification,
    begin_exploration,
    complete_certification,
    list_runs,
    load_run,
    new_run,
    review_candidate,
    synthesize,
)


def test_research_first_gate_cannot_be_skipped():
    run = new_run("deepseek-web", "1.0.0")
    with pytest.raises(ValueError):
        attach_baseline(run, {"runtime": {}, "session": {}, "page": {}, "account": {}})
    assert run.state == DiscoveryState.RESEARCH_REQUIRED.value


def test_discovery_pipeline_creates_review_candidate_on_drift(tmp_path: Path):
    run = new_run("deepseek-web", "1.0.0", "deepseek-web:default-account")
    attach_research(run, [{"kind": "internal_evidence", "ref": "baseline"}])
    attach_baseline(run, {"runtime": {}, "session": {}, "page": {}, "account": {}})
    begin_exploration(run)
    attach_exploration(run, {"frontend": {}, "backend": {}}, [{"type": "control_missing", "selector": "#old"}])
    synthesize(run)
    assert run.state == DiscoveryState.UPDATE_CANDIDATE.value
    assert run.candidate["status"] == "PENDING_REVIEW"
    path = run.save(tmp_path)
    assert path.exists()


def test_no_drift_still_requires_interactive_certification():
    run = new_run("qwen-web", "1.0.0")
    attach_research(run, [{"kind": "official", "ref": "provider-docs"}])
    attach_baseline(run, {"runtime": {}, "session": {}, "page": {}, "account": {}})
    begin_exploration(run)
    attach_exploration(run, {"frontend": {}, "backend": {}}, [])
    synthesize(run)
    assert run.state == DiscoveryState.CERTIFICATION_REQUIRED.value
    assert run.evidence_level == "E1"


def test_saved_runs_are_listed_and_reloadable(tmp_path: Path):
    run = new_run("chatgpt-web", "webchat-standard-v1", "chatgpt-web:default-account")
    run.save(tmp_path)
    rows = list_runs(tmp_path)
    assert len(rows) == 1
    assert rows[0]["run_id"] == run.run_id
    loaded = load_run("chatgpt-web", run.run_id, tmp_path)
    assert loaded.provider_id == "chatgpt-web"
    assert loaded.state == DiscoveryState.RESEARCH_REQUIRED.value


def test_candidate_review_accepts_only_explicit_decisions():
    run = new_run("deepseek-web", "webchat-standard-v1")
    attach_research(run, [{"kind": "official", "ref": "docs"}])
    attach_baseline(run, {"runtime": {}, "session": {}, "page": {}, "account": {}})
    begin_exploration(run)
    attach_exploration(run, {"frontend": {}, "backend": {}}, [{"type": "control_missing"}])
    synthesize(run)
    review_candidate(run, "ACCEPT", "reviewed")
    assert run.state == DiscoveryState.CERTIFICATION_REQUIRED.value
    assert run.candidate["status"] == "ACCEPT"


def test_e2_pass_requires_explicit_user_confirmation():
    run = new_run("chatgpt-web", "webchat-standard-v1")
    attach_research(run, [{"kind": "official", "ref": "docs"}])
    attach_baseline(run, {"runtime": {}, "session": {}, "page": {}, "account": {}})
    begin_exploration(run)
    attach_exploration(run, {"frontend": {}, "backend": {}}, [])
    synthesize(run)
    begin_certification(run)
    with pytest.raises(ValueError):
        complete_certification(run, True, "evidence/record", False)
    complete_certification(run, True, "evidence/record", True)
    assert run.state == DiscoveryState.CERTIFIED.value
    assert run.evidence_level == "E2"


def test_baseline_gates_login_and_requires_rebaseline():
    from core.discovery_orchestrator import request_rebaseline
    run = new_run("chatgpt-web", "webchat-standard-v1")
    attach_research(run, [{"kind":"official","ref":"docs"}])
    attach_baseline(run, {"runtime":{},"session":{"access_state":"LOGIN_REQUIRED"},"page":{},"account":{}})
    assert run.state == DiscoveryState.WAITING_FOR_LOGIN.value
    with pytest.raises(ValueError):
        begin_exploration(run)
    request_rebaseline(run)
    assert run.state == DiscoveryState.BASELINE_REQUIRED.value


def test_baseline_routes_interaction_blocked_and_unknown_states():
    cases = {
        "USER_INTERACTION_REQUIRED": DiscoveryState.WAITING_FOR_USER_INTERACTION,
        "BLOCKED": DiscoveryState.BLOCKED,
        "UNKNOWN": DiscoveryState.DIAGNOSTIC_REQUIRED,
    }
    for access, expected in cases.items():
        run = new_run("probe-web", "webchat-standard-v1")
        attach_research(run, [{"kind":"official","ref":"docs"}])
        attach_baseline(run, {"runtime":{},"session":{"access_state":access},"page":{},"account":{}})
        assert run.state == expected.value
