"""Which renderer traces the rays: `numpy` (the reference, always installed) or `numba` (the `spritekiln[fast]`
extra, about 6x faster per frame). `auto`, the default, takes numba when it imports.

The choice comes from `--backend` or SPRITEKILN_BACKEND, so worker processes inherit it. It is part of the
render cache key: the two agree on every part and on all but a handful of pixels per frame, and a cache never
mixes them.
"""

import os

from .errors import SpriteKilnError

ENV = 'SPRITEKILN_BACKEND'
CHOICES = ('auto', 'numpy', 'numba')
INSTALL = 'pip install "spritekiln[fast]"  (or: pipx install --force "spritekiln[fast]"; not for macOS Intel)'

_FAST = {}  # 'module' or 'error', imported once per process


def _fast():
    if not _FAST:
        try:
            from . import fast

            _FAST['module'] = fast
        except ImportError as e:  # numba missing, or no wheel for this platform or Python
            _FAST['error'] = str(e)
    return _FAST.get('module')


def requested():
    value = os.environ.get(ENV, 'auto').strip().lower() or 'auto'
    if value not in CHOICES:
        raise SpriteKilnError(f'{ENV}={value!r}: use {", ".join(CHOICES)}')
    return value


def name():
    """The backend in use: 'numba' or 'numpy'."""
    want = requested()
    if want == 'numpy':
        return 'numpy'
    if _fast() is not None:
        return 'numba'
    if want == 'numba':
        raise SpriteKilnError(f'the numba backend is not installed ({_FAST["error"]}): {INSTALL}')
    return 'numpy'


def use(choice):
    """Select a backend for this process and the workers it starts (None keeps the current choice)."""
    if choice:
        if choice not in CHOICES:
            raise SpriteKilnError(f'--backend {choice!r}: use {", ".join(CHOICES)}')
        os.environ[ENV] = choice
        name()  # an unavailable explicit choice fails now, not in a worker


def note():
    """One line on the backend, for logs: what runs and, the first time, that numba compiles."""
    if name() == 'numba':
        fast = _fast()
        first = '' if fast.compiled_before() else '; compiling it on this first run takes about 10 s'
        return f'renderer: numba{first}'
    hint = '' if requested() == 'numpy' else f' (about 6x faster with the fast extra: {INSTALL})'
    return f'renderer: numpy{hint}'


def render(scene, cam, light):
    """Supersampled buffers of a frame with the backend in use (render.render's contract)."""
    if name() == 'numba':
        return _fast().render(scene, cam, light)
    from .render import render as reference

    return reference(scene, cam, light)
