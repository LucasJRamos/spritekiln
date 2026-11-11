"""Checks on the built geometry that `validate` reports as warnings."""

import numpy as np

SAMPLES = 600  # points tried in a part's bounding sphere
ROUNDS = 4  # refinements around the points nearest to the rest of the model
GAP_PX = 1.5  # a part farther than this from every other part floats


def _others(groups, i, pts):
    """Distance from each point to the nearest solid part other than `i` (exact near the parts)."""
    d = np.full(len(pts), 1e3)
    for j, g in enumerate(groups):
        if j != i and not g.emissive:
            d = np.minimum(d, g(pts, exact_within=1e3))
    return d


def floating_parts(spec, groups):
    """[(part, gap in px)]: solid parts of the rest pose that touch no other part, with the gap to the nearest
    one. Emissive parts, smear arcs, parts with a `when` and parts marked `floating: true` are skipped; a model
    with a single part has nothing to float from. The search is seeded, so the answer never changes between runs."""
    scale = float(spec['camera']['scale'])
    solid = [i for i, g in enumerate(groups) if not g.emissive and ':' not in g.name]
    if len(solid) < 2:
        return []
    rng = np.random.default_rng(7)
    found = []
    for i in solid:
        g = groups[i]
        part = spec['parts'].get(g.name) or {}
        if part.get('floating') or 'when' in part:
            continue
        centre, radius = np.asarray(g.bc, float), float(g.br)
        best = None
        for _ in range(ROUNDS):
            v = rng.normal(size=(SAMPLES, 3))
            v *= (radius * rng.random((SAMPLES, 1)) ** (1 / 3)) / np.linalg.norm(v, axis=1, keepdims=True)
            pts = centre + v
            inside = g(pts, exact_within=1e3) <= 0
            if not inside.any():  # a part thinner than the sampling: its nearest points stand in for it
                inside = np.zeros(SAMPLES, bool)
                inside[np.argsort(g(pts, exact_within=1e3))[:20]] = True
            pts = pts[inside]
            d = _others(groups, i, pts)
            k = int(np.argmin(d))
            if best is None or d[k] < best:
                best = float(d[k])
            if best <= 0:
                break
            centre, radius = pts[k], max(radius * 0.4, 2 * scale)  # look closer around the nearest point
        if best is not None and best > GAP_PX * scale:
            found.append((g.name, best / scale))
    return found
