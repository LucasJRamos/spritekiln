"""`spritekiln review`: the numbers an art director checks, as JSON and contact sheets.

Ported from the scripts written during the Hunt Tower session (research/): CIE L* of the sprite against
the game floor, opaque pixels per material and direction, ramp band usage, silhouette IoU against the
camera-corrected reference, legibility next to another asset, and zoomed sheets per clip. Optional
targets in the spec (`review: {min_lstar: 20, materials: {lining: {min_px: 30}}}`) become QA warnings.
"""

import json
import os

import numpy as np
from PIL import Image, ImageDraw

from . import preview
from . import spec as specmod
from .export import BG, contact_sheet, font, upscale
from .pipeline import render_all, render_frame
from .pixelize import hx
from .rig import rest_env


def lstar(rgb):
    """CIE L* (0..100) of sRGB colours, shape (..., 3) uint8."""
    c = np.asarray(rgb, float) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    Y = c @ np.array([0.2126, 0.7152, 0.0722])
    f = np.where(Y > 216 / 24389, np.cbrt(Y), (24389 / 27 * Y + 16) / 116)
    return 116 * f - 16


def scene(spec, bg_path=None, tint=None):
    """(background array or None, tint or None) from options, falling back to the spec's `review:` block."""
    rv = spec.get('review') or {}
    bg_path = bg_path or (os.path.join(spec['_dir'], rv['background']) if rv.get('background') else None)
    if tint is None and rv.get('tint') is not None:
        t = rv['tint']
        tint = preview.parse_tint(','.join(str(v) for v in t) if isinstance(t, list) else t)
    return (preview.load_background(bg_path) if bg_path else None), tint


def frame_stats(fr, spec, tint=None):
    """Numbers for one frame. L* is measured as the frame looks under `tint` (emissive pixels keep their colour)."""
    img = fr.img
    op = img[..., 3] == 255
    if not op.any():
        return dict(area=0, width=0, height=0, lstar_median=0.0, lstar_p90=0.0, colors=0, materials={}, bands={})
    shown = preview.tint(img, tint, fr.emissive) if tint else img
    L = lstar(shown[op][:, :3])
    ys, xs = np.nonzero(op)
    px = img[op][:, :3]
    return dict(
        area=int(op.sum()),
        width=int(xs.max() - xs.min() + 1),
        height=int(ys.max() - ys.min() + 1),
        lstar_median=round(float(np.median(L)), 1),
        lstar_p90=round(float(np.percentile(L, 90)), 1),
        colors=int(len(np.unique(px, axis=0))),
        materials=dict(sorted(fr.materials.items(), key=lambda kv: -kv[1])),
        bands=_bands(px, spec),
    )


def _bands(px, spec):
    """Pixels per ramp index for every material ({material: {index: count}}); shared ramps count for each."""
    keys = px.astype(np.int64) @ np.array([1 << 16, 1 << 8, 1])
    u, c = np.unique(keys, return_counts=True)
    count = dict(zip(u.tolist(), c.tolist()))
    out = {}
    for name, m in spec['materials'].items():
        per = {}
        for i, col in enumerate(m['colors']):
            r, g, b = hx(col)
            n = count.get((r << 16) | (g << 8) | b, 0)
            if n:
                per[i] = n
        if per:
            out[name] = per
    return out


def background_stats(bg):
    L = lstar(bg[..., :3].reshape(-1, 3))
    return dict(lstar_median=round(float(np.median(L)), 1), lstar_p90=round(float(np.percentile(L, 90)), 1))


def target_warnings(spec, stats):
    """`review:` targets -> warnings. `stats`: {(pose, direction): [frame stats]}; a pose fails a target when
    the median over its frames misses it."""
    rv = spec.get('review') or {}
    found = {}
    for (pose, d), frames in stats.items():
        if 'min_lstar' in rv:
            v = float(np.median([s['lstar_median'] for s in frames]))
            if v < rv['min_lstar']:
                found.setdefault((f'review.min_lstar: {pose} below {rv["min_lstar"]:g}', pose), []).append((d, v))
        for mat, t in (rv.get('materials') or {}).items():
            v = float(np.median([s['materials'].get(mat, 0) for s in frames]))
            if 'min_px' in t and v < t['min_px']:
                found.setdefault((f'review.materials.{mat}: {pose} below {t["min_px"]} px', pose), []).append((d, v))
            if 'max_px' in t and v > t['max_px']:
                found.setdefault((f'review.materials.{mat}: {pose} above {t["max_px"]} px', pose), []).append((d, v))
    return [f'{msg} in {", ".join(f"{d} ({v:.0f})" for d, v in hits)}' for (msg, _), hits in sorted(found.items())]


def _rest(spec, dirs):
    return {d: render_frame(spec, rest_env(spec, y), y) for d, y in dirs}


def _strip(frames, look, scale, captions):
    """Frames side by side over the scene, upscaled, with a caption under each."""
    shown = [look(f.img, f.emissive) if look else f.img for f in frames]
    strip = upscale(np.concatenate(shown, 1), scale, None if look else BG)
    w = shown[0].shape[1] * scale
    lines = max(len(c) for c in captions)
    out = Image.new('RGBA', (strip.width, strip.height + 14 * lines + 6), BG)
    out.alpha_composite(strip.convert('RGBA'))
    d = ImageDraw.Draw(out)
    for i, cap in enumerate(captions):
        for j, line in enumerate(cap):
            d.text((i * w + 3, strip.height + 3 + 14 * j), line, fill=(230, 225, 235), font=font())
    return out


def run(
    spec_path,
    anims=None,
    dirs=None,
    bg_path=None,
    tint=None,
    against=None,
    ref=None,
    ref_dir='s',
    ref_anim=None,
    ref_frame=0,
    scale=4,
    out_dir=None,
    jobs=None,
    log=None,
):
    """Render what the review needs (cached), write review.json + review.png (+ clip_<anim>.png), return the report."""
    from . import ref as R

    spec = specmod.load(spec_path)
    bg, tint = scene(spec, bg_path, tint)
    look = preview.viewer(bg, tint)
    dl = [(d, y) for d, y in spec['directions'] if not dirs or d in dirs]
    if spec['kind'] == 'character' and not dirs:
        dl = specmod.DIRECTIONS8
    out_dir = out_dir or os.path.join(spec['_dir'], 'out', 'review', spec['name'])
    os.makedirs(out_dir, exist_ok=True)

    rest = _rest(spec, dl)
    stats = {('rest', d): [frame_stats(f, spec, tint)] for d, f in rest.items()}
    clips = {}
    if anims:
        _, anims, alist, out = render_all(os.path.abspath(spec_path), anims, [d for d, _ in dl], jobs, log=log)
        for a in anims:
            for d, _ in alist:
                frames = [out[k] for k in sorted(k for k in out if k[0] == a and k[1] == d)]
                stats[(a, d)] = [frame_stats(f, spec, tint) for f in frames]
                clips.setdefault(a, {})[d] = frames

    report = dict(spec=spec['name'], tint=list(tint) if tint else None, background=None, directions={}, poses={})
    if bg is not None:
        report['background'] = dict(
            image=bg_path or (spec.get('review') or {}).get('background'), **background_stats(bg)
        )
    for (pose, d), frames in stats.items():
        med = lambda key, frames=frames: round(float(np.median([s[key] for s in frames])), 1)  # noqa: E731
        entry = dict(
            lstar_median=med('lstar_median'),
            lstar_p90=med('lstar_p90'),
            area=med('area'),
            colors=med('colors'),
            frames=frames,
        )
        if report['background']:
            entry['contrast'] = round(entry['lstar_median'] - report['background']['lstar_median'], 1)
        report['poses'].setdefault(pose, {})[d] = entry
    report['directions'] = {
        d: {k: v for k, v in e.items() if k != 'frames'} for d, e in report['poses']['rest'].items()
    }

    if against:
        other = specmod.load(against)
        theirs = {d: frame_stats(f, other, tint) for d, f in _rest(other, dl).items()}
        mine = {d: report['poses']['rest'][d]['frames'][0] for d, _ in dl}
        report['against'] = dict(
            spec=other['name'],
            directions={
                d: dict(
                    area_ratio=round(mine[d]['area'] / max(theirs[d]['area'], 1), 2),
                    lstar_median_delta=round(mine[d]['lstar_median'] - theirs[d]['lstar_median'], 1),
                    lstar_p90_delta=round(mine[d]['lstar_p90'] - theirs[d]['lstar_p90'], 1),
                    colors=[mine[d]['colors'], theirs[d]['colors']],
                )
                for d, _ in dl
            },
        )
    if ref:
        _, mask, used = R.cutout(R.load(ref))
        yaw = dict(specmod.DIRECTIONS8)[ref_dir]
        if ref_anim:
            from .anim import frames_of

            fr = render_frame(spec, frames_of(spec, ref_anim, yaw)[ref_frame][0], yaw)
        else:
            fr = rest[ref_dir] if ref_dir in rest else render_frame(spec, rest_env(spec, yaw), yaw)
        sprite = fr.img[..., 3] == 255
        pitch = float(spec['camera']['pitch'])
        res = R.compare_masks(mask, sprite, pitch)[0]
        report['reference'] = dict(
            image=ref,
            direction=ref_dir,
            pose=ref_anim or 'rest',
            cutout=used,
            iou=res['iou'],
            iou_raw=R.compare_masks(mask, sprite)[0]['iou'],
            pitch=pitch,
            hints=res['hints'],
        )
    report['warnings'] = target_warnings(spec, stats)

    # sheets
    rest_frames = [rest[d] for d, _ in dl]
    caps = []
    for d, _ in dl:
        e = report['poses']['rest'][d]
        top = list(e['frames'][0]['materials'].items())[:2]
        caps.append([f'{d}  L* {e["lstar_median"]:.0f}/{e["lstar_p90"]:.0f}', ' '.join(f'{m[:6]} {n}' for m, n in top)])
    sheets = [_strip(rest_frames, look, scale, caps)]
    if against:
        theirs_frames = list(_rest(other, dl).values())
        sheets.append(_strip(theirs_frames, look, scale, [[f'{other["name"]} {d}'] for d, _ in dl]))
    W = max(s.width for s in sheets)
    sheet = Image.new('RGBA', (W, sum(s.height for s in sheets) + 22), BG)
    ImageDraw.Draw(sheet).text(
        (4, 4),
        f'{spec["name"]}: rest pose' + (f' vs {other["name"]}' if against else ''),
        fill=(230, 225, 235),
        font=font(),
    )
    y = 22
    for s in sheets:
        sheet.alpha_composite(s, (0, y))
        y += s.height
    paths = dict(json=os.path.join(out_dir, 'review.json'), sheet=os.path.join(out_dir, 'review.png'), clips={})
    sheet.save(paths['sheet'])
    for a, by_dir in clips.items():
        rows = [[(look(f.img, f.emissive) if look else f.img) for f in by_dir[d]] for d in by_dir]
        p = os.path.join(out_dir, f'clip_{a}.png')
        contact_sheet(rows, list(by_dir), max(len(r) for r in rows), spec['size'], scale).save(p)
        paths['clips'][a] = p
    report['files'] = paths
    with open(paths['json'], 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    return report


def check_review_block(spec):
    """Problems in the `review:` block that the schema cannot see (unknown materials)."""
    out = []
    for mat in (spec.get('review') or {}).get('materials') or {}:
        if mat not in spec['materials']:
            out.append(f'review.materials.{mat}: unknown material "{mat}"')
    return out
