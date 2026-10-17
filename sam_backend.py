from ultralytics import SAM
from ultralytics.models.sam import SAM3SemanticPredictor
import numpy as np
import cv2
import gc
import time
from pathlib import Path
from desktop.execution import torch_execution,model_tensor_device


class SAM3Backend:
    def __init__(self):
        self.model_path = "sam3.pt"
        self.model = None
        self.device = 'cpu'
        self.semantic_predictor = None
        self.semantic_key = None
        self.semantic_image_key = None
        self.model_key=None

    def set_model_path(self, path):
        self.model_path = path
        self.semantic_predictor = None
        self.semantic_key = None
        try:
            self.model = SAM(path)
            stat=Path(path).stat()
            self.model_key=(str(Path(path).resolve()),stat.st_mtime_ns,stat.st_size,self.device)
            print(f"SAM 模型載入成功: {path}")
            return True
        except Exception as e:
            print(f"SAM 模型載入失敗: {e}")
            return False

    def process_image(self, image_path, points=None, boxes=None, conf=0.3, iou=0.7, labels=None, return_image=True):
        # Geometry and text predictors may each own a full model; keep one path resident.
        if self.semantic_predictor is not None:
            self.semantic_predictor = None
            self.semantic_key = None
            gc.collect()
        stat=Path(self.model_path).stat()
        key=(str(Path(self.model_path).resolve()),stat.st_mtime_ns,stat.st_size,self.device)
        if self.model is not None and self.model_key!=key:
            self.model=None;gc.collect()
        if not self.model:
            if self.model_path:
                if not self.set_model_path(self.model_path):
                    raise ValueError('无法加载 SAM 模型，请检查权重与运行环境。')
            else:
                raise ValueError("請先在設定介面載入有效的模型檔案！")

        # 核心預測參數
        predict_kwargs = {
            "source": image_path,
            "retina_masks": True,
            "device": self.device,
            "conf": conf,
            "iou": iou
        }

        # 加入點擊提示 (Points)
        if points and len(points) > 0:
            predict_kwargs["points"] = points
            predict_kwargs["labels"] = labels if labels is not None else [1] * len(points)

        # 加入框選提示 (Boxes)
        if boxes and len(boxes) > 0:
            predict_kwargs["bboxes"] = boxes

        # 執行預測
        started = time.perf_counter()
        results = self.model.predict(**predict_kwargs)
        self.execution=torch_execution('cuda' if self.device=='0' else 'cpu',model_tensor_device(self.model.predictor),'segment')
        result = results[0]

        return self._output(result, image_path, return_image, started)

    def process_text_prompt(self, image_path, text_prompt, conf=0.3, iou=0.7, return_image=True):
        """處理基於文本提示的影像分割"""
        if self.model is not None:
            self.model = None;self.model_key=None;gc.collect()
        overrides = {
            "conf": conf,
            "iou": iou,
            "model": self.model_path,
            "device": self.device
        }

        # 建立專門處理語義預測的 Predictor
        stat=Path(self.model_path).stat()
        key = (self.model_path, self.device,stat.st_mtime_ns,stat.st_size)
        if self.semantic_predictor is None or self.semantic_key != key:
            self.semantic_predictor=None;gc.collect()
            self.semantic_predictor = SAM3SemanticPredictor(overrides=overrides)
            self.semantic_key = key
            self.semantic_image_key=None
        predictor = self.semantic_predictor
        predictor.args.conf=conf;predictor.args.iou=iou
        stat=Path(image_path).stat()
        image_key=(str(Path(image_path).resolve()),stat.st_mtime_ns,stat.st_size)
        started = time.perf_counter()
        if self.semantic_image_key!=image_key:
            predictor.set_image(image_path)
            self.semantic_image_key=image_key

        # 進行預測
        results = predictor(text=[text_prompt])
        self.execution=torch_execution('cuda' if self.device=='0' else 'cpu',model_tensor_device(predictor),'segment')
        result = results[0]

        return self._output(result, image_path, return_image, started)

    def _output(self, result, image_path, return_image, started):
        predicted_ms = (time.perf_counter() - started) * 1000
        output_started = time.perf_counter()
        # Ultralytics Results already retains the decoded BGR input and shape.
        # Managed workers only consume masks; legacy callers still receive RGB.
        bgr = getattr(result, 'orig_img', None)
        shape = getattr(result, 'orig_shape', None)
        if shape is None and bgr is not None:
            shape = bgr.shape[:2]
        if shape is None or (return_image and bgr is None):
            bgr = cv2.imread(image_path)
            if bgr is None:raise ValueError('无法读取输入图像。')
            shape = bgr.shape[:2]
        img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB) if return_image else None

        masks = []
        if result.masks is not None:
            mask_data = result.masks.data.cpu().numpy()
            for i in range(mask_data.shape[0]):
                mask_uint8 = mask_data[i].astype(np.uint8)
                mask_resized = mask_uint8 if mask_uint8.shape == tuple(shape) else cv2.resize(mask_uint8, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
                masks.append(mask_resized)

        self.diagnostics = dict(predict_call_ms=round(predicted_ms, 2),
                                mask_output_ms=round((time.perf_counter()-output_started)*1000, 2))
        return img, masks
