"""Turn rendered buffers into clean pixel art (palette bands, selout, cleanup).

Materials come from the spec: each has a colour ramp (index 0 = outline/darkest) and flags
(emissive, line, outline, glow, band/bands).
"""

import numpy as np


def hx(s):
    """'#5d4f6c' or '#abc' -> (r, g, b)."""
    h = str(s).strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    if len(h) != 6 or any(c not in '0123456789abcdefABCDEF' for c in h):
        raise ValueError(f'{s!r} is not a colour (use "#rrggbb" or "#rgb")')
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def band_of(M, v, flat=False, dither=None):
    """light value (0..1) -> ramp index for material M. `flat`: one tone per material, `flat_band` (default the
    upper middle of its bands), for games that light sprites themselves through the normal map. `dither`: an
    offset per value, in tones (ordered dithering near the borders between tones)."""
    n = len(M['colors'])
    if M['emissive'] or n == 1:
        b = M['band'] if M['band'] is not None else n - 1
        return np.full(v.shape, b, int)
    lo, hi = M['bands'] if M['bands'] else (1, n - 1)
    if M.get('highlight') and hi >= n - 1 and hi - 1 > lo and not flat:
        hi -= 1  # the top tone is the highlight's, as a pixel artist keeps it
    if flat:
        b = M.get('flat_band')
        return np.full(v.shape, (lo + hi + 1) // 2 if b is None else b, int)
    if M.get('thresholds'):  # toon: the tone steps up at each threshold
        return np.clip(lo + np.searchsorted(np.asarray(M['thresholds'], float), np.clip(v, 0, 1), 'right'), lo, hi)
    levels = hi - lo + 1
    g = np.clip(v, 0, 1) ** M['gamma']
    return np.clip(lo + np.floor(g * levels * 0.999 + (0 if dither is None else dither)).astype(int), lo, hi)


N4 = ((0, 1), (0, -1), (1, 0), (-1, 0))
BAYER = {
    'bayer2': np.array([[0, 2], [3, 1]]),
    'bayer4': np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]),
}
DITHER = 0.5  # tones: values within a quarter of a tone of a border mix the two tones


def shift(a, dy, dx, fill):
    out = np.full_like(a, fill)
    H, W = a.shape
    ys = slice(max(dy, 0), H + min(dy, 0))
    yd = slice(max(-dy, 0), H + min(-dy, 0))
    xs = slice(max(dx, 0), W + min(dx, 0))
    xd = slice(max(-dx, 0), W + min(-dx, 0))
    out[ys, xs] = a[yd, xd]
    return out


def clusters(mask, score, min_px=1, max_px=None):
    """`mask` without its 4-connected clusters smaller than min_px, each larger one cut to its max_px pixels of
    highest `score`."""
    out = np.zeros_like(mask)
    seen = np.zeros_like(mask)
    H, W = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, comp = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            comp.append((y, x))
            for dy, dx in N4:
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    stack.append((yy, xx))
        if len(comp) < min_px:
            continue
        if max_px and len(comp) > max_px:
            comp = sorted(comp, key=lambda p: -score[p])[:max_px]
        for p in comp:
            out[p] = True
    return out


def folds(gid, depth, normal, band, cam, light_dir, crease_on, edge_on, crease_angle=50.0, min_run=2):
    """(crease, up) inside each part, from 4-neighbour pairs of the same part: `crease` marks the farther pixel of
    a concave fold sharper than `crease_angle` degrees and of a jump in depth (a part folding over itself), runs
    shorter than `min_run` px dropped; `up` marks the brighter pixel of a convex edge facing the light (one tone
    up). `crease_on` / `edge_on`: per group (plus a trailing False), which parts take them."""
    H, W = gid.shape
    idx = np.where(gid >= 0, gid, -1)
    crease = np.zeros((H, W), bool)
    up = np.zeros((H, W), bool)
    cosmax = np.cos(np.radians(crease_angle))
    for (dy, dx), d3 in (((0, 1), cam.R), ((1, 0), -cam.U)):  # right and down neighbours, as world directions
        gb = shift(gid, -dy, -dx, -1)
        same = (gid >= 0) & (gb == gid)
        nb = np.stack([shift(normal[..., i], -dy, -dx, 0.0) for i in range(3)], -1)
        db = shift(depth, -dy, -dx, np.inf)
        bent = same & ((normal * nb).sum(-1) < cosmax)
        convex = ((nb - normal) @ d3) > 0  # normals open apart along the step: a ridge
        b_far = db > depth
        # the part folds over itself: the depth jumps more than its slope explains (a pixel step s along d3 on a
        # surface of normal n changes depth by -s (n.d3) / (n.D)), between two surfaces facing the camera
        navg = normal + nb
        navg /= np.maximum(np.linalg.norm(navg, axis=-1, keepdims=True), 1e-9)
        nd = navg @ cam.D
        facing = (-(normal @ cam.D) > 0.3) & (-(nb @ cam.D) > 0.3)
        jump = np.zeros((H, W), bool)
        pair = same & facing
        slope = -cam.scale * (navg[pair] @ d3) / np.minimum(nd[pair], -1e-3)
        jump[pair] = np.abs(db[pair] - depth[pair] - slope) > 0.06
        fold = (bent & ~convex) | jump
        crease |= fold & ~b_far
        crease |= shift(fold & b_far, dy, dx, False)
        ridge = bent & convex & (((normal + nb) @ np.asarray(light_dir, float)) > 0)
        a_up = band >= shift(band, -dy, -dx, -1)
        up |= ridge & a_up
        up |= shift(ridge & ~a_up, dy, dx, False)
    crease &= crease_on[idx]
    up &= edge_on[idx] & ~crease
    if min_run > 1:
        crease = clusters(crease, np.zeros((H, W)), min_run)
    return crease, up


def compose(
    gid,
    val,
    depth,
    groups,
    materials,
    shadow=None,
    flat=False,
    ndh=None,
    normal=None,
    cam=None,
    light_dir=None,
    opts=None,
    paint=None,
    layers=None,
    anchor=None,
):
    """-> RGBA uint8 image. shadow: (cx, cy, rx, ry, rgba) or None; flat: see band_of; ndh: render.facing, for the
    materials' highlights; normal, cam, light_dir: for creases and edge highlights (folds); opts: the spec's
    `render:` settings (crease_angle, min_run); paint, layers: the paint layer of each pixel (render.GBuffer)
    and the frame's paint.Layer list: a painted pixel takes the layer's material; anchor: [groups, 2] whole
    pixels (x, y) where each part's dither pattern starts (materials with `dither`)."""
    H, W = gid.shape
    names = list(materials)
    mid = {n: i for i, n in enumerate(names)}
    RAMPS = {mid[n]: [hx(c) for c in materials[n]['colors']] for n in names}
    EMISSIVE = {mid[n] for n in names if materials[n]['emissive']}
    NO_OUTLINE = {mid[n] for n in names if not materials[n]['outline']}
    OUTLINE = {  # the outer outline's colour: the material's `line_color` (from the style), or its darkest tone
        mid[n]: hx(materials[n]['line_color']) if materials[n].get('line_color') else RAMPS[mid[n]][0] for n in names
    }
    mats = np.array([mid[g.mat] for g in groups] + [-1])
    line_ok = np.array([bool(g.line) for g in groups] + [False])
    mat = np.where(gid >= 0, mats[gid], -1)
    painted = None
    if paint is not None and layers:
        pm = np.array([mid[layer.material] for layer in layers] + [-1])
        painted = (gid >= 0) & (paint >= 0)
        mat = np.where(painted, pm[np.where(paint >= 0, paint, -1)], mat)
    band = np.zeros((H, W), int)
    for n in names:
        sel = mat == mid[n]
        if sel.any():
            band[sel] = band_of(materials[n], val[sel], flat)

    # --- 1. remove orphan band pixels (pillow noise) ---
    band0 = band.copy()
    for _ in range(2):
        nb = np.stack([shift(band, dy, dx, -9) for dy, dx in N4])
        ng = np.stack([shift(gid, dy, dx, -9) for dy, dx in N4])
        nm = np.stack([shift(mat, dy, dx, -9) for dy, dx in N4])
        same = (ng == gid[None]) & (nm == mat[None])  # same part and material (paint splits a part)
        for y, x in zip(*np.nonzero(gid >= 0)):
            if mat[y, x] in EMISSIVE:
                continue
            s = same[:, y, x]
            if s.sum() >= 3:
                vals = nb[s, y, x]
                if not (vals == band[y, x]).any():
                    u, c = np.unique(vals, return_counts=True)
                    band[y, x] = u[c.argmax()]

    # --- 1a. dither near the borders between tones, after the cleanup (which would take it for noise), in a
    # pattern anchored on each part so that it moves with the part instead of crawling under it; only inside a
    # region (thin details and edges stay solid) ---
    if anchor is not None and not flat and any(materials[n].get('dither') for n in names):
        yy, xx = np.mgrid[0:H, 0:W]
        ax = np.asarray(anchor, int).reshape(-1, 2)[np.where(gid >= 0, gid, 0)]
        inner = gid >= 0
        for dy, dx in N4:
            inner &= (shift(gid, dy, dx, -9) == gid) & (shift(mat, dy, dx, -9) == mat)
        for n in names:
            pattern = materials[n].get('dither')
            sel = (mat == mid[n]) & inner & (band == band0)
            if not pattern or not sel.any():
                continue
            B = BAYER[pattern]
            k = len(B)
            t = (B[(yy[sel] - ax[sel, 1]) % k, (xx[sel] - ax[sel, 0]) % k] + 0.5) / k**2
            band[sel] = band_of(materials[n], val[sel], flat, DITHER * (t - 0.5))

    # --- 1b. creases and edge highlights from the normals, inside one part ---
    crease = np.zeros((H, W), bool)
    crease_on = np.array([bool(materials[g.mat].get('crease')) for g in groups] + [False])
    edge_on = np.array([bool(materials[g.mat].get('edge_highlight')) for g in groups] + [False])
    if normal is not None and (crease_on.any() or edge_on.any()):
        o = opts or {}
        crease, up = folds(
            gid,
            depth,
            normal,
            band,
            cam,
            light_dir,
            crease_on,
            edge_on,
            o.get('crease_angle', 50.0),
            o.get('min_run', 2),
        )
        crease &= ~np.isin(mat, list(EMISSIVE))
        for n in names:
            M = materials[n]
            sel = up & (mat == mid[n])
            if sel.any():
                top = len(M['colors']) - 1 - (1 if M.get('highlight') else 0)  # the highlight keeps its tone
                band[sel] = np.minimum(band[sel] + 1, max(top, 0))

    # --- 1c. highlights: a small hard cluster where the surface faces between the light and the camera ---
    hl_colors = []
    if ndh is not None and not flat:
        for n in names:
            h = materials[n].get('highlight')
            if not h or materials[n]['emissive']:
                continue
            sel = (mat == mid[n]) & (ndh >= h.get('size', 0.94))
            sel = clusters(sel, ndh, h.get('min_px', 1), h.get('max_px'))
            if not sel.any():
                continue
            hb = h.get('band')
            band[sel] = len(RAMPS[mid[n]]) - 1 if hb is None else hb
            if h.get('color'):
                hl_colors.append((sel, hx(h['color'])))

    # --- 2. internal contour lines where a nearer part overlaps a farther one ---
    line = np.zeros((H, W), bool)
    for dy, dx in N4 + ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        ng = shift(gid, dy, dx, -1)
        nd = shift(depth, dy, dx, np.inf)
        cand = (gid >= 0) & (ng >= 0) & (ng != gid) & (nd < depth - 0.06)
        cand &= line_ok[np.where(gid >= 0, gid, -1)] & line_ok[np.where(ng >= 0, ng, -1)]
        if abs(dy) + abs(dx) == 2:
            cand &= nd < depth - 0.25  # diagonals only for big depth jumps
        line |= cand
    line |= crease
    if painted is not None and any(layer.edge for layer in layers):  # a line where an edged paint meets the rest
        edged = np.array([layer.edge for layer in layers] + [False])[np.where(paint >= 0, paint, -1)] & painted
        for dy, dx in N4:
            other = shift(paint, dy, dx, -9)
            line |= edged & (shift(gid, dy, dx, -1) == gid) & (other != paint) & (other != -9)
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
        img[y, x, :3] = col
        img[y, x, 3] = 255

    for sel, col in hl_colors:
        img[sel & ~line, :3] = col

    # --- 4. outer outline (selout: tinted by neighbour material, or its `line_color` from the style) ---
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
            up = y > 0 and o[y - 1, x]
            dn = y < H - 1 and o[y + 1, x]
            lf = x > 0 and o[y, x - 1]
            rt = x < W - 1 and o[y, x + 1]
            for (a, ay, ax), (b, by, bx) in (
                ((up, -1, 0), (lf, 0, -1)),
                ((up, -1, 0), (rt, 0, 1)),
                ((dn, 1, 0), (lf, 0, -1)),
                ((dn, 1, 0), (rt, 0, 1)),
            ):
                if a and b:
                    # the diagonal between neighbours must be solid sprite (we're an outer corner of a stair)
                    yy, xx = y + ay + by, x + ax + bx
                    if 0 <= yy < H and 0 <= xx < W and solid[yy, xx]:
                        # only remove if removing keeps sprite 4-sealed: the pixel's other two sides empty
                        if not (0 <= y - ay < H and solid[y - ay, x]) and not (0 <= x - bx < W and solid[y, x - bx]):
                            o[y, x] = False
                            break
        out = o
    for y, x in zip(*np.nonzero(out)):
        m = owner[y, x]
        if m < 0:
            continue
        img[y, x, :3] = OUTLINE[m]
        img[y, x, 3] = 255

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


def aux_maps(img, gid, nrm, groups, materials, cam, paint=None, layers=None):
    """Normal map (camera space, RGB) and emissive mask aligned with the sprite.
    Outline pixels inherit the normal of the nearest sprite pixel; painted pixels are emissive when their paint's
    material is."""
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
    if paint is not None and layers:
        em_p = np.array([materials[layer.material]['emissive'] for layer in layers] + [False])
        e = np.where(has & (paint >= 0), em_p[np.where(paint >= 0, paint, -1)], e)
    emis[e] = img[e]
    return normal, emis
