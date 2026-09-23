"""HWG reference Python SDK."""
from __future__ import annotations
import json
import requests

class HwgError(RuntimeError):
    def __init__(self, message: str, code: str|None=None, status: int|None=None, details=None, provider: str|None=None):
        super().__init__(message); self.code=code; self.status=status; self.details=details; self.provider=provider

class HwgClient:
    def __init__(self, base_url="http://127.0.0.1:5080", api_key=None, timeout=240.0):
        self.base_url=base_url.rstrip("/"); self.timeout=timeout; self._session=requests.Session()
        if api_key: self._session.headers["Authorization"]=f"Bearer {api_key}"
    def _raise(self,r,method,path):
        if 200 <= r.status_code < 300: return
        body={}
        try: body=r.json() or {}
        except Exception: pass
        err=body.get("error") if isinstance(body,dict) else {}
        if not isinstance(err,dict): err={}
        raise HwgError(err.get("message") or f"{method} {path} -> {r.status_code}", err.get("code"), r.status_code, err.get("details"), err.get("provider"))
    def _get(self,path):
        r=self._session.get(self.base_url+path,timeout=self.timeout); self._raise(r,"GET",path); return r.json()
    def _post(self,path,body):
        r=self._session.post(self.base_url+path,json=body,timeout=self.timeout); self._raise(r,"POST",path); return r.json()
    def models(self): return self._get("/v1/models")["data"]
    def providers(self): return self._get("/v1/providers")["providers"]
    def capabilities(self): return self._get("/v1/capabilities")
    def openapi(self): return self._get("/v1/contracts/openapi.json")
    def schemas(self): return self._get("/v1/contracts/schemas")
    def compatibility(self): return self._get("/v1/compatibility")
    def inventory(self): return self._get("/panel/api/ng/inventory")
    def accounts(self): return self._get("/panel/api/accounts").get("accounts",[])
    @staticmethod
    def text_part(text): return {"type":"text","text":text}
    @staticmethod
    def image_part(image_url): return {"type":"input_image","image_url":image_url}
    @staticmethod
    def file_part(file_path): return {"type":"input_file","file_path":file_path}
    def chat(self,model,messages,provider=None,**kwargs):
        body={"model":model,"messages":messages,"stream":False,**kwargs}
        if provider: body["provider"]=provider
        return self._post("/v1/chat/completions",body)
    def chat_stream(self,model,messages,provider=None,**kwargs):
        body={"model":model,"messages":messages,"stream":True,**kwargs}
        if provider: body["provider"]=provider
        with self._session.post(self.base_url+"/v1/chat/completions",json=body,timeout=self.timeout,stream=True) as r:
            self._raise(r,"POST","/v1/chat/completions")
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"): continue
                data=line[5:].strip()
                if data=="[DONE]": return
                yield json.loads(data)
    def respond(self,model,user_input,provider=None,**kwargs):
        body={"model":model,"input":user_input,**kwargs}
        if provider: body["provider"]=provider
        return self._post("/v1/responses",body)
