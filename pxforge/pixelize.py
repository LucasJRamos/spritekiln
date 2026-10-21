"""Turn rendered buffers into clean pixel art (palette bands, selout, cleanup).

Materials come from the spec: each has a colour ramp (index 0 = outline/darkest) and flags
(emissive, line, outline, glow, band/bands).
"""
import numpy as np


def hx(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def band_of(M, v):
    """light value (0..1) -> ramp index for material M."""
    n = len(M['colors'])
    if M['emissive'] or n == 1:
        b = M['band'] if M['band'] is not None else n - 1
        return np.full(v.shape, b, int)
    lo, hi = M['bands'] if M['bands'] else (1, n - 1)
    levels = hi - lo + 1
    g = np.clip(v, 0, 1) ** M['gamma']
    return np.clip(lo + np.floor(g * levels * 0.999).astype(int), lo, hi)


N4 = ((0, 1), (0, -1), (1, 0), (-1, 0))


def shift(a, dy, dx, fill):
    out = np.full_like(a, fill)
    H, W = a.shape
    ys = slice(max(dy, 0), H + min(dy, 0)); yd = slice(max(-dy, 0), H + min(-dy, 0))
    xs = slice(max(dx, 0), W + min(dx, 0)); xd = slice(max(-dx, 0), W + min(-dx, 0))
    out[ys, xs] = a[yd, xd]
    return out


def compose(gid, val, depth, groups, materials, shadow=None):
    """-> RGBA uint8 image. shadow: (cx, cy, rx, ry, rgba) or None."""
    H, W = gid.shape
    names = list(materials)
    mid = {n: i for i, n in enumerate(names)}
    RAMPS = {mid[n]: [hx(c) for c in materials[n]['colors']] for n in names}
    EMISSIVE = {mid[n] for n in names if materials[n]['emissive']}
    NO_OUTLINE = {mid[n] for n in names if not materials[n]['outline']}
    mats = np.array([mid[g.mat] for g in groups] + [-1])
    line_ok = np.array([bool(g.line) for g in groups] + [False])
    mat = np.where(gid >= 0, mats[gid], -1)
    band = np.zeros((H, W), int)
    for n in names:
        sel = mat == mid[n]
        if sel.any():
            band[sel] = band_of(materials[n], val[sel])

    # --- 1. remove orphan band pixels (pillow noise) ---
    for _ in range(2):
        nb = np.stack([shift(band, dy, dx, -9) for dy, dx in N4])
        ng = np.stack([shift(gid, dy, dx, -9) for dy, dx in N4])
        same = ng == gid[None]
        for y, x in zip(*np.nonzero(gid >= 0)):
            if mat[y, x] in EMISSIVE:
                continue
            s = same[:, y, x]
            if s.sum() >= 3:
                vals = nb[s, y, x]
                if not (vals == band[y, x]).any():
                    u, c = np.unique(vals, return_counts=True)
                    band[y, x] = u[c.argmax()]

    # --- 2. internal contour lines where a nearer part overlaps a farther one ---
    line = np.zeros((H, W), bool)
    for dy, dx in N4 + ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        ng = shift(gid, dy, dx, -1)
        nd = shift(depth, dy, dx, np.inf)
        cand = (gid >= 0) & (ng >= 0) & (ng != gid) & (nd < depth - 0.06)
        cand &= line_ok[np.where(gid >= 0, gid, -1)] & line_ok[np.where(ng >= 0, ng, -1)]
        if abs(dy) + abs(dx) == 2:
            cand &= (nd < depth - 0.25)  # diagonals only for big depth jumps
        line |= cand
    # never line emissive pixels
    line &= ~np.isin(mat, list(EMISSIVE))

    # --- 3. build RGBA ---
    img = np.zeros((H, W, 4), np.uint8)
    for y, x in zip(*np.nonzero(gid >= 0)):
        m = mat[y, x]
        r = RAMPS[m]
        b = band[y, x]
        if line[y, x]:
            col = r[min(materials[names[m]]['line_band'], len(r) - 1)]
        else:
            col = r[b]
        img[y, x, :3] = col; img[y, x, 3] = 255

    # --- 4. outer outline (selout: tinted by neighbour material) ---
    solid = gid >= 0
    out = np.zeros((H, W), bool)
    owner = np.full((H, W), -1)
    for dy, dx in N4:
        ns = shift(solid, dy, dx, False)
        nm = shift(mat, dy, dx, -1)
        new = ns & ~solid
        sel = new & (owner < 0) & ~np.isin(nm, list(NO_OUTLINE))
        owner[sel] = nm[sel]
        out |= new & ~np.isin(nm, list(NO_OUTLINE))
    # pixel-perfect cleanup: drop redundant L-corner outline pixels
    for _ in range(1):
        o = out.copy()
        for y, x in zip(*np.nonzero(o)):
            up = y > 0 and o[y - 1, x]; dn = y < H - 1 and o[y + 1, x]
            lf = x > 0 and o[y, x - 1]; rt = x < W - 1 and o[y, x + 1]
            for (a, ay, ax), (b, by, bx) in (((up, -1, 0), (lf, 0, -1)), ((up, -1, 0), (rt, 0, 1)),
                                             ((dn, 1, 0), (lf, 0, -1)), ((dn, 1, 0), (rt, 0, 1))):
                if a and b:
                    # the diagonal between neighbours must be solid sprite (we're an outer corner of a stair)
                    yy, xx = y + ay + by, x + ax + bx
                    if 0 <= yy < H and 0 <= xx < W and solid[yy, xx]:
                        # only remove if removing keeps sprite 4-sealed: the pixel's other two sides empty
                        oy, ox = y - ay - by, x - ax - bx
                        if not (0 <= y - ay < H and solid[y - ay, x]) and not (0 <= x - bx < W and solid[y, x - bx]):
                            o[y, x] = False
                            break
        out = o
    for y, x in zip(*np.nonzero(out)):
        m = owner[y, x]
        if m < 0:
            continue
        img[y, x, :3] = RAMPS[m][0]; img[y, x, 3] = 255

    # --- 5. glow: emissive materials tint neighbouring pixels of other materials ---
    for n in names:
        gl = materials[n].get('glow')
        if not gl:
            continue
        src = mat == mid[n]
        if not src.any():
            continue
        col = np.array(hx(gl['color'] if isinstance(gl, dict) else gl), float)
        mix = gl.get('mix', 0.55) if isinstance(gl, dict) else 0.55
        rad = gl.get('radius', 1) if isinstance(gl, dict) else 1
        halo = src.copy()
        for _ in range(rad):
            h2 = halo.copy()
            for dy, dx in N4:
                h2 |= shift(halo, dy, dx, False)
            halo = h2
        halo &= (mat >= 0) & ~src & ~np.isin(mat, list(EMISSIVE)) & ~line
        img[halo, :3] = (np.array(img[halo, :3], float) * (1 - mix) + col * mix).astype(np.uint8)

    # --- 5b. drop isolated single opaque pixels ---
    a = img[..., 3] > 0
    pd = np.pad(a, 1)
    nn = pd[:-2, 1:-1].astype(int) + pd[2:, 1:-1] + pd[1:-1, :-2] + pd[1:-1, 2:]
    img[a & (nn == 0)] = 0

    # --- 6. ground shadow under everything ---
    if shadow is not None:
        cx, cy, rx, ry, SHADOW = shadow
        yy, xx = np.mgrid[0:H, 0:W]
        e = ((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2 <= 1
        e &= img[..., 3] == 0
        img[e] = SHADOW
    return img


def aux_maps(img, gid, nrm, groups, materials, cam):
    """Normal map (camera space, RGB) and emissive mask aligned with the sprite.
    Outline pixels inherit the normal of the nearest sprite pixel."""
    H, W = gid.shape
    n_cam = np.stack([nrm @ cam.R, nrm @ cam.U, -(nrm @ cam.D)], -1)
    has = gid >= 0
    filled = n_cam.copy()
    known = has.copy()
    for _ in range(2):
        for dy, dx in N4:
            sh = shift(known, dy, dx, False)
            sv = np.stack([shift(filled[..., i], dy, dx, 0.0) for i in range(3)], -1)
            take = ~known & sh
            filled[take] = sv[take]
            known |= take
    normal = np.zeros((H, W, 4), np.uint8)
    op = img[..., 3] == 255
    enc = np.clip((filled * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    flat = np.array([128, 128, 255], np.uint8)
    normal[..., :3] = np.where(known[..., None], enc, flat)
    normal[..., 3] = np.where(op, 255, 0)
    emis = np.zeros((H, W, 4), np.uint8)
    em_g = np.array([materials[g.mat]['emissive'] for g in groups] + [False])
    e = has & em_g[np.where(has, gid, -1)]
    emis[e] = img[e]
    return normal, emis
