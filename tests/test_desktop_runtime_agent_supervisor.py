from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_agent_task_uses_supervisor_wrapper():
    installer=(ROOT/'install_desktop_runtime_agent_task.ps1').read_text(encoding='utf-8-sig')
    supervisor=(ROOT/'run_desktop_runtime_agent.ps1').read_text(encoding='utf-8-sig')
    assert "run_desktop_runtime_agent.ps1" in installer
    assert 'New-ScheduledTaskAction -Execute "powershell.exe"' in installer
    assert 'while ($true)' in supervisor
    assert '& $Python $Agent' in supervisor
    assert 'Start-Sleep -Seconds 2' in supervisor
    assert 'AGENT_EXIT' in supervisor
