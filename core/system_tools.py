from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import time
from pathlib import Path

import psutil

from core.tool_contract import read_only_descriptor


class SystemToolError(RuntimeError):
    pass


def _fn(name, description, properties=None, required=None):
    return {"type":"function","function":{"name":name,"description":description,"parameters":{"type":"object","properties":properties or {},"required":required or []}}}


class SystemToolBackend:
    """Read-only Windows/system inspection tools backed by OS/Python runtimes."""
    def disk_usage(self, path="D:\\"):
        usage=psutil.disk_usage(path)
        return {"path":path,"total":usage.total,"used":usage.used,"free":usage.free,"percent":usage.percent}

    def memory_info(self):
        v=psutil.virtual_memory(); s=psutil.swap_memory()
        return {"virtual":{"total":v.total,"available":v.available,"used":v.used,"percent":v.percent},"swap":{"total":s.total,"used":s.used,"free":s.free,"percent":s.percent}}

    def cpu_info(self):
        freq=psutil.cpu_freq()
        return {"logical_cores":psutil.cpu_count(),"physical_cores":psutil.cpu_count(logical=False),"percent":psutil.cpu_percent(interval=0.15),"frequency_mhz":None if not freq else freq.current,"machine":platform.machine(),"processor":platform.processor()}

    def network_interfaces(self):
        addrs=psutil.net_if_addrs(); stats=psutil.net_if_stats(); rows=[]
        for name, values in addrs.items():
            rows.append({"name":name,"up":bool(stats.get(name) and stats[name].isup),"speed_mbps":stats[name].speed if name in stats else None,"addresses":[{"family":str(v.family),"address":v.address,"netmask":v.netmask} for v in values]})
        return {"interfaces":rows}

    def dns_lookup(self, host):
        rows=[]
        for family, socktype, proto, canonname, sockaddr in socket.getaddrinfo(host, None):
            address=sockaddr[0]
            item={"family":family,"address":address,"canonical_name":canonname or None}
            if item not in rows: rows.append(item)
        return {"host":host,"results":rows}

    def tcp_connect(self, host, port, timeout=3.0):
        timeout=max(0.1,min(float(timeout),10.0)); started=time.monotonic()
        try:
            with socket.create_connection((host,int(port)),timeout=timeout): ok=True; error=None
        except OSError as exc: ok=False; error=str(exc)
        return {"host":host,"port":int(port),"reachable":ok,"duration_ms":round((time.monotonic()-started)*1000,2),"error":error}

    def ping(self, host, count=2):
        count=max(1,min(int(count),4)); args=["ping","-n" if os.name=="nt" else "-c",str(count),host]
        cp=subprocess.run(args,capture_output=True,text=True,errors="ignore",timeout=12)
        return {"host":host,"exit_code":cp.returncode,"reachable":cp.returncode==0,"output":cp.stdout[-8000:]}

    def route_table(self, limit=200):
        limit=max(1,min(int(limit),500)); cp=subprocess.run(["route","print"],capture_output=True,text=True,errors="ignore",timeout=10)
        lines=[x for x in cp.stdout.splitlines() if x.strip()]
        return {"lines":lines[:limit],"truncated":len(lines)>limit}

    def arp_table(self, limit=200):
        limit=max(1,min(int(limit),500)); cp=subprocess.run(["arp","-a"],capture_output=True,text=True,errors="ignore",timeout=10)
        lines=[x for x in cp.stdout.splitlines() if x.strip()]
        return {"lines":lines[:limit],"truncated":len(lines)>limit}

    def list_services(self, limit=200):
        limit=max(1,min(int(limit),500))
        if os.name!="nt": return {"services":[],"unsupported":True}
        cmd="Get-Service | Select-Object -First %d Name,DisplayName,Status,StartType | ConvertTo-Json -Compress" % limit
        cp=subprocess.run(["powershell","-NoProfile","-Command",cmd],capture_output=True,text=True,errors="ignore",timeout=15)
        if cp.returncode: raise SystemToolError(cp.stderr.strip() or "Get-Service failed")
        data=json.loads(cp.stdout or "[]"); return {"services":data if isinstance(data,list) else [data]}

    def execute(self,name,args=None):
        args=dict(args or {}); allowed={
            "disk_usage":{"path"},"memory_info":set(),"cpu_info":set(),"network_interfaces":set(),
            "dns_lookup":{"host"},"tcp_connect":{"host","port","timeout"},"ping":{"host","count"},
            "route_table":{"limit"},"arp_table":{"limit"},"list_services":{"limit"},
        }
        if name not in allowed: raise SystemToolError(f"Unknown system tool: {name}")
        return getattr(self,name)(**{k:v for k,v in args.items() if k in allowed[name]})


def system_tool_definitions():
    limit={"limit":{"type":"integer","minimum":1,"maximum":500}}
    return [
        _fn("disk_usage","Read disk capacity and free-space information.",{"path":{"type":"string"}}),
        _fn("memory_info","Read physical/virtual memory usage."),
        _fn("cpu_info","Read CPU identity, cores, frequency and current load."),
        _fn("network_interfaces","List local network interfaces and addresses."),
        _fn("dns_lookup","Resolve a DNS host name.",{"host":{"type":"string"}},["host"]),
        _fn("tcp_connect","Test TCP reachability without sending application data.",{"host":{"type":"string"},"port":{"type":"integer","minimum":1,"maximum":65535},"timeout":{"type":"number","minimum":0.1,"maximum":10}},["host","port"]),
        _fn("ping","Test ICMP reachability.",{"host":{"type":"string"},"count":{"type":"integer","minimum":1,"maximum":4}},["host"]),
        _fn("route_table","Inspect the local route table.",limit),
        _fn("arp_table","Inspect the local ARP cache.",limit),
        _fn("list_services","List Windows services without changing service state.",limit),
    ]


def system_tool_descriptors():
    return [read_only_descriptor(x["function"]["name"],x["function"]["description"],x["function"]["parameters"],source="windows_native") for x in system_tool_definitions()]
