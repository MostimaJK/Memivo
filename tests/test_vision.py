"""Business/adapter tests use explicit model doubles, not accuracy benchmarks."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from desktop.application import Application
from desktop.detection import YOLOBackend


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / '图像.jpg'
        exif = Image.Exif()
        exif[274] = 6
        Image.new('RGB', (100, 60), 'blue').save(self.image, exif=exif)
        self.weights = self.root / 'best.pt'
        self.weights.touch()
        self.app = Application(self.root / 'work')
        self.app.action('scan', {'path': str(self.image)})
        self.wait()
        self.photo = self.app.photos[0]['id']
        self.app.action('config', {'yolo': str(self.weights), 'sam': str(self.weights)})

    def tearDown(self):
        if self.app.worker:
            self.app.worker.join(5)
        self.temp.cleanup()

    def wait(self):
        self.app.worker.join(5)
        self.assertFalse(self.app.worker.is_alive())
        self.assertNotEqual(self.app.task['state'], 'failed', self.app.task)

    def run_detection(self, items, stop=False):
        app = self.app
        class FakeYOLO:
            def __init__(self, weights, device):
                self.weights = weights
            def predict(self, image, conf, iou):
                self_test.assertEqual(image.size, (60, 100))
                if stop:
                    app.cancel.set()
                return items
        self_test = self
        app.detection_factory = FakeYOLO
        app.action('detect', {'id': self.photo, 'conf': .3, 'iou': .6})
        self.wait()

    def test_custom_classes_count_exif_and_json_export(self):
        objects = [dict(class_id=k, name=name, confidence=.9, bbox=[1, 2, 12, 20])
                   for k, name in [(0, 'person'), (1, 'pen'), (1, 'pen')]]
        self.run_detection(objects)
        result = self.app.snapshot()['detection']
        self.assertEqual(result['total'], 3)
        self.assertEqual({c['name']: c['count'] for c in result['counts']}, {'person': 1, 'pen': 2})
        self.assertEqual((result['width'], result['height']), (60, 100))
        saved = self.app.action('save-detection', {'id': self.photo, 'path': str(self.root / 'exports')})
        self.assertEqual(json.loads(Path(saved['path']).read_text(encoding='utf-8')), result)
        with self.assertRaises(ValueError):
            self.app.action('save-detection', {'id': 'different-image', 'path': str(self.root)})
        restored = Application(self.app.home)
        self.assertEqual(restored.config['yolo'], str(self.weights))
        self.assertEqual(len(restored.photos), 1)

    def test_empty_detections_and_cancel_preserve_previous_result(self):
        self.run_detection([])
        self.assertEqual(self.app.detection['total'], 0)
        previous = self.app.snapshot()['detection']
        self.run_detection([dict(class_id=0, name='person', confidence=.9, bbox=[0,0,10,10])], stop=True)
        self.assertEqual(self.app.task['state'], 'cancelled')
        self.assertEqual(self.app.detection, previous)

    def test_invalid_model_and_thresholds_fail_before_start(self):
        for data in ({'conf': float('nan')}, {'iou': -1}, {'conf': 1.1}):
            with self.assertRaises(ValueError):
                self.app.action('detect', dict(id=self.photo, **data))
        with self.assertRaises(ValueError):
            self.app.action('detect', {'id': 'not-a-photo'})
        self.app.action('config', {'yolo': 'yolo-do-not-download.pt'})
        with self.assertRaises(ValueError):
            self.app.action('detect', {'id': self.photo})

    def test_yolo_adapter_uses_local_weights_and_model_names(self):
        class Tensor:
            def __init__(self, value): self.value = value
            def cpu(self): return self
            def tolist(self): return self.value
        result = SimpleNamespace(names={3:'my-pen'}, boxes=SimpleNamespace(
            xyxy=Tensor([[-2,1,10,40]]), conf=Tensor([.91]), cls=Tensor([3.])))
        class Model:
            task = 'detect'
            def __init__(self, path): self.path = path
            def predict(self, **kwargs):
                Model.options = kwargs
                return [result]
        with patch.dict('sys.modules', {'ultralytics': SimpleNamespace(YOLO=Model)}):
            backend = YOLOBackend(self.weights, 'cuda')
            items = backend.predict(Image.new('RGB',(60,100)), .4, .5)
            self.assertEqual(items[0]['name'], 'my-pen')
            self.assertEqual(items[0]['bbox'], [0.,1.,10.,40.])
            self.assertEqual(Model.options['device'], '0')
            self.assertFalse(Model.options['save'])
            Model.task = 'classify'
            with self.assertRaises(ValueError): YOLOBackend(self.weights, 'cpu')

    def test_each_segmentation_instance_exports_its_own_alpha_and_crop(self):
        class FakeSAM:
            def __init__(self): self.model_path = None
            def process_image(self, *args, **kwargs):
                a = np.zeros((100,60),dtype=np.uint8); a[5:20,10:25]=1
                b = np.zeros_like(a); b[40:60,30:50]=1
                return None, [a,b]
        with patch.dict('sys.modules', {'sam_backend':SimpleNamespace(SAM3Backend=FakeSAM)}):
            self.app.sam_factory=FakeSAM
            self.app.action('segment', {'id': self.photo, 'points': [[15,10]], 'labels':[1]})
            self.wait()
        self.assertEqual(len(self.app.segment['instances']),2)
        for selection, size in [('0',(15,15)), ('1',(20,20)), ('all',(40,55))]:
            output = self.app.action('save-segment', {'path':str(self.root/'out'), 'id':self.photo,
                                                      'instance':selection, 'crop':True})
            with Image.open(output['path']) as image:
                self.assertEqual(image.mode, 'RGBA')
                self.assertEqual(image.size,size)
        original = self.app.action('save-segment', {'path':str(self.root/'out'), 'instance':'1'})
        with Image.open(original['path']) as image:
            self.assertEqual(image.size,(60,100))
            self.assertEqual(image.getpixel((15,10))[3],0)
            self.assertEqual(image.getpixel((35,45))[3],255)
        result = self.app.snapshot()['segment']
        folder = Path(result['directory'])
        self.assertEqual(folder.parent, self.app.home/'segments')
        self.assertEqual((result['width'],result['height']), (60,100))
        for filename in ('mask.png','cutout.png','crop.png','overlay.png','instance-1-mask.png','instance-2-mask.png'):
            self.assertTrue((folder/filename).is_file(), filename)
        for instance in ('all', '0', '1'):
            output = self.app.action('save-segment', {'path':str(self.root/'mask-out'),
                                    'id':self.photo,'instance':instance,'output':'mask','crop':True})
            with Image.open(output['path']) as image:
                self.assertEqual(image.mode,'L')
                self.assertEqual(image.size,(60,100))
                self.assertEqual(image.getpixel((15,10)),255 if instance in ('all','0') else 0)
                self.assertEqual(image.getpixel((35,45)),255 if instance in ('all','1') else 0)
                self.assertEqual(set(np.unique(np.asarray(image))),{0,255})
        with self.assertRaises(ValueError):
            self.app.action('save-segment', {'path':str(self.root),'output':'invalid'})
        with self.assertRaises(ValueError):
            self.app.action('save-segment', {'path':str(self.root), 'instance':'-1'})

    def test_empty_mask_does_not_create_empty_export(self):
        class EmptySAM:
            def __init__(self): self.model_path = None
            def process_image(self,*args,**kwargs): return None, []
        with patch.dict('sys.modules', {'sam_backend': SimpleNamespace(SAM3Backend=EmptySAM)}):
            self.app.sam_factory=EmptySAM
            self.app.action('segment', {'id':self.photo, 'points':[[1,1]], 'labels':[1]})
            self.app.worker.join(5)
        self.assertEqual(self.app.task['state'],'failed')
        self.assertIsNone(self.app.segment)


if __name__ == '__main__':
    unittest.main()
