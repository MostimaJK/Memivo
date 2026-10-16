"""Entry point executed only in an optional engine's interpreter."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    data=request['payload']
    def progress(*values):
        print('MEMIVO_PROGRESS:'+json.dumps(values,ensure_ascii=False),flush=True)
    if request['action']=='detect':
        from PIL import Image,ImageOps
        from desktop.detection import YOLOBackend
        with Image.open(data['path']) as image:
            original=ImageOps.exif_transpose(image).convert('RGB')
        result={'detections':YOLOBackend(data['weights'],data['device']).predict(original,data['conf'],data['iou'])}
    elif request['action']=='segment':
        import numpy as np
        from sam_backend import SAM3Backend
        backend=SAM3Backend()
        backend.model_path=data['model']
        backend.device='0' if data['device']=='cuda' else 'cpu'
        if data.get('text','').strip():
            _,masks=backend.process_text_prompt(data['path'],data['text'],data['conf'],data['iou'])
        else:
            _,masks=backend.process_image(data['path'],data['points'],data['boxes'],data['conf'],data['iou'],labels=data['labels'])
        # Numeric masks only; no object arrays/pickle cross the process boundary.
        np.savez_compressed(data['mask_file'],**{f'mask_{i}':mask for i,mask in enumerate(masks)})
        result={'masks':data['mask_file']}
    elif request['action']=='recognize':
        from album.backend import FaceBackend
        from album.service import run_project
        config=data['config']
        result=run_project(config,FaceBackend(config['detector'],config['recognition'],config['device']),progress)
    elif request['action']=='mask-polygons':
        import cv2
        import numpy as np
        from PIL import Image
        polygons=[]
        for path in data['paths']:
            with Image.open(path) as image:mask=np.array(image.convert('RGBA').getchannel('A'))
            contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                contour=cv2.approxPolyDP(contour,max(.5,cv2.arcLength(contour,True)*.001),True)
                if len(contour)>=3 and cv2.contourArea(contour)>=1:
                    polygons.append(contour[:,0,:].astype(float).tolist())
        result={'polygons':polygons}
    elif request['action']=='train':
        import math
        import torch
        from ultralytics import YOLO
        from album.core import save_json
        torch.set_num_threads(min(4,torch.get_num_threads()))
        model=YOLO(data['weights'])
        if model.task!=data['task']:raise ValueError('模型任务与数据集不匹配，请选择检测或分割对应权重。')
        output=Path(data['output']);history=[]
        if data['resume'] and (output/'metrics.json').exists():
            history=json.loads((output/'metrics.json').read_text(encoding='utf-8'))
        def on_epoch(trainer):
            metrics={key:float(value) for key,value in trainer.metrics.items() if isinstance(value,(int,float)) and math.isfinite(float(value))}
            metrics['epoch']=min(trainer.epoch+1,trainer.epochs)
            if history and history[-1]['epoch']==metrics['epoch']:history[-1]=metrics
            else:history.append(metrics)
            save_json(output/'metrics.json',history)
            progress(metrics['epoch'],trainer.epochs,'正在训练模型…')
        model.add_callback('on_fit_epoch_end',on_epoch)
        options=data['options'];device='0' if options['device']=='cuda' else 'cpu'
        if data['resume']:
            model.train(resume=True,device=device,workers=0)
        else:
            model.train(data=data['data'],epochs=options['epochs'],imgsz=options['imgsz'],batch=options['batch'],device=device,
                workers=0,project=str(output),name='training',exist_ok=False,plots=False,save=True,seed=42)
        result=dict(best=str(output/'training/weights/best.pt'),metrics=history)
    elif request['action']=='evaluate':
        from ultralytics import YOLO
        model=YOLO(data['weights']);options=data['options'];device='0' if options['device']=='cuda' else 'cpu'
        metrics=model.val(data=data['data'],split='test',imgsz=options['imgsz'],batch=options['batch'],device=device,
                          workers=0,plots=False,project=data['output'],name='test',exist_ok=True)
        summary={key:float(value) for key,value in metrics.results_dict.items()}
        errors=[];details=[]
        images=[i for i in data['manifest']['images'] if i['split']=='test']
        for n,image in enumerate(images):
            results=model.predict(str(Path(data['root'])/image['file']),conf=.25,iou=.7,device=device,verbose=False)
            count=len(results[0].boxes) if results[0].boxes is not None else 0
            errors.append(abs(count-image['objects']))
            details.append(dict(image=image['id'],expected=image['objects'],predicted=count))
            progress(n+1,len(images),'正在评估独立测试集…')
        result=dict(metrics=summary,count_mae=sum(errors)/len(errors),count_conf=.25,count_iou=.7,images=len(images),details=details)
    else:
        raise ValueError('Unknown engine operation')
    from album.core import save_json
    save_json(request['result'],result)


if __name__=='__main__':
    main()
