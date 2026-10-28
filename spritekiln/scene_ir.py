"""One frame's SDF scene as flat arrays: what the compiled backend (fast.py) reads.

`rig.build` makes numpy closures (sdf.py), the reference renderer. Each closure carries `ir = (code, params)`;
`compile_scene` lays them out here: primitive codes, the offset of each primitive's parameters in one float
array, and per group its primitive and cut ranges, blends, bounding sphere and flags. Adding a primitive means
a closure in sdf.py, its code and parameters, and its formula in fast.py, checked against each other by
tests/test_fast.py.
"""

from typing import NamedTuple

import numpy as np


class SceneIR(NamedTuple):
    codes: np.ndarray  # int64 [P]: sdf.SPHERE, sdf.BOX...
    offs: np.ndarray  # int64 [P]: where each primitive's parameters start in `data`
    data: np.ndarray  # float64: every primitive's parameters, one after the other
    gp: np.ndarray  # int64 [G, 2]: the group's primitives, codes[gp[g, 0]:gp[g, 1]]
    gc: np.ndarray  # int64 [G, 2]: its cuts
    gblend: np.ndarray  # float64 [G, 8]: union mode, k, n; cut mode, k, n, groove depth and width
    gb: np.ndarray  # float64 [G, 4]: bounding sphere (local centre, radius)
    flags: np.ndarray  # int64 [G, 2]: emissive, two-sided
    glip: np.ndarray  # float64 [G]: distance multiplier, 1 / Lipschitz bound (bent or twisted shapes < 1)
    C: np.ndarray  # float64 [G, 3]: bounding sphere centres in world space (for culling)
    W: np.ndarray  # float64 [4, 3]: world -> local rotation rows, then the offset


def _prim(p, codes, offs, data):
    if not hasattr(p, 'ir'):
        raise TypeError(f'{p!r}: a primitive without `ir` cannot be compiled')
    code, params = p.ir
    codes.append(code)
    offs.append(len(data))
    data.extend(params)


def compile_scene(scene):
    """SceneIR of a render.Scene."""
    codes, offs, data = [], [], []
    gp, gc, gblend, gb, flags, glip = [], [], [], [], [], []
    for g in scene.groups:
        start = len(codes)
        for p in g.prims:
            _prim(p, codes, offs, data)
        gp.append((start, len(codes)))
        start = len(codes)
        for p in g.cut:
            _prim(p, codes, offs, data)
        gc.append((start, len(codes)))
        gblend.append((g.mode, g.k, g.n, g.cut_mode, g.ck, g.cut_n, *g.groove))
        gb.append((*g.bc, g.br))
        flags.append((int(g.emissive), int(g.two_sided)))
        glip.append(1.0 / g.lipschitz)
    G = len(scene.groups)
    C = np.array([scene.Rlw @ g.bc + scene.off for g in scene.groups], float).reshape(G, 3)
    return SceneIR(
        np.asarray(codes, np.int64),
        np.asarray(offs, np.int64),
        np.asarray(data or [0.0], np.float64),
        np.asarray(gp, np.int64).reshape(G, 2),
        np.asarray(gc, np.int64).reshape(G, 2),
        np.asarray(gblend, np.float64).reshape(G, 8),
        np.asarray(gb, np.float64).reshape(G, 4),
        np.asarray(flags, np.int64).reshape(G, 2),
        np.asarray(glip, np.float64),
        C,
        np.vstack([scene.Rwl, scene.off]).astype(np.float64),
    )
