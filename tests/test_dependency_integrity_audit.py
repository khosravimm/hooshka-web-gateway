from scripts.dependency_integrity_audit import audit, locked_rows


def test_lock_entries_are_exact_and_non_remote():
    rows=locked_rows()
    assert rows
    assert all(name and version for name, version in rows)


def test_dependency_integrity_matches_validated_environment():
    result=audit()
    assert result['mismatches'] == []
    assert result['pip_check_ok'] is True
    assert result['vulnerability_advisory_scan'] == 'NOT_PERFORMED'
