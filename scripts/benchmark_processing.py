"""Compare CPU output work with a prior checkout; no real AI model or GPU benchmark.

Run from the repository root. Requires project Python dependencies and Git history.
The baseline module is read from the specified trusted local Git revision.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
import types

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image
from desktop.application import Application
from desktop.image_cache import ImageCache
from desktop.image_ops import segmentation_overlay


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref',default='6dbcc3093caafbbd85b4549c659fe362080b22fb')
    parser.add_argument('--runs',type=int,default=5)
    args=parser.parse_args()
    if args.runs<3:parser.error('Use at least 3 measured runs')
    source=subprocess.check_output(['git','show',args.baseline_ref+':desktop/application.py'],cwd=ROOT).decode('utf-8')
    baseline=types.ModuleType('desktop.benchmark_baseline')
    baseline.__package__='desktop';baseline.__file__=str(ROOT/'desktop/application.py')
    exec(compile(source,baseline.__file__,'exec'),baseline.__dict__)
    rng=np.random.default_rng(20261017)
    pixels=rng.integers(0,256,(1000,1600,3),dtype=np.uint8)
    mask=np.zeros((1000,1600),bool);mask[150:850,200:1400]=True
    class Backend:
        model_path=None
        def process_image(self,*args,**kwargs):return None,[mask]
    measurements={'baseline':[],'optimized':[]};hashes={}
    with tempfile.TemporaryDirectory(prefix='memivo-processing-') as folder:
        root=Path(folder);path=root/'photo.png';Image.fromarray(pixels).save(path)
        weights=root/'fixture.pt';weights.touch()
        apps={}
        try:
            for name,cls in [('baseline',baseline.Application),('optimized',Application)]:
                app=apps[name]=cls(root/name,sam_factory=Backend)
                app.scan(str(path));app.worker.join(10);app.config['sam']=str(weights)
            for iteration in range(args.runs+1):
                # Alternate order to reduce warm filesystem / thermal bias.
                for name in (['baseline','optimized'] if iteration%2==0 else ['optimized','baseline']):
                    app=apps[name];started=time.perf_counter()
                    app.segment_image(dict(id=app.photos[0]['id'],points=[[500,500]],labels=[1]))
                    app.worker.join(60)
                    if app.worker.is_alive() or app.task['state']!='completed':raise RuntimeError(app.task)
                    elapsed=(time.perf_counter()-started)*1000
                    if iteration:measurements[name].append(round(elapsed,2))
                    output=Path(app.segment['directory'])
                    hashes[name]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.png')}
            assert hashes['baseline']==hashes['optimized'],'Export bytes differ'
        finally:
            for app in apps.values():app.runtimes.close_detection();app.runtimes.gpu_memory.close()
        # Actual HTTP image serving uses this same cache and JPEG encode path.
        import io
        def encode():
            with Image.open(path) as image:
                buffer=io.BytesIO();image.convert('RGB').save(buffer,format='JPEG',quality=85)
                return buffer.getvalue()
        cache=ImageCache();cache.get('image',encode)
        preview={}
        for name,fn in [('uncached',encode),('cached',lambda:cache.get('image',encode))]:
            samples=[]
            for _ in range(args.runs):
                started=time.perf_counter();content=fn();samples.append((time.perf_counter()-started)*1000)
            preview[name]=dict(median_ms=round(statistics.median(samples),4),bytes=len(content))
    large=rng.integers(0,256,(4000,6000,3),dtype=np.uint8);selected=np.ones((4000,6000),bool)
    def old_overlay():
        output=large.copy();output[selected]=(output[selected]*.3+np.array([48,114,235])*.7).astype(np.uint8);return output
    memory={};digest=None
    for name,fn in [('baseline',old_overlay),('optimized',lambda:segmentation_overlay(large,selected))]:
        tracemalloc.start();started=time.perf_counter();output=fn()
        _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        memory[name]=dict(ms=round((time.perf_counter()-started)*1000,2),python_numpy_peak_mib=round(peak/1024**2,2))
        current=hashlib.sha256(output).hexdigest()
        if digest is not None:assert digest==current,'Overlay pixels differ'
        digest=current;del output
    result=dict(kind='CPU output and cache microbenchmarks; synthetic image and model double; not GPU inference',
        baseline_ref=args.baseline_ref,python=sys.version.split()[0],runs=args.runs,export_image=[1600,1000],
        single_mask_export=dict(samples_ms=measurements,median_ms={k:round(statistics.median(v),2) for k,v in measurements.items()},files=7,byte_identical=True),
        preview_encoding=preview,overlay_24mp=memory,overlay_pixel_identical=True)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
