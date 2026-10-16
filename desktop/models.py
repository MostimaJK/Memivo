"""Local model discovery and explicit, checksum-verified official downloads.

Discovery uses directory roles, never loads untrusted checkpoints to guess type.
Catalog URLs and expected digests are maintained with the application, not supplied
by the UI. Model loading/shape validation remains the inference engine's job.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import uuid


FOLDERS={'detector':('face/detector','.onnx'), 'recognition':('face/recognition','.onnx'),
         'sam':('sam3','.pt'), 'yolo':('yolo','.pt')}


class ModelStore:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.catalog=json.loads(Path(__file__).with_name('model_catalog.json').read_text(encoding='utf-8'))
        for directory,_ in FOLDERS.values(): (self.root/directory).mkdir(parents=True,exist_ok=True)
        for task in ('detect','segment'): (self.root/'yolo'/task).mkdir(exist_ok=True)
        self.items={role:[] for role in FOLDERS}
        self.scan()

    def scan(self):
        result={role:[] for role in FOLDERS}
        for role,(directory,suffix) in FOLDERS.items():
            for file in sorted((self.root/directory).rglob('*')):
                if file.suffix.lower()!=suffix or not file.is_file() or not file.stat().st_size: continue
                path=file.resolve()
                if self.root not in path.parents: continue
                result[role].append(dict(path=str(path),name=file.name,relative=file.relative_to(self.root).as_posix(),bytes=file.stat().st_size))
        self.items=result
        return result

    def defaults(self,config):
        """Keep saved models; auto-select only an unambiguous missing role."""
        changes={}
        for role,items in self.items.items():
            current=config.get(role,'')
            if (not current or not Path(current).is_file()) and len(items)==1:
                changes[role]=items[0]['path']
        return changes

    def snapshot(self,config):
        items=copy.deepcopy(self.items)
        for role,choices in items.items():
            current=config.get(role,'')
            if current and Path(current).is_file() and current not in {x['path'] for x in choices}:
                choices.append(dict(path=current,name=Path(current).name,relative=current,bytes=Path(current).stat().st_size))
        catalog=copy.deepcopy(self.catalog)
        for entry in catalog['models']:
            entry['installed']=bool(entry.get('sha256') and (self.root/entry['relative']).is_file())
        return dict(root=str(self.root),items=items,**catalog)

    def download(self,key,cancelled,progress):
        entry=next((e for e in self.catalog['models'] if e['id']==key),None)
        if not entry or entry['mode']!='download':raise ValueError('该权重需从官方页面下载后放入模型目录。')
        target=(self.root/entry['relative']).resolve()
        if self.root not in target.parents:raise ValueError('Invalid model destination.')
        if target.exists():raise ValueError('同名模型已存在，保留现有文件；请扫描或先手动移走。')
        target.parent.mkdir(parents=True,exist_ok=True)
        if shutil.disk_usage(target.parent).free<entry['size']*1.1:raise ValueError('模型目录磁盘空间不足。')
        part=target.with_name(target.name+'.'+uuid.uuid4().hex+'.part')
        done=0;digest=hashlib.sha256()
        try:
            progress(0,entry['size'],'正在下载官方模型…')
            request=urllib.request.Request(entry['url'],headers={'User-Agent':'Memivo/0.3.1'})
            with urllib.request.urlopen(request,timeout=30) as response, part.open('xb') as output:
                length=response.headers.get('Content-Length')
                if length and int(length)!=entry['size']:raise ValueError('官方模型大小已变化，请更新模型目录。')
                while True:
                    if cancelled():raise RuntimeError('模型下载已停止。')
                    chunk=response.read(256*1024)
                    if not chunk:break
                    done+=len(chunk)
                    if done>entry['size']:raise ValueError('模型下载大小异常。')
                    output.write(chunk);digest.update(chunk)
                    progress(done,entry['size'],'正在下载官方模型…')
            if cancelled():raise RuntimeError('模型下载已停止。')
            if done!=entry['size'] or digest.hexdigest()!=entry['sha256']:raise ValueError('模型校验失败，未保存下载文件。')
            # Hard-link publishes only if destination does not already exist, preserving user files.
            import os
            os.link(part,target)
            self.scan()
            return '官方模型下载并校验完成。'
        finally:
            part.unlink(missing_ok=True)
