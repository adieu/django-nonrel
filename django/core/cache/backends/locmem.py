"Thread-safe in-memory cache backend."

import time
try:
    import cPickle as pickle
except ImportError:
    import pickle

from django.core.cache.backends.base import BaseCache
from django.utils.synch import RWLock

class CacheClass(BaseCache):
    def __init__(self, _, params):
        BaseCache.__init__(self, params)
        self._cache = {}
        self._expire_info = {}

        max_entries = params.get('max_entries', 300)
        try:
            self._max_entries = int(max_entries)
        except (ValueError, TypeError):
            self._max_entries = 300

        cull_frequency = params.get('cull_frequency', 3)
        try:
            self._cull_frequency = int(cull_frequency)
        except (ValueError, TypeError):
            self._cull_frequency = 3

        self._lock = RWLock()

    def _add(self, key, value, timeout=None):
        if len(self._cache) >= self._max_entries:
            self._cull()
        if timeout is None:
            timeout = self.default_timeout
        if key not in self._cache.keys():
            self._cache[key] = value
            self._expire_info[key] = time.time() + timeout

    def add(self, key, value, timeout=None):
        self._lock.writer_enters()
        # Python 2.3 and 2.4 don't allow combined try-except-finally blocks.
        try:
            try:
                self._add(key, pickle.dumps(value), timeout)
            except pickle.PickleError:
                pass
        finally:
            self._lock.writer_leaves()

    def get(self, key, default=None):
        should_delete = False
        self._lock.reader_enters()
        try:
            now = time.time()
            exp = self._expire_info.get(key)
            if exp is None:
                return default
            elif exp < now:
                should_delete = True
            else:
                try:
                    return pickle.loads(self._cache[key])
                except pickle.PickleError:
                    return default
        finally:
            self._lock.reader_leaves()
        if should_delete:
            self._lock.writer_enters()
            try:
                del self._cache[key]
                del self._expire_info[key]
                return default
            finally:
                self._lock.writer_leaves()

    def _set(self, key, value, timeout=None):
        if len(self._cache) >= self._max_entries:
            self._cull()
        if timeout is None:
            timeout = self.default_timeout
        self._cache[key] = value
        self._expire_info[key] = time.time() + timeout

    def set(self, key, value, timeout=None):
        self._lock.writer_enters()
        # Python 2.3 and 2.4 don't allow combined try-except-finally blocks.
        try:
            try:
                self._set(key, pickle.dumps(value), timeout)
            except pickle.PickleError:
                pass
        finally:
            self._lock.writer_leaves()

    def has_key(self, key):
        return key in self._cache

    def _cull(self):
        if self._cull_frequency == 0:
            self._cache.clear()
            self._expire_info.clear()
        else:
            doomed = [k for (i, k) in enumerate(self._cache) if i % self._cull_frequency == 0]
            for k in doomed:
                self.delete(k)

    def _delete(self, key):
        try:
            del self._cache[key]
        except KeyError:
            pass
        try:
            del self._expire_info[key]
        except KeyError:
            pass

    def delete(self, key):
        self._lock.writer_enters()
        try:
            self._delete(key)
        finally:
            self._lock.writer_leaves()
