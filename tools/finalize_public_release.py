"""Repack the public portable app with SETUPGAME.exe at its root."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'dist' / 'LivingPlanet'
ARCHIVE = ROOT / 'dist' / 'LivingPlanet-8.5.3-Portable.zip'


def main():
    if not (APP / 'SETUPGAME.exe').is_file():
        raise SystemExit('SETUPGAME.exe must be copied to the LivingPlanet root first.')
    weights = list(APP.rglob('*.gguf'))
    if weights:
        raise SystemExit('Public package must not contain GGUF model weights.')
    temporary = ARCHIVE.with_suffix('.tmp.zip')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(APP.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(ROOT / 'dist').as_posix())
    temporary.replace(ARCHIVE)
    print(f'Final public package: {ARCHIVE}')


if __name__ == '__main__':
    main()
