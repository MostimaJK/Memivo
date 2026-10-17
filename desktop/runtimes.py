"""Owned optional environments; staged validation, fixed recipes, bounded logs.

Recipe sources (checked 2026-10-17):
https://pytorch.org/get-started/previous-versions/#v291
https://docs.ultralytics.com/quickstart/
No driver, CUDA toolkit, model weights or global Python installations are changed.
"""
from collections import deque
import csv
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import traceback

from album.core import save_json

ROOT = Path(__file__).resolve().parents[1]
FEATURES = {'vision': 'YOLO / SAM3', 'face': 'Face recognition'}
CLIP_SOURCE = 'https://github.com/ultralytics/CLIP/archive/7ffa84b3bfa40c42ecc1c77147a855e69cb2dd40.zip'
TORCH_CHECK = """import json, torch, torchvision, ultralytics
from ultralytics.models.sam import SAM3SemanticPredictor
from clip.simple_tokenizer import SimpleTokenizer
from timm.layers import DropPath, Mlp
from torchvision.ops import nms
assert SimpleTokenizer().encode('pen')
device = 'cuda' if PROFILE == 'cu128' else 'cpu'
if device == 'cuda' and not torch.cuda.is_available():
    raise RuntimeError('CUDA is not available after installation; check the NVIDIA driver.')
x = torch.ones((16,16),device=device)
(x @ x).cpu()
nms(torch.tensor([[0.,0.,10.,10.]],device=device),torch.tensor([.9],device=device),.5).cpu()
print(json.dumps(dict(torch=torch.__version__, cuda=torch.version.cuda, device=device)))
"""
FACE_CHECK = "from desktop.face_runtime import verify_face_runtime; verify_face_runtime(PROFILE)"


def child_options():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}


def clean_environment():
    env = os.environ.copy()
    for key in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'PIP_TARGET', 'PIP_PREFIX', 'PIP_USER'):
        env.pop(key, None)
    env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', PIP_DISABLE_PIP_VERSION_CHECK='1',
               PIP_CONFIG_FILE=os.devnull)
    return env


def probe_hardware(home):
    info = dict(os=platform.system(), architecture=platform.machine(),
                python=platform.python_version(), python_path=sys.executable,
                free_gb=round(shutil.disk_usage(home).free / 1024**3, 1),
                gpus=[], cuda_candidate=False, recommended='cpu', checked=True)
    command = shutil.which('nvidia-smi')
    if command:
        try:
            output = subprocess.run([command, '--query-gpu=name,driver_version,memory.total,compute_cap',
                                     '--format=csv,noheader,nounits'], capture_output=True,
                                    text=True, timeout=10, **child_options())
            if output.returncode:
                raise ValueError('nvidia-smi GPU query failed: ' + (output.stderr or output.stdout).strip()[:500])
            for row in csv.reader(io.StringIO(output.stdout)):
                if len(row) == 4:
                    info['gpus'].append(dict(name=row[0].strip(), driver=row[1].strip(),
                                             memory_mb=int(float(row[2])), capability=float(row[3])))
            summary = subprocess.run([command], capture_output=True, text=True, timeout=10, **child_options())
            if summary.returncode:
                raise ValueError('nvidia-smi summary failed: ' + (summary.stderr or summary.stdout).strip()[:500])
            version = re.search(r'CUDA\s+(?:UMD\s+)?Version\s*:\s*(\d+)\.(\d+)', summary.stdout, re.IGNORECASE)
            if version is None:
                info['diagnostic'] = 'Could not read CUDA / CUDA UMD Version from nvidia-smi; GPU compatibility is unconfirmed.'
                return info
            maximum = tuple(map(int, version.groups())) if version else (0, 0)
            info['driver_cuda_max'] = '.'.join(map(str, maximum))
            # Conservative candidate only. Actual tensor and torchvision checks are mandatory.
            info['cuda_candidate'] = maximum >= (12, 8) and any(8 <= g['capability'] <= 12 for g in info['gpus'])
            if info['cuda_candidate']:
                info['recommended'] = 'cu128'
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            info['diagnostic'] = str(exc)
    return info


class RuntimeManager:
    def __init__(self, home):
        self.root = (Path(home) / 'runtimes').resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.logs = deque(maxlen=80)
        self.log_root = self.root / 'logs'
        self.log_root.mkdir(exist_ok=True)
        self.last_log_file = ''
        self.last_failure = None
        self.detection_worker = None
        try:
            self.last_failure = json.loads((self.log_root/'last-failure.json').read_text(encoding='utf-8'))
            self.last_log_file = self.last_failure.get('log_file', '')
        except (OSError, ValueError, AttributeError):
            self.last_failure=None
        self.hardware = None
        self.records = {}
        self.process = None
        self.last_feature = ''
        for feature in FEATURES:
            try:
                record = json.loads((self.root / feature / '.memivo-runtime.json').read_text(encoding='utf-8'))
                if record.get('feature') == feature:
                    if record.get('state') == 'installing':
                        record.update(state='failed', error='Installation was interrupted. Retry to repair.')
                    self.records[feature] = record
            except (OSError, ValueError, AttributeError):
                pass

    def directory(self, feature):
        if feature not in FEATURES:
            raise ValueError('Unknown optional engine.')
        path = self.root / feature
        if path.is_symlink() or path.resolve().parent != self.root:
            raise ValueError('Managed environment path is invalid.')
        return path

    def executable(self, feature):
        return self.directory(feature) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

    def python_for(self, feature):
        with self.lock:
            record = self.records.get(feature, {})
            return self.executable(feature) if record.get('state') == 'ready' and self.executable(feature).is_file() else None

    def snapshot(self):
        with self.lock:
            return dict(hardware=self.hardware, engines=[dict(id=feature, **self.records.get(feature, {'state':'missing'}),
                       available=self.python_for(feature) is not None) for feature in FEATURES],
                       logs=list(self.logs), last_feature=self.last_feature, root=str(self.root),
                       log_root=str(self.log_root), log_file=self.last_log_file, last_failure=self.last_failure)

    def log(self, line):
        with self.lock:
            self.logs.append(str(line).strip()[-1500:])

    def save(self, feature, **changes):
        with self.lock:
            record = dict(self.records.get(feature, {}), feature=feature, **changes)
            save_json(self.directory(feature) / '.memivo-runtime.json', record)
            self.records[feature] = record

    def capture_exception(self, operation, error):
        """Keep diagnostics even for failures outside a managed subprocess."""
        if self.last_failure and self.last_failure.get('message') == str(error):
            return self.last_failure.get('log_file', '')
        path=self.log_root/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:10]+'-task.log')
        path.write_text(f'Memivo task: {operation}\n'+traceback.format_exc(),encoding='utf-8')
        failure=dict(message=str(error),log_file=str(path),time=time.strftime('%Y-%m-%d %H:%M:%S'),operation=operation)
        with self.lock:
            self.last_log_file=str(path)
            self.last_failure=failure
        save_json(self.log_root/'last-failure.json',failure)
        return str(path)

    def scan(self):
        info = probe_hardware(self.root)
        with self.lock:
            self.hardware = info
        return '环境检测完成。'

    def terminate(self, process):
        if process.poll() is not None:
            return
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=15, **child_options())
        else:
            os.killpg(process.pid, signal.SIGTERM)

    def run(self, command, cancelled, progress=None, timeout=3600):
        env=clean_environment()
        env['YOLO_CONFIG_DIR']=str(self.root/'ultralytics-settings')
        env['MPLCONFIGDIR']=str(self.root/'matplotlib-settings')
        env['YOLO_AUTOINSTALL']='false'
        log_path = self.log_root / (time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:10]+'.log')
        output_log = log_path.open('w', encoding='utf-8', buffering=1)
        output_log.write('Memivo engine subprocess\n')
        with self.lock:
            self.last_log_file = str(log_path)
        try:
            process = subprocess.Popen([str(c) for c in command], cwd=ROOT,
                                   env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                   **child_options())
        except Exception:
            output_log.close()
            raise
        with self.lock:
            self.process = process
        tail = deque(maxlen=12)
        def consume():
            for line in process.stdout:
                output_log.write(line)
                if line.strip():tail.append(line.strip())
                if line.startswith('MEMIVO_PROGRESS:') and progress:
                    try:
                        progress(*json.loads(line.removeprefix('MEMIVO_PROGRESS:')))
                    except (ValueError, TypeError):
                        self.log(line)
                else:
                    self.log(line)
        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        start = time.monotonic()
        try:
            while process.poll() is None:
                if cancelled() or time.monotonic() - start > timeout:
                    self.terminate(process)
                    process.wait(timeout=15)
                    raise RuntimeError('Operation cancelled.' if cancelled() else 'Operation timed out.')
                time.sleep(.1)
            reader.join(5)
            if cancelled():
                raise RuntimeError('Operation cancelled.')
            if process.returncode:
                detail='\n'.join(tail)[-2400:] or 'No output was produced by the subprocess.'
                message=f'Engine command failed (exit {process.returncode}).\n{detail}\nLog: {log_path}'
                failure=dict(message=message,returncode=process.returncode,log_file=str(log_path),
                             time=time.strftime('%Y-%m-%d %H:%M:%S'),feature=self.last_feature)
                with self.lock:
                    self.last_failure=failure
                save_json(self.log_root/'last-failure.json',failure)
                raise RuntimeError(message)
        finally:
            reader.join(2)
            process.stdout.close()
            output_log.close()
            with self.lock:
                self.process = None

    def install(self, feature, profile, cancelled, progress):
        target = self.directory(feature)
        if profile not in ('auto','cpu','cu128'):
            raise ValueError('Unknown engine profile.')
        if self.python_for(feature):
            raise ValueError('请先卸载当前引擎，再切换安装方案。')
        if self.hardware is None:
            self.scan()
        profile = self.hardware['recommended'] if profile == 'auto' else profile
        if profile == 'cu128' and not self.hardware['cuda_candidate']:
            raise ValueError('当前驱动或显卡未满足此 GPU 方案，请选择 CPU。')
        if platform.system() not in ('Windows','Linux') or platform.machine().lower() not in ('amd64','x86_64'):
            raise ValueError('自动安装目前支持 Windows/Linux x64。')
        if not (3, 10) <= sys.version_info[:2] <= (3, 12):
            raise ValueError('自动安装请使用 Python 3.10 至 3.12 启动主程序。')
        minimum = 12 if profile == 'cu128' else 4
        if shutil.disk_usage(self.root).free < minimum * 1024**3:
            raise ValueError(f'安装前至少预留 {minimum} GB 磁盘空间。')
        if target.exists():
            try:
                owner = json.loads((target / '.memivo-runtime.json').read_text(encoding='utf-8')).get('feature')
            except (OSError, ValueError, AttributeError):
                owner = None
            if owner != feature:
                raise ValueError('环境目录不属于 Memivo，拒绝覆盖。')
        target.mkdir(exist_ok=True)
        with self.lock:
            self.logs.clear()
            self.last_feature = feature
        self.save(feature, state='installing', profile=profile, error='')
        python = self.executable(feature)
        def step(number, label, command):
            progress(number-1, 5, label)
            self.log(label)
            self.run(command, cancelled)
        try:
            bootstrap = getattr(sys, '_base_executable', sys.executable)
            step(1, '创建独立 Python 环境…', [bootstrap,'-m','venv',target])
            pip = [python,'-m','pip','--isolated','install','--no-cache-dir','--index-url','https://pypi.org/simple']
            step(2, '准备安装工具…', pip + ['pip>=24,<26','setuptools<81','wheel'])
            if feature == 'vision':
                step(3, '安装 PyTorch 运行库…', [python,'-m','pip','--isolated','install','--no-cache-dir',
                     'torch==2.9.1','torchvision==0.24.1','--index-url',f'https://download.pytorch.org/whl/{profile}'])
                constraints = target / 'memivo-constraints.txt'
                constraints.write_text('torch==2.9.1\ntorchvision==0.24.1\n',encoding='utf-8')
                step(4, '安装视觉模型依赖…', pip + ['-c',constraints,'ultralytics==8.4.178','timm>=1.0,<2',CLIP_SOURCE])
                check = "PROFILE="+repr(profile)+'\n'+TORCH_CHECK
            else:
                runtime = (['onnxruntime-gpu[cuda,cudnn]==1.23.2',
                            'nvidia-cuda-runtime-cu12==12.8.90', 'nvidia-cuda-nvrtc-cu12==12.8.93',
                            'nvidia-cublas-cu12==12.8.4.1', 'nvidia-cudnn-cu12==9.10.2.21',
                            'nvidia-cufft-cu12==11.3.3.83', 'nvidia-curand-cu12==10.3.9.90']
                           if profile == 'cu128' else ['onnxruntime==1.23.2'])
                step(3, '安装人脸运行库…', pip + ['numpy>=1.26,<2','Pillow>=10,<13','opencv-python>=4.10,<4.12'] + runtime)
                # InsightFace can require local C++ build tools; never install a compiler silently.
                step(4, '安装人脸模型依赖…', pip + ['numpy>=1.26,<2','opencv-python>=4.10,<4.12','insightface==0.7.3'])
                check = "PROFILE="+repr(profile)+'\n'+FACE_CHECK
            step(5, '验证引擎与执行设备…', [python,'-c',check])
            self.run([python,'-m','pip','check'],cancelled)
            size = sum(p.stat().st_size for p in target.rglob('*') if p.is_file())
            self.save(feature, state='ready', profile=profile, bytes=size, error='')
            progress(5,5,'引擎安装并验证完成。')
            return '引擎安装并验证完成。'
        except Exception as exc:
            self.save(feature,state='failed',error=str(exc))
            raise

    def uninstall(self, feature):
        self.close_detection()
        target = self.directory(feature)
        if not target.exists():
            return '引擎未安装。'
        marker = target / '.memivo-runtime.json'
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')).get('feature') != feature:
            raise ValueError('环境目录不属于 Memivo，拒绝删除。')
        # Check resolved absolute target immediately before recursive removal.
        if target.resolve().parent != self.root or target.resolve() == self.root:
            raise ValueError('Managed environment path is invalid.')
        shutil.rmtree(target)
        with self.lock:
            self.records.pop(feature,None)
            self.log('已卸载引擎，模型与项目数据保留。')
        return '已卸载引擎，模型与项目数据保留。'

    def close_detection(self):
        if self.detection_worker is not None:self.detection_worker.close()

    def detect_job(self, python, payload, cancelled, progress):
        from .inference_worker import DetectionWorker
        self.last_feature='vision'
        if self.detection_worker is None:self.detection_worker=DetectionWorker(self)
        return self.detection_worker.request(python,payload,cancelled,progress)

    def job(self, feature, action, payload, cancelled, progress):
        python = self.python_for(feature)
        if python is None:
            raise ValueError('可选引擎尚未就绪，请先在功能中心安装。')
        with self.lock:
            self.last_feature=feature
            self.logs.clear()
            self.last_log_file=''
        device=payload.get('device',payload.get('config',{}).get('device',payload.get('options',{}).get('device','cpu')))
        self.log(f'Engine: {feature}; action: {action}; device: {device}; profile: {self.records.get(feature,{}).get("profile")}')
        if device == 'cuda' and self.records.get(feature,{}).get('profile') != 'cu128':
            raise ValueError('当前引擎为 CPU 版，但执行设备设为 NVIDIA CUDA。请安装 NVIDIA 引擎，或在设置中改用 CPU。')
        if action=='detect':
            return self.detect_job(python,payload,cancelled,progress)
        # Release cached YOLO VRAM before SAM3, training, evaluation or face jobs.
        self.close_detection()
        with tempfile.TemporaryDirectory(prefix='job-',dir=self.root) as folder:
            request, result = Path(folder)/'request.json', Path(folder)/'result.json'
            save_json(request,dict(action=action,payload=payload,result=str(result)))
            self.run([python,ROOT/'scripts/runtime_worker.py',request],cancelled,progress)
            return json.loads(result.read_text(encoding='utf-8'))
