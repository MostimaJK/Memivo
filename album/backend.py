"""Local SCRFD detection + interchangeable LVFace/ArcFace ONNX embeddings."""
from pathlib import Path

import numpy as np

from .core import fingerprint, unit


class FaceBackend:
    def __init__(self, detector_path, recognition_path, device='cpu'):
        import cv2
        import onnxruntime as ort
        from insightface.model_zoo import get_model
        from insightface.utils import face_align

        self.cv2, self.face_align = cv2, face_align
        for path in (detector_path, recognition_path):
            if not Path(path).is_file():
                raise FileNotFoundError(f'请选择已有的本地 ONNX 权重：{path}')
        if device not in {'cpu', 'cuda'}:
            raise ValueError('device 必须是 cpu 或 cuda')
        if device == 'cuda' and hasattr(ort, 'preload_dlls'):
            ort.preload_dlls(directory='')
        provider = 'CUDAExecutionProvider' if device == 'cuda' else 'CPUExecutionProvider'
        if provider not in ort.get_available_providers():
            raise RuntimeError(f'{provider} 不可用；检查 ONNX Runtime、CUDA、cuDNN。')
        providers = [provider, 'CPUExecutionProvider'] if device == 'cuda' else [provider]
        options = ort.SessionOptions()
        # Baseline uses one aligned face at a time; avoid multiple GPU sessions/jobs.
        self.session = ort.InferenceSession(str(recognition_path), sess_options=options, providers=providers)
        if device == 'cuda':
            self.session.disable_fallback()
        self.detector = get_model(str(detector_path), providers=providers)
        if self.detector is None or getattr(self.detector, 'taskname', '') != 'detection':
            raise ValueError('人脸检测器需要 InsightFace 支持的 SCRFD ONNX 模型。')
        self.detector.prepare(ctx_id=0 if device == 'cuda' else -1,
                              input_size=(640, 640), det_thresh=0.5)
        if device == 'cuda':
            self.detector.session.disable_fallback()
        if provider not in self.session.get_providers() or provider not in self.detector.session.get_providers():
            raise RuntimeError('所选执行后端未成功启用，停止任务，避免把 CPU 回退误报为 GPU。')
        self.providers = self.session.get_providers()
        self.input = self.session.get_inputs()[0]
        shape = self.input.shape
        if (len(shape) != 4 or shape[1:] != [3, 112, 112]
                or isinstance(shape[0], int) and shape[0] != 1):
            raise ValueError(f'需要 batch=1 或动态 batch 的 NCHW 112×112 模型，实际为 {shape}')
        if self.input.type not in {'tensor(float)', 'tensor(float16)'}:
            raise ValueError(f'不支持输入类型：{self.input.type}')
        self.dtype = np.float16 if self.input.type == 'tensor(float16)' else np.float32
        # Includes detector/preprocessing policy; do not mix embedding spaces.
        self.model_id = fingerprint(recognition_path)
        self.cache_id = self.model_id + ':' + fingerprint(detector_path) + ':rgb112-v1-scrfd640-exif'

    def extract(self, image_path):
        from PIL import Image, ImageOps
        with Image.open(image_path) as image:
            rgb = np.asarray(ImageOps.exif_transpose(image).convert('RGB'))
        bgr = self.cv2.cvtColor(rgb, self.cv2.COLOR_RGB2BGR)
        boxes, landmarks = self.detector.detect(bgr, max_num=0)
        if len(boxes) and landmarks is None:
            raise ValueError('检测器未输出对齐所需的五个人脸关键点。')
        faces = []
        for box, points in zip(boxes, landmarks if landmarks is not None else []):
            aligned = self.face_align.norm_crop(bgr, landmark=points, image_size=112)
            # Same RGB [-1,1] contract as official LVFace inference; image is aligned first.
            tensor = aligned[:, :, ::-1].transpose(2, 0, 1)[None].astype(self.dtype)
            tensor = np.ascontiguousarray((tensor / self.dtype(255) - self.dtype(.5)) / self.dtype(.5))
            output = self.session.run(None, {self.input.name: tensor})[0]
            faces.append({'bbox': box[:4].astype(float).tolist(),
                          'det_score': float(box[4]), 'embedding': unit(output).tolist()})
        return faces
