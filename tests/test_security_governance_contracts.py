import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_security_rollback_contract_delegates_operational_proof():
    text=(ROOT/'docs/governance/HWG_SECURITY_ROLLBACK_CONTRACT_V1.md').read_text(encoding='utf-8-sig')
    assert 'HWG-WORK-010' in text
    assert 'HWG-WORK-014' in text
    assert 'must not replace, copied, merged, or deleted' not in text  # guard accidental wording drift
    assert 'must not be replaced, copied, merged, or deleted' in text
    assert 'Actual rollback execution and proof remain exclusively owned by `HWG-WORK-014`' in text


def test_security_matrix_records_vulnerability_scan_after_real_evidence():
    text=(ROOT/'docs/governance/HWG_SECURITY_RELEASE_GATE_MATRIX_V1.md').read_text(encoding='utf-8-sig')
    assert '| Known-vulnerability advisory scan | PASS |' in text
    assert '| Dependency integrity/reproducibility | PASS |' in text
    assert '| File/multimodal enablement gate | PASS |' in text
    assert '| Challenge/account-risk handling | PASS |' in text


def test_work010_has_no_operational_rollback_dependency_cycle():
    doc=json.loads((ROOT/'docs/governance/HWG_REMAINING_WORK_REGISTER.json').read_text(encoding='utf-8-sig'))
    work010=next(x for x in doc['items'] if x['id']=='HWG-WORK-010')
    work014=next(x for x in doc['items'] if x['id']=='HWG-WORK-014')
    assert 'HWG-WORK-014' not in (work010.get('depends_on') or [])
    assert 'HWG-WORK-010' in (work014.get('depends_on') or [])
    assert any('delegated to HWG-WORK-014' in x for x in work010['exit_criteria'])

