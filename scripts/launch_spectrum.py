"""One-click bootstrap: isolated Python environment + locked frontend build."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd=ROOT):
    print('> ' + subprocess.list2cmdline([str(c) for c in command]), flush=True)
    subprocess.run([str(c) for c in command], cwd=cwd, check=True)


def python_candidate():
    explicit = (os.environ.get('MEMIVO_PYTHON') or os.environ.get('SEGMENTFLOW_PYTHON'))
    if explicit:
        return Path(explicit)
    # Reuse a user-configured inference environment when it is explicitly active.
    if os.environ.get('CONDA_DEFAULT_ENV') in ('memivo-album', 'segmentflow-album'):
        return Path(sys.executable)
    registry = Path.home() / '.conda/environments.txt'
    if registry.exists():
        for line in registry.read_text(encoding='utf-8').splitlines():
            path = Path(line.strip())
            if path.name in ('memivo-album', 'segmentflow-album') and (path / 'python.exe').is_file():
                return path / 'python.exe'
    return ROOT / '.venv-spectrum' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def build_fingerprint():
    digest = hashlib.sha256()
    for path in sorted(list((ROOT/'frontend/src').rglob('*')) + list((ROOT/'frontend/public').rglob('*')) +
                       [ROOT/'frontend/package.json', ROOT/'frontend/package-lock.json',
                        ROOT/'frontend/index.html', ROOT/'frontend/vite.config.ts', ROOT/'frontend/tsconfig.json']):
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Read-only environment check')
    parser.add_argument('--browser', action='store_true', help='Open browser instead of WebView desktop window')
    parser.add_argument('--rebuild', action='store_true')
    args = parser.parse_args()
    python = python_candidate()
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if args.check:
        print(f'Python: {python} ({"found" if python.is_file() else "will create isolated environment"})')
        print(f'Node/npm: {npm or "not installed"}')
        print(f'Frontend built: {(ROOT/"frontend/dist/index.html").is_file()}')
        if python.is_file():
            run([python,'-c',"import importlib.util,json; print(json.dumps({n:importlib.util.find_spec(n) is not None for n in ['numpy','PIL','webview','cv2','onnxruntime','insightface','ultralytics']}))"])
        return 0
    if not python.is_file():
        if (os.environ.get('MEMIVO_PYTHON') or os.environ.get('SEGMENTFLOW_PYTHON')):
            raise FileNotFoundError('MEMIVO_PYTHON (or legacy SEGMENTFLOW_PYTHON) does not point to a Python executable.')
        bootstrap = Path(sys.executable)
        # Prefer an already installed uv-managed Python 3.12; do not download runtimes.
        uv_root = Path(os.environ.get('APPDATA', '')) / 'uv/python'
        options = sorted(uv_root.glob('cpython-3.12.*-windows-x86_64-none/python.exe')) if os.name == 'nt' else []
        if options:
            bootstrap = options[-1]
        run([bootstrap,'-m','venv',ROOT/'.venv-spectrum'])
    check = subprocess.run([str(python),'-c','import numpy,PIL,webview'], capture_output=True)
    if check.returncode:
        run([python,'-m','pip','install','-r',ROOT/'requirements-spectrum.txt'])
    marker = ROOT / '.segmentflow/frontend-build.sha256'
    fingerprint = build_fingerprint()
    fresh = (ROOT/'frontend/dist/index.html').is_file() and marker.is_file() and marker.read_text() == fingerprint
    if args.rebuild or not fresh:
        if not npm:
            raise RuntimeError('Install Node.js LTS from https://nodejs.org/ and double-click the BAT again.')
        front = ROOT/'frontend'
        lock_hash = hashlib.sha256((front/'package-lock.json').read_bytes()).hexdigest()
        modules_marker = front/'node_modules/.segmentflow-lock'
        if not modules_marker.is_file() or modules_marker.read_text() != lock_hash:
            run([npm,'ci','--no-fund','--no-audit'], front)
            modules_marker.write_text(lock_hash)
        run([npm,'run','build'], front)
        marker.parent.mkdir(exist_ok=True)
        marker.write_text(fingerprint)
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    command = [str(python),str(ROOT/'spectrum_app.py')]
    if args.browser:
        command.append('--browser')
    print('Opening Memivo Spectrum...', flush=True)
    return subprocess.call(command, cwd=ROOT, env=env)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'\n[ERROR] {exc}\nSee docs/SPECTRUM_DESKTOP.md for setup and troubleshooting.', flush=True)
        raise SystemExit(1)
