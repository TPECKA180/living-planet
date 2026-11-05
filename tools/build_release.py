"""Create a clean, reproducible source release. No local config or saves allowed."""
from pathlib import Path
import hashlib,json,zipfile
from check_release import ROOT,check,public_files

def build(destination=None):
    report=check();destination=Path(destination or ROOT/'dist/LivingPlanet-7.5.6.zip')
    destination.parent.mkdir(parents=True,exist_ok=True)
    files=public_files();manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as out:
        for path in files:
            item=zipfile.ZipInfo('LivingPlanet/'+path.relative_to(ROOT).as_posix(),date_time=(2026,10,30,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=0o100644<<16
            out.writestr(item,path.read_bytes())
        item=zipfile.ZipInfo('LivingPlanet/RELEASE-MANIFEST.json',date_time=(2026,10,30,0,0,0))
        item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=0o100644<<16
        out.writestr(item,json.dumps(dict(version='7.5.6',files=manifest),ensure_ascii=False,sort_keys=True,indent=2))
    with zipfile.ZipFile(destination) as result:
        assert result.testzip() is None
        assert not any('/saves/' in name or name.endswith('/config.json') or '.sqlite' in name or name.endswith('.jsonl') for name in result.namelist())
    return dict(**report,archive=str(destination),sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),archive_bytes=destination.stat().st_size)

if __name__=='__main__':print(json.dumps(build()))
