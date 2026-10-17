"""Worker process lifecycle tests use a protocol double, not fake speed benchmarks."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image
from desktop.inference_worker import DetectionWorker
from desktop.runtimes import RuntimeManager
from scripts.detection_worker import DetectorSession


class DetectorSessionTests(unittest.TestCase):
    def test_model_reuse_and_invalidation_keep_image_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);weights=root/'w.pt';weights.touch()
            exif=Image.Exif();exif[274]=6
            Image.new('RGB',(60,90)).save(root/'im.jpg',exif=exif)
            calls=[]
            class Backend:
                def __init__(self,path,device):calls.append((path,device))
                def predict(self,image,conf,iou):
                    self_test.assertEqual(image.size,(90,60));return []
            self_test=self;session=DetectorSession(Backend)
            data=dict(weights=str(weights),device='cpu',path=str(root/'im.jpg'),conf=.25,iou=.7)
            self.assertFalse(session.detect(data)['performance']['model_reused'])
            self.assertTrue(session.detect(dict(data,conf=.5))['performance']['model_reused'])
            self.assertEqual(len(calls),1)
            weights.write_bytes(b'changed')
            self.assertFalse(session.detect(data)['performance']['model_reused'])
            self.assertFalse(session.detect(dict(data,device='cuda'))['performance']['model_reused'])
            self.assertEqual(len(calls),3)


class WorkerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        scripts=self.root/'scripts';scripts.mkdir()
        (scripts/'detection_worker.py').write_text('''import json,sys,time,os
from pathlib import Path
for line in sys.stdin:
    m=json.loads(line);r=json.loads(Path(m['request']).read_text(encoding='utf-8'));p=r['payload']
    if p.get('exit'):os._exit(9)
    time.sleep(p.get('delay',0))
    Path(r['result']).write_text(json.dumps(dict(detections=[],performance=dict(pid=os.getpid()))),encoding='utf-8')
    print('MEMIVO_DETECTION:'+json.dumps(dict(id=m['id'],ok=True)),flush=True)
''',encoding='utf-8')
        self.manager=RuntimeManager(self.root/'home')
        self.worker=DetectionWorker(self.manager)
        self.manager.detection_worker=self.worker
        self.patcher=patch('desktop.runtimes.ROOT',self.root);self.patcher.start()

    def tearDown(self):
        self.worker.close();self.patcher.stop();self.temp.cleanup()

    def request(self,payload=None,cancelled=lambda:False,timeout=5):
        return self.worker.request(sys.executable,payload or {},cancelled,lambda *a:None,timeout)

    def test_process_reuse_explicit_release_and_restart(self):
        first=self.request()['performance']['pid']
        self.assertEqual(self.request()['performance']['pid'],first)
        process=self.worker.process;self.worker.close()
        self.assertIsNotNone(process.poll())
        self.assertNotEqual(self.request()['performance']['pid'],first)
        self.assertFalse(list(self.manager.root.glob('detect-*')))

    def test_cancellation_and_timeout_kill_the_worker_without_stale_results(self):
        self.request();process=self.worker.process;start=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'cancelled'):
            self.request({'delay':5},lambda:time.monotonic()-start>.15)
        self.assertIsNotNone(process.poll())
        self.request();process=self.worker.process
        with self.assertRaisesRegex(RuntimeError,'timed out'):self.request({'delay':5},timeout=.15)
        self.assertIsNotNone(process.poll())
        self.assertIn('performance',self.request())
        self.assertFalse(list(self.manager.root.glob('detect-*')))

    def test_abrupt_exit_and_idle_release_allow_recovery(self):
        with self.assertRaisesRegex(RuntimeError,'exited'):self.request({'exit':True})
        self.worker.idle_seconds=.05
        self.request();process=self.worker.process
        deadline=time.monotonic()+3
        while process.poll() is None and time.monotonic()<deadline:time.sleep(.05)
        self.assertIsNotNone(process.poll())
        self.assertIn('performance',self.request())

    def test_uninstall_and_stdin_eof_release_the_process(self):
        self.manager.save('vision',state='ready',profile='cpu')
        self.request();process=self.worker.process
        self.manager.uninstall('vision')
        self.assertIsNotNone(process.poll())
        self.request();process=self.worker.process
        process.stdin.close();process.wait(timeout=5)
        self.assertIsNotNone(process.poll())


if __name__=='__main__':unittest.main()
