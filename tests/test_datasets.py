import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from desktop.datasets import DatasetStore
from desktop.application import Application


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'source';self.source.mkdir()
        for n in range(6):Image.new('RGB',(100,80),(n*30,80,150)).save(self.source/f'{n}.png')
        self.store=DatasetStore(self.root/'home');self.key=self.store.create('test','detect')['id']
        self.store.import_images(self.key,self.source,'',lambda *a:None,lambda:False)
        self.store.add_class(self.key,'pen')

    def tearDown(self):self.temp.cleanup()

    def label_all(self,polygon=False):
        for image in self.store.load()['images']:
            ann=dict(id='test-label',type='polygon',class_id=0,points=[[10,10],[50,10],[50,50],[10,50]]) if polygon else dict(id='test-label',type='box',class_id=0,bbox=[10,10,50,50])
            self.store.save_labels(self.key,image['id'],[ann],True,False,0)
        self.store.split(self.key,42)

    def test_pixel_duplicates_and_restored_selection(self):
        result=self.store.import_images(self.key,self.source,'',lambda *a:None,lambda:False)
        self.assertEqual(result['added'],0);self.assertEqual(result['skipped'],6)
        self.assertEqual(DatasetStore(self.root/'home').active,self.key)
        self.assertEqual(len(list(self.source.glob('*.png'))),6)

    def test_annotation_validation_revision_and_negative_samples(self):
        image=self.store.load()['images'][0]
        with self.assertRaises(ValueError):self.store.save_labels(self.key,image['id'],[],True,False,0)
        self.store.save_labels(self.key,image['id'],[],True,True,0)
        with self.assertRaises(ValueError):self.store.save_labels(self.key,image['id'],[],False,False,0)
        for box in ([-1,0,10,10],[10,10,10,20],[0,0,float('nan'),10]):
            with self.assertRaises(ValueError):self.store.save_labels(self.key,image['id'],[dict(type='box',class_id=0,bbox=box)],True,False,1)
        with self.assertRaises(ValueError):self.store.save_labels(self.key,image['id'],[dict(type='box',class_id=99,bbox=[0,0,10,10])],True,False,1)

    def test_group_split_and_seed_are_reproducible(self):
        images=self.store.load()['images']
        self.store.set_group(self.key,images[0]['id'],'burst')
        self.store.set_group(self.key,images[1]['id'],'burst')
        self.store.split(self.key,7);before={i['id']:i['split'] for i in self.store.load()['images']}
        self.assertEqual(before[images[0]['id']],before[images[1]['id']])
        self.store.split(self.key,7);self.assertEqual(before,{i['id']:i['split'] for i in self.store.load()['images']})
        self.store.set_split(self.key,images[0]['id'],'test')
        self.assertTrue(all(i['split']=='test' for i in self.store.load()['images'] if i['group']=='burst'))

    def test_snapshot_labels_normalized_and_checksums_detect_mutation(self):
        self.label_all();manifest=self.store.export_version(self.key)
        folder,_=self.store.version(self.key,manifest['id'])
        line=next(folder.glob('labels/train/*.txt')).read_text().strip().split()
        self.assertEqual(line[0],'0');self.assertEqual(list(map(float,line[1:])),[.3,.375,.4,.5])
        next(folder.glob('labels/train/*.txt')).write_text('changed')
        with self.assertRaises(ValueError):self.store.version(self.key,manifest['id'])

    def test_unreviewed_images_excluded_and_empty_splits_rejected(self):
        with self.assertRaises(ValueError):self.store.export_version(self.key)
        self.label_all()
        before=self.store.load();image=next(i for i in before['images'] if i['split']=='train')
        self.store.save_labels(self.key,image['id'],image['annotations'],False,False,image['revision'])
        result=self.store.export_version(self.key);self.assertEqual(result['excluded'],1)

    def test_segment_versions_require_real_polygons(self):
        data=self.store.load();data['task']='segment';self.store.write(data)
        self.label_all()
        with self.assertRaises(ValueError):self.store.export_version(self.key)
        for image in self.store.load()['images']:
            self.store.save_labels(self.key,image['id'],[dict(type='polygon',class_id=0,points=[[1,1],[50,1],[20,60]])],True,False,image['revision'])
        result=self.store.export_version(self.key)
        folder,_=self.store.version(self.key,result['id'])
        self.assertEqual(len(next(folder.glob('labels/train/*.txt')).read_text().split()),7)

    def test_cancelled_export_keeps_source_and_no_completed_version(self):
        self.label_all()
        with self.assertRaises(RuntimeError):self.store.export_version(self.key,lambda:True)
        self.assertEqual(len(self.store.load()['images']),6)
        self.assertFalse(list((self.store.folder(self.key)/'versions').glob('*/manifest.json')))

    def test_application_dataset_actions_do_not_change_album_project(self):
        app=Application(self.root/'application');before=dict(app.config)
        app.action('dataset-create',{'name':'independent','task':'detect'})
        app.action('dataset-class',{'name':'pen'})
        self.assertEqual(app.config,before)
        self.assertEqual(app.snapshot()['datasets']['active']['classes'][0]['name'],'pen')
        self.assertEqual(Application(app.home).datasets.active,app.datasets.active)

    def test_reject_directory_escape(self):
        for key in ('../source','',str(self.source)):
            with self.assertRaises(ValueError):self.store.folder(key)


if __name__=='__main__':unittest.main()
