"""Local reviewed annotations and immutable, checksummed YOLO snapshots."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil
import threading
import uuid

from album.core import IMAGE_SUFFIXES, save_json


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


class DatasetStore:
    def __init__(self, home):
        self.root=Path(home)/'datasets'; self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock(); self.active=None
        try:
            key=json.loads((self.root/'selection.json').read_text(encoding='utf-8'))['id']
            self.active=self.load(key)['id']
        except (OSError,ValueError,KeyError): pass

    def folder(self,key):
        if not isinstance(key,str) or not re.fullmatch(r'[a-f0-9]{32}',key):
            raise ValueError('Invalid dataset identifier.')
        path=self.root/key
        if path.resolve().parent!=self.root.resolve() or path.is_symlink():
            raise ValueError('Dataset path is invalid.')
        return path

    def load(self,key=None):
        return json.loads((self.folder(key or self.active)/'dataset.json').read_text(encoding='utf-8'))

    def write(self,data):
        data['revision']+=1; data['updated']=stamp()
        save_json(self.folder(data['id'])/'dataset.json',data)

    def create(self,name,task):
        name=str(name).strip()
        if not name or len(name)>120 or task not in ('detect','segment'):
            raise ValueError('请输入数据集名称，并选择检测或分割任务。')
        data=dict(id=uuid.uuid4().hex,name=name,task=task,revision=0,classes=[],images=[],created=stamp(),updated=stamp())
        self.write(data); self.select(data['id'])
        return data

    def select(self,key):
        self.load(key); save_json(self.root/'selection.json',{'id':key}); self.active=key

    def snapshot(self,register):
        with self.lock:
            items=[]
            for file in self.root.glob('*/dataset.json'):
                try:
                    data=json.loads(file.read_text(encoding='utf-8'))
                    items.append(dict(id=data['id'],name=data['name'],task=data['task'],count=len(data['images'])))
                except (OSError,ValueError,KeyError): continue
            active=None
            versions=[]
            if self.active:
                active=self.load()
                for image in active['images']:
                    image['file_id']=register(self.folder(self.active)/image['file'])
                for file in (self.folder(self.active)/'versions').glob('*/manifest.json'):
                    try:
                        version=json.loads(file.read_text(encoding='utf-8'))
                        versions.append({k:version[k] for k in ('id','created','task','counts','revision','excluded')})
                    except (OSError,ValueError,KeyError): continue
            return dict(items=items,active=active,versions=sorted(versions,key=lambda x:x['created'],reverse=True))

    def import_images(self,key,path,group,progress,cancelled):
        from PIL import Image,ImageOps
        source=Path(path).resolve()
        paths=[source] if source.is_file() else sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
        if not paths: raise ValueError('没有可导入的图像。')
        if source.is_dir() and (source==self.root.resolve() or source in self.root.resolve().parents):
            raise ValueError('请将数据集存储目录放在导入目录之外。')
        with self.lock: data=self.load(key)
        known={i['id'] for i in data['images']}; added=[]; errors=[]
        for index,file in enumerate(paths):
            if cancelled(): raise RuntimeError('Import cancelled; existing dataset is unchanged.')
            try:
                if file.suffix.lower() not in IMAGE_SUFFIXES: raise ValueError('Unsupported image format')
                with Image.open(file) as image:
                    image=ImageOps.exif_transpose(image).convert('RGB')
                    # Pixel identity after normalization avoids duplicate train/test copies.
                    identity=hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()
                    if identity not in known:
                        dest=self.folder(key)/'images'/f'{identity}.png'; dest.parent.mkdir(exist_ok=True)
                        image.save(dest)
                        added.append(dict(id=identity,name=file.name,file=f'images/{identity}.png',width=image.width,height=image.height,
                            group=str(group).strip() or identity,split='',reviewed=False,negative=False,annotations=[],revision=0))
                        known.add(identity)
            except (OSError,ValueError) as exc: errors.append(f'{file.name}: {exc}')
            progress(index+1,len(paths),'正在导入标注图像…')
        if not added and errors: raise ValueError('\n'.join(errors[:5]))
        with self.lock:
            # Application task serialization prevents concurrent writes during import.
            data['images'].extend(added); self.write(data)
        return dict(added=len(added),skipped=len(paths)-len(added)-len(errors),errors=errors)

    def add_class(self,key,name):
        name=str(name).strip()
        with self.lock:
            data=self.load(key)
            if not name or len(name)>80 or any(c['name']==name for c in data['classes']):
                raise ValueError('类别名称为空或已存在。')
            data['classes'].append(dict(id=max([c['id'] for c in data['classes']],default=-1)+1,name=name))
            self.write(data)

    def rename_class(self,key,class_id,name):
        with self.lock:
            data=self.load(key); name=str(name).strip()
            item=next((c for c in data['classes'] if c['id']==class_id),None)
            if not item or not name or any(c['id']!=class_id and c['name']==name for c in data['classes']):
                raise ValueError('类别名称为空或已存在。')
            item['name']=name; self.write(data)

    def validate_annotations(self,data,image,annotations):
        if not isinstance(annotations,list) or len(annotations)>5000: raise ValueError('Invalid annotation list.')
        classes={c['id'] for c in data['classes']}; cleaned=[]; ids=set()
        for item in annotations:
            if item.get('class_id') not in classes: raise ValueError('请先创建并选择有效类别。')
            label=dict(id=str(item.get('id') or uuid.uuid4().hex),class_id=item['class_id'],type=item.get('type'),source=str(item.get('source','manual'))[:32])
            if label['id'] in ids: raise ValueError('Duplicate annotation identifier.')
            ids.add(label['id'])
            if label['type']=='box':
                box=list(map(float,item.get('bbox',[])))
                if len(box)!=4: raise ValueError('Invalid bounding box.')
                x1,y1,x2,y2=box
                if not all(math.isfinite(x) for x in box) or not (0<=x1<x2<=image['width'] and 0<=y1<y2<=image['height']):
                    raise ValueError('标注坐标超出图像或面积为零。')
                label['bbox']=box
            elif label['type']=='polygon':
                points=item.get('points',[])
                if not 3<=len(points)<=10000: raise ValueError('轮廓至少需要三个顶点。')
                points=[[float(x),float(y)] for x,y in points]
                if any(not math.isfinite(x) or not math.isfinite(y) or not 0<=x<=image['width'] or not 0<=y<=image['height'] for x,y in points):
                    raise ValueError('标注坐标超出图像或面积为零。')
                area=abs(sum(x*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*y for i,(x,y) in enumerate(points)))/2
                if area<1: raise ValueError('标注坐标超出图像或面积为零。')
                label['points']=points
            else: raise ValueError('Unknown annotation geometry.')
            cleaned.append(label)
        return cleaned

    def save_labels(self,key,image_id,annotations,reviewed,negative,revision):
        with self.lock:
            data=self.load(key); image=next(i for i in data['images'] if i['id']==image_id)
            if revision!=image['revision']: raise ValueError('标注已被更新，请重新加载后再编辑。')
            cleaned=self.validate_annotations(data,image,annotations)
            if negative and cleaned: raise ValueError('负样本不能同时包含目标标注。')
            if reviewed and not cleaned and not negative: raise ValueError('空图像请明确确认为负样本。')
            image.update(annotations=cleaned,reviewed=bool(reviewed),negative=bool(negative),revision=image['revision']+1)
            self.write(data)
            return image

    def set_group(self,key,image_id,group):
        with self.lock:
            data=self.load(key); image=next(i for i in data['images'] if i['id']==image_id)
            group=str(group).strip()
            if not group: raise ValueError('场景组不能为空。')
            existing={i['split'] for i in data['images'] if i['group']==group and i['split']}
            if image['split'] and existing and image['split'] not in existing:
                raise ValueError('同一场景组不能跨训练、验证和测试集。')
            image['group']=group
            if existing: image['split']=next(iter(existing))
            self.write(data)

    def split(self,key,seed=42):
        with self.lock:
            data=self.load(key); groups=sorted({i['group'] for i in data['images']})
            if len(groups)<3: raise ValueError('自动划分至少需要三个独立场景组。')
            random.Random(int(seed)).shuffle(groups)
            test=max(1,round(len(groups)*.1)); val=max(1,round(len(groups)*.2))
            assigned={g:('test' if n<test else 'val' if n<test+val else 'train') for n,g in enumerate(groups)}
            for image in data['images']: image['split']=assigned[image['group']]
            data['split_seed']=int(seed); self.write(data)

    def set_split(self,key,image_id,split):
        if split not in ('train','val','test',''):raise ValueError('Invalid dataset split.')
        with self.lock:
            data=self.load(key);group=next(i['group'] for i in data['images'] if i['id']==image_id)
            for image in data['images']:
                if image['group']==group:image['split']=split
            self.write(data)

    def export_version(self,key,cancelled=lambda:False,progress=lambda *a:None):
        with self.lock: data=self.load(key)
        images=[i for i in data['images'] if i['reviewed']]
        if not data['classes']: raise ValueError('请先创建并选择有效类别。')
        if any(i['split'] not in ('train','val','test') for i in images): raise ValueError('请先划分训练、验证和测试集。')
        counts={s:sum(i['split']==s for i in images) for s in ('train','val','test')}
        if not all(counts.values()): raise ValueError('训练、验证和测试集均需包含已确认图像。')
        for group in {i['group'] for i in images}:
            if len({i['split'] for i in images if i['group']==group})>1: raise ValueError('同一场景组不能跨训练、验证和测试集。')
        classes={c['id']:n for n,c in enumerate(data['classes'])}
        trained={a['class_id'] for i in images if i['split']=='train' for a in i['annotations']}
        if any(c not in trained for c in classes): raise ValueError('每个类别都需要训练集中的已确认标注。')
        version=uuid.uuid4().hex; folder=self.folder(key)/'versions'/version
        folder.mkdir(parents=True)
        manifest=dict(id=version,dataset=key,created=stamp(),revision=data['revision'],task=data['task'],classes=data['classes'],
                      counts=counts,excluded=len(data['images'])-len(images),files={},images=[])
        try:
            for n,image in enumerate(images):
                if cancelled(): raise RuntimeError('Dataset export cancelled.')
                anns=self.validate_annotations(data,image,image['annotations'])
                if not anns and not image['negative']: raise ValueError('空图像请明确确认为负样本。')
                lines=[]; w,h=image['width'],image['height']
                for ann in anns:
                    if data['task']=='detect':
                        if ann['type']=='box': x1,y1,x2,y2=ann['bbox']
                        else:
                            xs,ys=zip(*ann['points']); x1,y1,x2,y2=min(xs),min(ys),max(xs),max(ys)
                        values=[(x1+x2)/2/w,(y1+y2)/2/h,(x2-x1)/w,(y2-y1)/h]
                    else:
                        if ann['type']!='polygon': raise ValueError('分割训练需要轮廓标注，请补充多边形或 SAM3 轮廓。')
                        values=[v for x,y in ann['points'] for v in (x/w,y/h)]
                    lines.append(str(classes[ann['class_id']])+' '+' '.join(f'{v:.8f}' for v in values))
                rel=f"images/{image['split']}/{image['id']}.png"; dest=folder/rel; dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(self.folder(key)/image['file'],dest)
                label=f"labels/{image['split']}/{image['id']}.txt"; label_path=folder/label; label_path.parent.mkdir(parents=True,exist_ok=True)
                label_path.write_text('\n'.join(lines)+('\n' if lines else ''),encoding='utf-8')
                manifest['images'].append(dict(id=image['id'],file=rel,label=label,split=image['split'],group=image['group'],objects=len(anns)))
                for file in (rel,label): manifest['files'][file]=digest(folder/file)
                progress(n+1,len(images),'正在固定数据集版本…')
            # JSON is a YAML subset; standard YOLO tooling can read this data.yaml.
            save_json(folder/'data.yaml',dict(path=str(folder.resolve()),train='images/train',val='images/val',test='images/test',
                                             names={str(n):c['name'] for n,c in enumerate(data['classes'])}))
            manifest['files']['data.yaml']=digest(folder/'data.yaml')
            save_json(folder/'manifest.json',manifest)
            return manifest
        except Exception:
            # Remove only this newly allocated export directory, never source images.
            if folder.resolve().parent==(self.folder(key)/'versions').resolve(): shutil.rmtree(folder)
            raise

    def version(self,key,version,verify=True):
        if not isinstance(version,str) or not re.fullmatch(r'[a-f0-9]{32}',version): raise ValueError('Invalid version identifier.')
        folder=self.folder(key)/'versions'/version
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if verify:
            for rel,expected in manifest['files'].items():
                file=(folder/rel).resolve()
                if folder.resolve() not in file.parents or digest(file)!=expected:
                    raise ValueError('数据集版本内容已变化，请重新创建版本。')
        return folder,manifest
