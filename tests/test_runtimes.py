"""Runtime lifecycle tests do not download real AI dependencies."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import subprocess
from unittest.mock import patch

from desktop.runtimes import RuntimeManager, probe_hardware
from desktop.application import Application


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.manager=RuntimeManager(self.root)
        self.manager.hardware=dict(recommended='cpu',cuda_candidate=False)

    def tearDown(self):
        self.manager.close_detection()
        self.temp.cleanup()

    def fake_commands(self,commands,fail_at=None):
        def run(command,cancelled,progress=None,timeout=3600):
            commands.append([str(x) for x in command])
            if fail_at and len(commands)==fail_at:
                raise RuntimeError('simulated installer failure')
            if command[1:3]==['-m','venv']:
                python=self.manager.executable(Path(command[-1]).name)
                python.parent.mkdir(parents=True,exist_ok=True)
                python.touch()
        return run

    def test_cpu_install_recipe_and_owned_uninstall_preserve_user_data(self):
        models=self.root/'models';models.mkdir();(models/'mine.pt').write_bytes(b'keep')
        commands=[]
        with patch.object(self.manager,'run',side_effect=self.fake_commands(commands)):
            self.manager.install('vision','auto',lambda:False,lambda *args:None)
        self.assertIsNotNone(self.manager.python_for('vision'))
        torch_command=next(c for c in commands if 'torch==2.9.1' in c)
        self.assertIn('https://download.pytorch.org/whl/cpu',torch_command)
        self.assertTrue(any('pip' in c and 'check' in c for c in commands))
        self.assertTrue(any('nms(' in ' '.join(c) for c in commands))
        self.assertEqual(RuntimeManager(self.root).records['vision']['state'],'ready')
        self.manager.uninstall('vision')
        self.assertFalse(self.manager.directory('vision').exists())
        self.assertEqual((models/'mine.pt').read_bytes(),b'keep')

    def test_failed_install_is_not_available_and_can_be_cleaned(self):
        commands=[]
        with patch.object(self.manager,'run',side_effect=self.fake_commands(commands,fail_at=3)):
            with self.assertRaises(RuntimeError):
                self.manager.install('vision','cpu',lambda:False,lambda *args:None)
        self.assertIsNone(self.manager.python_for('vision'))
        self.assertEqual(self.manager.records['vision']['state'],'failed')
        self.manager.uninstall('vision')
        self.assertNotIn('vision',self.manager.records)

    def test_refuse_foreign_directory_and_unknown_features(self):
        target=self.manager.directory('vision');target.mkdir();(target/'keep.txt').write_text('keep')
        with self.assertRaises(ValueError): self.manager.uninstall('vision')
        with self.assertRaises(ValueError): self.manager.install('vision','cpu',lambda:False,lambda *a:None)
        self.assertTrue((target/'keep.txt').exists())
        for feature in ('../models','','unknown'):
            with self.assertRaises(ValueError): self.manager.directory(feature)

    def test_gpu_profile_requires_compatible_probe_and_verified_recipe(self):
        with self.assertRaises(ValueError):
            self.manager.install('vision','cu128',lambda:False,lambda *a:None)
        self.manager.hardware=dict(recommended='cu128',cuda_candidate=True)
        commands=[]
        with patch.object(self.manager,'run',side_effect=self.fake_commands(commands)):
            self.manager.install('vision','auto',lambda:False,lambda *a:None)
        self.assertTrue(any('https://download.pytorch.org/whl/cu128' in c for c in commands))
        self.assertEqual(self.manager.records['vision']['profile'],'cu128')
        face_commands=[]
        with patch.object(self.manager,'run',side_effect=self.fake_commands(face_commands)):
            self.manager.install('face','auto',lambda:False,lambda *a:None)
        self.assertIsNotNone(self.manager.python_for('face'))
        self.assertEqual(self.manager.records['face']['profile'],'cu128')
        packages=[p for command in face_commands for p in command]
        self.assertIn('onnxruntime-gpu[cuda,cudnn]==1.23.2',packages)
        self.assertNotIn('onnxruntime==1.23.2',packages)
        self.assertIn('nvidia-cudnn-cu12==9.10.2.21',packages)
        self.assertTrue(any('verify_face_runtime' in ' '.join(c) for c in face_commands))

    def test_face_cpu_selection_and_failed_gpu_validation(self):
        commands=[]
        with patch.object(self.manager,'run',side_effect=self.fake_commands(commands)):
            self.manager.install('face','auto',lambda:False,lambda *a:None)
        self.assertEqual(self.manager.records['face']['profile'],'cpu')
        self.assertTrue(any('onnxruntime==1.23.2' in c for c in commands))
        self.manager.uninstall('face')
        self.manager.hardware=dict(recommended='cu128',cuda_candidate=True)
        with patch.object(self.manager,'run',side_effect=self.fake_commands([],fail_at=5)):
            with self.assertRaises(RuntimeError):
                self.manager.install('face','auto',lambda:False,lambda *a:None)
        self.assertIsNone(self.manager.python_for('face'))
        self.assertEqual(self.manager.records['face']['state'],'failed')

    def test_face_gpu_refused_without_compatible_hardware(self):
        with self.assertRaises(ValueError):
            self.manager.install('face','cu128',lambda:False,lambda *a:None)
        self.assertFalse(self.manager.directory('face').exists())

    def test_managed_face_recognition_gpu_profile_guard_and_forwarding(self):
        app=Application(self.root/'app')
        weight=self.root/'face.onnx';weight.touch()
        app.config.update(source=str(self.root),references={'friend':[str(weight)]},
                          detector=str(weight),recognition=str(weight),device='cuda')
        with patch.object(app.runtimes,'python_for',return_value=Path(sys.executable)), \
             patch.object(app.runtimes,'job',side_effect=RuntimeError('GPU job reached')) as job:
            app.runtimes.records['face']={'profile':'cpu'}
            app.recognize();app.worker.join(5)
            self.assertEqual(app.task['state'],'failed')
            self.assertIn('NVIDIA',app.task['error'])
            job.assert_not_called()
            app.runtimes.records['face']={'profile':'cu128'}
            app.recognize();app.worker.join(5)
            self.assertIn('GPU job reached',app.task['error'])
            self.assertEqual(job.call_args.args[2]['config']['device'],'cuda')

    def test_interrupted_install_not_reported_as_ready(self):
        self.manager.directory('vision').mkdir()
        self.manager.save('vision',state='installing',profile='cpu')
        restored=RuntimeManager(self.root)
        self.assertEqual(restored.records['vision']['state'],'failed')
        self.assertIsNone(restored.python_for('vision'))

    def test_actual_subprocess_logs_unicode_and_cancellation(self):
        self.manager.run([sys.executable,'-c',"print('测试 diagnostic')"],lambda:False,timeout=5)
        self.assertTrue(any('测试 diagnostic' in line for line in self.manager.logs))
        stop=threading.Event()
        timer=threading.Timer(.3,stop.set);timer.start()
        started=time.monotonic()
        try:
            with self.assertRaises(RuntimeError):
                self.manager.run([sys.executable,'-c','import time; time.sleep(30)'],stop.is_set,timeout=5)
        finally:
            timer.cancel()
        self.assertLess(time.monotonic()-started,8)
        self.assertIsNone(self.manager.process)

    def test_real_subprocess_failure_preserves_traceback_and_survives_restart(self):
        with self.assertRaisesRegex(RuntimeError,'test-only subprocess failure'):
            self.manager.run([sys.executable,'-c',"raise ValueError('test-only subprocess failure')"],lambda:False,timeout=5)
        snapshot=self.manager.snapshot()
        log=Path(snapshot['log_file'])
        self.assertEqual(log.parent,self.manager.log_root)
        self.assertIn('Traceback',log.read_text(encoding='utf-8'))
        self.assertEqual(snapshot['last_failure']['returncode'],1)
        restored=RuntimeManager(self.root).snapshot()
        self.assertEqual(restored['last_failure'],snapshot['last_failure'])

    def test_cpu_engine_rejects_cuda_before_spawning_for_all_job_payloads(self):
        target=self.manager.directory('vision');target.mkdir()
        python=self.manager.executable('vision');python.parent.mkdir(parents=True);python.touch()
        self.manager.save('vision',state='ready',profile='cpu')
        for payload in ({'device':'cuda'},{'config':{'device':'cuda'}},{'options':{'device':'cuda'}}):
            with self.subTest(payload=payload),patch.object(self.manager,'run') as run:
                with self.assertRaisesRegex(ValueError,'CPU'):
                    self.manager.job('vision','detect',payload,lambda:False,lambda *a:None)
                run.assert_not_called()

    def test_application_exception_has_persistent_traceback(self):
        app=Application(self.root/'app')
        def fail():raise ValueError('test-only application failure')
        app.start_task('test-only',fail);app.worker.join(5)
        self.assertEqual(app.task['state'],'failed')
        log=Path(app.task['log_file'])
        self.assertIn('ValueError: test-only application failure',log.read_text(encoding='utf-8'))

    def test_job_uses_managed_interpreter_and_private_json_contract(self):
        target=self.manager.directory('vision');target.mkdir()
        python=self.manager.executable('vision');python.parent.mkdir(parents=True);python.touch()
        self.manager.save('vision',state='ready',profile='cpu')
        def run(command,cancelled,progress=None,timeout=3600):
            self.assertEqual(command[0],python)
            request=json.loads(Path(command[-1]).read_text(encoding='utf-8'))
            self.assertEqual(request['action'],'mask-polygons')
            Path(request['result']).write_text(json.dumps({'detections':[]}),encoding='utf-8')
        with patch.object(self.manager,'run',side_effect=run):
            self.assertEqual(self.manager.job('vision','mask-polygons',{'path':'中文.png'},lambda:False,lambda *a:None),{'detections':[]})
        self.assertFalse(list(self.manager.root.glob('job-*')))

    def test_no_nvidia_recommends_cpu(self):
        with patch('desktop.runtimes.shutil.which',return_value=None):
            hardware=probe_hardware(self.root)
        self.assertEqual(hardware['recommended'],'cpu')
        self.assertFalse(hardware['cuda_candidate'])

    def test_nvidia_legacy_and_umd_version_formats(self):
        query='NVIDIA GeForce RTX 5070 Ti, 617.42, 16303, 12.0\n'
        for header,version in [('CUDA Version: 12.8','12.8'),
                               ('NVIDIA-SMI 617.42 KMD Version: 617.42 CUDA UMD Version: 13.4','13.4'),
                               ('CUDA UMD Version : 13.4','13.4')]:
            with self.subTest(header=header), \
                 patch('desktop.runtimes.shutil.which',return_value='nvidia-smi'), \
                 patch('desktop.runtimes.subprocess.run',side_effect=[
                     subprocess.CompletedProcess([],0,query,''),subprocess.CompletedProcess([],0,header,'')]):
                hardware=probe_hardware(self.root)
                self.assertEqual(hardware['driver_cuda_max'],version)
                self.assertTrue(hardware['cuda_candidate'])
                self.assertEqual(hardware['recommended'],'cu128')

    def test_nvidia_old_unknown_or_failed_driver_probe_not_approved(self):
        query=subprocess.CompletedProcess([],0,'NVIDIA GeForce RTX 5070 Ti, 617.42, 16303, 12.0\n','')
        for summary in [subprocess.CompletedProcess([],0,'CUDA Version: 12.7',''),
                        subprocess.CompletedProcess([],0,'CUDA UMD Version: N/A',''),
                        subprocess.CompletedProcess([],1,'','driver query failed')]:
            with self.subTest(summary=summary), \
                 patch('desktop.runtimes.shutil.which',return_value='nvidia-smi'), \
                 patch('desktop.runtimes.subprocess.run',side_effect=[query,summary]):
                hardware=probe_hardware(self.root)
                self.assertFalse(hardware['cuda_candidate'])
                self.assertEqual(hardware['recommended'],'cpu')
                if '12.7' not in summary.stdout:
                    self.assertTrue(hardware.get('diagnostic'))

    def test_real_worker_process_in_isolated_environment_with_model_double(self):
        # A genuine venv + subprocess/JSON round-trip. Only the model is synthetic.
        import PIL
        from PIL import Image
        target=self.manager.directory('vision')
        subprocess.run([sys.executable,'-m','venv','--without-pip',str(target)],check=True,
                       capture_output=True)
        python=self.manager.executable('vision')
        site=Path(subprocess.check_output([str(python),'-c','import site;print(site.getsitepackages()[0])'],text=True).strip())
        site.mkdir(parents=True,exist_ok=True)
        (site/'test-only-parent.pth').write_text(str(Path(PIL.__file__).resolve().parent.parent)+'\n',encoding='utf-8')
        (site/'ultralytics.py').write_text('''from types import SimpleNamespace
class Tensor:
    def __init__(self,value): self.value=value
    def cpu(self): return self
    def tolist(self): return self.value
class YOLO:
    task='detect'
    def __init__(self,path): pass
    def predict(self,**kwargs):
        return [SimpleNamespace(names={0:'test-only'},boxes=SimpleNamespace(xyxy=Tensor([[1,2,10,20]]),conf=Tensor([.9]),cls=Tensor([0])))]
''',encoding='utf-8')
        self.manager.save('vision',state='ready',profile='test-only')
        image=self.root/'test-image.png';Image.new('RGB',(30,40)).save(image)
        weights=self.root/'test.pt';weights.touch()
        result=self.manager.job('vision','detect',dict(path=str(image),weights=str(weights),
                device='cpu',conf=.25,iou=.7),lambda:False,lambda *a:None)
        self.assertEqual(result['detections'][0]['name'],'test-only')
        self.assertEqual(result['detections'][0]['bbox'],[1.,2.,10.,20.])
        self.assertFalse(result['performance']['model_reused'])
        second=self.manager.job('vision','detect',dict(path=str(image),weights=str(weights),
                device='cpu',conf=.4,iou=.7),lambda:False,lambda *a:None)
        self.assertTrue(second['performance']['model_reused'])
        self.assertEqual(result['performance']['pid'],second['performance']['pid'])
        weights.write_bytes(b'updated weights')
        third=self.manager.job('vision','detect',dict(path=str(image),weights=str(weights),
                device='cpu',conf=.4,iou=.7),lambda:False,lambda *a:None)
        self.assertFalse(third['performance']['model_reused'])

    def test_environment_action_runs_without_changing_project(self):
        app=Application(self.root/'app');before=dict(app.config)
        with patch.object(app.runtimes,'scan',return_value='test-only scan'):
            app.action('environment-detect',{})
            app.worker.join(5)
        self.assertEqual(app.task['state'],'completed')
        self.assertEqual(app.config,before)
        self.assertEqual(len(app.snapshot()['runtimes']['engines']),2)


if __name__=='__main__':
    unittest.main()
