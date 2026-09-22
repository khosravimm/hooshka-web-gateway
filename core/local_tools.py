from pathlib import Path
import fnmatch

class LocalToolError(ValueError):
    pass

class LocalToolRegistry:
    """Governed read-only filesystem tools for the interactive HWG agent."""
    def __init__(self, roots=None):
        roots = roots or [Path.cwd()]
        self.roots = [Path(x).resolve() for x in roots]

    def _path(self, value='.'):
        raw = Path(value or '.')
        p = raw.resolve() if raw.is_absolute() else (self.roots[0] / raw).resolve()
        if not any(p == root or root in p.parents for root in self.roots):
            raise LocalToolError('Path is outside the configured agent roots')
        return p

    def list_files(self, path='.', recursive=False, pattern='*'):
        p = self._path(path)
        if not p.is_dir():
            raise LocalToolError(f'Directory not found: {path}')
        items = p.rglob('*') if recursive else p.glob('*')
        rows=[]
        for x in items:
            if fnmatch.fnmatch(x.name, pattern):
                rows.append({'name':x.name,'path':str(x),'type':'directory' if x.is_dir() else 'file'})
        return {'path':str(p),'items':sorted(rows,key=lambda r:(r['type']!='directory',r['name'].lower()))}

    def read_file(self, path, max_chars=100000):
        p = self._path(path)
        if not p.is_file(): raise LocalToolError(f'File not found: {path}')
        return {'path':str(p),'content':p.read_text(encoding='utf-8',errors='ignore')[:max_chars]}

    def search_files(self, query, path='.', pattern='*'):
        if not query: raise LocalToolError('query is required')
        root=self._path(path); matches=[]
        for x in root.rglob('*'):
            if x.is_file() and fnmatch.fnmatch(x.name,pattern):
                try: lines=x.read_text(encoding='utf-8',errors='ignore').splitlines()
                except OSError: continue
                for n,line in enumerate(lines,1):
                    if query.lower() in line.lower(): matches.append({'path':str(x),'line':n,'text':line[:500]})
        return {'query':query,'matches':matches[:500]}

    def execute(self,name,arguments=None):
        if name not in ('list_files','read_file','search_files'):
            raise LocalToolError(f'Unknown or non-read-only local tool: {name}')
        args=dict(arguments or {})
        if 'path' not in args and args.get('filePath'): args['path']=args['filePath']
        allowed={'list_files':{'path','recursive','pattern'},'read_file':{'path','max_chars'},'search_files':{'query','path','pattern'}}[name]
        args={k:v for k,v in args.items() if k in allowed}
        return getattr(self,name)(**args)


def agent_tool_definitions():
    return [
        {'type':'function','function':{'name':'list_files','description':'List files and directories on an allowed local filesystem path. Use this for requests to inspect a drive or directory.','parameters':{'type':'object','properties':{'path':{'type':'string'},'recursive':{'type':'boolean'},'pattern':{'type':'string'}},'required':['path']}}},
        {'type':'function','function':{'name':'read_file','description':'Read a text file from an allowed local filesystem path.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
        {'type':'function','function':{'name':'search_files','description':'Search text inside files under an allowed local filesystem path.','parameters':{'type':'object','properties':{'query':{'type':'string'},'path':{'type':'string'},'pattern':{'type':'string'}},'required':['query','path']}}},
    ]
