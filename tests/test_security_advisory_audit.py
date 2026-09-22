from scripts import security_advisory_audit as mod


class _Resp:
    def raise_for_status(self):
        return None
    def json(self):
        return {'results':[{} for _ in mod.resolved_closure()]}


def test_osv_audit_maps_exact_lock(monkeypatch):
    seen={}
    def fake_post(url, json, timeout):
        seen['url']=url
        seen['payload']=json
        return _Resp()
    monkeypatch.setattr(mod.requests,'post',fake_post)
    result=mod.audit(timeout=3)
    assert result['source']=='OSV'
    assert result['packages_checked']==len(mod.resolved_closure())
    assert result['direct_packages']==len(mod.locked_rows())
    assert result['scope']=='resolved_dependency_closure'
    assert result['findings']==[]
    assert all(q['package']['ecosystem']=='PyPI' and q.get('version') for q in seen['payload']['queries'])
