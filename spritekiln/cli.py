"""SpriteKiln command line. Run `spritekiln -h` (or `python -m spritekiln -h`)."""

import argparse
import json
import os
import shutil
import sys
import time

from . import __version__, system
from .errors import SpriteKilnError


def _spec(path, size=None, warn=True):
    from . import spec as S

    sp = S.load(path, size=size)
    if warn:
        _, warnings = S.check(sp) if sp.get('_raw') else ([], [])
        for w in warnings[:5]:
            _note(f'warning: {w}')
        if len(warnings) > 5:
            _note(f'... {len(warnings) - 5} more warning(s): run `spritekiln validate {path}`')
    return sp


def cmd_validate(a):
    from . import api

    _spec(a.spec, warn=False)
    res = api.validate(a.spec)
    for w in res['warnings']:
        print('warning:', w)
    if res['errors']:
        print('INVALID:')
        for p in res['errors']:
            print('  -', p)
        return 1
    if res['warnings'] and a.strict:
        print(f'INVALID: {len(res["warnings"])} warning(s) with --strict')
        return 1
    s = res['summary']
    print(
        f'OK: {s["name"]} - {s["parts"]} parts, {s["bones"]} bones, {len(s["directions"])} directions, '
        'animations: ' + ', '.join(f'{k}({n})' for k, n in s['animations'].items())
    )
    return 0


def cmd_pose(a):
    """Quick look: one pose in several directions, zoomed (cheap; use it while modelling)."""
    from . import api

    _spec(a.spec)
    t = time.time()
    out, dirs = api.pose(a.spec, a.anim, a.frame, a.dirs, a.scale, a.bg, a.tint, a.out)
    print(f'{out}  ({", ".join(dirs)}; {time.time() - t:.1f}s)')


def cmd_render(a):
    from . import api, qa

    _spec(a.spec, a.size)  # report spec warnings before the long part
    t = time.time()
    res = api.render(
        a.spec,
        a.anims.split(',') if a.anims else None,
        a.dirs.split(',') if a.dirs else None,
        a.jobs,
        a.force,
        size=a.size,
        out=a.out,
        block='pxforge' if a.prog == 'pxforge' else 'spritekiln',
        bg=a.bg,
        tint=a.tint,
        progress=True,
        log=_note,
    )
    print(f'{res["frames"]} frames in {time.time() - t:.0f}s -> {res["dir"]}')
    print(qa.summary(res['qa']))
    print('review: ' + ', '.join(res['contact_sheets'].values()))
    if a.godot is not None or a.export:
        w = api.export(a.spec, 'godot' if a.godot is not None else None, res['dir'], project=a.godot or None)
        print(f'{w["engine"]}: {w.get("scene") or w["dir"]}')


def cmd_export(a):
    from . import api

    _spec(a.spec)
    w = api.export(a.spec, a.engine, a.render_dir, a.to, a.project, a.lit)
    print(f'{w["engine"]}: {w["dir"]}')
    if w['engine'] == 'godot':
        print('  scene:', w['scene'])
        if w.get('addon_installed'):
            print('  addon installed (enable it in Project > Project Settings > Plugins if needed)')
    else:
        for f in w['files']:
            print('  ', f)


def _look(a):
    """preview.viewer() from --bg / --tint, or None."""
    from . import preview

    bg = preview.load_background(a.bg) if getattr(a, 'bg', None) else None
    return preview.viewer(bg, preview.parse_tint(getattr(a, 'tint', None)))


def _note(msg):
    print(msg, file=sys.stderr, flush=True)


def cmd_cache(a):
    from . import cache

    roots = a.paths or ['.']
    dirs = sorted({d for r in roots for d in cache.find_dirs(r, legacy=True)})
    kiln = [d for d in dirs if os.path.basename(d) == cache.DIRNAME]
    legacy = [d for d in dirs if os.path.basename(d) == cache.LEGACY_DIRNAME]
    if a.action == 'info':
        for d in kiln:
            print(f'{cache.size_mb(d):9.1f} MB  {d}')
        for d in legacy:
            print(f'{cache.size_mb(d):9.1f} MB  {d}  (old pxforge cache, never read: `cache clear --legacy`)')
        if not dirs:
            print('no render cache found')
        return
    if a.action == 'prune':
        if a.max_mb is None and a.older_than is None:
            raise SpriteKilnError('cache prune needs --max-mb and/or --older-than')
        for d in kiln:
            for spec_dir in sorted(os.listdir(d)):
                n, mb = cache.prune(os.path.join(d, spec_dir), a.max_mb, a.older_than)
                if n:
                    print(f'{os.path.join(d, spec_dir)}: removed {n} entries ({mb:.1f} MB)')
        return
    for d in kiln + (legacy if a.legacy else []):
        mb = cache.size_mb(d)
        shutil.rmtree(d, ignore_errors=True)
        print(f'removed {d} ({mb:.1f} MB)')
    if legacy and not a.legacy:
        print(f'{len(legacy)} old pxforge cache folder(s) kept; add --legacy to remove them too')


def cmd_review(a):
    from . import preview
    from .review import run

    _spec(a.spec)  # warnings first
    rep = run(
        a.spec,
        anims=a.anims.split(',') if a.anims else None,
        dirs=a.dirs.split(',') if a.dirs else None,
        bg_path=a.bg,
        tint=preview.parse_tint(a.tint),
        against=a.against,
        ref=a.ref,
        ref_dir=a.ref_dir,
        ref_anim=a.ref_anim,
        ref_frame=a.ref_frame,
        scale=a.scale,
        out_dir=a.out,
        jobs=a.jobs,
        log=_note,
    )
    bg = rep['background']
    print(f'{rep["spec"]}: rest pose' + (f' over {bg["image"]} (floor L* {bg["lstar_median"]:.0f})' if bg else ''))
    print('dir   L*med  L*p90  contrast  area  colours  top materials (px)')
    for d, e in rep['directions'].items():
        mats = rep['poses']['rest'][d]['frames'][0]['materials']
        top = ', '.join(f'{m} {n}' for m, n in list(mats.items())[:4])
        contrast = f'{e["contrast"]:+8.1f}' if 'contrast' in e else '       -'
        L = f'{e["lstar_median"]:6.1f} {e["lstar_p90"]:6.1f}'
        print(f'{d:4s} {L} {contrast} {e["area"]:6.0f} {e["colors"]:7.0f}  {top}')
    if 'against' in rep:
        ag = rep['against']
        print(
            f'vs {ag["spec"]}: '
            + ', '.join(
                f'{d} area x{v["area_ratio"]:.2f} L* {v["lstar_median_delta"]:+.1f}'
                for d, v in ag['directions'].items()
            )
        )
    if 'reference' in rep:
        r = rep['reference']
        print(
            f'reference IoU ({r["direction"]}, {r["pose"]}): {r["iou"]:.3f} corrected for {r["pitch"]:g} deg '
            f'(raw {r["iou_raw"]:.3f})'
        )
    for w in rep['warnings']:
        print('warning:', w)
    print('report:', rep['files']['json'])
    print('sheet:', rep['files']['sheet'], *rep['files']['clips'].values())


def cmd_init(a):
    from .scaffold import init

    res = init(a.dir, a.engine, a.ai.split(','), a.specs, a.export_dir, a.godot_project, not a.no_mcp, a.force)
    print(f'SpriteKiln project in {res["root"]} (engine: {res["engine"]}; AI: {", ".join(res["ais"])})')
    for p in res['written']:
        print('  ', os.path.relpath(p, res['root']))
    for n in res['notes']:
        print('note:', n)
    print('next: spritekiln new <name>   (then validate, pose, render, export)')


def cmd_mcp(a):
    from .mcp_server import main

    main()


def cmd_palette(a):
    import numpy as np

    from . import palette as P

    if a.action == 'ramp':
        r = P.ramp(a.input, a.steps, a.hue_shift)
        print('[' + ', '.join(f'"{c}"' for c in r) + ']')
        return
    from .ref import cutout, load

    cut, mask, used = cutout(load(a.input))
    y = P.palette_yaml(P.families(P.extract(np.asarray(cut), mask, a.k)), a.steps)
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as fh:
            fh.write(y)
        print('saved', a.out)
    print(y)


def cmd_ref(a):
    import numpy as np
    from PIL import Image

    from . import palette as P
    from . import ref as R

    if a.action == 'prep':
        cut, mask, used = R.cutout(R.load(a.image), tol=a.tol)
        dst = a.out or os.path.splitext(a.image)[0] + '_ref'
        os.makedirs(dst, exist_ok=True)
        cut.save(os.path.join(dst, 'cutout.png'))
        squashed = R.pitch_corrected(mask, a.pitch)
        pc = np.asarray(cut.resize((squashed.shape[1], squashed.shape[0]), Image.NEAREST)).copy()
        pc[..., 3] = np.where(squashed, 255, 0)
        Image.fromarray(pc).save(os.path.join(dst, f'cutout_pitch{a.pitch:g}.png'))
        m = R.metrics(mask)
        fams = P.families(P.extract(np.asarray(cut), mask, a.k))
        with open(os.path.join(dst, 'palette.yaml'), 'w', encoding='utf-8') as fh:
            fh.write(P.palette_yaml(fams))
        info = dict(
            method=used,
            size=cut.size,
            metrics=m,
            pitch=a.pitch,
            metrics_pitch_corrected=R.metrics(squashed),
            families=[
                dict(base=f['base'], share=round(f['share'], 3), neutral=f['neutral'], hue=round(f['hue']))
                for f in fams
            ],
        )
        with open(os.path.join(dst, 'ref.json'), 'w', encoding='utf-8') as fh:
            json.dump(info, fh, indent=1)
        print(f'cutout ({used}) -> {dst}/cutout.png (+ cutout_pitch{a.pitch:g}.png)  | palette -> {dst}/palette.yaml')
        print(
            f'height/width aspect {m["aspect"]:.2f}; width profile per band (top->bottom): '
            + ' '.join(f'{v:.2f}' for v in m['width_profile'])
        )
        if used == 'border':
            print(
                'note: background removed from the border inwards; check cutout.png (if it cut wrong, try --tol '
                '4-15 (colour step, default 9), a PNG with transparency, or the [splash] extra for rembg)'
            )
        return
    # compare
    from . import api

    _spec(a.spec)
    res = api.ref_compare(a.spec, a.image, a.dir, a.anim, a.frame, not a.no_pitch_correction, a.tol, a.out)
    corr = (
        f'reference squashed by cos(camera pitch), raw {res["iou_raw"]:.3f}' if res['pitch'] else 'no pitch correction'
    )
    print(f'silhouette IoU ({a.dir}): {res["iou"]:.3f} ({corr})   (>0.80 great, 0.65-0.80 ok, <0.65 redo proportions)')
    for h in res['hints'][:8]:
        print('  -', h)
    print('comparison sheet:', res['sheet'])


def cmd_godot(a):
    from . import config
    from .godot import DEFAULT_DEST, _find_project, export_godot, install_addon

    project = _find_project(a.project, start=a.spec)
    if a.install_addon:
        install_addon(project, True)
        print('addon installed ->', os.path.join(project, 'addons', 'pxforge'))
        if not a.spec:
            return
    if not a.spec:
        raise SpriteKilnError('give a spec (or use --install-addon alone)')
    sp = _spec(a.spec)
    cfg = config.load(a.spec)
    dest = a.dest or (cfg.get('export_dir') if cfg.get('engine') == 'godot' else None) or DEFAULT_DEST
    w = export_godot(sp, project, dest, lit=a.lit, update_addon=a.update_addon)
    print(f'{sp["name"]} -> {w["res"]}/')
    print('  scene:', w['scene'])
    print('  SpriteFrames:', w['frames'] + ('  (+ _lit, _canvas)' if 'lit' in w else ''))
    if 'emissive' in w:
        print('  emissive:', w['emissive'])
    if w['addon_installed']:
        print(
            '  addon installed in',
            os.path.join(project, 'addons', 'pxforge'),
            '(enable it in Project > Project Settings > Plugins if needed)',
        )


def cmd_new(a):
    from . import api

    print('created', api.new(a.name, a.template, a.dir, a.ref))


DIRS = ['s', 'se', 'e', 'ne', 'n', 'nw', 'w', 'sw']


def _preview_args(s):
    s.add_argument('--bg', metavar='IMAGE', help='preview over this image (a game floor capture, tiled at 1 px = 1 px)')
    s.add_argument('--tint', metavar='LIGHT', help='scene light for previews: 0.7,0.7,1.0 or #b3b5ff (emissive stays)')


def build_parser(prog='spritekiln'):
    p = argparse.ArgumentParser(
        prog=prog, description='Procedural SDF models in YAML -> animated 8-direction pixel art'
    )
    p.add_argument('--version', action='version', version=f'spritekiln {__version__}')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('validate', help='check a spec')
    s.add_argument('spec')
    s.add_argument('--strict', action='store_true', help='treat warnings (unknown keys, no version header) as errors')
    s.set_defaults(f=cmd_validate)

    s = sub.add_parser('pose', help='quick preview of one pose (rest by default)')
    s.add_argument('spec')
    s.add_argument('--anim')
    s.add_argument('--frame', type=int, default=0)
    s.add_argument('--dirs', help='e.g. s,se,e or all')
    s.add_argument('--scale', type=int, default=4, help='zoom of the preview PNG (default 4)')
    _preview_args(s)
    s.add_argument('-o', '--out')
    s.set_defaults(f=cmd_pose)

    s = sub.add_parser('render', help='render animations and export atlas, JSON, GIFs and QA')
    s.add_argument('spec')
    s.add_argument('--anims', help='comma-separated (default: all)')
    s.add_argument('--dirs', help='comma-separated (default: all of the spec)')
    s.add_argument('-o', '--out')
    s.add_argument('--jobs', type=int, help='worker processes')
    s.add_argument('--force', action='store_true', help='ignore the render cache')
    s.add_argument('--size', type=int, help='32/48/64/128: rescale the camera, keeping the framing')
    s.add_argument(
        '--godot',
        nargs='?',
        const='',
        metavar='PROJECT',
        help='after rendering, export to a Godot project (default: $SPRITEKILN_GODOT_PROJECT)',
    )
    s.add_argument('--export', action='store_true', help="after rendering, export to the project's engine")
    _preview_args(s)
    s.set_defaults(f=cmd_render)

    s = sub.add_parser('godot', help='export a rendered spec to a Godot 4 project (SpriteFrames + scene)')
    s.add_argument('spec', nargs='?')
    s.add_argument('--project', help='folder with project.godot (default: $SPRITEKILN_GODOT_PROJECT)')
    s.add_argument('--dest', help='folder inside the project (default: assets/pxforge)')
    s.add_argument('--lit', action='store_true', help='the scene uses the SpriteFrames with the normal map (Light2D)')
    s.add_argument('--install-addon', action='store_true', help='install/update addons/pxforge in the project')
    s.add_argument('--update-addon', action='store_true', help='overwrite the addon in the project when exporting')
    s.set_defaults(f=cmd_godot)

    s = sub.add_parser('review', help='art-direction report: value, materials, bands, IoU, legibility (JSON + PNG)')
    s.add_argument('spec')
    s.add_argument('--anims', help='also review these clips (all frames; zoomed sheets per clip)')
    s.add_argument('--dirs', help='comma-separated (default: the 8 directions)')
    _preview_args(s)
    s.add_argument('--against', metavar='SPEC', help='compare legibility with another asset (e.g. the Templar)')
    s.add_argument('--ref', metavar='IMAGE', help='splash art: silhouette IoU, corrected for the camera pitch')
    s.add_argument('--ref-dir', default='s', choices=DIRS, help='direction the splash art shows')
    s.add_argument('--ref-anim', help='compare this animation instead of the rest pose')
    s.add_argument('--ref-frame', type=int, default=0)
    s.add_argument('--scale', type=int, default=4, help='zoom of the sheets (default 4)')
    s.add_argument('--jobs', type=int)
    s.add_argument('-o', '--out', help='folder (default: <spec dir>/out/review/<name>)')
    s.set_defaults(f=cmd_review)

    s = sub.add_parser('init', help='set up a game project: spritekiln.toml, specs folder, AI instructions, MCP')
    s.add_argument('dir', nargs='?', default='.')
    s.add_argument('--engine', default='generic', choices=['godot', 'unity', 'monogame', 'generic'])
    s.add_argument(
        '--ai', default='generic', help='claude, codex, cursor, copilot, gemini, generic or all (comma-separated)'
    )
    s.add_argument('--specs', default='art/specs', help='specs folder, relative to the project (default art/specs)')
    s.add_argument('--export-dir', help='where exports go (default depends on the engine)')
    s.add_argument('--godot-project', help='folder with project.godot, relative to the project (default .)')
    s.add_argument('--no-mcp', action='store_true', help="do not register `spritekiln mcp` in the AI client's config")
    s.add_argument('--force', action='store_true', help='rewrite an existing spritekiln.toml')
    s.set_defaults(f=cmd_init)

    s = sub.add_parser('mcp', help='serve SpriteKiln as MCP tools over stdio (needs the mcp extra)')
    s.set_defaults(f=cmd_mcp)

    s = sub.add_parser('cache', help='show, prune or clear render caches')
    s.add_argument('action', choices=['info', 'prune', 'clear'])
    s.add_argument('paths', nargs='*', help='spec files or folders to search (default: current folder)')
    s.add_argument('--max-mb', type=float, help='prune: keep each spec cache under this size (oldest go first)')
    s.add_argument('--older-than', type=float, metavar='DAYS', help='prune: drop entries unused for DAYS')
    s.add_argument('--legacy', action='store_true', help='clear: also remove old pxforge .pxcache folders')
    s.set_defaults(f=cmd_cache)

    s = sub.add_parser('palette', help='hue-shifted ramps / extract a palette from an image')
    s.add_argument('action', choices=['ramp', 'extract'])
    s.add_argument('input', help='base colour (#hex) or image')
    s.add_argument('--steps', type=int, default=6)
    s.add_argument('--hue-shift', type=float, default=22)
    s.add_argument('--k', type=int, default=10)
    s.add_argument('-o', '--out')
    s.set_defaults(f=cmd_palette)

    s = sub.add_parser('ref', help='splash art: prepare a reference and compare it with the model')
    s.add_argument('action', choices=['prep', 'compare'])
    s.add_argument('a1', help='prep: image | compare: spec')
    s.add_argument('a2', nargs='?', help='compare: image')
    s.add_argument('--dir', default='s', choices=DIRS, help='direction the splash art shows')
    s.add_argument('--anim')
    s.add_argument('--frame', type=int, default=0)
    s.add_argument('--tol', type=float, help='prep: colour step of the background flood (default 9)')
    s.add_argument('--pitch', type=float, default=38, help='prep: camera pitch for cutout_pitchN.png (default 38)')
    s.add_argument('--no-pitch-correction', action='store_true', help='compare: IoU against the raw reference')
    s.add_argument('--k', type=int, default=10)
    s.add_argument('-o', '--out')
    s.set_defaults(f=cmd_ref)

    s = sub.add_parser('new', help='create a spec from a template')
    s.add_argument('name')
    s.add_argument('--template', default='humanoid')
    s.add_argument('--dir', help='parent folder (default: <specs of spritekiln.toml>/characters or specs/characters)')
    s.add_argument('--ref', help='splash art to copy next to the spec')
    s.set_defaults(f=cmd_new)

    s = sub.add_parser('export', help='export a rendered spec to the engine of spritekiln.toml (or --engine)')
    s.add_argument('spec')
    s.add_argument('--engine', choices=['godot', 'unity', 'monogame', 'generic'])
    s.add_argument('--to', help='destination folder (godot: inside the project; default from spritekiln.toml)')
    s.add_argument('--project', help='Godot project folder')
    s.add_argument('--render-dir', help='render folder (default: <spec dir>/out/<name>)')
    s.add_argument('--lit', action='store_true', help='godot: the scene uses the normal-mapped SpriteFrames')
    s.set_defaults(f=cmd_export)
    return p


def main(argv=None, prog='spritekiln'):
    system.limit_blas_threads()  # before numpy loads: ~500 MB less committed memory
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding='utf-8', errors='replace')
        except Exception:  # noqa: BLE001 - not every stream can be reconfigured
            pass
    p = build_parser(prog)
    a = p.parse_args(argv)
    a.prog = prog
    if a.cmd == 'ref':
        if a.action == 'prep':
            a.image = a.a1
        else:
            if not a.a2:
                p.error('ref compare SPEC IMAGE')
            a.spec, a.image = a.a1, a.a2
    try:
        rc = a.f(a)
    except SpriteKilnError as e:
        print(f'error: {e}', file=sys.stderr)
        rc = 1
    except KeyboardInterrupt:
        print('interrupted', file=sys.stderr)
        rc = 130
    if rc:
        sys.exit(rc)


if __name__ == '__main__':
    main()
