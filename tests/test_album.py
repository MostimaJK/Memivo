import tempfile
import unittest
from pathlib import Path

from album.core import export_albums, match_identity, save_json
from album.service import run_project


class FakeBackend:
    model_id = 'test-model'
    cache_id = 'test-model:detector:v1'
    providers = ['test-only']

    def __init__(self):
        self.calls = 0

    def extract(self, path):
        self.calls += 1
        return [{'bbox': [0, 0, 10, 10], 'det_score': .99, 'embedding': [1, 0]}]


class AlbumTests(unittest.TestCase):
    def test_unknown_and_conflicting_candidates(self):
        self.assertEqual(match_identity([1, 0], {})['status'], 'unknown')
        result = match_identity([1, 0], {'A': [[1, 0]], 'B': [[.99, .01]]})
        self.assertEqual(result['status'], 'review')
        self.assertIsNone(result['identity'])
        self.assertEqual(match_identity([0, 1], {'A': [[1, 0]]})['status'], 'review')

    def test_multiple_references_and_invalid_features(self):
        self.assertEqual(match_identity([0, 1], {'A': [[1, 0], [0, 1]]})['identity'], 'A')
        with self.assertRaises(ValueError):
            match_identity([0, 0], {'A': [[1, 0]]})

    def test_cache_space_isolation_and_preserve_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'photos'
            source.mkdir()
            photo = source / '合照.jpg'
            photo.write_bytes(b'test-photo')
            ref = root / 'reference.jpg'
            ref.write_bytes(b'test-reference')
            config = dict(source=str(source), workspace=str(root / 'work'), references={'A': [str(ref)]})
            backend = FakeBackend()
            first = run_project(config, backend)
            self.assertEqual(backend.calls, 2)
            first['photos'][0]['faces'][0].update(status='rejected', identity=None)
            save_json(first['report_path'], first)
            second = run_project(config, backend)
            self.assertEqual(backend.calls, 2)
            self.assertEqual(second['photos'][0]['faces'][0]['status'], 'rejected')
            backend.cache_id = 'other-model:detector:v1'
            backend.model_id = 'other-model'
            third = run_project(config, backend)
            self.assertEqual(backend.calls, 4)
            self.assertEqual(third['photos'][0]['faces'][0]['status'], 'matched')

    def test_group_photo_export_dedup_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'photos'
            source.mkdir()
            photo = source / '合照.jpg'
            photo.write_bytes(b'original')
            report = dict(source=str(source), photos=[dict(path=str(photo), faces=[
                dict(identity='../A', status='confirmed'), dict(identity='../A', status='matched'),
                dict(identity='B', status='matched'), dict(identity='C', status='review')])])
            out = root / 'export'
            self.assertEqual(export_albums(report, out), 2)
            self.assertEqual(len(list(out.glob('*/*.jpg'))), 2)
            self.assertEqual(export_albums(report, out), 2)
            with self.assertRaises(ValueError):
                export_albums(report, source / 'nested')
            next(out.glob('*/*.jpg')).write_bytes(b'modified')
            with self.assertRaises(FileExistsError):
                export_albums(report, out)

    def test_cancel_keeps_completed_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'photos'
            source.mkdir()
            (source / 'photo.jpg').write_bytes(b'photo')
            ref = root / 'ref.jpg'
            ref.write_bytes(b'ref')
            config = dict(source=str(source), workspace=str(root / 'work'), references={'A': [str(ref)]})
            first = run_project(config, FakeBackend())
            before = Path(first['report_path']).read_bytes()
            result = run_project(config, FakeBackend(), cancelled=lambda: True)
            self.assertTrue(result['cancelled'])
            self.assertEqual(Path(first['report_path']).read_bytes(), before)

    def test_invalid_reference_cannot_silently_drop_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'photos').mkdir()
            (root / 'photos' / 'photo.jpg').write_bytes(b'photo')
            config = dict(source=str(root / 'photos'), workspace=str(root / 'work'), references={'A': [str(root / 'missing.jpg')]})
            with self.assertRaisesRegex(ValueError, '没有有效参考照'):
                run_project(config, FakeBackend())


if __name__ == '__main__':
    unittest.main()
