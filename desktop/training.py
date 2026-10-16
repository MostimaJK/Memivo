"""Recorded training/evaluation jobs tied to fixed dataset versions."""
import copy
import json
from pathlib import Path
import re
import shutil
import threading
import uuid

from album.core import save_json
from .datasets import digest, stamp


class TrainingStore:
    def __init__(self,home,datasets,runtimes):
        self.root=Path(home)/'training';self.root.mkdir(parents=True,exist_ok=True)
        self.datasets=datasets;self.runtimes=runtimes;self.lock=threading.RLock()
        self.records={}
        for file in self.root.glob('*/run.json'):
            try:
                record=json.loads(file.read_text(encoding='utf-8'))
                if record['state'] in ('running','evaluating'):
                    record.update(state='interrupted',error='Previous process ended before the task completed.')
                self.records[record['id']]=record
            except (OSError,ValueError,KeyError):pass

    def folder(self,key):
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('Invalid training identifier.')
        path=self.root/key
        if path.resolve().parent!=self.root.resolve():raise ValueError('Invalid training directory.')
        return path

    def update(self,key,**changes):
        with self.lock:
            record=dict(self.records[key],**changes,updated=stamp())
            save_json(self.folder(key)/'run.json',record);self.records[key]=record

    def snapshot(self):
        with self.lock:
            return [dict(copy.deepcopy(r),can_resume=r['state'] in ('cancelled','failed','interrupted') and (self.folder(r['id'])/'training/weights/last.pt').is_file())
                    for r in sorted(self.records.values(),key=lambda r:r['created'],reverse=True)]

    def run(self,data,cancelled,progress):
        if not self.runtimes.python_for('vision'):raise ValueError('请先在功能中心安装视觉 AI 引擎。')
        resume=data.get('resume')
        if resume:
            record=copy.deepcopy(self.records[resume]);key=record['id']
            if record['state'] not in ('cancelled','failed','interrupted'):raise ValueError('此训练不需要恢复。')
            checkpoint=self.folder(key)/'training/weights/last.pt'
            if not checkpoint.is_file():raise ValueError('尚无可恢复的 last.pt，请重新开始训练。')
            weights=str(checkpoint);options=record['options']
        else:
            weights=str(Path(data.get('weights','')).resolve())
            if not Path(weights).is_file() or Path(weights).suffix.lower()!='.pt':raise ValueError('请选择已有的本地 YOLO .pt 权重。')
            options={k:int(data.get(k,v)) for k,v in (('epochs',50),('imgsz',640),('batch',4))}
            options['device']=str(data.get('device','cpu'))
            if not (1<=options['epochs']<=1000 and 320<=options['imgsz']<=2048 and options['imgsz']%32==0 and 1<=options['batch']<=64 and options['device'] in ('cpu','cuda')):
                raise ValueError('训练参数无效，请检查轮数、尺寸、批量与设备。')
            key=uuid.uuid4().hex
            folder,manifest=self.datasets.version(data['dataset'],data['version'])
            record=dict(id=key,dataset=data['dataset'],version=data['version'],task=manifest['task'],created=stamp(),updated=stamp(),
                        state='pending',options=options,weights=weights,weights_sha256=digest(weights),metrics=[],evaluation=None,best='',error='')
            with self.lock:self.records[key]=record
        folder,manifest=self.datasets.version(record['dataset'],record['version'])
        out=self.folder(key);out.mkdir(exist_ok=True)
        self.update(key,state='running',error='')
        def report(done,total,message):
            metrics=out/'metrics.json'
            if metrics.exists():
                try:self.update(key,metrics=json.loads(metrics.read_text(encoding='utf-8')))
                except (OSError,ValueError):pass
            progress(done,total,message)
        try:
            result=self.runtimes.job('vision','train',dict(weights=weights,task=record['task'],data=str(folder/'data.yaml'),
                output=str(out),options=options,resume=bool(resume)),cancelled,report)
            best=Path(result['best']).resolve()
            if not best.is_file() or out.resolve() not in best.parents:raise ValueError('Training did not produce a valid best.pt.')
            self.update(key,state='completed',best=str(best),best_sha256=digest(best),metrics=result.get('metrics',[]))
            return '训练完成，可评估或应用模型。'
        except Exception as exc:
            self.update(key,state='cancelled' if cancelled() else 'failed',error=str(exc))
            raise

    def evaluate(self,key,cancelled,progress):
        record=copy.deepcopy(self.records[key]);weights=Path(record.get('best',''))
        if not weights.is_file() or digest(weights)!=record.get('best_sha256'):raise ValueError('模型文件缺失或已变化，请重新训练。')
        folder,manifest=self.datasets.version(record['dataset'],record['version'])
        self.update(key,state='evaluating',error='')
        try:
            evaluation=self.runtimes.job('vision','evaluate',dict(weights=str(weights),data=str(folder/'data.yaml'),
                manifest=manifest,root=str(folder),output=str(self.folder(key)/'evaluation'),options=record['options']),cancelled,progress)
            self.update(key,state='completed',evaluation=evaluation)
            return '独立测试集评估完成。'
        except Exception as exc:
            self.update(key,state='completed',error=str(exc))
            raise

    def model(self,key):
        record=self.records[key];path=Path(record.get('best',''))
        if not path.is_file() or digest(path)!=record.get('best_sha256'):raise ValueError('模型文件缺失或已变化，请重新训练。')
        return path

    def export_model(self,key,destination):
        model=self.model(key);target=Path(destination).resolve()/f'memivo-{key[:8]}'
        if target.exists():raise ValueError('导出目录已存在，请选择其他目录。')
        target.mkdir(parents=True)
        shutil.copy2(model,target/'best.pt')
        record=copy.deepcopy(self.records[key])
        _,manifest=self.datasets.version(record['dataset'],record['version'],verify=False)
        save_json(target/'model.json',dict(run=record,classes=manifest['classes'],dataset_version=manifest['id']))
        return {'path':str(target)}
