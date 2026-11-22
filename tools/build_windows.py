"""Build the Windows application bundle and portable ZIP for a tagged release."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='8.0.1'
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
    run(sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir',
        '--name','LivingPlanet','--icon',str(ROOT/'docs/assets/living-planet.ico'),
        '--distpath',str(DIST),'--workpath',str(BUILD),'--specpath',str(BUILD),
        '--collect-all','planet',
        '--add-data',f"{ROOT / 'docs/assets/living-planet.ico'}{os.pathsep}assets",'main.py')
    if not (APP/'LivingPlanet.exe').is_file():
        raise SystemExit('PyInstaller did not create LivingPlanet.exe')
    archive=DIST/f'LivingPlanet-{VERSION}-Portable.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for path in sorted(APP.rglob('*')):
            if path.is_file():
                bundle.write(path,path.relative_to(DIST).as_posix())
    print(f'Built {APP / "LivingPlanet.exe"}')
    print(f'Built {archive} ({archive.stat().st_size:,} bytes)')

if __name__=='__main__':
    main()
