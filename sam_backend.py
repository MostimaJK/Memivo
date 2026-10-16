from ultralytics import SAM
from ultralytics.models.sam import SAM3SemanticPredictor
import numpy as np
import cv2


class SAM3Backend:
    def __init__(self):
        self.model_path = "sam3.pt"
        self.model = None
        self.device = 'cpu'
        self.semantic_predictor = None
        self.semantic_key = None

    def set_model_path(self, path):
        self.model_path = path
        self.semantic_predictor = None
        self.semantic_key = None
        try:
            self.model = SAM(path)
            print(f"SAM 模型載入成功: {path}")
            return True
        except Exception as e:
            print(f"SAM 模型載入失敗: {e}")
            return False

    def process_image(self, image_path, points=None, boxes=None, conf=0.3, iou=0.7, labels=None):
        # Geometry and text predictors may each own a full model; keep one path resident.
        if self.semantic_predictor is not None:
            self.semantic_predictor = None
            self.semantic_key = None
        if not self.model:
            if self.model_path:
                if not self.set_model_path(self.model_path):
                    raise ValueError('无法加载 SAM 模型，请检查权重与运行环境。')
            else:
                raise ValueError("請先在設定介面載入有效的模型檔案！")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError('无法读取输入图像。')
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

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
        results = self.model.predict(**predict_kwargs)
        result = results[0]

        masks = []
        if result.masks is not None:
            mask_data = result.masks.data.cpu().numpy()
            for i in range(mask_data.shape[0]):
                mask_uint8 = mask_data[i].astype(np.uint8)
                mask_resized = cv2.resize(mask_uint8, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
                masks.append(mask_resized)

        return img, masks

    def process_text_prompt(self, image_path, text_prompt, conf=0.3, iou=0.7):
        """處理基於文本提示的影像分割"""
        self.model = None
        overrides = {
            "conf": conf,
            "iou": iou,
            "model": self.model_path,
            "device": self.device
        }

        # 建立專門處理語義預測的 Predictor
        key = (self.model_path, conf, iou, self.device)
        if self.semantic_predictor is None or self.semantic_key != key:
            self.semantic_predictor = SAM3SemanticPredictor(overrides=overrides)
            self.semantic_key = key
        predictor = self.semantic_predictor
        predictor.set_image(image_path)

        # 進行預測
        results = predictor(text=[text_prompt])
        result = results[0]

        img = cv2.imread(image_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        masks = []
        if result.masks is not None:
            mask_data = result.masks.data.cpu().numpy()
            for i in range(mask_data.shape[0]):
                mask_uint8 = mask_data[i].astype(np.uint8)
                mask_resized = cv2.resize(mask_uint8, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
                masks.append(mask_resized)

        return img, masks
