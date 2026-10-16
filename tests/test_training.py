import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from desktop.datasets import DatasetStore
from desktop.training import TrainingStore


class FakeRuntime:
    def __init__(self):self.calls=[];self.fail=False
    def python_for(self,key):return Path('test-only-python')
    def job(self,feature,action,payload,cancelled,progress):
        self.calls.append((action,payload))
        if self.fail:raise RuntimeError('test failure')
        if action=='evaluate':return dict(metrics={'metrics/mAP50(B)':.5},count_mae=.25,images=1,count_conf=.25)
        out=Path(payload['output']);best=out/'training/weights/best.pt';best.parent.mkdir(parents=True,exist_ok=True);best.write_bytes(b'test-only-weights')
        (best.parent/'last.pt').write_bytes(b'test-only-checkpoint')
        return dict(best=str(best),metrics=[{'epoch':1,'metrics/mAP50(B)':.1}])


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        source=self.root/'source';source.mkdir()
        for n in range(3):Image.new('RGB',(50,60),(n*60,70,80)).save(source/f'{n}.png')
        self.datasets=DatasetStore(self.root/'home');self.key=self.datasets.create('train','detect')['id']
        self.datasets.import_images(self.key,source,'',lambda *a:None,lambda:False);self.datasets.add_class(self.key,'pen')
        for image in self.datasets.load()['images']:
            self.datasets.save_labels(self.key,image['id'],[dict(type='box',class_id=0,bbox=[1,1,20,30])],True,False,0)
        self.datasets.split(self.key);self.version=self.datasets.export_version(self.key)['id']
        self.runtime=FakeRuntime();self.store=TrainingStore(self.root/'home',self.datasets,self.runtime)
        self.weights=self.root/'initial.pt';self.weights.write_bytes(b'initial')
        self.options=dict(dataset=self.key,version=self.version,weights=str(self.weights),epochs=1,imgsz=320,batch=2,device='cpu')

    def tearDown(self):self.temp.cleanup()

    def test_record_links_fixed_version_and_model_digest(self):
        self.store.run(self.options,lambda:False,lambda *a:None)
        run=self.store.snapshot()[0]
        self.assertEqual(run['state'],'completed');self.assertEqual(run['version'],self.version)
        self.assertEqual(self.store.model(run['id']).read_bytes(),b'test-only-weights')
        self.assertEqual(TrainingStore(self.root/'home',self.datasets,self.runtime).snapshot()[0]['id'],run['id'])

    def test_evaluate_export_and_detect_mutated_model(self):
        self.store.run(self.options,lambda:False,lambda *a:None);key=self.store.snapshot()[0]['id']
        self.store.evaluate(key,lambda:False,lambda *a:None)
        self.assertEqual(self.store.records[key]['evaluation']['count_mae'],.25)
        exported=self.store.export_model(key,self.root/'export')
        self.assertTrue((Path(exported['path'])/'model.json').is_file())
        self.store.model(key).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.store.model(key)

    def test_cancelled_training_can_resume_existing_checkpoint(self):
        self.store.run(self.options,lambda:False,lambda *a:None);key=self.store.snapshot()[0]['id']
        self.store.update(key,state='cancelled');self.assertTrue(self.store.snapshot()[0]['can_resume'])
        self.store.run({'resume':key},lambda:False,lambda *a:None)
        self.assertTrue(self.runtime.calls[-1][1]['resume'])
        self.assertEqual(self.store.records[key]['state'],'completed')

    def test_invalid_configuration_and_missing_engine(self):
        for change in ({'epochs':0},{'imgsz':321},{'batch':0},{'weights':'missing.pt'}):
            with self.assertRaises(ValueError):self.store.run(dict(self.options,**change),lambda:False,lambda *a:None)
        self.runtime.python_for=lambda _:None
        with self.assertRaises(ValueError):self.store.run(self.options,lambda:False,lambda *a:None)

    def test_failed_run_is_recorded_and_interrupted_run_restored(self):
        self.runtime.fail=True
        with self.assertRaises(RuntimeError):self.store.run(self.options,lambda:False,lambda *a:None)
        key=self.store.snapshot()[0]['id'];self.assertEqual(self.store.records[key]['state'],'failed')
        self.store.update(key,state='running')
        restored=TrainingStore(self.root/'home',self.datasets,self.runtime)
        self.assertEqual(restored.records[key]['state'],'interrupted')


if __name__=='__main__':unittest.main()
