"""Byte-bounded encoded-image LRU with per-key request coalescing."""
from collections import OrderedDict
import threading


class ImageCache:
    def __init__(self, max_bytes=48 * 1024 * 1024, max_entries=160):
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.bytes = 0
        self.items = OrderedDict()
        self.pending = {}
        self.lock = threading.Lock()

    def get(self, key, encode):
        while True:
            with self.lock:
                if key in self.items:
                    self.items.move_to_end(key)
                    return self.items[key]
                event = self.pending.get(key)
                if event is None:
                    event = self.pending[key] = threading.Event()
                    break
            event.wait()
        try:
            content = encode()
            with self.lock:
                if len(content) <= self.max_bytes and self.max_entries > 0:
                    self.items[key] = content
                    self.bytes += len(content)
                    while self.bytes > self.max_bytes or len(self.items) > self.max_entries:
                        _, previous = self.items.popitem(last=False)
                        self.bytes -= len(previous)
            return content
        finally:
            with self.lock:
                self.pending.pop(key).set()
