import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from desktop.execution import torch_execution,face_execution,onnx_profile,model_tensor_device
from desktop.runtimes import RuntimeManager
from scripts.detection_worker import VisionSession


class ExecutionTests(unittest.TestCase):
    def test_tensor_device_mismatch_and_unknown_are_not_gpu_success(self):
        with self.assertRaisesRegex(RuntimeError,'actually executed on cpu'):torch_execution('cuda','cpu','segment')
        self.assertIsNone(model_tensor_device(SimpleNamespace(device='cuda:0')))
        wrapped=SimpleNamespace(parameters=lambda:iter([]),model=SimpleNamespace(parameters=lambda:iter([SimpleNamespace(device='cpu')])))
        self.assertEqual(model_tensor_device(SimpleNamespace(model=wrapped)),'cpu')
        self.assertEqual(torch_execution('cuda',None,'segment')['evidence'],'unverified')
        self.assertEqual(torch_execution('cuda','0','detect')['actual'],'unknown')
        self.assertEqual(torch_execution('cpu','cpu','train')['actual'],'cpu')

    def test_onnx_placement_is_checked_for_each_active_model_and_cache(self):
        mixed={'detector':{'CUDAExecutionProvider':20,'CPUExecutionProvider':2},'recognition':{'CUDAExecutionProvider':10}}
        report=face_execution('cuda',mixed)
        self.assertEqual(report['actual'],'cuda:0');self.assertEqual(report['cpu_nodes'],2)
        with self.assertRaises(RuntimeError):face_execution('cuda',dict(mixed,recognition={'CPUExecutionProvider':5}))
        self.assertEqual(face_execution('cuda',{'detector':{},'recognition':{}})['actual'],'cache')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'events.json';path.write_text(json.dumps([{'cat':'Node','args':{'provider':'CUDAExecutionProvider'}},{'cat':'Session','args':{'provider':'CPUExecutionProvider'}}]))
            self.assertEqual(onnx_profile(path),{'CUDAExecutionProvider':1})

    def test_execution_journal_and_snapshot_distinguish_setting_from_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            manager=RuntimeManager(folder)
            manager.begin_execution('train','cuda');self.assertEqual(manager.snapshot()['execution']['actual'],'unknown')
            manager.record_execution(dict(operation='train',requested='cuda',actual='cuda:0',evidence='tensor_device'))
            saved=json.loads((manager.log_root/'execution.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(saved['actual'],'cuda:0');self.assertEqual(manager.snapshot()['execution'],saved)

    def test_sam_worker_reuses_model_and_reloads_changed_weight(self):
        calls=[]
        class SAM:
            def __init__(self):calls.append('load');self.execution={'actual':'cpu','evidence':'tensor_device'}
            def process_image(self,*args,**kwargs):return None,[np.ones((3,4),dtype=np.uint8)]
        with tempfile.TemporaryDirectory() as folder,patch.dict('sys.modules',{'sam_backend':SimpleNamespace(SAM3Backend=SAM)}):
            root=Path(folder);weights=root/'sam.pt';weights.touch()
            data=dict(model=str(weights),device='cpu',conf=.3,iou=.7,points=[[1,1]],labels=[1],boxes=[],path='test.png',mask_file=str(root/'mask.npz'))
            session=VisionSession()
            self.assertFalse(session.run('segment',data)['performance']['model_reused'])
            self.assertTrue(session.run('segment',dict(data,conf=.5))['performance']['model_reused'])
            self.assertEqual(len(calls),1)
            weights.write_bytes(b'changed')
            self.assertFalse(session.run('segment',data)['performance']['model_reused']);self.assertEqual(len(calls),2)
            with np.load(data['mask_file'],allow_pickle=False) as masks:self.assertEqual(masks['mask_0'].shape,(3,4))

    def test_sam_text_threshold_changes_reuse_model_and_image_features(self):
        calls=[]
        class Predictor:
            def __init__(self,overrides):calls.append('model');self.args=SimpleNamespace(**overrides);self.device='cpu'
            def set_image(self,path):calls.append('image')
            def __call__(self,**kwargs):return [SimpleNamespace(masks=None)]
        cv2=SimpleNamespace(imread=lambda path:np.zeros((10,20,3),dtype=np.uint8),cvtColor=lambda im,mode:im,COLOR_BGR2RGB=1)
        modules={'ultralytics':SimpleNamespace(SAM=None),'ultralytics.models.sam':SimpleNamespace(SAM3SemanticPredictor=Predictor),'cv2':cv2}
        with tempfile.TemporaryDirectory() as folder,patch.dict('sys.modules',modules):
            spec=importlib.util.spec_from_file_location('sam_backend_audit_test',Path(__file__).resolve().parents[1]/'sam_backend.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            root=Path(folder);weights=root/'sam.pt';weights.touch();image=root/'image.png';image.touch()
            backend=module.SAM3Backend();backend.model_path=str(weights)
            backend.process_text_prompt(str(image),'person',.3,.7)
            backend.process_text_prompt(str(image),'bag',.5,.6)
            self.assertEqual(calls,['model','image'])
            self.assertEqual(backend.semantic_predictor.args.conf,.5)
            image.write_bytes(b'updated');backend.process_text_prompt(str(image),'bag')
            self.assertEqual(calls,['model','image','image'])


if __name__=='__main__':unittest.main()
