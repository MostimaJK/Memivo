"""Private JSON-lines worker. The owning UI closes stdin / terminates it at shutdown."""
import gc
import json
import os
from pathlib import Path
import sys
import time
import traceback
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


class DetectorSession:
    def __init__(self, factory=None):
        self.factory=factory
        self.backend=None
        self.key=None

    def detect(self, data, progress=lambda message:None):
        from PIL import Image,ImageOps
        from desktop.detection import YOLOBackend
        started=time.perf_counter()
        path=Path(data['weights']).resolve();stat=path.stat()
        key=(str(path),stat.st_mtime_ns,stat.st_size,data['device'])
        reused=self.backend is not None and self.key==key
        load_started=time.perf_counter()
        if not reused:
            self.backend=None;self.key=None;gc.collect()
            torch=sys.modules.get('torch')
            if torch and torch.cuda.is_available():torch.cuda.empty_cache()
            progress('YOLO 首次加载模型与初始化设备…')
            self.backend=(self.factory or YOLOBackend)(str(path),data['device']);self.key=key
        else:progress('YOLO 正在复用模型检测图像…')
        load_ms=(time.perf_counter()-load_started)*1000
        decode_started=time.perf_counter()
        with Image.open(data['path']) as image:original=ImageOps.exif_transpose(image).convert('RGB')
        decode_ms=(time.perf_counter()-decode_started)*1000
        predict_started=time.perf_counter()
        detections=self.backend.predict(original,data['conf'],data['iou'])
        performance=dict(getattr(self.backend,'diagnostics',{}),model_reused=reused,pid=os.getpid(),
            model_load_ms=round(load_ms,2),image_decode_ms=round(decode_ms,2),
            predict_ms=round((time.perf_counter()-predict_started)*1000,2),
            engine_total_ms=round((time.perf_counter()-started)*1000,2))
        return dict(detections=detections,width=original.width,height=original.height,performance=performance)


class VisionSession:
    def __init__(self):
        self.detector=DetectorSession();self.sam=None;self.sam_key=None;self.active=None

    def run(self,action,data,progress=lambda message:None):
        if action!=self.active:
            self.detector=DetectorSession();self.sam=None;self.sam_key=None
            gc.collect()
            torch=sys.modules.get('torch')
            if torch and torch.cuda.is_available():torch.cuda.empty_cache()
            self.active=action
        if action=='detect':return self.detector.detect(data,progress)
        if action!='segment':raise ValueError('Unknown resident vision action')
        import numpy as np
        from sam_backend import SAM3Backend
        path=Path(data['model']).resolve();stat=path.stat()
        key=(str(path),stat.st_mtime_ns,stat.st_size,data['device'],'text' if data.get('text','').strip() else 'geometry')
        reused=self.sam is not None and self.sam_key==key
        if not reused:
            self.sam=None;gc.collect()
            torch=sys.modules.get('torch')
            if torch and torch.cuda.is_available():torch.cuda.empty_cache()
            self.sam=SAM3Backend();self.sam.model_path=str(path)
            self.sam.device='0' if data['device']=='cuda' else 'cpu';self.sam_key=key
        progress('SAM3 正在复用引擎分割图像…' if reused else 'SAM3 首次加载模型与初始化设备…')
        started = time.perf_counter()
        if data.get('text','').strip():_,masks=self.sam.process_text_prompt(data['path'],data['text'],data['conf'],data['iou'],return_image=False)
        else:_,masks=self.sam.process_image(data['path'],data['points'],data['boxes'],data['conf'],data['iou'],labels=data['labels'],return_image=False)
        transfer_started = time.perf_counter()
        np.savez_compressed(data['mask_file'],**{f'mask_{i}':mask for i,mask in enumerate(masks)})
        execution=getattr(self.sam,'execution',dict(actual='unknown',evidence='unverified'))
        from desktop.execution import torch_memory_snapshot
        performance=dict(getattr(self.sam,'diagnostics',{}),device=execution['actual'],
            gpu_name=execution.get('gpu_name'),model_reused=reused,
            mask_archive_ms=round((time.perf_counter()-transfer_started)*1000,2),
            engine_call_ms=round((time.perf_counter()-started)*1000,2),pid=os.getpid())
        performance.update(torch_memory_snapshot(execution['actual']))
        return dict(masks=data['mask_file'],execution=execution,performance=performance)

    def warmup(self,data,progress=lambda message:None):
        from PIL import Image
        with tempfile.TemporaryDirectory(prefix='memivo-warmup-') as folder:
            path=Path(folder)/'warmup.png';Image.new('RGB',(640,640),'#808080').save(path)
            target=data['target']
            payload=dict(data,path=str(path),conf=.25,iou=.7)
            if target=='segment':payload.update(text='object' if data.get('mode')=='text' else '',points=[[320,320]],labels=[1],boxes=[],mask_file=str(Path(folder)/'masks.npz'))
            result=self.run(target,payload,progress)
            performance=result['performance']
            torch=sys.modules.get('torch')
            if torch and performance.get('device','').startswith('cuda'):
                performance['allocated_mb']=round(torch.cuda.memory_allocated(torch.device(performance['device']))/1024**2,1)
            # Warmup never creates user detections or segmentation exports.
            return dict(performance=performance,warmed=target)



def main():
    from album.core import save_json
    session=VisionSession()
    def send(value):print('MEMIVO_DETECTION:'+json.dumps(value,ensure_ascii=False),flush=True)
    # Parent death closes the pipe; there is no network listener or global service.
    for line in sys.stdin:
        message={}
        try:
            message=json.loads(line)
            request=json.loads(Path(message['request']).read_text(encoding='utf-8'))
            action=request.get('action','detect')
            callback=lambda text:send(dict(id=message['id'],progress=text))
            result=session.warmup(request['payload'],callback) if action=='warmup' else session.run(action,request['payload'],callback)
            save_json(request['result'],result)
            send(dict(id=message['id'],ok=True))
        except Exception:
            send(dict(id=message.get('id'),error=traceback.format_exc()))
            return


if __name__=='__main__':main()
