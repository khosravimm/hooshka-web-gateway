import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MATRIX=ROOT/'docs/governance/HWG_EXPLORER_CAPABILITY_TEST_MATRIX_V1.json'


def test_explorer_capability_matrix_is_complete_and_grounded():
    doc=json.loads(MATRIX.read_text(encoding='utf-8'))
    allowed=set(doc['status_vocabulary'])
    rows=doc['capabilities']
    ids={x['id'] for x in rows}
    required={'user_view_state','visual_capture','interaction_map','behavior_click_guard','upload_surface','selector_rediscovery','roundtrip_qualification','adapter_synthesis','readiness_reconcile','ai_routing','ai_hypotheses','ai_queue_partition','ai_verification','ai_visual_semantics','ai_exact_ocr','evidence_provenance'}
    assert required.issubset(ids)
    assert len(ids)==len(rows)
    for item in rows:
        assert item['status'] in allowed
        assert item.get('implementation') and item.get('tests')
        for rel in item['implementation']+item['tests']:
            assert (ROOT/rel).exists(), f"missing reference: {rel}"
        if item['status']=='E2_LIVE':
            assert item.get('live_evidence'), item['id']
        for rel in item.get('live_evidence',[]):
            assert (ROOT/rel).exists(), f"missing evidence: {rel}"
        if item['status']=='LIMITATION':
            assert item.get('limitation')


def test_explorer_matrix_preserves_ai_safety_policy():
    doc=json.loads(MATRIX.read_text(encoding='utf-8'))
    assert doc['policy']['deterministic_first'] is True
    assert doc['policy']['ai_output_default']=='E0/CANDIDATE'
    assert doc['policy']['click_requires_explicit_approval'] is True
