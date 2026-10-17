import subprocess
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from desktop.gpu_memory import GpuMemoryMonitor,query_memory


class GpuMemoryTests(unittest.TestCase):
    def test_query_reports_whole_gpu_counters_without_importing_ai_engines(self):
        result=SimpleNamespace(returncode=0,stdout='"NVIDIA Example, GPU", 4096, 16384\n',stderr='')
        with patch('desktop.gpu_memory.shutil.which',return_value='nvidia-smi'),patch('desktop.gpu_memory.subprocess.run',return_value=result) as run:
            sample=query_memory()
        self.assertEqual(sample['name'],'NVIDIA Example, GPU')
        self.assertEqual(sample['percent'],25)
        self.assertEqual(sample['used_mb'],4096)
        self.assertEqual(sample['total_mb'],16384)
        self.assertIn('--id=0',run.call_args.args[0])
        self.assertLessEqual(run.call_args.kwargs['timeout'],2)

    def test_missing_gpu_and_invalid_samples_never_report_zero_usage(self):
        with patch('desktop.gpu_memory.shutil.which',return_value=None):self.assertEqual(query_memory(),{'state':'no_gpu'})
        with patch('desktop.gpu_memory.shutil.which',return_value='nvidia-smi'),patch('desktop.gpu_memory.subprocess.run',return_value=SimpleNamespace(returncode=9,stdout='No devices were found',stderr='')):
            self.assertEqual(query_memory(),{'state':'no_gpu'})
        for output in ['GPU, N/A, 16000','GPU, 1, 0','GPU, -1, 16000','GPU, 17000, 16000','GPU, nan, 16000','GPU, 4, inf','bad']:
            with self.subTest(output=output),patch('desktop.gpu_memory.shutil.which',return_value='nvidia-smi'),patch('desktop.gpu_memory.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=output,stderr='')):
                with self.assertRaises(ValueError):query_memory()

    def test_monitor_is_nonblocking_coalesces_requests_and_respects_interval(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();calls=[]
        def query():
            calls.append(1);entered.set();release.wait(2);done.set()
            return dict(state='ready',used_mb=1,total_mb=2,percent=50,sampled_at=time.time())
        monitor=GpuMemoryMonitor(query,interval=10)
        try:
            self.assertEqual(monitor.snapshot()['state'],'loading');self.assertFalse(calls)
            start=time.perf_counter();monitor.snapshot(refresh=True);self.assertLess(time.perf_counter()-start,.2)
            self.assertTrue(entered.wait(1))
            for _ in range(10):monitor.snapshot(refresh=True)
            self.assertEqual(len(calls),1)
            release.set();self.assertTrue(done.wait(1))
            # Wait for the result to be published, not for any external GPU process.
            deadline=time.monotonic()+1
            while monitor.snapshot()['state']=='loading' and time.monotonic()<deadline:time.sleep(.005)
            self.assertEqual(monitor.snapshot(refresh=True)['percent'],50)
            self.assertEqual(len(calls),1)
            monitor.close();monitor.next_sample=0;monitor.snapshot(refresh=True);self.assertEqual(len(calls),1)
        finally:release.set();monitor.close()

    def test_failure_timeout_recovery_and_stale_reading(self):
        monitor=GpuMemoryMonitor(query=lambda: (_ for _ in ()).throw(subprocess.TimeoutExpired('nvidia-smi',1.5)),interval=0)
        monitor._refresh();self.assertEqual(monitor.snapshot()['state'],'unavailable')
        self.assertNotIn('percent',monitor.snapshot())
        monitor.query=lambda:dict(state='ready',used_mb=1,total_mb=2,percent=50,sampled_at=time.time())
        monitor._refresh();self.assertEqual(monitor.snapshot()['percent'],50)
        monitor.sample['sampled_at']=time.time()-7
        self.assertEqual(monitor.snapshot()['state'],'unavailable')
        self.assertNotIn('percent',monitor.snapshot());monitor.close()


if __name__=='__main__':unittest.main()
