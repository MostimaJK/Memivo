from __future__ import annotations

import time
from pathlib import Path

from .core import FeatureCache, IMAGE_SUFFIXES, fingerprint, match_identity, save_json


def run_project(config, backend, progress=lambda done, total, message: None, cancelled=lambda: False):
    source = Path(config['source']).resolve()
    workspace = Path(config['workspace']).resolve()
    if not source.is_dir() and not (source.is_file() and source.suffix.lower() in IMAGE_SUFFIXES):
        raise ValueError('相册目录不存在。')
    if workspace == source or source in workspace.parents:
        raise ValueError('工作目录必须位于原始相册目录之外。')
    threshold, margin = float(config.get('threshold', .55)), float(config.get('margin', .08))
    if not 0 <= threshold <= 1 or not 0 <= margin <= 1:
        raise ValueError('匹配阈值和差距必须位于 0 到 1 之间。')
    if not config.get('references'):
        raise ValueError('请至少登记一位朋友的参考照。')
    paths = [source] if source.is_file() else sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    if not paths:
        raise ValueError('目录内没有支持的照片。')
    workspace.mkdir(parents=True, exist_ok=True)
    cache = FeatureCache(workspace / 'features.sqlite3')
    hits = 0

    def extract(path):
        nonlocal hits
        key = backend.cache_id + ':' + fingerprint(path)
        faces = cache.get(key)
        if faces is None:
            faces = backend.extract(str(path))
            cache.put(key, faces)
        else:
            hits += 1
        return faces

    started = time.perf_counter()
    report = {'schema': 1, 'source': str(source), 'workspace': str(workspace),
              'model_id': backend.model_id, 'providers': backend.providers,
              'threshold': threshold, 'margin': margin, 'photos': [], 'cancelled': False,
              'reference_errors': [], 'cache_hits': 0}
    try:
        gallery = {}
        for name, references in config['references'].items():
            gallery[name] = []
            for path in references:
                if cancelled():
                    report['cancelled'] = True
                    break
                progress(0, len(paths), f'登记参考照：{name}')
                try:
                    faces = extract(path)
                    if len(faces) != 1:
                        raise ValueError(f'参考照必须恰好包含一张可检测的人脸，检测到 {len(faces)} 张。')
                    gallery[name].append(faces[0]['embedding'])
                except Exception as exc:
                    report['reference_errors'].append(f'{name} / {path}: {exc}')
            if not gallery[name] and not report['cancelled']:
                raise ValueError(f'{name} 没有有效参考照。' + '\n'.join(report['reference_errors']))
        # Preserve human decisions only for unchanged photos and identical model space.
        previous = {}
        report_path = workspace / 'report.json'
        if report_path.exists():
            import json
            old = json.loads(report_path.read_text(encoding='utf-8'))
            if old.get('model_id') == backend.model_id:
                previous = {p['path']: p for p in old['photos']}
        for index, path in enumerate(paths):
            if cancelled():
                report['cancelled'] = True
                break
            photo = {'path': str(path), 'faces': [], 'error': None}
            try:
                photo['sha256'] = fingerprint(path)
                for face in extract(path):
                    result = {k: v for k, v in face.items() if k != 'embedding'}
                    result.update(match_identity(face['embedding'], gallery, threshold, margin))
                    old_photo = previous.get(str(path), {})
                    if old_photo.get('sha256') == photo['sha256']:
                        for old_face in old_photo.get('faces', []):
                            if old_face['bbox'] == result['bbox'] and old_face['status'] in {'confirmed', 'rejected'}:
                                result.update(identity=old_face['identity'], status=old_face['status'])
                    photo['faces'].append(result)
            except Exception as exc:
                photo['error'] = str(exc)
            report['photos'].append(photo)
            progress(index + 1, len(paths), path.name)
        report['elapsed_seconds'] = round(time.perf_counter() - started, 3)
        report['cache_hits'] = hits
        # Cancelled runs preserve an existing completed report and its human decisions.
        filename = 'report.partial.json' if report['cancelled'] else 'report.json'
        report['report_path'] = str(workspace / filename)
        save_json(report['report_path'], report)
        return report
    finally:
        cache.close()
