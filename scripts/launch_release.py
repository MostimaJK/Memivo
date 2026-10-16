"""Prebuilt-front-end release bootstrap. External Python; no Node.js required."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    home=Path(os.environ.get('MEMIVO_RELEASE_HOME',Path.home()/'AppData/Local/Memivo'))
    home.mkdir(parents=True,exist_ok=True)
    python=home/'ui/Scripts/python.exe'
    info=dict(python=sys.version.split()[0],interpreter=sys.executable,frontend=(ROOT/'frontend/dist/index.html').is_file(),
              ui_environment=python.is_file(),data=os.environ.get('MEMIVO_HOME'),model_root=os.environ.get('MEMIVO_MODEL_ROOT'),app=str(ROOT))
    if args.check:
        (home/'release-check.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(info,ensure_ascii=False),flush=True)
        return 0 if info['frontend'] and (3,10)<=sys.version_info[:2]<=(3,12) else 1
    if not info['frontend']:raise RuntimeError('The prebuilt frontend is missing. Extract the complete ZIP.')
    if not python.is_file():
        print('Creating the isolated UI environment…',flush=True)
        subprocess.run([getattr(sys,'_base_executable',sys.executable),'-m','venv',str(home/'ui')],check=True)
    check=subprocess.run([str(python),'-c','import numpy,PIL,webview'],capture_output=True)
    if check.returncode:
        print('Downloading UI dependencies. AI engines are installed separately in Feature center.',flush=True)
        subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements-spectrum.txt')],check=True)
    subprocess.run([str(python),str(ROOT/'spectrum_app.py')],cwd=ROOT,check=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
