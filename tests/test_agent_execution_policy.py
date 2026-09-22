import json
import time

from core.agent_execution import AgentLoopPolicy, execute_tool_call, remaining_loop_seconds


class FakeRegistry:
    def __init__(self, value=None, delay=0):
        self.value=value if value is not None else {'ok': True}
        self.delay=delay
    def execute(self, name, args):
        if self.delay:
            time.sleep(self.delay)
        return self.value


def call(name='system_info', args=None, call_id='c1'):
    return {'id':call_id,'function':{'name':name,'arguments':json.dumps(args or {})}}


def test_policy_is_bounded_from_config():
    p=AgentLoopPolicy.from_config({'max_steps':999,'per_tool_timeout_seconds':999,'max_result_chars':999999,'duplicate_call_limit':99,'max_loop_seconds':9999})
    assert p.max_steps == 20
    assert p.per_tool_timeout_seconds == 60
    assert p.max_result_chars == 200000
    assert p.duplicate_call_limit == 5
    assert p.max_loop_seconds == 600


def test_duplicate_call_is_blocked_and_evidenced():
    p=AgentLoopPolicy(duplicate_call_limit=1)
    seen={}
    _msg1, ev1, dup1=execute_tool_call(FakeRegistry(),call(),p,seen,1)
    msg2, ev2, dup2=execute_tool_call(FakeRegistry(),call(call_id='c2'),p,seen,2)
    assert dup1 is False and ev1['execution_state']=='ok'
    assert dup2 is True and ev2['execution_state']=='duplicate_blocked'
    assert 'Duplicate tool call blocked' in msg2['content']


def test_result_is_bounded_for_provider_delivery():
    p=AgentLoopPolicy(max_result_chars=1000)
    msg, ev, _dup=execute_tool_call(FakeRegistry({'data':'x'*5000}),call(),p,{},1)
    body=json.loads(msg['content'])
    assert body['truncated'] is True
    assert ev['truncated'] is True


def test_tool_timeout_is_recorded():
    p=AgentLoopPolicy(per_tool_timeout_seconds=0.05)
    msg, ev, _dup=execute_tool_call(FakeRegistry(delay=0.2),call(),p,{},1)
    assert ev['execution_state']=='timeout'
    assert 'timeout' in msg['content'].lower()


def test_loop_budget_reaches_zero():
    p=AgentLoopPolicy(max_loop_seconds=0.01)
    started=time.monotonic(); time.sleep(0.02)
    assert remaining_loop_seconds(started,p) == 0.0
