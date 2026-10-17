"""Serialized, supervised local inference process; never shares a YOLO model across threads."""
import atexit
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import uuid

from album.core import save_json


class DetectionWorker:
    def __init__(self, manager, idle_seconds=300):
        self.manager=manager
        self.idle_seconds=idle_seconds
        self.lock=threading.RLock()
        self.process=None
        self.reader=None
        self.responses=queue.Queue()
        self.last_used=0
        self.interpreter=None
        atexit.register(self.close)

    def close(self):
        with self.lock:
            process=self.process
            if process is None:return
            self.process=None
            if process.poll() is None:
                self.manager.terminate(process)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            if self.reader:self.reader.join(3)
            for pipe in (process.stdin,process.stdout):
                if pipe:pipe.close()

    def expire(self, process):
        while process.poll() is None:
            time.sleep(1)
            # A live request holds the same lock, so it cannot expire mid-inference.
            with self.lock:
                if self.process is not process:return
                if time.monotonic()-self.last_used>=self.idle_seconds:
                    self.close();return

    def start(self, python):
        from .runtimes import ROOT, clean_environment, child_options
        if self.process and self.process.poll() is None and self.interpreter==str(python):return
        self.close()
        env=clean_environment()
        env.update(YOLO_CONFIG_DIR=str(self.manager.root/'ultralytics-settings'),
                   MPLCONFIGDIR=str(self.manager.root/'matplotlib-settings'),YOLO_AUTOINSTALL='false')
        process=subprocess.Popen([str(python),str(ROOT/'scripts/detection_worker.py')],cwd=ROOT,env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,encoding='utf-8',errors='replace',bufsize=1,**child_options())
        responses=queue.Queue()
        self.process=process;self.interpreter=str(python);self.responses=responses
        def consume():
            for line in process.stdout:
                if line.startswith('MEMIVO_DETECTION:'):
                    try:responses.put(json.loads(line.removeprefix('MEMIVO_DETECTION:')))
                    except ValueError:self.manager.log(line)
                else:self.manager.log(line)
            responses.put({'exited':True})
        self.reader=threading.Thread(target=consume,daemon=True);self.reader.start()
        self.last_used=time.monotonic()
        threading.Thread(target=self.expire,args=(process,),daemon=True).start()

    def request(self, python, payload, cancelled, progress, timeout=300):
        with self.lock:
            start=time.perf_counter()
            try:
                if cancelled():raise RuntimeError('Operation cancelled.')
                self.start(python)
                process=self.process
                with tempfile.TemporaryDirectory(prefix='detect-',dir=self.manager.root) as folder:
                    job=uuid.uuid4().hex
                    request=Path(folder)/'request.json';result=Path(folder)/'result.json'
                    save_json(request,dict(payload=payload,result=str(result)))
                    process.stdin.write(json.dumps(dict(id=job,request=str(request)),ensure_ascii=False)+'\n')
                    process.stdin.flush()
                    while True:
                        if cancelled():raise RuntimeError('Operation cancelled.')
                        if time.perf_counter()-start>timeout:raise RuntimeError('Detection timed out.')
                        try:message=self.responses.get(timeout=.05)
                        except queue.Empty:continue
                        if message.get('exited'):raise RuntimeError('YOLO worker exited unexpectedly.\n'+'\n'.join(self.manager.logs)[-2400:])
                        if message.get('id')!=job:continue
                        if message.get('progress'):
                            progress(0,0,message['progress']);continue
                        if message.get('error'):
                            detail='\n'.join(list(self.manager.logs)[-12:])[-2400:]
                            raise RuntimeError(message['error']+'\nRecent engine output:\n'+detail)
                        data=json.loads(result.read_text(encoding='utf-8'))
                        data['performance']['worker_roundtrip_ms']=round((time.perf_counter()-start)*1000,2)
                        self.manager.log('YOLO performance: '+json.dumps(data['performance'],ensure_ascii=False))
                        return data
            except Exception:
                # A failed/cancelled model is discarded; retry starts a clean worker.
                self.close()
                raise
            finally:self.last_used=time.monotonic()
