"""Regression checks for unchanged pixels, bounded caches and optional telemetry."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import os
import urllib.request
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from desktop.application import Application
from desktop.image_cache import ImageCache
from desktop.image_ops import segmentation_overlay
from desktop.execution import torch_memory_snapshot


class PerformanceTests(unittest.TestCase):
    def test_overlay_is_pixel_identical_for_all_channel_values_and_partial_blocks(self):
        values=np.arange(256,dtype=np.uint8)
        image=np.stack(list(np.meshgrid(values,values,indexing='ij'))+[np.broadcast_to(values,(256,256))],axis=-1)
        for mask in [np.ones((256,256),bool),np.indices((256,256)).sum(axis=0)%3==0,np.zeros((256,256),bool)]:
            expected=image.copy()
            expected[mask]=(expected[mask]*.3+np.array([48,114,235])*.7).astype(np.uint8)
            for rows in (1,31,128,300):
                np.testing.assert_array_equal(segmentation_overlay(image,mask,rows),expected)

    def test_cache_byte_budget_lru_and_oversized_bypass(self):
        cache=ImageCache(max_bytes=6,max_entries=3)
        self.assertEqual(cache.get('a',lambda:b'aaa'),b'aaa')
        cache.get('b',lambda:b'bb')
        cache.get('a',lambda:self.fail('cache miss'))
        cache.get('c',lambda:b'cc')
        self.assertEqual(list(cache.items),['a','c'])
        self.assertEqual(cache.bytes,5)
        cache.get('large',lambda:b'0123456789')
        self.assertEqual(cache.bytes,5)
        self.assertNotIn('large',cache.items)
        empty=ImageCache(max_entries=0)
        empty.get('x',lambda:b'x')
        self.assertFalse(empty.items)

    def test_concurrent_cache_requests_encode_once_and_failure_does_not_deadlock(self):
        cache=ImageCache();started=threading.Event();release=threading.Event();calls=[]
        def encode():
            calls.append(1);started.set()
            if not release.wait(3):raise TimeoutError()
            return b'encoded'
        with ThreadPoolExecutor(max_workers=6) as pool:
            jobs=[pool.submit(cache.get,'same',encode) for _ in range(6)]
            self.assertTrue(started.wait(2));release.set()
            self.assertEqual([job.result(3) for job in jobs],[b'encoded']*6)
        self.assertEqual(len(calls),1)
        with self.assertRaises(ValueError):cache.get('broken',lambda:(_ for _ in ()).throw(ValueError()))
        self.assertEqual(cache.get('broken',lambda:b'retry'),b'retry')
        self.assertFalse(cache.pending)

    def test_sam_result_reuses_decode_and_skips_same_size_resize(self):
        cv=SimpleNamespace(COLOR_BGR2RGB=1,INTER_NEAREST=0,
            imread=lambda _:self.fail('duplicate image decode'),
            cvtColor=lambda image,_:image[...,::-1].copy(),
            resize=lambda *a,**k:self.fail('redundant resize'))
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('sam_output_under_test',root/'sam_backend.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules',{'cv2':cv,'ultralytics':SimpleNamespace(SAM=object),
                'ultralytics.models.sam':SimpleNamespace(SAM3SemanticPredictor=object)}):
            spec.loader.exec_module(module)
        backend=module.SAM3Backend()
        bgr=np.arange(18,dtype=np.uint8).reshape(2,3,3)
        mask=np.array([[[0.,1.,0.],[1.,1.,0.]]],dtype=np.float32)
        tensor=SimpleNamespace(cpu=lambda:SimpleNamespace(numpy=lambda:mask))
        result=SimpleNamespace(orig_img=bgr,orig_shape=(2,3),masks=SimpleNamespace(data=tensor))
        rgb,masks=backend._output(result,'unused',True,time.perf_counter())
        np.testing.assert_array_equal(rgb,bgr[...,::-1])
        np.testing.assert_array_equal(masks[0],mask[0].astype(np.uint8))
        result.orig_img=None
        rgb,masks=backend._output(result,'unused',False,time.perf_counter())
        self.assertIsNone(rgb)
        self.assertEqual(masks[0].dtype,np.uint8)

    def test_segmentation_keeps_every_export_and_exact_pixels(self):
        rng=np.random.default_rng(93)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'photo.png'
            pixels=rng.integers(0,256,(61,83,3),dtype=np.uint8);Image.fromarray(pixels).save(path)
            weights=root/'model.pt';weights.touch()
            for count in (1,3):
                masks=[]
                for i in range(count):
                    mask=np.zeros((61,83),bool);mask[2+i:30+i,5+i:50+i]=True;masks.append(mask)
                class Backend:
                    model_path=None
                    def process_image(self,*args,**kwargs):return None,masks
                app=Application(root/f'work-{count}',sam_factory=Backend)
                try:
                    app.scan(str(path));app.worker.join(5)
                    app.config['sam']=str(weights)
                    app.segment_image(dict(id=app.photos[0]['id'],points=[[10,10]],labels=[1]))
                    app.worker.join(5)
                    self.assertFalse(app.worker.is_alive());self.assertEqual(app.task['state'],'completed',app.task)
                    output=Path(app.segment['directory'])
                    self.assertEqual(len(list(output.glob('*.png'))),4+3*count)
                    combined=np.logical_or.reduce(masks)
                    def expected_rgba(mask):
                        rgba=Image.fromarray(np.dstack((pixels,mask.astype(np.uint8)*255)))
                        return rgba,rgba.getbbox()
                    for index,mask in enumerate(masks):
                        rgba,bounds=expected_rgba(mask)
                        for suffix,expected in [('.png',rgba),('-mask.png',Image.fromarray(mask.astype(np.uint8)*255)),('-crop.png',rgba.crop(bounds))]:
                            with Image.open(output/f'instance-{index+1}{suffix}') as actual:np.testing.assert_array_equal(np.asarray(actual),np.asarray(expected))
                        self.assertEqual(app.segment['instances'][index]['bbox'],list(bounds))
                    rgba,bounds=expected_rgba(combined)
                    for name,expected in [('mask.png',Image.fromarray(combined.astype(np.uint8)*255)),('cutout.png',rgba),('crop.png',rgba.crop(bounds))]:
                        with Image.open(output/name) as actual:np.testing.assert_array_equal(np.asarray(actual),np.asarray(expected))
                    expected=pixels.copy();expected[combined]=(expected[combined]*.3+np.array([48,114,235])*.7).astype(np.uint8)
                    with Image.open(output/'overlay.png') as actual:np.testing.assert_array_equal(np.asarray(actual),expected)
                    if count==1:
                        self.assertEqual((output/'cutout.png').read_bytes(),(output/'instance-1.png').read_bytes())
                        (output/'instance-1.png').write_bytes(b'independently editable')
                        with Image.open(output/'cutout.png') as original:self.assertEqual(original.size,(83,61))
                finally:
                    app.runtimes.close_detection();app.runtimes.gpu_memory.close()

    def test_memory_stats_do_not_import_torch_or_initialize_cpu_cuda(self):
        with patch.dict('sys.modules',{'torch':None}):self.assertEqual(torch_memory_snapshot('cuda:0'),{})
        cuda=SimpleNamespace(memory_allocated=lambda d:2*1024**2,memory_reserved=lambda d:4*1024**2,
            max_memory_allocated=lambda d:3*1024**2,max_memory_reserved=lambda d:5*1024**2)
        with patch.dict('sys.modules',{'torch':SimpleNamespace(cuda=cuda)}):
            self.assertEqual(torch_memory_snapshot('cpu'),{})
            self.assertEqual(torch_memory_snapshot('cuda:0'),dict(allocated_mb=2.,reserved_mb=4.,worker_peak_allocated_mb=3.,worker_peak_reserved_mb=5.))

    def test_http_preview_cache_invalidation_exif_and_raw_download(self):
        from desktop.server import create_server
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'oriented.jpg'
            exif=Image.Exif();exif[274]=6
            Image.new('RGB',(24,16),'red').save(path,exif=exif)
            app=Application(root/'state');image_id=app.register(path)
            server=create_server(application=app,port=0)
            worker=threading.Thread(target=server.serve_forever);worker.start()
            def get(size):
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/image?id={image_id}&size={size}&token={server.url.split("#token=")[1]}') as response:return response.read()
            try:
                real_open=Image.open
                with patch('PIL.Image.open',wraps=real_open) as opened:
                    first=get('full');second=get('full')
                    self.assertEqual(first,second);self.assertEqual(opened.call_count,1)
                    get('preview');get('preview');self.assertEqual(opened.call_count,2)
                with Image.open(io.BytesIO(first)) as image:self.assertEqual(image.size,(16,24))
                before=path.stat();Image.new('RGB',(24,16),'blue').save(path,exif=exif)
                os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns+10000000))
                self.assertNotEqual(first,get('full'))
                self.assertEqual(get('download'),path.read_bytes())
            finally:
                server.shutdown();server.server_close();worker.join(3)
                app.runtimes.close_detection();app.runtimes.gpu_memory.close()

    def test_segmentation_worker_skips_rgb_return_and_preserves_archive_masks(self):
        from scripts.detection_worker import VisionSession
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);weights=root/'model.pt';weights.touch()
            mask=np.array([[False,True],[True,False]])
            calls=[]
            class Backend:
                execution=dict(actual='cpu',evidence='tensor_device')
                def process_image(self,*args,**kwargs):
                    calls.append(kwargs);return None,[mask]
            with patch.dict('sys.modules',{'sam_backend':SimpleNamespace(SAM3Backend=Backend)}):
                session=VisionSession()
                data=dict(model=str(weights),device='cpu',path='unused',points=[[1,1]],labels=[1],boxes=[],conf=.3,iou=.7,mask_file=str(root/'masks.npz'))
                output=session.run('segment',data)
                self.assertFalse(calls[0]['return_image'])
                with np.load(output['masks']) as archive:np.testing.assert_array_equal(archive['mask_0'],mask)
                self.assertIn('mask_archive_ms',output['performance'])
                self.assertFalse(output['performance']['model_reused'])
                self.assertTrue(session.run('segment',data)['performance']['model_reused'])
