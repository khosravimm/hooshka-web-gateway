from pathlib import Path
import fnmatch, json, os, platform, shutil, subprocess
from datetime import datetime, timezone

class LocalToolError(ValueError): pass

class LocalToolRegistry:
    """Governed local read/inspection tool plane for the interactive HWG agent."""
    def __init__(self, roots=None):
        roots=roots or [Path.cwd()]; self.roots=[Path(x).resolve() for x in roots]

    def _path(self,value='.'):
        raw=Path(value or '.'); p=raw.resolve() if raw.is_absolute() else (self.roots[0]/raw).resolve()
        if not any(p==root or root in p.parents for root in self.roots): raise LocalToolError('Path is outside the configured agent roots')
        return p

    def list_files(self,path='.',recursive=False,pattern='*',limit=500):
        p=self._path(path)
        if not p.is_dir(): raise LocalToolError(f'Directory not found: {path}')
        items=p.rglob('*') if recursive else p.glob('*'); rows=[]
        for x in items:
            if fnmatch.fnmatch(x.name,pattern):
                try: st=x.stat()
                except OSError: continue
                rows.append({'name':x.name,'path':str(x),'type':'directory' if x.is_dir() else 'file','size':None if x.is_dir() else st.st_size,'modified':datetime.fromtimestamp(st.st_mtime,timezone.utc).isoformat()})
                if len(rows)>=int(limit): break
        return {'path':str(p),'items':sorted(rows,key=lambda r:(r['type']!='directory',r['name'].lower())),'truncated':len(rows)>=int(limit)}

    def file_info(self,path):
        p=self._path(path)
        if not p.exists(): raise LocalToolError(f'Path not found: {path}')
        st=p.stat(); return {'path':str(p),'type':'directory' if p.is_dir() else 'file','size':None if p.is_dir() else st.st_size,'modified':datetime.fromtimestamp(st.st_mtime,timezone.utc).isoformat()}

    def read_file(self,path,max_chars=100000):
        p=self._path(path)
        if not p.is_file(): raise LocalToolError(f'File not found: {path}')
        return {'path':str(p),'content':p.read_text(encoding='utf-8',errors='ignore')[:int(max_chars)]}

    def search_files(self,query,path='.',pattern='*',limit=500):
        if not query: raise LocalToolError('query is required')
        root=self._path(path); matches=[]
        for x in root.rglob('*'):
            if x.is_file() and fnmatch.fnmatch(x.name,pattern):
                try: lines=x.read_text(encoding='utf-8',errors='ignore').splitlines()
                except OSError: continue
                for n,line in enumerate(lines,1):
                    if query.lower() in line.lower(): matches.append({'path':str(x),'line':n,'text':line[:500]})
                    if len(matches)>=int(limit): return {'query':query,'matches':matches,'truncated':True}
        return {'query':query,'matches':matches,'truncated':False}

    def find_files(self,path='.',pattern='*',limit=500):
        root=self._path(path); rows=[]
        for x in root.rglob(pattern):
            rows.append({'name':x.name,'path':str(x),'type':'directory' if x.is_dir() else 'file'})
            if len(rows)>=int(limit): break
        return {'path':str(root),'pattern':pattern,'items':rows,'truncated':len(rows)>=int(limit)}

    def list_drives(self):
        if os.name!='nt': return {'drives':[{'path':'/'}]}
        import ctypes
        mask=ctypes.windll.kernel32.GetLogicalDrives(); rows=[]
        for i in range(26):
            if mask & (1<<i):
                root=f'{chr(65+i)}:\\'; total,used,free=shutil.disk_usage(root)
                rows.append({'path':root,'total':total,'used':used,'free':free})
        return {'drives':rows}

    def system_info(self):
        return {'hostname':platform.node(),'os':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),'python':platform.python_version()}

    def environment_info(self,names=None):
        safe={'COMPUTERNAME','USERNAME','USERPROFILE','TEMP','TMP','PATH','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS'}
        requested=set(names or safe); requested &= safe
        return {'environment':{k:os.environ.get(k) for k in sorted(requested)}}


    def list_processes(self,limit=100):
        limit=max(1,min(int(limit),200))
        if os.name=='nt':
            cp=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,errors='ignore',timeout=10)
            import csv, io
            rows=[]
            for row in csv.reader(io.StringIO(cp.stdout)):
                if len(row)>=5: rows.append({'name':row[0],'pid':row[1],'session':row[2],'memory':row[4]})
                if len(rows)>=limit: break
            return {'processes':rows,'truncated':len(rows)>=limit}
        cp=subprocess.run(['ps','-eo','pid,comm'],capture_output=True,text=True,errors='ignore',timeout=10)
        return {'processes':cp.stdout.splitlines()[1:limit+1],'truncated':len(cp.stdout.splitlines())>limit+1}

    def network_listeners(self,limit=100):
        limit=max(1,min(int(limit),200))
        if os.name=='nt':
            cp=subprocess.run(['netstat','-ano','-p','tcp'],capture_output=True,text=True,errors='ignore',timeout=10)
            rows=[]
            for line in cp.stdout.splitlines():
                parts=line.split()
                if len(parts)>=5 and parts[0].upper()=='TCP' and parts[3].upper()=='LISTENING': rows.append({'local':parts[1],'pid':parts[4]})
                if len(rows)>=limit: break
            return {'listeners':rows,'truncated':len(rows)>=limit}
        cp=subprocess.run(['ss','-lntp'],capture_output=True,text=True,errors='ignore',timeout=10)
        return {'listeners':cp.stdout.splitlines()[1:limit+1],'truncated':len(cp.stdout.splitlines())>limit+1}

    def tool_catalog(self):
        return {'tools':[{'name':x['function']['name'],'description':x['function']['description'],'risk':'read_only'} for x in agent_tool_definitions()]}

    def execute(self,name,arguments=None):
        names={x['function']['name'] for x in agent_tool_definitions()}
        if name not in names: raise LocalToolError(f'Unknown or unauthorized local tool: {name}')
        args=dict(arguments or {}); args.setdefault('path',args.pop('filePath',None)) if 'filePath' in args and 'path' not in args else None
        allowed={'list_files':{'path','recursive','pattern','limit'},'file_info':{'path'},'read_file':{'path','max_chars'},'search_files':{'query','path','pattern','limit'},'find_files':{'path','pattern','limit'},'list_drives':set(),'system_info':set(),'environment_info':{'names'},'list_processes':{'limit'},'network_listeners':{'limit'},'tool_catalog':set()}[name]
        return getattr(self,name)(**{k:v for k,v in args.items() if k in allowed})

def _fn(name,description,properties=None,required=None):
    return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties or {},'required':required or []}}}

def agent_tool_definitions():
    path={'path':{'type':'string'}}; limit={'limit':{'type':'integer','minimum':1,'maximum':500}}
    return [
        _fn('tool_catalog','Describe the governed tools currently available to the HWG agent.'),
        _fn('list_drives','List local filesystem drives and capacity. Use before inspecting an unknown Windows drive.'),
        _fn('system_info','Read basic local host operating-system and hardware identity information.'),
        _fn('environment_info','Read a safe allowlisted subset of non-secret environment information.',{'names':{'type':'array','items':{'type':'string'}}}),
        _fn('list_processes','Inspect currently running local processes without changing them.',limit),
        _fn('network_listeners','Inspect local TCP listening endpoints without changing them.',limit),
        _fn('list_files','List files/directories on an allowed path.',{**path,'recursive':{'type':'boolean'},'pattern':{'type':'string'},**limit},['path']),
        _fn('file_info','Read metadata for an allowed file or directory.',path,['path']),
        _fn('find_files','Find files/directories recursively by glob pattern.',{**path,'pattern':{'type':'string'},**limit},['path','pattern']),
        _fn('read_file','Read a text file from an allowed path.',{**path,'max_chars':{'type':'integer','minimum':1,'maximum':100000}},['path']),
        _fn('search_files','Search text inside files under an allowed path.',{'query':{'type':'string'},**path,'pattern':{'type':'string'},**limit},['query','path']),
    ]
