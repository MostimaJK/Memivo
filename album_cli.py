"""CLI entry and target-machine recognition benchmark (no synthetic accuracy claims)."""
import argparse
import json
import statistics
import time
from pathlib import Path

from album.core import export_albums, save_json


def benchmark(args):
    import numpy as np
    import onnxruntime as ort
    from PIL import Image, ImageOps
    from album.core import fingerprint, unit

    if args.repeats < 1:
        raise ValueError('repeats 必须大于零。')
    if args.device == 'cuda' and hasattr(ort, 'preload_dlls'):
        ort.preload_dlls()
    provider = 'CUDAExecutionProvider' if args.device == 'cuda' else 'CPUExecutionProvider'
    if provider not in ort.get_available_providers():
        raise RuntimeError(f'{provider} 不可用。')
    started = time.perf_counter()
    session = ort.InferenceSession(args.model, providers=[provider])
    if provider not in session.get_providers():
        raise RuntimeError('执行后端初始化失败。')
    load_seconds = time.perf_counter() - started
    inp = session.get_inputs()[0]
    with Image.open(args.face) as image:
        # Benchmark requires an already aligned face; does not evaluate detection/accuracy.
        image = ImageOps.exif_transpose(image).convert('RGB').resize((112, 112))
        dtype = np.float16 if inp.type == 'tensor(float16)' else np.float32
        value = ((np.asarray(image).astype(dtype) / dtype(255)) - dtype(.5)) / dtype(.5)
        value = np.ascontiguousarray(value.transpose(2, 0, 1)[None])
    for _ in range(5):
        unit(session.run(None, {inp.name: value})[0])
    durations = []
    for _ in range(args.repeats):
        tick = time.perf_counter()
        session.run(None, {inp.name: value})
        durations.append((time.perf_counter() - tick) * 1000)
    result = dict(model_sha256=fingerprint(args.model), providers=session.get_providers(),
                  onnxruntime=ort.__version__, batch=1, precision=inp.type,
                  input_size=[112, 112], load_seconds=load_seconds,
                  repeats=args.repeats, median_ms=statistics.median(durations),
                  p95_ms=float(np.percentile(durations, 95)),
                  scope='recognition session.run only; excludes detection, preprocessing, disk I/O; no accuracy measurement')
    save_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('config', help='project.json')
    export = commands.add_parser('export')
    export.add_argument('report')
    export.add_argument('destination')
    bench = commands.add_parser('benchmark')
    bench.add_argument('--model', required=True)
    bench.add_argument('--face', required=True, help='已对齐的单人脸裁剪图')
    bench.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    bench.add_argument('--repeats', type=int, default=50)
    bench.add_argument('--output', default='benchmark.json')
    args = parser.parse_args()
    if args.command == 'benchmark':
        benchmark(args)
    elif args.command == 'run':
        from album.backend import FaceBackend
        from album.service import run_project
        config = json.loads(Path(args.config).read_text(encoding='utf-8'))
        backend = FaceBackend(config['detector'], config['recognition'], config.get('device', 'cpu'))
        report = run_project(config, backend, lambda i, n, name: print(f'{i}/{n}: {name}'))
        print(report['report_path'])
    else:
        report = json.loads(Path(args.report).read_text(encoding='utf-8'))
        print(f'导出 {export_albums(report, args.destination)} 个人物照片关联')


if __name__ == '__main__':
    main()
