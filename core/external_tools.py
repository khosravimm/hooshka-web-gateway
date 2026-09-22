from __future__ import annotations

import base64
import ipaddress
import json
import socket
import subprocess
from urllib.parse import urljoin, urlparse

import requests
import yaml

from core.tool_contract import ToolAnnotations, ToolAuthorizationMode, ToolDescriptor, ToolRiskClass, read_only_descriptor


class ExternalToolError(RuntimeError):
    pass


def _fn(name, description, properties=None, required=None):
    return {"type":"function","function":{"name":name,"description":description,"parameters":{"type":"object","properties":properties or {},"required":required or []}}}


def _external_descriptor(item, source):
    fn=item["function"]
    return ToolDescriptor(name=fn["name"],description=fn["description"],source=source,risk_class=ToolRiskClass.READ_ONLY,authorization_mode=ToolAuthorizationMode.NONE,input_schema=fn["parameters"],annotations=ToolAnnotations(read_only_hint=True,destructive_hint=False,idempotent_hint=True,open_world_hint=True))


class GitHubToolBackend:
    """Read-only GitHub API tools using the already-authenticated GitHub CLI."""
    def _api(self, endpoint, fields=None, timeout=20):
        cmd=["gh","api","-X","GET",endpoint]
        for key,value in (fields or {}).items(): cmd += ["-f",f"{key}={value}"]
        cp=subprocess.run(cmd,capture_output=True,text=True,errors="ignore",timeout=timeout)
        if cp.returncode: raise ExternalToolError(cp.stderr.strip() or "GitHub API request failed")
        return json.loads(cp.stdout)

    def repo_info(self, repo):
        data=self._api(f"repos/{repo}")
        keys=("full_name","description","private","default_branch","archived","forks_count","stargazers_count","open_issues_count","updated_at","html_url")
        return {k:data.get(k) for k in keys}

    def list_issues(self, repo, state="open", limit=30):
        limit=max(1,min(int(limit),100)); data=self._api(f"repos/{repo}/issues",{"state":state,"per_page":limit})
        rows=[]
        for x in data:
            if "pull_request" in x: continue
            rows.append({"number":x.get("number"),"title":x.get("title"),"state":x.get("state"),"updated_at":x.get("updated_at"),"html_url":x.get("html_url")})
        return {"issues":rows}

    def list_prs(self, repo, state="open", limit=30):
        limit=max(1,min(int(limit),100)); data=self._api(f"repos/{repo}/pulls",{"state":state,"per_page":limit})
        return {"pull_requests":[{"number":x.get("number"),"title":x.get("title"),"state":x.get("state"),"draft":x.get("draft"),"updated_at":x.get("updated_at"),"html_url":x.get("html_url")} for x in data]}

    def get_file(self, repo, path, ref=None, max_chars=100000):
        fields={"ref":ref} if ref else None; data=self._api(f"repos/{repo}/contents/{path}",fields)
        if not isinstance(data,dict) or data.get("type")!="file": raise ExternalToolError("GitHub path is not a file")
        raw=base64.b64decode((data.get("content") or "").encode()).decode("utf-8",errors="replace"); limit=max(1,min(int(max_chars),200000))
        return {"repo":repo,"path":path,"ref":ref,"sha":data.get("sha"),"content":raw[:limit],"truncated":len(raw)>limit}

    def search_code(self, query, repo=None, limit=20):
        limit=max(1,min(int(limit),100)); q=f"{query} repo:{repo}" if repo else query; data=self._api("search/code",{"q":q,"per_page":limit})
        return {"total_count":data.get("total_count"),"items":[{"name":x.get("name"),"path":x.get("path"),"repository":(x.get("repository") or {}).get("full_name"),"html_url":x.get("html_url")} for x in data.get("items",[])]}

    def execute(self,name,args=None):
        args=dict(args or {}); mapping={"github_repo_info":("repo_info",{"repo"}),"github_list_issues":("list_issues",{"repo","state","limit"}),"github_list_prs":("list_prs",{"repo","state","limit"}),"github_get_file":("get_file",{"repo","path","ref","max_chars"}),"github_search_code":("search_code",{"query","repo","limit"})}
        if name not in mapping: raise ExternalToolError(f"Unknown GitHub tool: {name}")
        method,allowed=mapping[name]; return getattr(self,method)(**{k:v for k,v in args.items() if k in allowed})


class RestOpenApiBackend:
    """Bounded read-only HTTP/OpenAPI client with redirect-aware SSRF protection."""
    _USER_AGENT={"User-Agent":"Hooshka-Web-Gateway-Agent/1"}

    def _validate_url(self,url):
        parsed=urlparse(url)
        if parsed.scheme not in ("http","https") or not parsed.hostname or parsed.username or parsed.password:
            raise ExternalToolError("Only credential-free http/https URLs are allowed")
        try:
            infos=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=="https" else 80),type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ExternalToolError(f"DNS resolution failed: {exc}")
        for info in infos:
            ip=ipaddress.ip_address(info[4][0])
            if ip.is_loopback:
                continue
            if ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                raise ExternalToolError("Private/link-local/reserved HTTP targets are blocked")
        return url

    def _request(self,method,url,timeout,max_bytes=200000,redirects=3):
        current=url
        timeout=max(0.5,min(float(timeout),30))
        for _ in range(redirects+1):
            self._validate_url(current)
            r=requests.request(method,current,timeout=timeout,allow_redirects=False,stream=True,headers=self._USER_AGENT)
            if r.is_redirect or r.is_permanent_redirect:
                location=r.headers.get("location")
                r.close()
                if not location:
                    raise ExternalToolError("HTTP redirect is missing Location")
                current=urljoin(current,location)
                continue
            if method=="HEAD":
                return r,b"",False
            buf=bytearray(); truncated=False
            for chunk in r.iter_content(chunk_size=16384):
                if not chunk:
                    continue
                remaining=max_bytes-len(buf)
                if remaining<=0:
                    truncated=True; break
                buf.extend(chunk[:remaining])
                if len(chunk)>remaining:
                    truncated=True; break
            return r,bytes(buf),truncated
        raise ExternalToolError("Too many HTTP redirects")

    def http_get(self,url,timeout=10,max_chars=50000):
        limit=max(1000,min(int(max_chars),200000))
        r,raw,truncated=self._request("GET",url,timeout,max_bytes=limit)
        encoding=r.encoding or "utf-8"
        content=raw.decode(encoding,errors="replace")
        return {"url":r.url,"status_code":r.status_code,"content_type":r.headers.get("content-type"),"content":content,"truncated":truncated}

    def http_head(self,url,timeout=10):
        r,_,_=self._request("HEAD",url,timeout,max_bytes=0)
        safe={k:v for k,v in r.headers.items() if k.lower() not in {"set-cookie","authorization","proxy-authorization"}}
        return {"url":r.url,"status_code":r.status_code,"headers":safe}

    def openapi_inspect(self,url,timeout=10):
        r,raw,truncated=self._request("GET",url,timeout,max_bytes=2_000_001)
        r.raise_for_status()
        if truncated or len(raw)>2_000_000:
            raise ExternalToolError("OpenAPI document exceeds 2 MB limit")
        text=raw.decode(r.encoding or "utf-8",errors="replace")
        try:
            doc=json.loads(text)
        except ValueError:
            doc=yaml.safe_load(text)
        if not isinstance(doc,dict) or not (doc.get("openapi") or doc.get("swagger")):
            raise ExternalToolError("Document is not recognized as OpenAPI/Swagger")
        ops=[]
        for path,item in (doc.get("paths") or {}).items():
            if not isinstance(item,dict):
                continue
            for method,value in item.items():
                if method.lower() in {"get","post","put","patch","delete","head","options","trace"}:
                    value=value if isinstance(value,dict) else {}
                    ops.append({"method":method.upper(),"path":path,"operation_id":value.get("operationId"),"summary":value.get("summary")})
        info=doc.get("info") or {}
        return {"spec":doc.get("openapi") or doc.get("swagger"),"title":info.get("title"),"version":info.get("version"),"servers":doc.get("servers",[]),"operations":ops,"operation_count":len(ops)}

    def execute(self,name,args=None):
        args=dict(args or {})
        mapping={"http_get":("http_get",{"url","timeout","max_chars"}),"http_head":("http_head",{"url","timeout"}),"openapi_inspect":("openapi_inspect",{"url","timeout"})}
        if name not in mapping:
            raise ExternalToolError(f"Unknown REST/OpenAPI tool: {name}")
        method,allowed=mapping[name]
        return getattr(self,method)(**{k:v for k,v in args.items() if k in allowed})

def github_tool_definitions():
    return [
        _fn("github_repo_info","Read GitHub repository metadata.",{"repo":{"type":"string"}},["repo"]),
        _fn("github_list_issues","List GitHub issues.",{"repo":{"type":"string"},"state":{"type":"string","enum":["open","closed","all"]},"limit":{"type":"integer","minimum":1,"maximum":100}},["repo"]),
        _fn("github_list_prs","List GitHub pull requests.",{"repo":{"type":"string"},"state":{"type":"string","enum":["open","closed","all"]},"limit":{"type":"integer","minimum":1,"maximum":100}},["repo"]),
        _fn("github_get_file","Read a UTF-8 text file from GitHub.",{"repo":{"type":"string"},"path":{"type":"string"},"ref":{"type":"string"},"max_chars":{"type":"integer","minimum":1,"maximum":200000}},["repo","path"]),
        _fn("github_search_code","Search GitHub code using authenticated GitHub API.",{"query":{"type":"string"},"repo":{"type":"string"},"limit":{"type":"integer","minimum":1,"maximum":100}},["query"]),
    ]


def rest_tool_definitions():
    return [
        _fn("http_get","Perform a bounded read-only HTTP GET with SSRF protections.",{"url":{"type":"string"},"timeout":{"type":"number","minimum":0.5,"maximum":30},"max_chars":{"type":"integer","minimum":1000,"maximum":200000}},["url"]),
        _fn("http_head","Perform a read-only HTTP HEAD with SSRF protections.",{"url":{"type":"string"},"timeout":{"type":"number","minimum":0.5,"maximum":30}},["url"]),
        _fn("openapi_inspect","Fetch and summarize an OpenAPI/Swagger document without invoking its operations.",{"url":{"type":"string"},"timeout":{"type":"number","minimum":0.5,"maximum":30}},["url"]),
    ]


def external_tool_descriptors():
    return [_external_descriptor(x,"github_cli") for x in github_tool_definitions()] + [_external_descriptor(x,"rest_openapi") for x in rest_tool_definitions()]
