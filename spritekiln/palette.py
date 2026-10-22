"""Palette tools: hue-shifted ramps and palette extraction from images (splash arts)."""

import colorsys

import numpy as np

from .pixelize import hx


def to_hex(rgb):
    r, g, b = [int(np.clip(round(c * 255), 0, 255)) for c in rgb]
    return f'#{r:02x}{g:02x}{b:02x}'


def _toward(h, target, amt):
    """rotate hue h (0..1) toward target hue by amt (0..1 of a turn, shortest path)."""
    d = ((target - h + 0.5) % 1.0) - 0.5
    step = np.sign(d) * min(abs(d), amt)
    return (h + step) % 1.0


def ramp(base, steps=6, hue_shift=22, light_range=None, sat_drop=0.22):
    """Pixel-art ramp from one base colour.
    Index 0 is a near-black outline tone. Shadows rotate toward blue-violet, lights toward yellow."""
    r, g, b = [c / 255 for c in hx(base)]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    lo, hi = light_range or (0.05, float(np.clip(l + 0.36, 0.45, 0.92)))
    out = []
    n = steps
    for i in range(n):
        t = i / (n - 1)  # 0 dark .. 1 light
        L = lo + (hi - lo) * (t**0.9)
        rel = (L - l) / max(hi - lo, 1e-6) * 2  # -..+ relative to base
        hh = (
            _toward(h, 0.70, hue_shift / 360 * min(1, max(0, -rel)))
            if rel < 0
            else _toward(h, 0.14, hue_shift / 360 * min(1, rel))
        )
        ss = s * (1 - sat_drop * min(1, abs(rel)) ** 1.5)
        if i == 0:
            ss *= 0.85
        out.append(to_hex(colorsys.hls_to_rgb(hh, L, min(max(ss, 0), 1))))
    return out


# ---------------- OKLab helpers ----------------
def _srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def oklab(rgb):
    c = _srgb_to_lin(np.asarray(rgb, float) / 255.0)
    M1 = np.array(
        [
            [0.4122214708, 0.5363325363, 0.0514459929],
            [0.2119034982, 0.6806995451, 0.1073969566],
            [0.0883024619, 0.2817188376, 0.6299787005],
        ]
    )
    lms = np.cbrt(c @ M1.T)
    M2 = np.array(
        [
            [0.2104542553, 0.7936177850, -0.0040720468],
            [1.9779984951, -2.4285922050, 0.4505937099],
            [0.0259040371, 0.7827717662, -0.8086757660],
        ]
    )
    return lms @ M2.T


def kmeans(X, k, iters=25, seed=0):
    rng = np.random.default_rng(seed)
    C = X[rng.choice(len(X), 1)]
    for _ in range(1, k):  # k-means++ init
        d = ((X[:, None] - C[None]) ** 2).sum(-1).min(1)
        if d.sum() <= 0:  # fewer distinct colours than k: keep fewer clusters
            break
        C = np.vstack([C, X[rng.choice(len(X), p=d / d.sum())]])
    for _ in range(iters):
        lab = ((X[:, None] - C[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            if (lab == j).any():
                C[j] = X[lab == j].mean(0)
    return C, lab


def extract(img_rgba, mask=None, k=10, max_px=40000):
    """Dominant colours of the (masked) image -> list of dicts sorted by coverage."""
    a = np.asarray(img_rgba)
    if mask is None:
        mask = a[..., 3] > 128 if a.shape[-1] == 4 else np.ones(a.shape[:2], bool)
    px = a[..., :3][mask].astype(float)
    if not len(px):
        from .errors import SpriteKilnError

        raise SpriteKilnError('the image has no opaque pixels to take colours from')
    if len(px) > max_px:
        px = px[np.random.default_rng(1).choice(len(px), max_px, replace=False)]
    X = oklab(px)
    C, lab = kmeans(X, min(k, len(px)))
    out = []
    for j in range(len(C)):
        sel = lab == j
        if not sel.any():
            continue
        rgb = np.median(px[sel], 0)
        L, A, B = C[j]
        out.append(
            dict(
                hex=to_hex(rgb / 255),
                share=float(sel.mean()),
                L=float(L),
                chroma=float(np.hypot(A, B)),
                hue=float(np.degrees(np.arctan2(B, A)) % 360),
            )
        )
    return sorted(out, key=lambda d: -d['share'])


def families(colors, hue_tol=28, chroma_neutral=0.035):
    """Group extracted colours into material families (same hue, different light)."""
    fams = []
    for c in colors:
        neutral = c['chroma'] < chroma_neutral
        for f in fams:
            if f['neutral'] and neutral:
                f['members'].append(c)
                break
            if not f['neutral'] and not neutral:
                dh = abs((c['hue'] - f['hue'] + 180) % 360 - 180)
                if dh < hue_tol:
                    f['members'].append(c)
                    break
        else:
            fams.append(dict(hue=c['hue'], neutral=neutral, members=[c]))
    for f in fams:
        f['share'] = sum(m['share'] for m in f['members'])
        mid = sorted(f['members'], key=lambda m: m['L'])[len(f['members']) // 2]
        f['base'] = max(f['members'], key=lambda m: m['share'])['hex']
        f['mid'] = mid['hex']
        f['light_span'] = (min(m['L'] for m in f['members']), max(m['L'] for m in f['members']))
    return sorted(fams, key=lambda f: -f['share'])


def palette_yaml(fams, steps=6, accent_steps=4):
    lines = [
        '# Generated by spritekiln from a reference image.',
        '# Rename the ramps (e.g. skin, cloth, metal) and adjust them by hand if needed.',
        'ramps:',
    ]
    for i, f in enumerate(fams):
        n = steps if f['share'] > 0.08 else accent_steps
        r = ramp(f['base'], n)
        tag = 'neutral' if f['neutral'] else f'hue {f["hue"]:.0f}°'
        lines.append(
            f'  fam{i + 1}: [{", ".join(chr(34) + c + chr(34) for c in r)}]   '
            f'# {f["share"] * 100:.0f}% of the image, {tag}, base {f["base"]}'
        )
    return '\n'.join(lines) + '\n'
