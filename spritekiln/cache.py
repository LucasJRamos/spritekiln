"""On-disk render cache: one compressed `.npz` per (model, pose, direction).

The key hashes everything that changes the rendered buffers, including the source of the engine modules,
so an engine change never reuses stale buffers. Files are plain numpy archives read with
`allow_pickle=False`: opening a project with a planted cache cannot run code.
"""

import hashlib
import json
import os
import time
import zipfile

import numpy as np

DIRNAME = '.kilncache'
LEGACY_DIRNAME = '.pxcache'  # pickle cache of pxforge <= 0.1; never read, `cache clear --legacy` removes it
DEFAULT_MAX_MB = 1024  # per spec, enforced after each render (least recently used go first)
FORMAT = 4

_ENGINE_MODULES = ('expr.py', 'rig.py', 'sdf.py', 'render.py')


def _engine_hash():
    h = hashlib.sha1()
    here = os.path.dirname(os.path.abspath(__file__))
    for name in _ENGINE_MODULES:
        with open(os.path.join(here, name), 'rb') as fh:
            h.update(fh.read().replace(b'\r\n', b'\n'))
    return h.hexdigest()[:12]


ENGINE = _engine_hash()


def key(spec, env, yaw):
    """Hash of everything that changes geometry/lighting (not the palette, applied after the cache)."""
    payload = dict(
        bones=spec['bones'],
        ik=spec['ik'],
        parts=spec['parts'],
        camera=spec['camera'],
        light=spec['light'],
        size=spec['size'],
        mats={k: (v['emissive'], v['two_sided']) for k, v in spec['materials'].items()},
        env={k: np.asarray(v).round(6).tolist() for k, v in env.items()},
        yaw=yaw,
        engine=ENGINE,
        v=FORMAT,
    )
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:20]


def spec_dir(spec):
    return os.path.join(spec['_dir'], DIRNAME, spec['name'])


def entry(spec, env, yaw):
    return os.path.join(spec_dir(spec), key(spec, env, yaw) + '.npz')


def load(path):
    """Buffers (gid, val, depth, normal) or None when missing or unreadable."""
    try:
        with np.load(path, allow_pickle=False) as z:
            buf = (z['g'], z['v'], z['d'], z['n'])
    except (FileNotFoundError, OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None
    try:
        os.utime(path)  # mark as recently used for pruning
    except OSError:
        pass
    return buf


def save(path, buf):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f'{path}.{os.getpid()}.tmp'
    with open(tmp, 'wb') as fh:
        g, v, d, n = buf
        np.savez_compressed(fh, g=g, v=v, d=d, n=n)
    os.replace(tmp, path)  # a killed render never leaves a half-written entry


# ---------------------------------------------------------------- maintenance


def find_dirs(root, legacy=False):
    """Cache folders under `root` (a folder, or a spec file meaning its folder)."""
    if os.path.isfile(root):
        root = os.path.dirname(os.path.abspath(root))
    names = {DIRNAME} | ({LEGACY_DIRNAME} if legacy else set())
    found = []
    for d, subdirs, _ in os.walk(root):
        for s in list(subdirs):
            if s in names:
                found.append(os.path.join(d, s))
                subdirs.remove(s)
            elif s in ('.git', '.venv', 'venv', 'node_modules', '__pycache__'):
                subdirs.remove(s)
    return sorted(found)


def _files(folder):
    for d, _, files in os.walk(folder):
        for f in files:
            p = os.path.join(d, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            yield p, st.st_size, st.st_mtime


def size_mb(folder):
    return sum(s for _, s, _ in _files(folder)) / 2**20


def prune(folder, max_mb=None, older_than_days=None):
    """Delete least recently used entries until `folder` fits `max_mb`, and entries unused for
    `older_than_days`. Returns (files removed, MB freed)."""
    files = sorted(_files(folder), key=lambda f: f[2])  # oldest first
    total = sum(s for _, s, _ in files)
    cutoff = time.time() - older_than_days * 86400 if older_than_days is not None else None
    removed, freed = 0, 0
    for p, s, m in files:
        too_big = max_mb is not None and total - freed > max_mb * 2**20
        too_old = cutoff is not None and m < cutoff
        if not (too_big or too_old):
            continue
        try:
            os.remove(p)
        except OSError:
            continue
        removed += 1
        freed += s
    return removed, freed / 2**20
