import json
from pathlib import Path

from control_panel import _model_usage_window


def test_model_usage_reports_measured_success_failure_latency_and_activity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_dir = Path('logs')
    log_dir.mkdir()
    events = [
        {'event': 'request_complete', 'timestamp': 1000, 'endpoint': '/v1/chat/completions', 'provider': 'deepseek-web', 'model': 'deepseek-web', 'status_code': 200, 'latency_ms': 120, 'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30},
        {'event': 'request_complete', 'timestamp': 1010, 'endpoint': '/v1/chat/completions', 'provider': 'deepseek-web', 'model': 'deepseek-web', 'status_code': 503, 'latency_ms': 280, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
    ]
    (log_dir / 'audit.log').write_text('\n'.join(json.dumps(e) for e in events) + '\n', encoding='utf-8')

    result = _model_usage_window(now=1020, seconds=60)
    row = result['models'][0]
    assert row['requests'] == 2
    assert row['success_count'] == 1
    assert row['failure_count'] == 1
    assert row['avg_latency_ms'] == 200
    assert row['last_activity'] == 1010
    assert row['total_tokens'] == 30
