"""Splash art / concept art reference tools.

- prepare(): cut the character out of the splash art (alpha, rembg if installed, or border flood)
- metrics(): silhouette proportions (aspect, width profile per height band)
- compare(): reference vs rendered sprite -> IoU, per-band hints and a comparison sheet PNG
"""

from collections import deque

import numpy as np
from PIL import Image, ImageDraw

from . import palette as pal
from .errors import SpriteKilnError
from .export import BG, _ascii, font, upscale

BANDS = 10


def load(path):
    return Image.open(path).convert('RGBA')


def _largest_component(mask):
    H, W = mask.shape
    lab = np.zeros((H, W), np.int32)
    best, best_n, cur = 0, 0, 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        cur += 1
        q = deque([(y0, x0)])
        lab[y0, x0] = cur
        n = 0
        while q:
            y, x = q.popleft()
            n += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    q.append((yy, xx))
        if n > best_n:
            best, best_n = cur, n
    return lab == best


def _fill_holes(mask):
    H, W = mask.shape
    outside = np.zeros((H, W), bool)
    q = deque()
    for y in range(H):
        for x in (0, W - 1):
            if not mask[y, x]:
                outside[y, x] = True
                q.append((y, x))
    for x in range(W):
        for y in (0, H - 1):
            if not mask[y, x] and not outside[y, x]:
                outside[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= yy < H and 0 <= xx < W and not mask[yy, xx] and not outside[yy, xx]:
                outside[yy, xx] = True
                q.append((yy, xx))
    return ~outside


def cutout(img, work=320, method='auto', tol=None):
    """-> (rgba image cropped to the character, boolean mask, method used)."""
    a = np.asarray(img)
    used = None
    if method in ('auto', 'alpha') and (a[..., 3] < 250).mean() > 0.02:
        mask_full = a[..., 3] > 128
        used = 'alpha'
    elif method in ('auto', 'rembg'):
        try:
            from rembg import remove  # optional, much better on busy backgrounds

            cut = np.asarray(remove(img))
            mask_full = cut[..., 3] > 128
            used = 'rembg'
        except Exception:  # noqa
            used = None
    if used is None:
        # border-colour flood: works for flat / gradient backgrounds
        sm = img.copy()
        sm.thumbnail((work, work))
        s = np.asarray(sm)[..., :3].astype(float)
        border = np.concatenate([s[0], s[-1], s[:, 0], s[:, -1]])
        bg = np.median(border, 0)
        d = np.linalg.norm(s - bg, axis=-1)
        t = tol if tol is not None else max(28.0, np.percentile(np.linalg.norm(border - bg, axis=-1), 95) * 1.6)
        m = _fill_holes(_largest_component(d > t))
        mask_full = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize(img.size, Image.NEAREST)) > 0
        used = 'border'
    ys, xs = np.nonzero(mask_full)
    if len(ys) == 0:
        raise SpriteKilnError(
            'could not find the character in the reference image (try --tol or a PNG with transparency)'
        )
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    out = a[y0:y1, x0:x1].copy()
    m = mask_full[y0:y1, x0:x1]
    out[..., 3] = np.where(m, 255, 0)
    return Image.fromarray(out), m, used


def metrics(mask):
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    m = mask[y0:y1, x0:x1]
    H, W = m.shape
    prof = []
    for i in range(BANDS):
        band = m[int(i * H / BANDS) : max(int((i + 1) * H / BANDS), int(i * H / BANDS) + 1)]
        cols = np.nonzero(band.any(0))[0]
        prof.append(float((cols.max() - cols.min() + 1) / W) if len(cols) else 0.0)
    cy = float(ys.mean() - y0) / H
    return dict(aspect=float(H / W), width_profile=prof, mass_center_y=cy, fill=float(m.mean()))


def _norm_grid(mask, n=96):
    ys, xs = np.nonzero(mask)
    m = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    H, W = m.shape
    s = n / max(H, W)
    im = Image.fromarray(m.astype(np.uint8) * 255).resize((max(1, round(W * s)), max(1, round(H * s))), Image.NEAREST)
    g = np.zeros((n, n), bool)
    a = np.asarray(im) > 0
    oy = n - a.shape[0]
    ox = (n - a.shape[1]) // 2  # bottom-centre aligned
    g[oy : oy + a.shape[0], ox : ox + a.shape[1]] = a
    return g


BAND_NAMES = [
    'top (0-10%)',
    '10-20%',
    '20-30%',
    '30-40%',
    '40-50%',
    '50-60%',
    '60-70%',
    '70-80%',
    '80-90%',
    'bottom (90-100%)',
]


def compare_masks(ref_mask, spr_mask):
    a, b = _norm_grid(ref_mask), _norm_grid(spr_mask)
    iou = float((a & b).sum() / max((a | b).sum(), 1))
    mr, ms = metrics(ref_mask), metrics(spr_mask)
    hints = []
    for i, (pr, ps) in enumerate(zip(mr['width_profile'], ms['width_profile'])):
        d = ps - pr
        if abs(d) > 0.12:
            hints.append(
                (
                    abs(d),
                    f'band {BAND_NAMES[i]}: render {"wider" if d > 0 else "narrower"} '
                    f'than the reference ({ps:.2f} vs {pr:.2f} of the total width)',
                )
            )
    ar = ms['aspect'] / mr['aspect']
    if abs(ar - 1) > 0.12:
        hints.append(
            (
                abs(ar - 1),
                f'height/width aspect: render {ms["aspect"]:.2f} vs reference {mr["aspect"]:.2f} '
                f'({"too tall/narrow" if ar > 1 else "too short/wide"})',
            )
        )
    dc = ms['mass_center_y'] - mr['mass_center_y']
    if abs(dc) > 0.06:
        hints.append(
            (
                abs(dc),
                f'centre of mass {"lower" if dc > 0 else "higher"} than in the reference '
                f'(mass concentrated {"in the legs" if dc > 0 else "in the torso/head"})',
            )
        )
    hints = [h for _, h in sorted(hints, reverse=True)]
    return dict(iou=round(iou, 3), ref=mr, render=ms, hints=hints), a, b


def sheet(ref_img, sprite, turn, iou_grids, ref_colors, spec_mats, out_path, title=''):
    """Side-by-side review sheet for the agent: reference | sprite 6x | overlay | 8-dir turnaround | palettes."""
    big = upscale(sprite, 6)
    H = big.size[1]
    r = ref_img.copy()
    r.thumbnail((int(H * 1.2), H))
    a, b = iou_grids
    ov = np.zeros(a.shape + (4,), np.uint8)
    ov[a & ~b] = (220, 70, 70, 255)
    ov[b & ~a] = (70, 120, 230, 255)
    ov[a & b] = (170, 120, 210, 255)
    ov_im = Image.fromarray(ov).resize((H, H), Image.NEAREST)
    trow = upscale(np.concatenate(turn, 1), 3)
    W = max(r.size[0] + big.size[0] + ov_im.size[0] + 40, trow.size[0] + 20)
    im = Image.new('RGBA', (W, H + trow.size[1] + 110), BG)
    d = ImageDraw.Draw(im)
    x = 10
    im.alpha_composite(r, (x, 20))
    d.text((x, 4), 'reference', fill=(230, 225, 235), font=font())
    x += r.size[0] + 10
    im.alpha_composite(big, (x, 20))
    d.text((x, 4), 'sprite', fill=(230, 225, 235), font=font())
    x += big.size[0] + 10
    im.alpha_composite(ov_im, (x, 20))
    d.text((x, 4), 'silhouette: red=reference only, blue=sprite only', fill=(230, 225, 235), font=font())
    y = H + 30
    im.alpha_composite(trow, (10, y))
    d.text((10, y - 14), '8 directions: ' + _ascii(title), fill=(230, 225, 235), font=font())
    y += trow.size[1] + 12
    d.text((10, y), 'reference palette', fill=(230, 225, 235), font=font())
    for i, c in enumerate(ref_colors[:14]):
        d.rectangle([150 + i * 22, y, 170 + i * 22, y + 16], fill=c['hex'])
    y += 24
    d.text((10, y), 'spec materials', fill=(230, 225, 235), font=font())
    xx = 150
    for M in spec_mats.values():
        for c in M['colors']:
            d.rectangle([xx, y, xx + 12, y + 16], fill=c)
            xx += 13
        xx += 8
    im.save(out_path)
    return out_path


def ref_palette(ref_img, mask, k=10):
    return pal.extract(np.asarray(ref_img), mask, k)
