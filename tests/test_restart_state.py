from types import SimpleNamespace

import pytest

import control_panel


def _capture_states(monkeypatch):
    states = []
    monkeypatch.setattr(
        control_panel,
        "_write_restart_state",
        lambda path, request_id, state, success, reason, errors=None: states.append(
            {"state": state, "success": success, "reason": reason, "errors": list(errors or [])}
        ),
    )
    monkeypatch.setattr(
        control_panel,
        "load_orchestration_settings",
        lambda _path: {"restart_all_task": "HWG-All", "restart_gateway_task": "HWG-Gateway"},
    )
    return states


def test_restart_all_records_schedule_failure(monkeypatch):
    states = _capture_states(monkeypatch)
    monkeypatch.setattr(
        control_panel.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="task missing"),
    )
    result = control_panel._schedule_restart_all("test-save")

    assert result["scheduled"] is False
    assert states[0]["state"] == "scheduled"
    assert states[-1]["state"] == "schedule_failed"
    assert states[-1]["success"] is False
    assert "task missing" in states[-1]["errors"]


def test_gateway_restart_records_missing_schtasks(monkeypatch):
    states = _capture_states(monkeypatch)

    def missing(*args, **kwargs):
        raise FileNotFoundError("schtasks")

    monkeypatch.setattr(control_panel.subprocess, "run", missing)

    with pytest.raises(RuntimeError, match="not available"):
        control_panel._schedule_gateway_restart("test-service-restart")

    assert states[0]["state"] == "scheduled"
    assert states[-1]["state"] == "schedule_failed"
    assert states[-1]["errors"] == ["schtasks_not_found"]
