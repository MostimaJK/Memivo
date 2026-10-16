import json
import io
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path

from PIL import Image

from desktop.application import Application
from desktop.server import create_server


class FakeBackend:
    model_id = 'test-model'
    cache_id = 'test-model:detector:v1'
    providers = ['test-only']

    def extract(self, path):
        return [{'bbox':[10,10,60,70], 'embedding':[1.,0.], 'det_score':.99}]


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'photos'
        self.source.mkdir()
        Image.new('RGB',(100,80),'blue').save(self.source/'中文照片.jpg')
        self.ref = self.root/'reference.jpg'
        Image.new('RGB',(100,80),'red').save(self.ref)
        self.app = Application(self.root/'work', backend_factory=lambda _:FakeBackend())

    def tearDown(self):
        if self.app.worker:
            self.app.worker.join(3)
        self.temp.cleanup()

    def wait(self):
        self.app.worker.join(5)
        self.assertFalse(self.app.worker.is_alive())
        self.assertNotEqual(self.app.task['state'],'failed',self.app.task)

    def setup_recognition(self):
        self.app.action('scan',{'path':str(self.source)})
        self.wait()
        self.app.action('reference',{'name':'小明','paths':[str(self.ref)]})
        self.app.action('config',{'detector':str(self.ref),'recognition':str(self.ref),'threshold':.8})
        self.app.action('recognize',{})
        self.wait()

    def test_real_file_scan_dimensions_and_reference_persistence(self):
        self.app.action('scan',{'path':str(self.source)})
        self.wait()
        photo = self.app.snapshot()['photos'][0]
        self.assertEqual((photo['width'],photo['height']),(100,80))
        self.assertFalse(photo['processed'])
        self.assertTrue(Path(self.app.config['workspace'],'project.json').exists())
        self.app.action('reference',{'name':'小明','paths':[str(self.ref)]})
        restored = Application(self.app.home)
        self.assertIn('小明',restored.config['references'])
        self.assertEqual(len(restored.photos),1)
        self.assertFalse(restored.photos[0]['processed'])

    def test_language_preferences_persist_without_changing_project(self):
        original_config = self.app.config.copy()
        for language in ('en-US', 'zh-TW', 'zh-CN'):
            self.app.action('preferences', {'language': language})
            restored = Application(self.app.home)
            self.assertEqual(restored.snapshot()['preferences']['language'], language)
            self.assertEqual(self.app.config, original_config)
        for invalid in ({'language': 'fr-FR'}, {'language': ['en-US']}, {'language': 'en-US', 'device': 'cuda'}):
            with self.assertRaises(ValueError):
                self.app.action('preferences', invalid)
        self.assertEqual(Application(self.app.home).preferences['language'], 'zh-CN')

    def test_recognition_review_undo_and_multirun_persistence(self):
        self.setup_recognition()
        photo = self.app.photos[0]
        self.assertEqual(photo['faces'][0]['identity'],'小明')
        self.app.action('review',{'id':photo['id'],'face':0,'identity':None})
        self.assertEqual(self.app.photos[0]['faces'][0]['status'],'rejected')
        restored = Application(self.app.home)
        self.assertEqual(restored.photos[0]['faces'][0]['status'],'rejected')
        self.app.action('undo',{})
        self.assertEqual(self.app.photos[0]['faces'][0]['identity'],'小明')
        self.app.action('export',{'path':str(self.root/'export')})
        self.wait()
        self.assertEqual(len(list((self.root/'export').glob('*/*.jpg'))),1)

    def test_unknown_person_and_invalid_settings(self):
        with self.assertRaises(ValueError):
            self.app.action('config',{'threshold':float('nan')})
        with self.assertRaises(ValueError):
            self.app.action('recognize',{})
        self.setup_recognition()
        with self.assertRaises(ValueError):
            self.app.action('review',{'id':self.app.photos[0]['id'],'face':0,'identity':'未登记'})

    def test_segment_coordinates_negative_points_and_alpha_export(self):
        import numpy as np
        class FakeSAM:
            received = None
            def __init__(self):
                self.model_path = None
            def process_image(self, path, points, boxes, conf, iou, labels=None):
                FakeSAM.received = (points, boxes, labels)
                with Image.open(path) as image:
                    image = np.asarray(image.convert('RGB'))
                mask = np.zeros(image.shape[:2],dtype=np.uint8)
                mask[10:30,20:40] = 1
                return image,[mask]
        self.app.action('scan',{'path':str(self.source)})
        self.wait()
        self.app.action('config',{'sam':str(self.ref)})
        photo = self.app.photos[0]
        with patch.dict('sys.modules',{'sam_backend':SimpleNamespace(SAM3Backend=FakeSAM)}):
            self.app.action('segment',{'id':photo['id'],'points':[[25,20]],'labels':[0],
                                       'boxes':[[10,5,80,70]],'text':''})
            self.wait()
        self.assertEqual(FakeSAM.received,([[25,20]],[[10,5,80,70]],[0]))
        result = self.app.action('save-segment',{'path':str(self.root/'cutouts')})
        with Image.open(result['path']) as cutout:
            self.assertEqual(cutout.mode,'RGBA')
            self.assertEqual(cutout.getpixel((0,0))[3],0)
            self.assertEqual(cutout.getpixel((25,20))[3],255)

    def test_failed_task_preserves_previous_photos(self):
        self.app.action('scan',{'path':str(self.source)})
        self.wait()
        empty = self.root/'empty'
        empty.mkdir()
        self.app.action('scan',{'path':str(empty)})
        self.app.worker.join(3)
        self.assertEqual(self.app.task['state'],'failed')
        self.assertEqual(len(self.app.photos),1)

    def test_api_auth_and_registered_image_boundary(self):
        self.app.action('scan',{'path':str(self.source)})
        self.wait()
        server = create_server(self.app)
        worker = threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def get(path, auth=True):
            headers={'X-Memivo-Token':server.token} if auth else {}
            return urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=3)
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                get('/api/state',False)
            self.assertEqual(error.exception.code,403)
            with get('/api/state') as response:
                data=json.load(response)
            with get('/api/image?id='+data['photos'][0]['id']) as response:
                self.assertEqual(response.headers['Content-Type'],'image/jpeg')
                self.assertTrue(response.read().startswith(b'\xff\xd8'))
            large=self.root/'full-size.jpg'
            exif=Image.Exif();exif[274]=6
            Image.new('RGB',(2600,600),'blue').save(large,exif=exif)
            image_id=self.app.register(large)
            with get('/api/image?id='+image_id+'&size=full') as response:
                with Image.open(io.BytesIO(response.read())) as image:
                    self.assertEqual(image.size,(600,2600))
            with self.assertRaises(urllib.error.HTTPError):
                get('/api/image?id=../../README.md')
            with self.assertRaises(urllib.error.HTTPError):
                get('/%2e%2e/README.md')
        finally:
            server.shutdown()
            server.server_close()
            worker.join(3)


if __name__ == '__main__':
    unittest.main()
