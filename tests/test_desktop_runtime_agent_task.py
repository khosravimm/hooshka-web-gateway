from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_runtime_agent_task_is_laptop_resilient():
    text = (ROOT / 'install_desktop_runtime_agent_task.ps1').read_text(encoding='utf-8-sig')
    assert '-RestartCount 3' in text
    assert '-RestartInterval (New-TimeSpan -Minutes 1)' in text
    assert '-AllowStartIfOnBatteries' in text
    assert '-DontStopIfGoingOnBatteries' in text
    assert '-StartWhenAvailable' in text
