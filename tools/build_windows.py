"""Build the Windows application bundle and portable ZIP for a tagged release."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='8.5.1'
DIST=ROOT/'dist'
BUILD=ROOT/'build'/'pyinstaller'
APP=DIST/'LivingPlanet'

def run(*args):
    subprocess.run(args,cwd=ROOT,check=True)

def main():
    if os.name!='nt':
        raise SystemExit('This release builder must run on Windows.')
    shutil.rmtree(DIST,ignore_errors=True)
    shutil.rmtree(BUILD,ignore_errors=True)
    private_temp=BUILD/'tmp'
    private_temp.mkdir(parents=True,exist_ok=True)
    os.environ['TEMP']=str(private_temp)
    os.environ['TMP']=str(private_temp)
    os.environ['PYINSTALLER_CONFIG_DIR']=str(BUILD/'config')
    run(sys.executable,'tools/create_windows_icon.py')
    if not (ROOT/'runtime/llama-server.exe').is_file():
        run(sys.executable,'tools/prepare_runtime.py')
    run(sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir',
        '--name','LivingPlanet','--icon',str(ROOT/'docs/assets/living-planet.ico'),
        '--distpath',str(DIST),'--workpath',str(BUILD),'--specpath',str(BUILD),
        '--collect-all','planet',
        '--add-data',f"{ROOT / 'docs/assets/living-planet.ico'}{os.pathsep}assets",
        '--add-data',f"{ROOT / 'docs/assets/living-planet-logo.png'}{os.pathsep}assets",'main.py')
    if not (APP/'LivingPlanet.exe').is_file():
        raise SystemExit('PyInstaller did not create LivingPlanet.exe')
    shutil.copytree(ROOT/'docs',APP/'docs',dirs_exist_ok=True)
    if not (APP/'docs/index.html').is_file():
        raise SystemExit('The offline help page was not copied into the game folder.')
    shutil.copytree(ROOT/'runtime',APP/'runtime',dirs_exist_ok=True)
    ignored=['*.tmp','*.partial']
    if os.environ.get('LIVING_PLANET_PUBLIC')=='1':ignored.append('*.gguf')
    shutil.copytree(ROOT/'models',APP/'models',dirs_exist_ok=True,ignore=shutil.ignore_patterns(*ignored))
    archive=DIST/f'LivingPlanet-{VERSION}-Portable.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for path in sorted(APP.rglob('*')):
            if path.is_file():
                if os.environ.get('LIVING_PLANET_PUBLIC')=='1' and path.suffix=='.gguf':continue
                bundle.write(path,path.relative_to(DIST).as_posix(),compress_type=zipfile.ZIP_STORED if path.suffix=='.gguf' else zipfile.ZIP_DEFLATED)
    print(f'Built {APP / "LivingPlanet.exe"}')
    print(f'Built {archive} ({archive.stat().st_size:,} bytes)')

if __name__=='__main__':
    main()
