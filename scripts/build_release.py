"""Build a small Windows EXE launcher plus prebuilt application files."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.3.13-preview'


def main():
    destination=ROOT/'release'/f'Memivo-{VERSION}-windows-x64'
    if destination.exists():raise RuntimeError('Release output already exists; inspect it before using a new output directory.')
    destination.mkdir(parents=True)
    app=destination/'app';app.mkdir()
    for folder in ('album','desktop'):
        shutil.copytree(ROOT/folder,app/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (app/'scripts').mkdir()
    for file in ('runtime_worker.py','detection_worker.py','launch_release.py'):
        shutil.copy2(ROOT/'scripts'/file,app/'scripts'/file)
    for file in ('spectrum_app.py','sam_backend.py','requirements-spectrum.txt'):
        shutil.copy2(ROOT/file,app/file)
    shutil.copytree(ROOT/'frontend/dist',app/'frontend/dist')
    shutil.copytree(ROOT/'docs',destination/'docs')
    for name in ('README.md','THIRD_PARTY_NOTICES.md','RELEASE_NOTES.md','LICENSE','NOTICE'):
        shutil.copy2(ROOT/name,destination/name)
    # Include the preferred form for modifying the app, frontend and launcher,
    # plus the scripts and dependency locks needed to rebuild this release.
    source_archive=destination/f'Memivo-{VERSION}-source.zip'
    source_roots=('album','desktop','docs','frontend/src','frontend/public',
                  'packaging','scripts','tests','model')
    source_files={p for folder in source_roots for p in (ROOT/folder).rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts
                  and p.suffix not in ('.pyc','.pt','.onnx')}
    source_files.update(p for p in ROOT.iterdir() if p.is_file() and
                        (p.suffix in ('.py','.md','.txt','.bat','.json')
                         or p.name in ('LICENSE','NOTICE','.gitignore')))
    source_files.update(ROOT/'frontend'/name for name in
                        ('package.json','package-lock.json','index.html','tsconfig.json','vite.config.ts'))
    with zipfile.ZipFile(source_archive,'w',zipfile.ZIP_DEFLATED) as source:
        for file in sorted(source_files):
            source.write(file,file.relative_to(ROOT))
    (destination/'SOURCE.txt').write_text(
        f'Memivo original code: GPL-3.0-only; see LICENSE and NOTICE.\n'
        f'Corresponding project source: {source_archive.name}\n'
        'Extract the source ZIP into a separate folder. See README.md for dependencies.\n'
        'Rebuild on Windows: cd frontend; npm ci; npm run build; cd ..\n'
        'Then run: python scripts/build_release.py\n'
        'The source includes the C# launcher, Python backend, frontend, tests,\n'
        'build scripts and dependency manifests. Third-party terms apply separately.\n',encoding='utf-8')
    for directory in ('face/detector','face/recognition','sam3','yolo/detect','yolo/segment'):
        (destination/'model'/directory).mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'model/README.md',destination/'model/README.md')
    # Preserve upstream license/notice files for the bundled frontend packages.
    import json
    lock=json.loads((ROOT/'frontend/package-lock.json').read_text(encoding='utf-8'))
    for relative in lock['packages']:
        if not relative:continue
        package=ROOT/'frontend'/relative
        for notice in list(package.glob('LICENSE*'))+list(package.glob('LICENCE*'))+list(package.glob('NOTICE*')):
            if notice.is_file():
                safe=relative.replace('node_modules/','').replace('/','__')
                target=destination/'THIRD-PARTY'/safe/notice.name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(notice,target)
    compiler=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:x64',
        '/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll',
        '/win32icon:'+str(ROOT/'frontend/public/memivo.ico'),'/out:'+str(destination/'Memivo.exe'),
        str(ROOT/'packaging/MemivoLauncher.cs')],check=True)
    (destination/'START-HERE.txt').write_text('''Memivo — Organize memories, together.

1. Extract this entire folder. Keep Memivo.exe next to app/.
2. Install external Python 3.12 x64 and Microsoft Edge WebView2 Runtime.
   Windows 10/11 with .NET Framework 4.x is required by the small launcher.
3. Double-click Memivo.exe. First launch creates a UI environment and downloads UI dependencies.
4. Open Feature center to install optional AI engines. Configure local model weights separately.
5. Put weights into the matching model/ subfolder, then Scan models in Settings.
   Feature center offers official weight variants and verified YOLO downloads.

No Node.js, CUDA toolkit, model weights, Python runtime or AI engines are bundled.
NVIDIA GPU use needs a compatible driver. CPU is available.
Application data / UI environment / logs: %LOCALAPPDATA%/Memivo/
Read docs/LEARNING_WORKFLOW.md and docs/OPTIONAL_ENGINES.md.
Memivo.exe --check writes %LOCALAPPDATA%/Memivo/release-check.json.

This preview is not code-signed. It is a launcher with external dependencies, not a standalone executable.
''',encoding='utf-8')
    files=sorted(p for p in destination.rglob('*') if p.is_file())
    (destination/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(destination).as_posix() for p in files)+'\n',encoding='utf-8')
    archive=destination.parent/(destination.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for file in destination.rglob('*'):
            bundle.write(file,Path(destination.name)/file.relative_to(destination))
    print(destination)
    print(archive)


if __name__=='__main__':main()
