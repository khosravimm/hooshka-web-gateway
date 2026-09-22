from __future__ import annotations

from pathlib import Path

from core.engineering_tools import EngineeringToolBackend, engineering_tool_definitions, engineering_tool_descriptors
from core.external_tools import GitHubToolBackend, RestOpenApiBackend, external_tool_descriptors, github_tool_definitions, rest_tool_definitions
from core.local_tools import LocalToolRegistry, agent_tool_definitions as local_tool_definitions, local_tool_descriptors
from core.system_tools import SystemToolBackend, system_tool_definitions, system_tool_descriptors
from core.tool_contract import read_only_descriptor


def _fn(name, description, properties=None, required=None):
    return {"type":"function","function":{"name":name,"description":description,"parameters":{"type":"object","properties":properties or {},"required":required or []}}}


def registry_tool_definitions():
    return [
        _fn("tool_catalog","List all active HWG agent tools with canonical risk/source metadata."),
        _fn("tool_describe","Describe one active HWG agent tool and its input/risk contract.",{"name":{"type":"string"}},["name"]),
        _fn("tool_search","Search active HWG tools by name or description.",{"query":{"type":"string"},"limit":{"type":"integer","minimum":1,"maximum":100}},["query"]),
    ]


def agent_tool_definitions():
    local=[x for x in local_tool_definitions() if x["function"]["name"]!="tool_catalog"]
    return registry_tool_definitions()+local+system_tool_definitions()+engineering_tool_definitions()+github_tool_definitions()+rest_tool_definitions()


def agent_tool_descriptors():
    local=[x for x in local_tool_descriptors() if x.name!="tool_catalog"]
    reg=[read_only_descriptor(x["function"]["name"],x["function"]["description"],x["function"]["parameters"],source="hwg_registry") for x in registry_tool_definitions()]
    return reg+local+system_tool_descriptors()+engineering_tool_descriptors()+external_tool_descriptors()


class AgentToolRegistry:
    """Canonical dispatch registry for active HWG agent tool backends."""
    def __init__(self, roots=None, repo_root=None):
        roots=roots or [Path.cwd()]
        self.local=LocalToolRegistry(roots=roots)
        self.system=SystemToolBackend()
        self.engineering=EngineeringToolBackend(repo_root or Path.cwd())
        self.github=GitHubToolBackend()
        self.rest=RestOpenApiBackend()
        self._descriptors={x.name:x for x in agent_tool_descriptors()}
        self._definitions={x["function"]["name"]:x for x in agent_tool_definitions()}

    def describe(self,name):
        desc=self._descriptors.get(name)
        return desc.to_dict() if desc else None

    def tool_catalog(self):
        return {"count":len(self._descriptors),"tools":[x.to_dict() for x in self._descriptors.values()]}

    def tool_describe(self,name):
        desc=self.describe(name)
        if not desc: raise ValueError(f"Unknown active tool: {name}")
        return desc

    def tool_search(self,query,limit=20):
        q=str(query or "").strip().lower()
        if not q: raise ValueError("query is required")
        limit=max(1,min(int(limit),100)); rows=[]
        for d in self._descriptors.values():
            if q in d.name.lower() or q in d.description.lower() or q in d.source.lower(): rows.append(d.to_dict())
            if len(rows)>=limit: break
        return {"query":query,"matches":rows,"count":len(rows)}

    def execute(self,name,arguments=None):
        args=dict(arguments or {})
        if name=="tool_catalog": return self.tool_catalog()
        if name=="tool_describe": return self.tool_describe(**{k:v for k,v in args.items() if k=="name"})
        if name=="tool_search": return self.tool_search(**{k:v for k,v in args.items() if k in {"query","limit"}})
        local_names={x["function"]["name"] for x in local_tool_definitions() if x["function"]["name"]!="tool_catalog"}
        system_names={x["function"]["name"] for x in system_tool_definitions()}
        eng_names={x["function"]["name"] for x in engineering_tool_definitions()}
        gh_names={x["function"]["name"] for x in github_tool_definitions()}
        rest_names={x["function"]["name"] for x in rest_tool_definitions()}
        if name in local_names: return self.local.execute(name,args)
        if name in system_names: return self.system.execute(name,args)
        if name in eng_names: return self.engineering.execute(name,args)
        if name in gh_names: return self.github.execute(name,args)
        if name in rest_names: return self.rest.execute(name,args)
        raise ValueError(f"Unknown or unauthorized agent tool: {name}")
