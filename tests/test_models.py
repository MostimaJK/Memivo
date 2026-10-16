import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from desktop.models import ModelStore
from desktop.application import Application


class Response(io.BytesIO):
    def __init__(self,data):super().__init__(data);self.headers={'Content-Length':str(len(data))}


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.home=Path(self.temp.name)
        self.store=ModelStore(self.home/'model')

    def tearDown(self):self.temp.cleanup()

    def file(self,name):
        path=self.store.root/name;path.parent.mkdir(exist_ok=True,parents=True);path.write_bytes(b'model-fixture');return str(path)

    def recipe(self,data=b'test-model'):
        self.store.catalog={'checked':'test','models':[dict(id='test',role='yolo',relative='yolo/detect/test.pt',mode='download',url='https://example.invalid/model.pt',size=len(data),sha256=hashlib.sha256(data).hexdigest())]}
        return data

    def test_scan_roles_unicode_nested_and_ignore_partial_empty_wrong_extension(self):
        face=self.file('face/detector/中文/det.onnx');self.file('face/recognition/id.onnx');self.file('sam3/sam3.pt');self.file('yolo/detect/custom.pt')
        self.file('yolo/not-model.txt');self.file('yolo/unfinished.pt.part');(self.store.root/'yolo/empty.pt').touch()
        items=self.store.scan()
        self.assertEqual(items['detector'][0]['path'],face)
        self.assertEqual({k:len(v) for k,v in items.items()},{'detector':1,'recognition':1,'sam':1,'yolo':1})

    def test_single_default_multiple_candidates_and_external_saved_selection(self):
        first=self.file('yolo/detect/a.pt');self.store.scan();self.assertEqual(self.store.defaults({})['yolo'],first)
        self.file('yolo/segment/b-seg.pt');self.store.scan();self.assertNotIn('yolo',self.store.defaults({}))
        external=self.home/'existing.pt';external.write_bytes(b'existing')
        self.assertNotIn('yolo',self.store.defaults({'yolo':str(external)}))
        self.assertEqual(len(self.store.snapshot({'yolo':str(external)})['items']['yolo']),3)

    def test_app_scan_persists_unique_model_and_keeps_choices_on_restart(self):
        app=Application(self.home/'state');weight=app.models.root/'yolo/detect/one.pt';weight.write_bytes(b'fixture')
        app.action('models-scan',{});self.assertEqual(app.config['yolo'],str(weight))
        restored=Application(self.home/'state');self.assertEqual(restored.config['yolo'],str(weight))
        (weight.parent/'two.pt').write_bytes(b'another');restored.action('models-scan',{})
        self.assertEqual(restored.config['yolo'],str(weight))

    def test_verified_download_and_never_overwrite_user_model(self):
        data=self.recipe();progress=[]
        with patch('urllib.request.urlopen',return_value=Response(data)):
            self.store.download('test',lambda:False,lambda *args:progress.append(args))
        target=self.store.root/'yolo/detect/test.pt';self.assertEqual(target.read_bytes(),data)
        self.assertEqual(progress[-1][:2],(len(data),len(data)))
        with self.assertRaises(ValueError):self.store.download('test',lambda:False,lambda *_:None)
        self.assertEqual(target.read_bytes(),data)
        self.assertFalse(list(self.store.root.rglob('*.part')))

    def test_corrupt_or_cancelled_download_is_not_a_model(self):
        data=self.recipe()
        with patch('urllib.request.urlopen',return_value=Response(b'wrong-model')):
            with self.assertRaises(ValueError):self.store.download('test',lambda:False,lambda *_:None)
        with patch('urllib.request.urlopen',return_value=Response(data)):
            with self.assertRaises(RuntimeError):self.store.download('test',lambda:True,lambda *_:None)
        self.assertFalse(list(self.store.root.rglob('*.pt')))
        self.assertFalse(list(self.store.root.rglob('*.part')))

    def test_unregistered_and_gated_models_cannot_be_downloaded_by_url(self):
        for key in ('https://example.invalid/arbitrary.pt','sam3','../../escape'):
            with self.assertRaises(ValueError):self.store.download(key,lambda:False,lambda *_:None)

    def test_symlink_candidates_outside_model_root_are_ignored(self):
        outside=self.home/'outside.pt';outside.write_bytes(b'model')
        try:(self.store.root/'yolo/link.pt').symlink_to(outside)
        except OSError:self.skipTest('Symlink creation unavailable')
        self.assertEqual(self.store.scan()['yolo'],[])


if __name__=='__main__':unittest.main()
