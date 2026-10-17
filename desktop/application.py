from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

from album.core import IMAGE_SUFFIXES, export_albums, save_json

ROOT = Path(__file__).resolve().parents[1]


class Application:
    def __init__(self, home=None, backend_factory=None, detection_factory=None):
        self.home = Path(home or os.environ.get('MEMIVO_HOME') or ROOT / '.segmentflow')
        self.home.mkdir(parents=True, exist_ok=True)
        from .runtimes import RuntimeManager
        self.runtimes = RuntimeManager(self.home)
        from .datasets import DatasetStore
        from .training import TrainingStore
        self.datasets = DatasetStore(self.home)
        self.training = TrainingStore(self.home,self.datasets,self.runtimes)
        from .models import ModelStore
        self.models = ModelStore(os.environ.get('MEMIVO_MODEL_ROOT') or (self.home/'model' if home is not None else ROOT/'model'))
        self.lock = threading.RLock()
        self.window = None
        self.backend_factory = backend_factory
        self.detection_factory = detection_factory
        self.detection = None
        self.cancel = threading.Event()
        self.worker = None
        self.report = None
        self.photos = []
        self.files = {}
        self.history = []
        self.undo_stack = []
        self.segment = None
        self.sam_backend = None
        self.config = dict(source='', workspace=str(self.home / 'project'), detector='',
                           recognition='', sam='', yolo='', device='cpu', threshold=.55, margin=.08, references={})
        self.preferences = {'language': 'zh-CN'}
        try:
            stored_preferences = json.loads((self.home / 'preferences.json').read_text(encoding='utf-8'))
            if stored_preferences.get('language') in ('zh-CN', 'zh-TW', 'en-US'):
                self.preferences['language'] = stored_preferences['language']
        except (OSError, ValueError, AttributeError):
            pass
        self.task = dict(state='idle', kind='', done=0, total=0, message='准备就绪')
        saved = self.home / 'session.json'
        if saved.exists():
            try:
                self.config.update(json.loads(saved.read_text(encoding='utf-8')))
                self.restore_report()
            except (OSError, ValueError, KeyError):
                self.task['message'] = '上次项目未能恢复，请重新打开项目。'

        self.refresh_models()

    def refresh_models(self):
        self.models.scan()
        with self.lock:
            changes=self.models.defaults(self.config)
            if changes:
                self.config.update(changes)
                self.persist()
        return {'models':self.models.snapshot(self.config)}

    def register(self, path):
        import hashlib
        path = Path(path).resolve()
        key = hashlib.sha256(str(path).encode()).hexdigest()[:24]
        self.files[key] = path
        return key

    def view_photo(self, photo, processed=True):
        result = dict(photo, id=self.register(photo['path']), name=Path(photo['path']).name, processed=processed)
        try:
            from PIL import Image
            with Image.open(photo['path']) as image:
                width, height = image.size
                if image.getexif().get(274, 1) in (5,6,7,8):
                    width, height = height, width
                result.update(width=width, height=height)
        except (OSError, ValueError):
            pass
        return result

    def restore_report(self):
        self.photos, self.files, self.report, self.undo_stack, self.segment = [], {}, None, [], None
        self.detection = None
        path = Path(self.config['workspace']) / 'report.json'
        if path.exists():
            self.report = json.loads(path.read_text(encoding='utf-8'))
            self.photos = [self.view_photo(p,p.get('processed',True)) for p in self.report['photos']]
        elif (Path(self.config['workspace']) / 'library.json').exists():
            records = json.loads((Path(self.config['workspace']) / 'library.json').read_text(encoding='utf-8'))
            self.photos = [self.view_photo(p, p.get('processed', False)) for p in records]
        for samples in self.config['references'].values():
            for sample in samples:
                self.register(sample)

    def persist(self):
        save_json(self.home / 'session.json', self.config)
        save_json(Path(self.config['workspace']) / 'project.json', self.config)
        save_json(Path(self.config['workspace']) / 'library.json', self.photos)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(dict(preferences=self.preferences, config=self.config, photos=self.photos, task=self.task,
                history=self.history[-30:], desktop=self.window is not None,
                dependencies={name: importlib.util.find_spec(name) is not None
                              for name in ('numpy', 'PIL', 'cv2', 'onnxruntime', 'insightface', 'ultralytics')},
                segment=self.segment, detection=self.detection, runtimes=self.runtimes.snapshot(),models=self.models.snapshot(self.config),
                datasets=self.datasets.snapshot(self.register),training=self.training.snapshot(),canUndo=bool(self.undo_stack)))

    def require_idle(self):
        if self.task['state'] == 'running':
            raise ValueError('请等待当前任务完成，或先停止任务。')

    @property
    def window_title(self):
        return {'zh-CN': 'Memivo · 影像工作台', 'zh-TW': 'Memivo · 影像工作臺',
                'en-US': 'Memivo · Photo workspace'}[self.preferences['language']]

    def start_task(self, kind, operation):
        with self.lock:
            self.require_idle()
            self.cancel.clear()
            self.task = dict(state='running', kind=kind, done=0, total=0, message='正在准备…')
            def run():
                started = time.perf_counter()
                try:
                    if kind in ('SAM3 分割','人物识别','训练模型','评估模型','转换 SAM3 标注'):
                        self.runtimes.close_detection()
                    message = operation()
                    with self.lock:
                        stopped = self.cancel.is_set()
                        self.task.update(state='cancelled' if stopped else 'completed',
                                         message=message or ('已停止' if stopped else '完成'))
                except Exception as exc:
                    try:
                        log_file=self.runtimes.last_log_file if self.cancel.is_set() else self.runtimes.capture_exception(kind,exc)
                    except Exception:
                        log_file=''
                    with self.lock:
                        self.task.update(state='cancelled' if self.cancel.is_set() else 'failed', message=str(exc), error=str(exc),log_file=log_file)
                finally:
                    with self.lock:
                        self.history.append(dict(self.task, seconds=round(time.perf_counter()-started, 2),
                                                 time=time.strftime('%H:%M:%S')))
            self.worker = threading.Thread(target=run, name='memivo-worker', daemon=True)
            self.worker.start()
        return {'ok': True}

    def progress(self, done, total, message):
        with self.lock:
            self.task.update(done=done, total=total, message=message)

    def action(self, route, data):
        if route == 'diagnostics-open':
            if os.name != 'nt' or self.window is None:
                raise ValueError('请在桌面程序中打开日志文件夹。')
            os.startfile(self.runtimes.log_root)
            return {'ok':True}
        if route == 'segment-open':
            if os.name != 'nt' or self.window is None:
                raise ValueError('请在桌面程序中打开结果文件夹。')
            with self.lock:
                if not self.segment or data.get('id') != self.segment['photo']:
                    raise ValueError('请先生成当前图像的分割结果。')
                folder = Path(self.segment['directory']).resolve()
            if folder.parent != (self.home/'segments').resolve() or not folder.is_dir():
                raise ValueError('结果文件夹不可用。')
            os.startfile(folder)
            return {'ok': True}
        if route == 'models-scan':
            self.require_idle()
            return self.refresh_models()
        if route == 'models-open':
            if os.name!='nt' or self.window is None:raise ValueError('请在桌面程序中打开模型文件夹。')
            os.startfile(self.models.root)
            return {'ok':True}
        if route == 'model-download':
            def download():
                message=self.models.download(data.get('id'),self.cancel.is_set,self.progress)
                self.refresh_models()
                return message
            return self.start_task('下载官方模型',download)
        if route.startswith('dataset-') or route.startswith('training-'):
            return self.learning_action(route,data)
        if route == 'preferences':
            if set(data) != {'language'} or data['language'] not in ('zh-CN', 'zh-TW', 'en-US'):
                raise ValueError('不支持的界面语言。')
            with self.lock:
                updated = {'language': data['language']}
                save_json(self.home / 'preferences.json', updated)
                self.preferences = updated
                if self.window is not None:
                    self.window.set_title(self.window_title)
            return {'ok': True}
        if route == 'cancel':
            self.cancel.set()
            return {'ok': True}
        if route == 'environment-detect':
            return self.start_task('检测计算机环境', self.runtimes.scan)
        if route == 'engine-install':
            feature, profile = data.get('feature'), data.get('profile','auto')
            self.runtimes.directory(feature)
            return self.start_task('安装可选引擎', lambda:self.runtimes.install(feature,profile,self.cancel.is_set,self.progress))
        if route == 'engine-uninstall':
            feature = data.get('feature')
            self.runtimes.directory(feature)
            return self.start_task('卸载可选引擎',lambda:self.runtimes.uninstall(feature))
        if route == 'scan':
            return self.scan(data['path'])
        if route == 'import-drop':
            return self.import_drop(data['path'])
        if route == 'recognize':
            return self.recognize()
        if route == 'export':
            with self.lock:
                if not self.report:
                    raise ValueError('请先运行识别并审核结果。')
                report = copy.deepcopy(self.report)
            def export():
                count = export_albums(report, data['path'], self.progress, self.cancel.is_set)
                return f'{"导出已停止" if self.cancel.is_set() else "导出完成"}：{count} 个人物照片关联'
            return self.start_task('导出原图', export)
        if route == 'segment':
            return self.segment_image(data)
        if route == 'detect':
            return self.detect_image(data)
        with self.lock:
            self.require_idle()
            if route == 'config':
                allowed = {'workspace','detector','recognition','sam','yolo','device','threshold','margin'}
                if set(data) - allowed:
                    raise ValueError('包含不支持的设置项。')
                updated = dict(self.config, **data)
                if updated['device'] not in ('cpu','cuda'):
                    raise ValueError('请选择 CPU 或 CUDA。')
                if not all(0 <= float(updated[k]) <= 1 for k in ('threshold','margin')):
                    raise ValueError('阈值必须介于 0 和 1 之间。')
                workspace = Path(updated['workspace']).resolve()
                source = Path(updated['source']).resolve() if updated['source'] else None
                if source and (workspace == source or source in workspace.parents):
                    raise ValueError('工作目录必须在照片目录之外。')
                # Workspace changes are a project switch, rather than moving an old report.
                if updated['workspace'] != self.config['workspace'] and self.photos:
                    raise ValueError('已有照片时请使用“打开项目”切换工作目录。')
                self.config = updated
                self.persist()
            elif route == 'open':
                config = json.loads(Path(data['path']).read_text(encoding='utf-8'))
                if not isinstance(config.get('references'), dict):
                    raise ValueError('不是有效的项目配置。')
                self.config.update(config)
                self.restore_report()
                self.persist()
            elif route == 'reference':
                name = str(data['name']).strip()
                paths = [str(Path(p).resolve()) for p in data['paths']]
                if not name or not paths or any(not Path(p).is_file() or Path(p).suffix.lower() not in IMAGE_SUFFIXES for p in paths):
                    raise ValueError('请填写姓名并选择有效的单人参考照片。')
                self.config['references'][name] = list(dict.fromkeys(self.config['references'].get(name, []) + paths))
                self.persist()
            elif route == 'remove-reference':
                self.config['references'].pop(data['name'], None)
                self.persist()
            elif route == 'review':
                photo = next(p for p in self.photos if p['id'] == data['id'])
                index = int(data['face'])
                if not 0 <= index < len(photo['faces']) or not self.report:
                    raise ValueError('请选择已检测的人脸。')
                identity = data.get('identity') or None
                if identity and identity not in self.config['references']:
                    raise ValueError('请先登记这位朋友。')
                canonical = next(p for p in self.report['photos'] if p['path'] == photo['path'])
                before = copy.deepcopy(canonical['faces'][index])
                canonical['faces'][index].update(identity=identity, status='confirmed' if identity else 'rejected')
                try:
                    save_json(self.report['report_path'], self.report)
                except Exception:
                    canonical['faces'][index] = before
                    raise
                self.undo_stack.append((photo['path'], index, before))
                photo['faces'] = copy.deepcopy(canonical['faces'])
            elif route == 'undo':
                if not self.undo_stack or not self.report:
                    raise ValueError('没有可撤销的修改。')
                path, index, before = self.undo_stack[-1]
                canonical = next(p for p in self.report['photos'] if p['path'] == path)
                current = canonical['faces'][index]
                canonical['faces'][index] = before
                try:
                    save_json(self.report['report_path'], self.report)
                except Exception:
                    canonical['faces'][index] = current
                    raise
                next(p for p in self.photos if p['path'] == path)['faces'] = copy.deepcopy(canonical['faces'])
                self.undo_stack.pop()
            elif route == 'save-segment':
                if not self.segment:
                    raise ValueError('请先生成分割结果。')
                if data.get('id') and data['id'] != self.segment['photo']:
                    raise ValueError('图像已切换，请重新选择分割结果。')
                instance = data.get('instance', 'all')
                result = self.segment
                if instance != 'all':
                    try:
                        index = int(instance)
                    except (TypeError, ValueError) as exc:
                        raise ValueError('请选择有效的分割目标。') from exc
                    if not 0 <= index < len(self.segment.get('instances', [])):
                        raise ValueError('请选择有效的分割目标。')
                    result = self.segment['instances'][index]
                import shutil
                output = data.get('output', 'cutout')
                if output not in ('cutout', 'mask'):
                    raise ValueError('请选择透明抠图或黑白掩码。')
                key = 'mask' if output == 'mask' else ('crop' if data.get('crop') else 'cutout')
                target = Path(data['path']).expanduser().resolve() / f'{output}_{uuid.uuid4().hex[:10]}.png'
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.files[result[key]], target)
                return {'path': str(target)}
            elif route == 'save-detection':
                if not self.detection or data.get('id') != self.detection['photo']:
                    raise ValueError('请先检测当前图像。')
                target = Path(data['path']).expanduser().resolve() / f'detection_{uuid.uuid4().hex[:10]}.json'
                save_json(target, self.detection)
                return {'path': str(target)}
            else:
                raise ValueError('未知操作。')
        return {'ok': True}

    def scan(self, folder):
        source = Path(folder).resolve()
        if not source.is_dir() and not (source.is_file() and source.suffix.lower() in IMAGE_SUFFIXES):
            raise ValueError('请选择有效的图像或照片文件夹。')
        workspace = Path(self.config['workspace']).resolve()
        if workspace == source or source in workspace.parents:
            raise ValueError('照片目录不能包含工作目录。')
        def operation():
            paths = [source] if source.is_file() else sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
            if not paths:
                raise ValueError('此目录内没有支持的照片。')
            photos = []
            for index, path in enumerate(paths):
                if self.cancel.is_set():
                    return '已停止导入，原项目保持不变。'
                photos.append(self.view_photo(dict(path=str(path), faces=[], error=None), False))
                self.progress(index+1, len(paths), path.name)
            with self.lock:
                self.config.pop('input_paths',None)
                # A new source is a fresh project; avoid importing old human decisions.
                if str(source) != self.config['source']:
                    self.config['workspace'] = str(self.home / 'projects' / uuid.uuid4().hex[:12])
                    self.report, self.undo_stack, self.segment, self.detection = None, [], None, None
                self.config['source'] = str(source)
                self.photos = photos
                self.persist()
            return f'已导入 {len(photos)} 张照片，可以浏览或开始识别。'
        return self.start_task('导入照片', operation)

    def import_drop(self, folder):
        source=Path(folder).resolve()
        if source.parent!=(self.home/'imports').resolve() or not source.is_dir():
            raise ValueError('拖入图片目录不可用。')
        def operation():
            from album.core import fingerprint
            paths=sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
            if not paths:raise ValueError('请拖入支持的图片文件。')
            with self.lock:photos=copy.deepcopy(self.photos)
            seen=set()
            for photo in photos:
                if self.cancel.is_set():return '已停止导入，原项目保持不变。'
                seen.add(photo.get('sha256') or fingerprint(photo['path']))
            added=0
            for index,path in enumerate(paths):
                if self.cancel.is_set():return '已停止导入，原项目保持不变。'
                key=fingerprint(path)
                if key not in seen:
                    photos.append(self.view_photo(dict(path=str(path),faces=[],error=None,sha256=key),False))
                    seen.add(key);added+=1
                self.progress(index+1,len(paths),path.name)
            with self.lock:
                if self.cancel.is_set():return '已停止导入，原项目保持不变。'
                if not self.config['source']:self.config['source']=str(source.parent)
                self.config['input_paths']=[p['path'] for p in photos]
                self.photos=photos
                if self.report:
                    self.report['photos']=copy.deepcopy(photos)
                    save_json(Path(self.config['workspace'])/'report.json',self.report)
                self.persist()
            return f'已追加 {added} 张照片，重复图像已跳过。'
        return self.start_task('导入照片',operation)

    def recognize(self):
        with self.lock:
            config = copy.deepcopy(self.config)
        if not config['source'] or not config['references']:
            raise ValueError('请先导入照片并登记至少一位朋友。')
        if not all(Path(config[k]).is_file() for k in ('detector','recognition')):
            raise ValueError('请在模型设置中选择 SCRFD 和识别模型的本地权重。')
        def operation():
            from album.service import run_project
            managed = self.runtimes.python_for('face') if not self.backend_factory else None
            if managed:
                if config['device'] == 'cuda' and self.runtimes.records.get('face', {}).get('profile') != 'cu128':
                    raise ValueError('请先在功能中心将人物识别引擎切换为 NVIDIA 方案。')
                report = self.runtimes.job('face','recognize',{'config':config},self.cancel.is_set,self.progress)
            elif self.backend_factory:
                backend = self.backend_factory(config)
            else:
                from album.backend import FaceBackend
                backend = FaceBackend(config['detector'], config['recognition'], config['device'])
            if not managed:
                report = run_project(config, backend, self.progress, self.cancel.is_set)
            with self.lock:
                self.report = report
                self.photos = [self.view_photo(p) for p in report['photos']]
                self.undo_stack = []
            failures = sum(bool(p['error']) for p in report['photos'])
            return f'{"已停止" if report["cancelled"] else "整理完成"}：{len(report["photos"])} 张，{failures} 张失败，缓存命中 {report["cache_hits"]} 次。'
        return self.start_task('人物识别', operation)

    def detect_image(self, data):
        from .detection import validate_options, summarize
        conf, iou = validate_options(data)
        with self.lock:
            self.require_idle()
            path = self.files.get(data.get('id'))
            weights, device = self.config['yolo'], self.config['device']
        if path is None:
            raise ValueError('请选择一张已导入的照片。')
        if not weights or not Path(weights).is_file() or Path(weights).suffix.lower() != '.pt':
            raise ValueError('请选择已有的本地 YOLO .pt 权重。')
        def operation():
            started=time.perf_counter()
            self.progress(0, 0, 'YOLO 正在检测图像…')
            payload=dict(path=str(path),weights=weights,device=device,conf=conf,iou=iou)
            if not self.detection_factory and self.runtimes.python_for('vision'):
                prediction=self.runtimes.job('vision','detect',payload,self.cancel.is_set,self.progress)
            elif self.detection_factory:
                from scripts.detection_worker import DetectorSession
                session=DetectorSession(self.detection_factory)
                prediction=session.detect(payload,lambda message:self.progress(0,0,message))
            else:
                prediction=self.runtimes.detect_job(sys.executable,payload,self.cancel.is_set,self.progress)
            detections=prediction['detections']
            performance=prediction['performance']
            performance['total_ms']=round((time.perf_counter()-started)*1000,2)
            result = dict(photo=data['id'], source=str(path), model=str(Path(weights).resolve()),
                          conf=conf, iou=iou, width=prediction['width'], height=prediction['height'],
                          performance=performance,detections=detections, counts=summarize(detections), total=len(detections))
            with self.lock:
                if self.cancel.is_set():
                    return '检测已停止，原结果保持不变。'
                self.detection = result
            self.progress(1, 1, '检测完成')
            return f'检测完成：{len(detections)} 个目标。'
        return self.start_task('目标检测', operation)

    def learning_action(self,route,data):
        with self.lock:self.require_idle()
        key=data.get('dataset') or self.datasets.active
        if route=='dataset-import':
            def operation():
                result=self.datasets.import_images(key,data['path'],data.get('group',''),self.progress,self.cancel.is_set)
                return f"导入完成：{result['added']} 张，跳过 {result['skipped']} 张，失败 {len(result['errors'])} 张。"
            return self.start_task('导入标注图像',operation)
        if route=='dataset-version':
            def operation():
                self.datasets.export_version(key,self.cancel.is_set,self.progress)
                return '数据集版本已固定。'
            return self.start_task('创建数据集版本',operation)
        if route=='training-start':
            return self.start_task('训练模型',lambda:self.training.run(data,self.cancel.is_set,self.progress))
        if route=='training-evaluate':
            return self.start_task('评估模型',lambda:self.training.evaluate(data['run'],self.cancel.is_set,self.progress))
        if route=='dataset-sam-labels':
            image=next(i for i in self.datasets.load(key)['images'] if i['id']==data['image'])
            file_id=self.register(self.datasets.folder(key)/image['file'])
            if not self.segment or self.segment['photo']!=file_id:raise ValueError('请先为当前标注图像生成 SAM3 结果。')
            paths=[str(self.files[item['cutout']]) for item in self.segment['instances']]
            def operation():
                result=self.runtimes.job('vision','mask-polygons',{'paths':paths},self.cancel.is_set,self.progress)
                annotations=[a for a in image['annotations'] if a['id']!=data.get('replace')]+[dict(id=uuid.uuid4().hex,type='polygon',points=points,class_id=int(data['class_id']),source='sam3') for points in result['polygons']]
                self.datasets.save_labels(key,image['id'],annotations,False,False,data['revision'])
                return 'SAM3 轮廓已加入草稿，请人工确认。'
            return self.start_task('转换 SAM3 标注',operation)
        with self.lock:
            self.require_idle()
            if route=='dataset-create':self.datasets.create(data['name'],data.get('task','detect'))
            elif route=='dataset-select':self.datasets.select(data['dataset'])
            elif route=='dataset-class':self.datasets.add_class(key,data['name'])
            elif route=='dataset-rename-class':self.datasets.rename_class(key,int(data['class_id']),data['name'])
            elif route=='dataset-save':
                return self.datasets.save_labels(key,data['image'],data['annotations'],data.get('reviewed',False),data.get('negative',False),data['revision'])
            elif route=='dataset-group':self.datasets.set_group(key,data['image'],data['group'])
            elif route=='dataset-split':self.datasets.split(key,int(data.get('seed',42)))
            elif route=='dataset-set-split':self.datasets.set_split(key,data['image'],data['split'])
            elif route=='dataset-yolo-labels':
                dataset=self.datasets.load(key); image=next(i for i in dataset['images'] if i['id']==data['image'])
                if not self.detection or self.detection['photo']!=self.register(self.datasets.folder(key)/image['file']):
                    raise ValueError('请先检测当前标注图像。')
                for name in dict.fromkeys(item['name'] for item in self.detection['detections']):
                    if name not in {c['name'] for c in self.datasets.load(key)['classes']}:self.datasets.add_class(key,name)
                classes={c['name']:c['id'] for c in self.datasets.load(key)['classes']}
                annotations=list(image['annotations'])
                for item in self.detection['detections']:
                    if not any(a['type']=='box' and a['class_id']==classes[item['name']] and a['bbox']==item['bbox'] for a in annotations):
                        annotations.append(dict(id=uuid.uuid4().hex,type='box',bbox=item['bbox'],class_id=classes[item['name']],source='yolo'))
                self.datasets.save_labels(key,image['id'],annotations,False,False,data['revision'])
            elif route=='training-apply':
                self.config['yolo']=str(self.training.model(data['run']));self.persist()
            elif route=='training-export':return self.training.export_model(data['run'],data['path'])
            elif route=='dataset-export':
                import shutil
                folder,manifest=self.datasets.version(key,data['version'])
                target=Path(data['path']).resolve()/f"memivo-dataset-{manifest['id'][:8]}"
                if target==folder.resolve() or folder.resolve() in target.parents:raise ValueError('不能将数据集导出到自身目录。')
                if target.exists():raise ValueError('导出目录已存在，请选择其他目录。')
                shutil.copytree(folder,target)
                # Rebase the dataset root without modifying the original fixed version.
                config=json.loads((target/'data.yaml').read_text(encoding='utf-8'));config['path']=str(target);save_json(target/'data.yaml',config)
                from .datasets import digest
                manifest['files']['data.yaml']=digest(target/'data.yaml');save_json(target/'manifest.json',manifest)
                return {'path':str(target)}
            else:raise ValueError('Unknown learning operation.')
        return {'ok':True}

    def segment_image(self, data):
        with self.lock:
            path = self.files.get(data.get('id'))
            model = self.config['sam']
        if path is None:
            raise ValueError('请选择一张已导入的照片。')
        if not model or not Path(model).is_file():
            raise ValueError('请先在模型设置中选择 SAM3 权重。')
        def operation():
            import numpy as np
            from PIL import Image, ImageOps
            with Image.open(path) as image:
                original = ImageOps.exif_transpose(image).convert('RGB')
            width, height = original.size
            points = data.get('points', [])
            labels = data.get('labels', [])
            boxes = data.get('boxes', [])
            if len(points) != len(labels) or any(x not in (0,1) for x in labels):
                raise ValueError('点标记格式错误。')
            for x,y in points:
                if not 0 <= x < width or not 0 <= y < height:
                    raise ValueError('标记超出图像范围。')
            for x1,y1,x2,y2 in boxes:
                if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                    raise ValueError('框选范围无效。')
            work = self.home / 'segments'
            work.mkdir(exist_ok=True)
            normalized = work / 'input.png'
            original.save(normalized)
            self.progress(0, 0, 'SAM3 正在分割图像…')
            confidence = float(data.get('conf', .3))
            iou = float(data.get('iou', .7))
            if not 0 <= confidence <= 1 or not 0 <= iou <= 1:
                raise ValueError('分割阈值必须介于 0 与 1 之间。')
            if not data.get('text','').strip() and not points and not boxes:
                raise ValueError('请添加点、框选或文本提示。')
            if self.runtimes.python_for('vision'):
                self.sam_backend = None
                mask_file = work / f'masks-{uuid.uuid4().hex}.npz'
                try:
                    self.runtimes.job('vision','segment',dict(path=str(normalized),model=model,
                        device=self.config['device'],conf=confidence,iou=iou,text=data.get('text',''),
                        points=points,labels=labels,boxes=boxes,mask_file=str(mask_file)),self.cancel.is_set,self.progress)
                    with np.load(mask_file,allow_pickle=False) as output:
                        masks = [output[key] for key in output.files]
                finally:
                    mask_file.unlink(missing_ok=True)
            else:
                from sam_backend import SAM3Backend
                if self.sam_backend is None or self.sam_backend.model_path != model:
                    self.sam_backend = SAM3Backend()
                    self.sam_backend.model_path = model
                self.sam_backend.device = '0' if self.config['device'] == 'cuda' else 'cpu'
            if not self.runtimes.python_for('vision') and data.get('text', '').strip():
                image, masks = self.sam_backend.process_text_prompt(str(normalized), data['text'], confidence, iou)
            elif not self.runtimes.python_for('vision'):
                if not points and not boxes:
                    raise ValueError('请添加点、框选或文本提示。')
                image, masks = self.sam_backend.process_image(str(normalized), points, boxes, confidence, iou, labels=labels)
            if self.cancel.is_set():
                return '分割已停止，原结果保持不变。'
            masks = [np.asarray(mask, dtype=bool) for mask in masks if np.any(mask)]
            if not masks:
                raise ValueError('没有找到分割目标，请调整提示或阈值后重试。')
            combined = np.zeros((height, width), dtype=bool)
            for mask in masks:
                if mask.shape != (height, width):
                    raise ValueError('分割掩码尺寸与图像不一致。')
                combined |= mask.astype(bool)
            rgba = original.convert('RGBA')
            rgba.putalpha(Image.fromarray(combined.astype(np.uint8)*255))
            run_id = uuid.uuid4().hex
            output_dir = work / run_id
            output_dir.mkdir()
            mask_path = output_dir / 'mask.png'
            Image.fromarray(combined.astype(np.uint8)*255).save(mask_path)
            cutout = output_dir / 'cutout.png'
            rgba.save(cutout)
            crop = output_dir / 'crop.png'
            rgba.crop(rgba.getbbox()).save(crop)
            instances = []
            for index, mask in enumerate(masks):
                item = original.convert('RGBA')
                item.putalpha(Image.fromarray(mask.astype(np.uint8)*255))
                item_path = output_dir / f'instance-{index+1}.png'
                crop_path = output_dir / f'instance-{index+1}-crop.png'
                item_mask_path = output_dir / f'instance-{index+1}-mask.png'
                Image.fromarray(mask.astype(np.uint8)*255).save(item_mask_path)
                bounds = item.getbbox()
                item.save(item_path)
                item.crop(bounds).save(crop_path)
                instances.append(dict(cutout=self.register(item_path), crop=self.register(crop_path),
                                      mask=self.register(item_mask_path), bbox=list(bounds)))
            overlay = np.asarray(original).copy()
            overlay[combined] = (overlay[combined]*.3 + np.array([48,114,235])*.7).astype(np.uint8)
            overlay_path = output_dir / 'overlay.png'
            Image.fromarray(overlay).save(overlay_path)
            with self.lock:
                if self.cancel.is_set():
                    return '分割已停止，原结果保持不变。'
                self.segment = dict(photo=data['id'], count=len(masks), instances=instances,
                                    width=width, height=height, directory=str(output_dir.resolve()),
                                    mask=self.register(mask_path), cutout=self.register(cutout),
                                    crop=self.register(crop), overlay=self.register(overlay_path))
            return f'分割完成：{len(masks)} 个掩码，可导出透明 PNG。'
        return self.start_task('SAM3 分割', operation)
