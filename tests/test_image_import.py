"""Exercise the real local HTTP upload and collection persistence, without models."""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PIL import Image
from desktop.application import Application
from desktop.server import create_server


class ImageImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.app=Application(self.root/'app')
        self.server=create_server(self.app)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.batch=str(uuid.uuid4())

    def tearDown(self):
        if self.app.worker:self.app.worker.join(5)
        self.server.shutdown();self.server.server_close();self.thread.join(3)
        self.temp.cleanup()

    def upload(self,name='照片.png',color='blue',body=None,auth=True,batch=None):
        if body is None:
            output=io.BytesIO();Image.new('RGB',(64,48),color).save(output,format='PNG');body=output.getvalue()
        query=urllib.parse.urlencode(dict(name=name,batch=batch or self.batch))
        headers={'X-Memivo-Token':self.server.token} if auth else {}
        request=urllib.request.Request(self.base+'/api/upload-image?'+query,data=body,headers=headers)
        with urllib.request.urlopen(request,timeout=3) as response:return json.load(response)

    def wait(self):
        self.app.worker.join(5)
        self.assertFalse(self.app.worker.is_alive())
        self.assertEqual(self.app.task['state'],'completed',self.app.task)

    def test_upload_validates_files_and_auth_before_import(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.upload(auth=False)
        self.assertEqual(error.exception.code,403)
        for name,body,batch in [('../escape.png',b'x',None),('x:evil.png',b'x',None),
                                ('bad.exe',b'x',None),('bad.png',b'not an image',None),
                                ('bad.png',b'x','../escape'),('empty.png',b'',None)]:
            with self.subTest(name=name,body=body,batch=batch):
                with self.assertRaises(urllib.error.HTTPError):self.upload(name,body=body,batch=batch)
        self.assertFalse(list(self.app.home.rglob('*.part')))
        saved=self.upload()
        self.assertEqual(Path(saved['path']).name,'照片.png')
        self.assertEqual(Path(saved['path']).parent,Path(saved['folder']))
        with Image.open(saved['path']) as image:self.assertEqual(image.size,(64,48))
        self.assertEqual(self.app.photos,[])
        other=self.upload(color='red')
        self.assertNotEqual(other['path'],saved['path'])

    def test_append_deduplicates_and_persists_without_replacing_project(self):
        original=self.root/'original.png';Image.new('RGB',(64,48),'blue').save(original)
        self.app.scan(str(original));self.wait()
        workspace=self.app.config['workspace'];old_id=self.app.photos[0]['id']
        self.upload('duplicate.png');saved=self.upload('new.png',color='red')
        self.app.action('import-drop',{'path':saved['folder']});self.wait()
        self.assertEqual(len(self.app.photos),2)
        self.assertEqual(self.app.photos[0]['id'],old_id)
        self.assertEqual(self.app.config['workspace'],workspace)
        self.assertEqual(self.app.config['source'],str(original.resolve()))
        restored=Application(self.app.home)
        self.assertEqual(len(restored.photos),2)
        self.assertEqual(len(restored.config['input_paths']),2)
        self.assertTrue(all(not p['processed'] for p in restored.photos))
        self.assertTrue(original.is_file())
        self.app.scan(str(original));self.wait()
        self.assertNotIn('input_paths',self.app.config)

    def test_report_review_is_preserved_and_only_imported_files_are_recognized(self):
        class Backend:
            model_id=cache_id='test-only';providers=['test-only']
            def extract(self,path):return [{'bbox':[1,1,30,30],'embedding':[1.,0.],'det_score':.99}]
        original=self.root/'original.png';Image.new('RGB',(64,48),'blue').save(original)
        self.app.backend_factory=lambda _:Backend()
        self.app.scan(str(original));self.wait()
        self.app.action('reference',{'name':'Friend','paths':[str(original)]})
        self.app.action('config',{'detector':str(original),'recognition':str(original)})
        self.app.recognize();self.wait()
        self.app.action('review',{'id':self.app.photos[0]['id'],'face':0,'identity':None})
        saved=self.upload(color='red');self.app.import_drop(saved['folder']);self.wait()
        restored=Application(self.app.home)
        self.assertEqual([p['processed'] for p in restored.photos],[True,False])
        self.assertEqual(restored.photos[0]['faces'][0]['status'],'rejected')
        # This uncommitted upload is a sibling of the selected batch and must stay out.
        self.upload(color='green',batch=str(uuid.uuid4()))
        self.app.recognize();self.wait()
        self.assertEqual(len(self.app.photos),2)
        self.assertEqual(self.app.photos[0]['faces'][0]['status'],'rejected')

    def test_cancel_before_commit_preserves_original_library(self):
        saved=self.upload()
        self.app.progress=lambda *args:self.app.cancel.set()
        self.app.import_drop(saved['folder']);self.app.worker.join(5)
        self.assertEqual(self.app.task['state'],'cancelled')
        self.assertEqual(self.app.photos,[])
        self.assertNotIn('input_paths',self.app.config)
        with self.assertRaises(ValueError):self.app.import_drop(str(self.root))


if __name__=='__main__':unittest.main()
