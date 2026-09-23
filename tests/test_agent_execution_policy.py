import json
import time

from core.agent_execution import (
    AgentLoopPolicy,
    ToolAuthorizationContext,
    execute_tool_call,
    remaining_loop_seconds,
)


class FakeRegistry:
    def __init__(self, value=None, delay=0):
        self.value=value if value is not None else {'ok': True}
        self.delay=delay
        self.executions=0
    def describe(self, name):
        return {'name': name, 'source': 'test', 'risk_class': 'READ_ONLY', 'authorization_mode': 'none'}
    def execute(self, name, args):
        self.executions += 1
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


class GuardedRegistry(FakeRegistry):
    def __init__(self, mode='cag', risk='EXECUTION'):
        super().__init__()
        self.mode=mode
        self.risk=risk
    def describe(self, name):
        return {
            'name': name,
            'source': 'test',
            'risk_class': self.risk,
            'authorization_mode': self.mode,
        }


def test_non_read_only_tool_fails_closed_without_trusted_authorization():
    registry=GuardedRegistry(mode='cag')
    msg, ev, _dup=execute_tool_call(registry,call('run_command'),AgentLoopPolicy(),{},1)
    assert registry.executions == 0
    assert ev['execution_state'] == 'authorization_blocked'
    assert ev['authorization_state'] == 'trusted_authorization_required'
    assert 'blocked' in msg['content'].lower()


def test_cag_tool_requires_scoped_verified_evidence():
    registry=GuardedRegistry(mode='cag')
    auth=ToolAuthorizationContext(
        trusted=True,
        approved_tools=('run_command',),
        cag_decision='approved',
        cag_evidence_id='CAG-EVIDENCE-001',
    )
    _msg, ev, _dup=execute_tool_call(registry,call('run_command'),AgentLoopPolicy(),{},1,authorization=auth)
    assert registry.executions == 1
    assert ev['execution_state'] == 'ok'
    assert ev['authorization_state'] == 'cag_approved'


def test_authorized_scope_blocks_other_tool():
    registry=GuardedRegistry(mode='approval', risk='CONTROLLED_WRITE')
    auth=ToolAuthorizationContext(
        trusted=True,
        approved_tools=('write_file',),
        approval_id='approval-1',
        approved_by='owner',
    )
    _msg, ev, _dup=execute_tool_call(registry,call('run_command'),AgentLoopPolicy(),{},1,authorization=auth)
    assert registry.executions == 0
    assert ev['authorization_state'] == 'tool_outside_authorized_scope'


class DescriptorlessRegistry(FakeRegistry):
    def describe(self, name):
        return None


def test_tool_without_descriptor_fails_closed():
    registry=DescriptorlessRegistry()
    _msg, ev, _dup=execute_tool_call(registry,call('unknown_tool'),AgentLoopPolicy(),{},1)
    assert registry.executions == 0
    assert ev['execution_state'] == 'authorization_blocked'
    assert ev['authorization_state'] == 'tool_descriptor_required'


def test_authorization_gate_can_be_disabled_for_development():
    registry=GuardedRegistry(mode='cag', risk='EXECUTION')
    _msg, ev, _dup=execute_tool_call(
        registry, call('run_command'), AgentLoopPolicy(), {}, 1, enforce_authorization=False
    )
    assert registry.executions == 1
    assert ev['execution_state'] == 'ok'
    assert ev['authorization_state'] == 'disabled_by_configuration'
