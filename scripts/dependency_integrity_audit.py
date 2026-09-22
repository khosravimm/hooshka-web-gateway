"""Release-gate audit for dependency integrity/reproducibility.

This intentionally does not claim vulnerability-advisory coverage.
"""
from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements.lock"


def locked_rows() -> list[tuple[str, str]]:
    rows=[]
    for raw in LOCK.read_text(encoding="utf-8-sig").splitlines():
        line=raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line or any(x in line.lower() for x in ("git+", "http://", "https://", "-e ")):
            raise RuntimeError(f"unsafe or non-exact lock entry: {line}")
        name, ver = line.split("==", 1)
        rows.append((name.strip(), ver.strip()))
    return rows


def audit() -> dict:
    rows=locked_rows()
    mismatches=[]
    for name, locked in rows:
        try:
            actual=version(name)
        except Exception as exc:
            mismatches.append({"package":name,"locked":locked,"actual":None,"error":type(exc).__name__})
            continue
        if actual != locked:
            mismatches.append({"package":name,"locked":locked,"actual":actual})
    proc=subprocess.run([sys.executable,"-m","pip","check"],capture_output=True,text=True)
    return {"locked_packages":len(rows),"mismatches":mismatches,"pip_check_ok":proc.returncode==0,"pip_check_output":(proc.stdout or proc.stderr).strip(),"vulnerability_advisory_scan":"NOT_PERFORMED"}


def main() -> int:
    result=audit()
    print(result)
    return 0 if not result["mismatches"] and result["pip_check_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
