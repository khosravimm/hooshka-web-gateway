from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from core.tool_contract import read_only_descriptor


class EngineeringToolError(RuntimeError):
    pass


def _fn(name, description, properties=None, required=None):
    return {"type":"function","function":{"name":name,"description":description,"parameters":{"type":"object","properties":properties or {},"required":required or []}}}


class EngineeringToolBackend:
    def __init__(self, root):
        self.root=Path(root).resolve()

    def _git(self,*args,timeout=15):
        cp=subprocess.run(["git","-C",str(self.root),*args],capture_output=True,text=True,errors="ignore",timeout=timeout)
        if cp.returncode: raise EngineeringToolError(cp.stderr.strip() or f"git {' '.join(args)} failed")
        return cp.stdout

    def git_status(self):
        return {"root":str(self.root),"status":self._git("status","--short","--branch")}

    def git_diff(self, staged=False, max_chars=50000):
        args=["diff"] + (["--cached"] if staged else [])
        out=self._git(*args); limit=max(1000,min(int(max_chars),100000))
        return {"staged":bool(staged),"diff":out[:limit],"truncated":len(out)>limit}

    def git_log(self, limit=20):
        limit=max(1,min(int(limit),100)); out=self._git("log",f"-{limit}","--date=iso-strict","--pretty=format:%H%x09%ad%x09%an%x09%s")
        rows=[]
        for line in out.splitlines():
            p=line.split("\t",3)
            if len(p)==4: rows.append({"sha":p[0],"date":p[1],"author":p[2],"subject":p[3]})
        return {"commits":rows}

    def git_branches(self):
        out=self._git("branch","--all","--verbose","--no-abbrev")
        return {"branches":[x for x in out.splitlines() if x.strip()]}

    def git_remotes(self):
        out=self._git("remote","-v")
        return {"remotes":[x for x in out.splitlines() if x.strip()]}

    def runtime_inventory(self):
        commands={"git":["git","--version"],"python":[str(self.root/".venv/Scripts/python.exe"),"--version"],"node":["node","--version"],"npm":["npm.cmd" if shutil.which("npm.cmd") else "npm","--version"],"pwsh":["pwsh","--version"],"gh":["gh","--version"]}
        rows={}
        for name,cmd in commands.items():
            exe=cmd[0]
            if ("/" not in exe and "\\" not in exe and not shutil.which(exe)) or (exe.endswith('.exe') and ("/" in exe or "\\" in exe) and not Path(exe).exists()):
                rows[name]={"available":False}; continue
            try:
                cp=subprocess.run(cmd,capture_output=True,text=True,errors="ignore",timeout=8)
                rows[name]={"available":cp.returncode==0,"version":(cp.stdout or cp.stderr).splitlines()[0] if (cp.stdout or cp.stderr) else None,"path":shutil.which(exe) or exe}
            except Exception as exc: rows[name]={"available":False,"error":str(exc)}
        return {"runtimes":rows}

    def python_packages(self, limit=300):
        py=self.root/".venv/Scripts/python.exe"
        if not py.exists(): raise EngineeringToolError("Project virtualenv Python not found")
        cp=subprocess.run([str(py),"-m","pip","list","--format=json"],capture_output=True,text=True,errors="ignore",timeout=20)
        if cp.returncode: raise EngineeringToolError(cp.stderr.strip() or "pip list failed")
        rows=json.loads(cp.stdout); limit=max(1,min(int(limit),1000)); return {"packages":rows[:limit],"truncated":len(rows)>limit}

    def execute(self,name,args=None):
        args=dict(args or {}); allowed={"git_status":set(),"git_diff":{"staged","max_chars"},"git_log":{"limit"},"git_branches":set(),"git_remotes":set(),"runtime_inventory":set(),"python_packages":{"limit"}}
        if name not in allowed: raise EngineeringToolError(f"Unknown engineering tool: {name}")
        return getattr(self,name)(**{k:v for k,v in args.items() if k in allowed[name]})


def engineering_tool_definitions():
    return [
        _fn("git_status","Inspect Git working-tree and branch status."),
        _fn("git_diff","Read the current Git diff without modifying the repository.",{"staged":{"type":"boolean"},"max_chars":{"type":"integer","minimum":1000,"maximum":100000}}),
        _fn("git_log","Read recent Git commit history.",{"limit":{"type":"integer","minimum":1,"maximum":100}}),
        _fn("git_branches","List local and remote Git branches."),
        _fn("git_remotes","List configured Git remotes."),
        _fn("runtime_inventory","Inspect installed engineering runtimes used by HWG."),
        _fn("python_packages","List packages in the HWG project virtual environment.",{"limit":{"type":"integer","minimum":1,"maximum":1000}}),
    ]


def engineering_tool_descriptors():
    return [read_only_descriptor(x["function"]["name"],x["function"]["description"],x["function"]["parameters"],source="engineering_runtime") for x in engineering_tool_definitions()]
