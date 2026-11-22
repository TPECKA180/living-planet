"""Fetch the official llama.cpp Windows Vulkan runtime into the local build tree."""
from pathlib import Path
import json
import shutil
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TAG='b12628'
ASSET=f'llama-{TAG}-bin-win-vulkan-x64.zip'
API=f'https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{TAG}'

def main():
    target=ROOT/'runtime'
    license_file=target/'LICENSE-llama.cpp.txt'
    if (target/'llama-server.exe').is_file():
        if not license_file.is_file():
            request=urllib.request.Request(f'https://raw.githubusercontent.com/ggml-org/llama.cpp/{TAG}/LICENSE',headers={'User-Agent':'Living-Planet-build'})
            with urllib.request.urlopen(request,timeout=30) as response:license_file.write_bytes(response.read())
        return
    request=urllib.request.Request(API,headers={'User-Agent':'Living-Planet-build'})
    with urllib.request.urlopen(request,timeout=30) as response: release=json.load(response)
    asset=next((item for item in release['assets'] if item['name']==ASSET),None)
    if not asset:raise SystemExit(f'Official llama.cpp runtime not found: {ASSET}')
    staging=ROOT/'build'/'runtime-download';staging.mkdir(parents=True,exist_ok=True)
    archive=staging/ASSET
    request=urllib.request.Request(asset['browser_download_url'],headers={'User-Agent':'Living-Planet-build'})
    with urllib.request.urlopen(request,timeout=180) as response,archive.open('wb') as output:
        shutil.copyfileobj(response,output,1024*1024)
    extracted=staging/'extracted';shutil.rmtree(extracted,ignore_errors=True);extracted.mkdir()
    with zipfile.ZipFile(archive) as bundle:bundle.extractall(extracted)
    server=next(iter(extracted.rglob('llama-server.exe')),None)
    if server is None:raise SystemExit('The official archive contains no llama-server.exe')
    target.mkdir(parents=True,exist_ok=True)
    for path in server.parent.iterdir():
        if path.is_file():shutil.copy2(path,target/path.name)
    if not (target/'llama-server.exe').is_file():raise SystemExit('Could not stage llama-server.exe')
    request=urllib.request.Request(f'https://raw.githubusercontent.com/ggml-org/llama.cpp/{TAG}/LICENSE',headers={'User-Agent':'Living-Planet-build'})
    with urllib.request.urlopen(request,timeout=30) as response:license_file.write_bytes(response.read())
    archive.unlink();shutil.rmtree(extracted,ignore_errors=True)
    print(f'Staged llama.cpp {TAG} Windows Vulkan runtime ({asset["size"]:,} bytes).')

if __name__=='__main__':main()
