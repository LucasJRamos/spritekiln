"""Automatic quality checks over rendered frames. Returns a report dict (also saved as qa.json)."""
import numpy as np


def _opaque(img):
    return img[..., 3] == 255


def check(spec, anims, dlist, out):
    S = spec['size']
    rep = dict(errors=[], warnings=[], info={})
    colors = set()
    area = {}
    for (a, d, i), (img, nm, em, ms, ev) in out.items():
        op = _opaque(img)
        alpha = img[..., 3] > 0
        if op.sum() < 20:
            rep['errors'].append(f'{a}/{d}/{i}: frame quase vazio ({int(op.sum())} px)')
            continue
        if alpha[0].any() or alpha[-1].any() or alpha[:, 0].any() or alpha[:, -1].any():
            side = [n for n, v in (('topo', alpha[0]), ('base', alpha[-1]), ('esquerda', alpha[:, 0]),
                                   ('direita', alpha[:, -1])) if v.any()]
            rep['errors'].append(f'{a}/{d}/{i}: sprite cortado na borda ({", ".join(side)}) -> reduza camera.scale '
                                 f'ou ajuste camera.center')
        pd = np.pad(op, 1)
        nn = pd[:-2, 1:-1].astype(int) + pd[2:, 1:-1] + pd[1:-1, :-2] + pd[1:-1, 2:]
        iso = int((op & (nn == 0)).sum())
        if iso:
            rep['warnings'].append(f'{a}/{d}/{i}: {iso} pixel(s) isolado(s)')
        for c in np.unique(img[op][:, :3], axis=0):
            colors.add(tuple(int(x) for x in c))
        area[(a, d, i)] = int(op.sum())
        ys, xs = np.nonzero(op)
        margin = min(ys.min(), S - 1 - ys.max(), xs.min(), S - 1 - xs.max())
        if margin < 2 and not any('cortado' in e and f'{a}/{d}/{i}' in e for e in rep['errors']):
            rep['warnings'].append(f'{a}/{d}/{i}: só {margin}px de margem até a borda')
    pal_size = sum(len(m['colors']) for m in spec['materials'].values())
    rep['info']['colors_used'] = len(colors)
    rep['info']['palette_size'] = pal_size
    if len(colors) > pal_size + 12:
        rep['warnings'].append(f'{len(colors)} cores usadas para {pal_size} na paleta (brilho de emissivos mistura cores)')
    # per animation checks
    for a in anims:
        loop = spec['animations'][a].get('loop', 'keys' not in spec['animations'][a])
        for d, _ in dlist:
            n = len([k for k in out if k[0] == a and k[1] == d])
            frames = [out[(a, d, i)][0] for i in range(n)]
            ops = [_opaque(f) for f in frames]
            cy = [np.nonzero(o)[0].mean() if o.any() else 0 for o in ops]
            cx = [np.nonzero(o)[1].mean() if o.any() else 0 for o in ops]
            if a.startswith('idle') and (np.ptp(cx) > 2.5):
                rep['warnings'].append(f'{a}/{d}: idle desliza {np.ptp(cx):.1f}px na horizontal')
            if loop and n > 2:
                seam = float((ops[0] ^ ops[-1]).sum()) / max(ops[0].sum(), 1)
                step = np.mean([(ops[i] ^ ops[i + 1]).sum() / max(ops[i].sum(), 1) for i in range(n - 1)])
                if seam > step * 2.2 and seam > 0.08:
                    rep['warnings'].append(f'{a}/{d}: emenda do loop (último->primeiro) salta mais que os outros '
                                           f'frames ({seam:.2f} vs média {step:.2f})')
            same = [i for i in range(n - 1) if np.array_equal(frames[i], frames[i + 1])]
            if same:
                rep['warnings'].append(f'{a}/{d}: frames idênticos em {same} (pose não muda)')
        areas = [np.mean([area.get((a, d, i), 0) for i in range(len([k for k in out if k[0] == a and k[1] == d]))])
                 for d, _ in dlist]
        if min(areas) > 0:
            rep['info'][f'{a}_area_ratio_min_max'] = round(min(areas) / max(areas), 2)
    rep['ok'] = not rep['errors']
    return rep


def summary(rep, limit=12):
    lines = [f"QA: {'OK' if rep['ok'] else 'FALHOU'} - {len(rep['errors'])} erro(s), {len(rep['warnings'])} aviso(s); "
             f"{rep['info'].get('colors_used')} cores"]
    for e in rep['errors'][:limit]:
        lines.append('  ERRO  ' + e)
    for w in rep['warnings'][:limit]:
        lines.append('  aviso ' + w)
    if len(rep['warnings']) > limit:
        lines.append(f'  ... +{len(rep["warnings"]) - limit} avisos em qa.json')
    return '\n'.join(lines)
