from core.reliability import ReliabilityPolicy, evaluate_probe, evaluate_window, evaluate_program


def _record(checked='2026-09-22T06:30:00Z', provider='deepseek-web', account='deepseek-web:default-account', model='deepseek-web', duration=12000):
    return {'provider_id':provider,'account_id':account,'model':model,'state':'READY','ready':True,'checked_at':checked,'duration_ms':duration,
            'stages':[{'stage':'functional_probe','ok':True,'evidence':{'expected':'X','observed':'X','feature_application':{'mismatches':{}},'commitment':{'commitment_state':'terminal','retry_allowed':False}}}]}


def test_three_probes_make_one_window_not_e3():
    records=[_record(),_record('2026-09-22T06:31:00Z'),_record('2026-09-22T06:32:00Z')]
    w=evaluate_window(records,window_id='W1',started_at='2026-09-22T06:29:00Z')
    assert w['passed'] is True
    assert w['evidence_level']=='REPEATED_E2_WINDOW'
    program=evaluate_program([w])
    assert program['passed'] is False
    assert program['evidence_level']=='E2'
    assert 'insufficient_windows' in program['reasons']


def test_three_windows_30_minutes_apart_are_required_for_e3():
    windows=[]
    for wid,start in [('W1','2026-09-22T06:00:00Z'),('W2','2026-09-22T06:30:00Z'),('W3','2026-09-22T07:00:00Z')]:
        windows.append(evaluate_window([_record(start),_record(start),_record(start)],window_id=wid,started_at=start))
    result=evaluate_program(windows)
    assert result['passed'] is True
    assert result['evidence_level']=='E3'


def test_short_window_separation_blocks_e3():
    starts=['2026-09-22T06:00:00Z','2026-09-22T06:10:00Z','2026-09-22T06:40:00Z']
    windows=[evaluate_window([_record(s),_record(s),_record(s)],window_id=f'W{i+1}',started_at=s) for i,s in enumerate(starts)]
    result=evaluate_program(windows)
    assert result['passed'] is False
    assert 'window_separation_too_short' in result['reasons']


def test_probe_requires_terminal_commitment_exact_token_and_duration():
    r=_record(duration=61000); result=evaluate_probe(r,ReliabilityPolicy()); assert 'duration_exceeded' in result['reasons']
    r=_record(); r['stages'][0]['evidence']['observed']='WRONG'; assert 'exact_token_mismatch' in evaluate_probe(r)['reasons']
    r=_record(); r['stages'][0]['evidence']['commitment']['commitment_state']='committed'; assert 'commitment_not_terminal' in evaluate_probe(r)['reasons']
