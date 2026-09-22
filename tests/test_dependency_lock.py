from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _names(path: Path, operator: str):
    rows = []
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        assert operator in line
        rows.append(tuple(x.strip().lower() for x in line.split(operator, 1)))
    return rows


def test_direct_dependencies_are_locked_exactly():
    ranges = _names(ROOT / 'requirements.txt', '>=')
    locked = _names(ROOT / 'requirements.lock', '==')
    assert {n for n, _ in ranges} == {n for n, _ in locked}
    text = (ROOT / 'requirements.lock').read_text(encoding='utf-8-sig')
    assert 'git+' not in text and 'http://' not in text and 'https://' not in text and '-e ' not in text


def test_lock_matches_validated_environment():
    for name, locked_version in _names(ROOT / 'requirements.lock', '=='):
        assert version(name) == locked_version
