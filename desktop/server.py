"""Loopback-only, token-authenticated API; file serving uses registered IDs only."""
import hmac
import io
import json
import mimetypes
import secrets
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, unquote

from .application import Application, ROOT


def create_server(application=None, port=0):
    app = application or Application()
    token = secrets.token_urlsafe(32)
    thumbnails = OrderedDict()
    cache_lock = threading.Lock()
    dist = ROOT / 'frontend/dist'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Do not log local file paths or session tokens.

        def send_bytes(self, value, mime, status=200, cache='no-store'):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(value)))
            self.send_header('Cache-Control', cache)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(value)

        def json(self, value, status=200):
            self.send_bytes(json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8', status)

        def authorized(self, query):
            supplied = self.headers.get('X-Memivo-Token', '') or self.headers.get('X-SegmentFlow-Token', '') or query.get('token', [''])[0]
            return hmac.compare_digest(supplied, token)

        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path.startswith('/api/'):
                    if not self.authorized(query):
                        return self.json({'error':'会话验证失败，请重新启动应用。'}, 403)
                    if parsed.path == '/api/state':
                        return self.json(app.snapshot())
                    if parsed.path == '/api/image':
                        with app.lock:
                            path = app.files.get(query.get('id', [''])[0])
                        if path is None or not path.is_file():
                            return self.json({'error':'图片不可用'}, 404)
                        size = query.get('size', ['thumb'])[0]
                        from PIL import Image, ImageOps
                        if size == 'download':
                            return self.send_bytes(path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                        key = (str(path), path.stat().st_mtime_ns, path.stat().st_size, size)
                        with cache_lock:
                            content = thumbnails.get(key)
                        if content is None:
                            with Image.open(path) as image:
                                image = ImageOps.exif_transpose(image)
                                if size != 'full':
                                    image.thumbnail((440, 330) if size == 'thumb' else (2200, 2200))
                                buffer = io.BytesIO()
                                image.convert('RGB').save(buffer, format='JPEG', quality=85)
                                content = buffer.getvalue()
                            # Thumbnails only; don't retain dozens of full-size previews.
                            if size == 'thumb':
                                with cache_lock:
                                    thumbnails[key] = content
                                    while len(thumbnails) > 160:
                                        thumbnails.popitem(last=False)
                        return self.send_bytes(content, 'image/jpeg')
                    return self.json({'error':'未知接口'}, 404)
                path = (dist / unquote(parsed.path).lstrip('/')).resolve()
                if dist.resolve() not in path.parents and path != dist.resolve():
                    return self.json({'error':'路径不可用'}, 403)
                if parsed.path == '/' or not path.is_file():
                    path = dist / 'index.html'
                if not path.is_file():
                    return self.json({'error':'前端未构建，请运行一键启动脚本。'}, 503)
                return self.send_bytes(path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            except Exception as exc:
                self.json({'error':str(exc)}, 400)

        def do_POST(self):
            parsed = urlsplit(self.path)
            if not self.authorized(parse_qs(parsed.query)):
                return self.json({'error':'会话验证失败'}, 403)
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 <= length <= 1024*1024:
                    raise ValueError('请求过大。')
                data = json.loads(self.rfile.read(length) or b'{}')
                route = parsed.path.removeprefix('/api/')
                if route == 'pick':
                    if app.window is None:
                        raise ValueError('浏览器预览中请直接填写本地路径；桌面版可使用文件选择器。')
                    import webview
                    kind = data.get('kind', 'file')
                    if kind == 'folder':
                        result = app.window.create_file_dialog(webview.FileDialog.FOLDER)
                    else:
                        result = app.window.create_file_dialog(webview.FileDialog.OPEN,
                            allow_multiple=kind == 'references')
                    return self.json({'paths': list(result or [])})
                return self.json(app.action(route, data))
            except Exception as exc:
                return self.json({'error':str(exc)}, 400)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.app = app
    server.token = token
    server.url = f'http://127.0.0.1:{server.server_port}/#token={token}'
    return server
