"""The publication allowlist deliberately has no knowledge of local save paths."""
from pathlib import Path
import ast,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'main.py','README.md','CHANGELOG.md','CONTRIBUTING.md','requirements.txt','config.example.json','install.bat','run.bat','.gitignore','.gitattributes'}
FOLDERS={'planet','tests','docs','tools','.github'}
FORBIDDEN={'__pycache__','.git','.venv','saves','data','logs','work','backups','states'}

def public_files(root=ROOT):
    files=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        rel=path.relative_to(root)
        if any(p in FORBIDDEN for p in rel.parts):continue
        if len(rel.parts)==1 and rel.name not in ROOT_FILES:continue
        if len(rel.parts)>1 and rel.parts[0] not in FOLDERS:continue
        if path.suffix not in ('.py','.md','.html','.png','.json','.txt','.yml','.yaml','.bat','') and path.name not in ('.gitignore','.gitattributes'):continue
        if path.name=='config.json' or path.suffix in ('.jsonl','.sqlite3','.db','.log','.pyc'):continue
        files.append(path)
    return files

def check(root=ROOT):
    files=public_files(root);errors=[];markdown=[]
    for path in files:
        rel=path.relative_to(root).as_posix()
        if path.suffix=='.png':
            if rel!='docs/assets/interface.png':errors.append('Unexpected image: '+rel)
            continue
        content=path.read_text(encoding='utf-8-sig')
        if re.search(r'(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,}|sk-[A-Za-z0-9_-]{25,})',content):errors.append('Possible credential: '+rel)
        if re.search(r'[A-Z]:\\Users\\[^\s"\']+',content):errors.append('Machine-specific user path: '+rel)
        if path.suffix=='.py':
            try:ast.parse(content,filename=rel)
            except SyntaxError as exc:errors.append(str(exc))
        if path.suffix=='.md':markdown.append((path,content))
    for path,content in markdown:
        if content.count('```')%2:errors.append('Unclosed code block: '+path.name)
        for url in re.findall(r'\]\(([^)]+)\)',content):
            if url.startswith(('http:','https:','#','mailto:')):continue
            target=(path.parent/url.split('#')[0]).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():errors.append('Broken local link: '+path.name+' → '+url)
    config=json.loads((root/'config.example.json').read_text(encoding='utf-8'))
    if config.get('api_key') or config.get('model') or config.get('state_models'):errors.append('Example configuration must be neutral and unauthenticated')
    if config.get('saves_directory')!='saves':errors.append('Nonportable save directory')
    if not (root/'docs/index.html').is_file():errors.append('Offline manual missing')
    report=dict(files=len(files),bytes=sum(p.stat().st_size for p in files),errors=errors)
    if errors:raise ValueError(json.dumps(report,ensure_ascii=False))
    return report

if __name__=='__main__':print(json.dumps(check(),ensure_ascii=False))
