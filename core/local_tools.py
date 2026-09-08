from pathlib import Path
import fnmatch

class LocalToolError(ValueError):
    pass

class LocalToolRegistry:
    def __init__(self, root=None):
        self.root = Path(root or Path.cwd()).resolve()
    def _path(self, value='.'):
        p = (self.root / (value or '.')).resolve()
        if p != self.root and self.root not in p.parents:
            raise LocalToolError('Path is outside the configured workspace')
        return p
    def list_files(self, path='.', recursive=False, pattern='*'):
        p = self._path(path)
        if not p.is_dir(): raise LocalToolError(f'Directory not found: {path}')
        items = p.rglob('*') if recursive else p.glob('*')
        return {'path': path, 'files': sorted(str(x.relative_to(self.root)) for x in items if x.is_file() and fnmatch.fnmatch(x.name, pattern))}
    def read_file(self, path, max_chars=100000):
        p = self._path(path)
        if not p.is_file(): raise LocalToolError(f'File not found: {path}')
        return {'path': path, 'content': p.read_text(encoding='utf-8', errors='ignore')[:max_chars]}
    def search_files(self, query, path='.', pattern='*'):
        if not query: raise LocalToolError('query is required')
        root = self._path(path); matches=[]
        for x in root.rglob('*'):
            if x.is_file() and fnmatch.fnmatch(x.name, pattern):
                for n, line in enumerate(x.read_text(encoding='utf-8', errors='ignore').splitlines(), 1):
                    if query.lower() in line.lower(): matches.append({'path': str(x.relative_to(self.root)), 'line': n, 'text': line[:500]})
        return {'query': query, 'matches': matches}
    def execute(self, name, arguments=None):
        return getattr(self, name)(**(arguments or {})) if name in ('list_files','read_file','search_files') else (_ for _ in ()).throw(LocalToolError(f'Unknown local tool: {name}'))
