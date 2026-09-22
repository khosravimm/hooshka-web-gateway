from core.commitment import Commitment, CommitmentTracker, annotate_error_details, commitment_metadata


def test_commitment_metadata_controls_retry():
    assert commitment_metadata(Commitment.NOT_SENT) == {
        'commitment_state': 'not_sent',
        'retry_allowed': True,
    }
    assert commitment_metadata(Commitment.MAYBE_SENT)['retry_allowed'] is False
    assert commitment_metadata('committed') == {
        'commitment_state': 'committed',
        'retry_allowed': False,
    }


def test_annotate_error_details_preserves_existing_and_adds_failure_class():
    details = annotate_error_details({'provider': 'qwen-web'}, Commitment.MAYBE_SENT, failure_class='stalled_or_timeout')
    assert details['provider'] == 'qwen-web'
    assert details['commitment_state'] == 'maybe_sent'
    assert details['retry_allowed'] is False
    assert details['failure_class'] == 'stalled_or_timeout'


def test_tracker_forbids_retry_after_maybe_sent():
    t = CommitmentTracker('cid-work012')
    assert t.may_retry()
    t.advance(Commitment.MAYBE_SENT)
    assert not t.may_retry()


def test_all_web_adapters_expose_commitment_metadata_contract():
    files = {
        'adapters/chatgpt_web_provider.py': ['commitment_state', 'retry_allowed'],
        'adapters/deepseek_browser_transport.py': ['last_commitment_state', 'annotate_error_details'],
        'adapters/deepseek_web_provider.py': ['commitment_state', 'retry_allowed'],
        'adapters/qwen_browser_transport.py': ['last_commitment_state', 'ambiguous_submission_failure'],
        'adapters/qwen_web_provider.py': ['commitment_state', 'retry_allowed'],
        'adapters/zai_browser_transport.py': ['last_commitment_state', 'annotate_error_details'],
        'adapters/zai_web_provider.py': ['commitment_state', 'retry_allowed'],
    }
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel, needles in files.items():
        text = (root / rel).read_text(encoding='utf-8-sig')
        for needle in needles:
            assert needle in text, f'{needle} missing from {rel}'
