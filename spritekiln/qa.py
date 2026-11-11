"""Automatic quality checks over rendered frames. Returns a report dict (also saved as qa.json)."""

import numpy as np

from .anim import is_loop, timing_problems
from .motion import ground_speed

BOIL_WARN = 0.04  # share of the inside blinking for one frame (A B A)...
STILL_IOU = 0.95  # ...while the silhouette stays this similar: pixels boil


def _opaque(img):
    return img[..., 3] == 255


def _inner(op):
    """Opaque pixels whose four neighbours are opaque too (not the outline)."""
    pd = np.pad(op, 1)
    return op & pd[:-2, 1:-1] & pd[2:, 1:-1] & pd[1:-1, :-2] & pd[1:-1, 2:]


HIDDEN_MIN_PX = 8  # a part this big in some frame of a clip is reported when another frame hides it


def _hidden(spec, shown):
    """{part: [frames]}: parts that show at least HIDDEN_MIN_PX pixels in some frame of a clip and none in others
    (a weapon swinging behind the body). Parts with a `when` come and go on purpose and are left out."""
    out = {}
    for p in sorted({k for s in shown for k in s}):
        if 'when' in (spec['parts'].get(p) or {}):
            continue
        px = [s.get(p, 0) for s in shown]
        if max(px) >= HIDDEN_MIN_PX and min(px) == 0:
            out[p] = [i for i, v in enumerate(px) if v == 0]
    return out


def boil(frames, loop):
    """(boil, silhouette IoU): the share of inner pixels that change colour for one frame and change back the
    next (A B A, a blink), and how much consecutive silhouettes overlap, averaged over the frames (around the
    seam in a loop). Measured on the showcase idles: 2-5 % (half that with `snap`), runs 8-14 %. Emissive pixels
    may flicker on purpose: left out."""
    n = len(frames)
    if n < 3:
        return 0.0, 1.0
    share, iou = [], []
    for i in range(n) if loop else range(1, n - 1):
        fa, fb, fc = frames[i - 1], frames[i], frames[(i + 1) % n]
        a, b, c = fa.img, fb.img, fc.img
        oa, ob = _opaque(a), _opaque(b)
        inner = _inner(oa) & _inner(ob) & _inner(_opaque(c))
        for f in (fa, fb, fc):
            if f.emissive is not None:
                inner &= f.emissive[..., 3] == 0
        back = (a[..., :3] == c[..., :3]).all(-1) & (b[..., :3] != a[..., :3]).any(-1)
        share.append((inner & back).sum() / max(int(inner.sum()), 1))
        iou.append((oa & ob).sum() / max(int((oa | ob).sum()), 1))
    return float(np.mean(share)), float(np.mean(iou))


def check(spec, anims, dlist, out):
    S = spec['size']
    rep = dict(errors=[], warnings=[], info={})
    colors = set()
    area = {}
    for (a, d, i), (img, *_) in out.items():
        op = _opaque(img)
        alpha = img[..., 3] > 0
        if op.sum() < 20:
            rep['errors'].append(f'{a}/{d}/{i}: frame almost empty ({int(op.sum())} px)')
            continue
        edges = [
            n
            for n, v in (('top', alpha[0]), ('bottom', alpha[-1]), ('left', alpha[:, 0]), ('right', alpha[:, -1]))
            if v.any()
        ]
        if edges:
            rep['errors'].append(
                f'{a}/{d}/{i}: sprite clipped at the edge ({", ".join(edges)}) -> move camera.center, '
                f'raise size or reduce the gesture (camera.scale only for the whole game)'
            )
        pd = np.pad(op, 1)
        nn = pd[:-2, 1:-1].astype(int) + pd[2:, 1:-1] + pd[1:-1, :-2] + pd[1:-1, 2:]
        iso = int((op & (nn == 0)).sum())
        if iso:
            rep['warnings'].append(f'{a}/{d}/{i}: {iso} isolated pixel(s)')
        for c in np.unique(img[op][:, :3], axis=0):
            colors.add(tuple(int(x) for x in c))
        area[(a, d, i)] = int(op.sum())
        ys, xs = np.nonzero(op)
        margin = min(ys.min(), S - 1 - ys.max(), xs.min(), S - 1 - xs.max())
        if margin < 2 and not edges:
            rep['warnings'].append(f'{a}/{d}/{i}: only {margin}px of margin to the edge')
    pal_size = sum(len(m['colors']) for m in spec['materials'].values())
    rep['info']['colors_used'] = len(colors)
    rep['info']['palette_size'] = pal_size
    if len(colors) > pal_size + 12:
        rep['warnings'].append(
            f'{len(colors)} colours used for {pal_size} in the palette (emissive glow mixes colours)'
        )
    # per animation checks
    for a in anims:
        loop = is_loop(spec['animations'][a])
        for d, _ in dlist:
            n = len([k for k in out if k[0] == a and k[1] == d])
            frames = [out[(a, d, i)][0] for i in range(n)]
            ops = [_opaque(f) for f in frames]
            cx = [np.nonzero(o)[1].mean() if o.any() else 0 for o in ops]
            if a.startswith('idle') and (np.ptp(cx) > 2.5):
                rep['warnings'].append(f'{a}/{d}: idle slides {np.ptp(cx):.1f}px horizontally')
            if loop and n > 2:
                seam = float((ops[0] ^ ops[-1]).sum()) / max(ops[0].sum(), 1)
                step = np.mean([(ops[i] ^ ops[i + 1]).sum() / max(ops[i].sum(), 1) for i in range(n - 1)])
                if seam > step * 2.2 and seam > 0.08:
                    rep['warnings'].append(
                        f'{a}/{d}: loop seam (last->first) jumps more than the other frames '
                        f'({seam:.2f} vs mean {step:.2f})'
                    )
            share, still = boil([out[(a, d, i)] for i in range(n)], loop)
            rep['info'].setdefault('boil', {})[f'{a}/{d}'] = round(share, 3)
            if still >= STILL_IOU and share >= BOIL_WARN:
                rep['warnings'].append(
                    f'{a}/{d}: {share:.0%} of the inside blinks for one frame while the silhouette barely moves '
                    f'(pixels boil): snap the moving frames to whole pixels (`snap: [root, ...]`) and check again'
                )
            same = [i for i in range(n - 1) if np.array_equal(frames[i], frames[i + 1])]
            if same:
                rep['warnings'].append(f'{a}/{d}: identical frames at {same} (the pose does not change)')
            shown = [out[(a, d, i)].parts for i in range(n)]
            gone = _hidden(spec, shown)
            if gone:
                rep['info'].setdefault('hidden', {})[f'{a}/{d}'] = gone
            for trait, t in ((spec.get('review') or {}).get('keep') or {}).items():
                if t.get('dirs') and d not in t['dirs']:
                    continue
                px = [sum(s.get(p, 0) for p in t.get('parts') or []) for s in shown]
                px = [
                    v + sum(out[(a, d, i)].materials.get(m, 0) for m in t.get('materials') or [])
                    for i, v in enumerate(px)
                ]
                lost = [i for i, v in enumerate(px) if v == 0]
                if lost and max(px) > 0:
                    rep['warnings'].append(
                        f'review.keep.{trait}: hidden in {a}/{d} frame(s) {lost} (it shows in the others): raise or '
                        f'turn it there, or cheat per direction with `yaw`'
                    )
        areas = [
            np.mean([area.get((a, d, i), 0) for i in range(len([k for k in out if k[0] == a and k[1] == d]))])
            for d, _ in dlist
        ]
        if min(areas) > 0:
            rep['info'][f'{a}_area_ratio_min_max'] = round(min(areas) / max(areas), 2)
    for a in anims:
        try:
            speed = ground_speed(spec, a)
        except Exception:  # noqa: BLE001 - a number for the report, never a reason to fail a render
            speed = None
        if speed:
            rep['info'].setdefault('ground_speed', {})[a] = speed
    rep['errors'] += timing_problems(spec, anims)
    if spec.get('review'):
        from .review import frame_stats, scene, target_warnings

        tint = scene(spec)[1]
        stats = {}
        for (a, d, _i), fr in sorted(out.items()):
            stats.setdefault((a, d), []).append(frame_stats(fr, spec, tint))
        rep['warnings'] += target_warnings(spec, stats)
    rep['ok'] = not rep['errors']
    return rep


def summary(rep, limit=12):
    lines = [
        f'QA: {"OK" if rep["ok"] else "FAILED"} - {len(rep["errors"])} error(s), {len(rep["warnings"])} '
        f'warning(s); {rep["info"].get("colors_used")} colours'
    ]
    for e in rep['errors'][:limit]:
        lines.append('  ERROR  ' + e)
    for w in rep['warnings'][:limit]:
        lines.append('  warning ' + w)
    if len(rep['warnings']) > limit:
        lines.append(f'  ... +{len(rep["warnings"]) - limit} warnings in qa.json')
    for a, g in (rep['info'].get('ground_speed') or {}).items():
        lines.append(
            f'  {a}: the ground passes at {g["px_per_s"]:g} px/s under the feet (move the character at that speed)'
        )
    hidden = rep['info'].get('hidden') or {}
    if hidden:
        parts = sorted({p for v in hidden.values() for p in v})
        lines.append(
            f'  hidden in some frames ({len(hidden)} clip/direction(s), qa.json info.hidden): {", ".join(parts[:8])}'
            + (', ...' if len(parts) > 8 else '')
        )
    return '\n'.join(lines)
