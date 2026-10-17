"""Local YOLO adapter. Downloads are explicit and separate in the model library."""
from collections import Counter
import math
import sys
from pathlib import Path


def validate_options(data):
    conf, iou = float(data.get('conf', .25)), float(data.get('iou', .7))
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (conf, iou)):
        raise ValueError('检测阈值必须介于 0 与 1 之间。')
    return conf, iou


def summarize(detections):
    counts = Counter(item['class_id'] for item in detections)
    names = {item['class_id']: item['name'] for item in detections}
    return [dict(class_id=key, name=names[key], count=count)
            for key, count in sorted(counts.items())]


class YOLOBackend:
    def __init__(self, weights, device):
        path = Path(weights).resolve()
        if not path.is_file() or path.suffix.lower() != '.pt':
            raise ValueError('请选择已有的本地 YOLO .pt 权重。')
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ValueError('尚未安装 YOLO 推理依赖，请在模型环境安装 ultralytics。') from exc
        self.model = YOLO(str(path))
        if self.model.task not in ('detect', 'segment'):
            raise ValueError('请选择目标检测或实例分割权重，分类模型不能用于框选计数。')
        self.device = '0' if device == 'cuda' else 'cpu'

    def predict(self, image, conf, iou):
        # PIL input is already EXIF-normalized and RGB, matching the UI coordinates.
        results = self.model.predict(source=image, conf=conf, iou=iou,
                                     device=self.device, verbose=False, save=False)
        result = results[0]
        from .execution import torch_execution,model_tensor_device
        actual=model_tensor_device(getattr(self.model,'predictor',None))
        self.execution=torch_execution('cuda' if self.device=='0' else 'cpu',actual,'detect')
        torch=sys.modules.get('torch')
        self.diagnostics=dict(device=str(actual) if actual is not None else 'unknown',
            torch_version=str(getattr(torch,'__version__','unknown')),
            cuda_version=getattr(getattr(torch,'version',None),'cuda',None),
            stages_ms={key:round(float(value),2) for key,value in (getattr(result,'speed',None) or {}).items()
                       if isinstance(value,(float,int)) and math.isfinite(value)})
        if actual is not None and str(actual).startswith('cuda') and torch:
            self.diagnostics['gpu_name']=torch.cuda.get_device_name(actual)
        if result.boxes is None:
            return []
        width, height = image.size
        items = []
        for box, score, label in zip(result.boxes.xyxy.cpu().tolist(),
                                     result.boxes.conf.cpu().tolist(),
                                     result.boxes.cls.cpu().tolist()):
            class_id = int(label)
            x1, y1, x2, y2 = map(float, box)
            bbox = [max(0., min(width, x1)), max(0., min(height, y1)),
                    max(0., min(width, x2)), max(0., min(height, y2))]
            if not all(math.isfinite(v) for v in (*bbox, score)) or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                continue
            items.append(dict(class_id=class_id, name=str(result.names[class_id]),
                              confidence=float(score), bbox=bbox))
        return items
