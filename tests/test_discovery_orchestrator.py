from pathlib import Path

import pytest

from core.discovery_orchestrator import (
    DiscoveryState,
    attach_baseline,
    attach_exploration,
    attach_research,
    begin_exploration,
    new_run,
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
