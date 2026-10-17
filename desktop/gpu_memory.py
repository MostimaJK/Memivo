"""Bounded NVIDIA memory sampling. UI requests never wait for nvidia-smi.

Reports whole GPU 0 frame-buffer usage, not Memivo process/tensor allocation.
Source: https://docs.nvidia.com/deploy/nvidia-smi/index.html
"""
import csv
import io
import math
import shutil
import subprocess
import threading
import time


def query_memory():
    from .runtimes import child_options
    command=shutil.which('nvidia-smi')
    if not command:return dict(state='no_gpu')
    result=subprocess.run([command,'--id=0','--query-gpu=name,memory.used,memory.total',
                           '--format=csv,noheader,nounits'],capture_output=True,text=True,
                          encoding='utf-8',errors='replace',timeout=1.5,**child_options())
    if result.returncode:
        message=(result.stderr or result.stdout).strip()[:300]
        if 'no devices were found' in message.lower() or 'no devices found' in message.lower():return dict(state='no_gpu')
        raise ValueError(message or 'NVIDIA memory query failed.')
    rows=list(csv.reader(io.StringIO(result.stdout)))
    if len(rows)!=1 or len(rows[0])!=3:raise ValueError('Unexpected NVIDIA memory response.')
    name,used,total=(value.strip() for value in rows[0])
    used,total=float(used),float(total)
    if not name or not all(math.isfinite(value) for value in (used,total)) or total<=0 or not 0<=used<=total:
        raise ValueError('NVIDIA memory counters are unavailable or invalid.')
    return dict(state='ready',index=0,name=name,used_mb=used,total_mb=total,percent=round(100*used/total,1),sampled_at=time.time())


class GpuMemoryMonitor:
    def __init__(self,query=None,interval=2):
        self.query=query or query_memory
        self.interval=interval
        self.lock=threading.Lock()
        self.sample=dict(state='loading')
        self.next_sample=0
        self.pending=False
        self.closed=False

    def snapshot(self,refresh=False):
        with self.lock:
            if refresh and not self.closed and not self.pending and time.monotonic()>=self.next_sample:
                self.pending=True
                self.next_sample=time.monotonic()+self.interval
                threading.Thread(target=self._refresh,name='memivo-gpu-memory',daemon=True).start()
            sample=dict(self.sample)
        # Never present an old successful reading as a live measurement.
        if sample.get('state')=='ready' and time.time()-sample['sampled_at']>6:
            return dict(state='unavailable',error='NVIDIA memory sample is stale.')
        return sample

    def _refresh(self):
        try:sample=self.query()
        except Exception as exc:sample=dict(state='unavailable',error=str(exc)[:300])
        with self.lock:
            if not self.closed:self.sample=sample
            self.pending=False

    def close(self):
        with self.lock:self.closed=True
