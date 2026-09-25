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


def test_stats_count_only_provider_bound_model_requests(tmp_path, monkeypatch):
    from control_panel import _build_request_history_window
    monkeypatch.chdir(tmp_path)
    log_dir = Path('logs')
    log_dir.mkdir()
    events = [
        {'event': 'request_complete', 'timestamp': 1000, 'endpoint': '/panel/api/stats', 'provider': 'unknown', 'status_code': 200},
        {'event': 'request_complete', 'timestamp': 1001, 'endpoint': '/health', 'provider': 'unknown', 'status_code': 200},
        {'event': 'request_complete', 'timestamp': 1002, 'endpoint': '/v1/chat/completions', 'provider': 'deepseek-web', 'status_code': 200},
        {'event': 'request_complete', 'timestamp': 1003, 'endpoint': '/v1/responses', 'provider': 'qwen-web', 'status_code': 503},
    ]
    (log_dir / 'audit.log').write_text('\n'.join(json.dumps(e) for e in events) + '\n', encoding='utf-8')
    result = _build_request_history_window(now=1020, minutes=60)
    assert result['requests_1h'] == 2
    assert result['breakdown'] == {'success': 1, 'failure': 1}
    assert sum(point['count'] for point in result['requests_history']) == 2


def test_stats_counts_direct_provider_send_and_deduplicates_matching_api_request(tmp_path, monkeypatch):
    from control_panel import _build_request_history_window
    monkeypatch.chdir(tmp_path)
    log_dir = Path('logs')
    log_dir.mkdir()
    events = [
        {'event': 'provider_send', 'timestamp': 1000, 'request_id': 'req-1', 'provider': 'grok-web', 'model': 'grok-web'},
        {'event': 'provider_result', 'timestamp': 1001, 'request_id': 'req-1', 'provider': 'grok-web', 'model': 'grok-web', 'outcome': 'success'},
        {'event': 'request_complete', 'timestamp': 1002, 'request_id': 'req-1', 'endpoint': '/v1/chat/completions', 'provider': 'grok-web', 'status_code': 200},
        {'event': 'provider_send', 'timestamp': 1003, 'request_id': 'unknown', 'provider': 'grok-web', 'model': 'grok-web'},
    ]
    (log_dir / 'audit.log').write_text('\n'.join(json.dumps(e) for e in events) + '\n', encoding='utf-8')
    result = _build_request_history_window(now=1020, minutes=60)
    assert result['requests_1h'] == 2
    assert result['breakdown'] == {'success': 1, 'failure': 0}
    assert sum(point['count'] for point in result['requests_history']) == 2


def test_audit_logger_preserves_token_metrics_but_redacts_secrets(tmp_path):
    from core.governance import AuditLogger
    audit_path = tmp_path / "audit.log"
    logger = AuditLogger(str(audit_path))
    logger.log({
        "event": "request_complete",
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
        "access_token": "secret-value",
        "authorization": "Bearer secret",
    })
    row = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert row["prompt_tokens"] == 11
    assert row["completion_tokens"] == 7
    assert row["total_tokens"] == 18
    assert row["access_token"] == "[REDACTED]"
    assert row["authorization"] == "[REDACTED]"


def test_audit_logger_records_provider_send_without_flask_request_context(tmp_path):
    from core.governance import AuditLogger
    audit_path = tmp_path / 'audit.log'
    logger = AuditLogger(str(audit_path))
    logger.log({'event': 'provider_send', 'provider': 'grok-web'})
    row = json.loads(audit_path.read_text(encoding='utf-8').strip())
    assert row['event'] == 'provider_send'
    assert row['provider'] == 'grok-web'
    assert row['request_id'] == 'unknown'


def test_model_usage_excludes_requests_without_selected_provider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_dir = Path('logs')
    log_dir.mkdir()
    events = [
        {'event': 'request_complete', 'timestamp': 1000, 'endpoint': '/v1/chat/completions', 'provider': 'unknown', 'model': 'no-such-model-xyz', 'status_code': 404, 'latency_ms': 0},
        {'event': 'request_complete', 'timestamp': 1001, 'endpoint': '/v1/responses', 'provider': 'default', 'model': 'chatgpt-web', 'status_code': 404, 'latency_ms': 0},
        {'event': 'request_complete', 'timestamp': 1002, 'endpoint': '/v1/chat/completions', 'provider': 'deepseek-web', 'model': 'deepseek-web', 'status_code': 200, 'latency_ms': 10},
    ]
    (log_dir / 'audit.log').write_text('\n'.join(json.dumps(e) for e in events) + '\n', encoding='utf-8')
    result = _model_usage_window(now=1020, seconds=60)
    assert [(row['provider'], row['model'], row['requests']) for row in result['models']] == [('deepseek-web', 'deepseek-web', 1)]
