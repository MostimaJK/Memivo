"""Model-independent matching, persistent feature cache and safe photo export."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
from pathlib import Path

import numpy as np

IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}


def fingerprint(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def unit(vector):
    value = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(value)
    if not np.isfinite(value).all() or norm < 1e-10:
        raise ValueError('模型输出了无效或零特征。')
    return value / norm


def match_identity(embedding, gallery, threshold=0.55, margin=0.08):
    """Max reference similarity per identity; scores are not probabilities."""
    if not 0 <= threshold <= 1 or not 0 <= margin <= 1:
        raise ValueError('匹配阈值和候选差距必须在 0 到 1 之间。')
    query = unit(embedding)
    ranking = []
    for name, samples in gallery.items():
        if samples:
            score = max(float(query @ unit(sample)) for sample in samples)
            ranking.append({'name': name, 'score': min(1., max(-1., score))})
    ranking.sort(key=lambda item: (-item['score'], item['name']))
    if not ranking:
        return {'identity': None, 'status': 'unknown', 'candidates': []}
    top = ranking[0]
    gap = top['score'] - ranking[1]['score'] if len(ranking) > 1 else None
    accepted = top['score'] >= threshold and (gap is None or gap >= margin)
    return {'identity': top['name'] if accepted else None,
            'status': 'matched' if accepted else 'review',
            'gap': gap, 'candidates': ranking[:3]}


class FeatureCache:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS features '
                        '(key TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def get(self, key):
        row = self.db.execute('SELECT payload FROM features WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key, faces):
        self.db.execute('INSERT OR REPLACE INTO features VALUES (?,?)',
                        (key, json.dumps(faces)))
        self.db.commit()

    def close(self):
        self.db.close()


def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def export_albums(report, destination, progress=lambda done, total, message: None, cancelled=lambda: False):
    """Copy original photos; multi-person photos belong to multiple albums."""
    root = Path(destination).resolve()
    source_root = Path(report['source']).resolve()
    if root == source_root or source_root in root.parents:
        raise ValueError('导出目录必须位于原始相册目录之外，以免再次导入导出副本。')
    plan = []
    for photo in report['photos']:
        if cancelled():
            break
        source = Path(photo['path'])
        identities = {f['identity'] for f in photo['faces']
                      if f.get('identity') and f['status'] in {'matched', 'confirmed'}}
        for identity in sorted(identities):
            # Prefix prevents reserved device names; hash separates sanitized names.
            clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', identity).strip(' .')[:60] or 'person'
            folder = 'person_' + clean + '_' + hashlib.sha256(identity.encode()).hexdigest()[:8]
            key = fingerprint(source)
            if photo.get('sha256') and key != photo['sha256']:
                raise ValueError(f'原图在识别后发生变化，请重新整理：{source}')
            target = root / folder / (key[:16] + '_' + source.name)
            if target.exists() and fingerprint(target) != key:
                raise FileExistsError(f'导出文件已存在且内容不同：{target}')
            plan.append((source, target, identity))
    manifest = []
    for index, (source, target, identity) in enumerate(plan):
        if cancelled():
            break
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
        manifest.append({'identity': identity, 'source': str(source), 'export': str(target)})
        progress(index + 1, len(plan), source.name)
    save_json(root / ('manifest.partial.json' if cancelled() else 'manifest.json'), manifest)
    return len(manifest)
