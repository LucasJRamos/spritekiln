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
    errors = S.quick_errors(sp)  # cheap checks only; `validate` builds every pose
    if errors:
        listed = ''.join(f'\n  - {e}' for e in errors)
        raise SpriteKilnError(f'the spec has errors (run `spritekiln validate` for all of them):{listed}')
    if warn:
        warnings = S.warnings_only(sp)
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
        f'OK: {s["name"]} - {s["parts"]} parts ({s["primitives"]} primitives, {s["cuts"]} cuts), {s["bones"]} bones, '
        f'{len(s["directions"])} directions, '
        'animations: ' + ', '.join(f'{k}({n})' for k, n in s['animations'].items())
    )
    return 0


def cmd_spec(a):
    """Read only what you edit: a map of the spec file, or the source lines of some blocks."""
    from . import outline

    if a.action == 'outline':
        if a.paths:
            raise SpriteKilnError('spec outline takes no paths (use `spec show SPEC PATH...`)')
        print(json.dumps(outline.outline(a.spec), indent=1) if a.json else outline.outline_text(a.spec))
    else:
        print(outline.show(a.spec, a.paths, a.resolved))


def _compile_note():
    """Say why the first frame takes a while when the numba renderer compiles (first run only)."""
    from . import backend

    note = backend.note()
    if 'compiling' in note:
        _note(note)


def cmd_pose(a):
    """Quick look: one pose in several directions, zoomed (cheap; use it while modelling)."""
    from . import api

    _spec(a.spec)
    _compile_note()
    t = time.time()
    out, dirs, view = api.pose(
        a.spec, a.anim, a.frame, a.dirs, a.scale, a.bg, a.tint, a.out, a.draft, crop=not a.no_crop, focus=a.focus
    )
    want = a.scale or (12 if a.focus else 4)
    zoom = f'; zoom {view["scale"]}' if view['scale'] != want else ''
    print(f'{out}  ({", ".join(dirs)}; {time.time() - t:.1f}s{zoom}{"; draft" if a.draft else ""})')


def cmd_render(a):
    from . import api, qa

    if a.draft and (a.godot is not None or a.export):
        raise SpriteKilnError('a draft render writes previews only and cannot be exported: drop --draft')
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
        draft=a.draft,
    )
    print(f'{res["frames"]} frames in {time.time() - t:.0f}s -> {res["dir"]}')
    if a.draft:
        print('draft previews (no atlas, JSON or QA): ' + ', '.join(res['contact_sheets'].values()))
        return
    print(qa.summary(res['qa']))
    print('review: ' + ', '.join(res['contact_sheets'].values()))
    if a.anims or a.dirs:
        _note('note: this atlas and JSON hold only the clips rendered now; run a full `render` before exporting')
    if a.godot is not None or a.export:
        engine = 'godot' if a.godot is not None else None
        w = api.export(a.spec, engine, res['dir'], project=a.godot or None, legacy=a.prog == 'pxforge')
        print(f'{w["engine"]}: {w.get("scene") or w["dir"]}')
        _warn_missing(w)


def cmd_export(a):
    from . import api

    _spec(a.spec)
    w = api.export(a.spec, a.engine, a.render_dir, a.to, a.project, a.lit, legacy=a.prog == 'pxforge')
    print(f'{w["engine"]}: {w["dir"]}')
    if w['engine'] == 'godot':
        print('  scene:', w['scene'])
        if w.get('addon_installed'):
            print('  addon installed (enable it in Project > Project Settings > Plugins if needed)')
    else:
        for f in w['files']:
            print('  ', f)
    _warn_missing(w)


def _warn_missing(w):
    if w.get('missing'):
        _note(f'warning: the render lacks {", ".join(w["missing"])} (made with --anims?); run a full `render` first')


def _look(a):
    """preview.viewer() from --bg / --tint, or None."""
    from . import preview

    bg = preview.load_background(a.bg) if getattr(a, 'bg', None) else None
    return preview.viewer(bg, preview.parse_tint(getattr(a, 'tint', None)))


def _note(msg):
    print(msg, file=sys.stderr, flush=True)


def _stale_note():
    from .update import stale_note

    note = stale_note()
    if note:
        _note('note: ' + note)


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
    _compile_note()
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

    ais = [x.strip() for x in a.ai.split(',') if x.strip()]
    res = init(a.dir, a.engine, ais, a.specs, a.export_dir, a.godot_project, not a.no_mcp, a.force, a.view)
    print(f'SpriteKiln project in {res["root"]} (engine: {res["engine"]}; AI: {", ".join(res["ais"])})')
    for p in res['written']:
        print('  ', os.path.relpath(p, res['root']))
    for n in res['notes']:
        print('note:', n)
    if res['style']:
        print('next: ask your AI assistant for a sprite (the recorded art style was kept: `spritekiln style`)')
    else:
        print(
            'next: open this folder in your AI assistant and ask for a sprite; before the first one it asks you '
            'a few questions\n      about the art style (by hand: spritekiln style set ..., then spritekiln new <name>)'
        )


def cmd_style(a):
    from . import style as S

    if a.spec and a.action != 'preview':
        raise SpriteKilnError(f'style {a.action}: only `style preview` takes a spec')
    if a.action == 'preview':
        from .api import style_preview

        out, rows = style_preview(a.spec, a.field, a.dir, a.anim, a.frame, a.zoom, a.out)
        print(f'style preview: {out}')
        for r in rows:
            names = [
                (('yes' if c else 'no') if isinstance(c, bool) else c) + (' *' if c == r['current'] else '')
                for c in r['choices']
            ]
            print(f'  {r["field"]:<11} ' + ', '.join(names))
        print('* = the current style; record a choice with `spritekiln style set --<field> <choice>`')
        return
    if a.action == 'set':
        answers = {k: getattr(a, k) for k in S.FIELDS}
        if all(v is None for v in answers.values()):
            raise SpriteKilnError('style set: give at least one answer (options: spritekiln style set -h)')
        res = S.record(answers)
        print(f'art style recorded in {res["file"]}:')
        for line in S.describe(res['style']):
            print(line)
        if res['defaulted']:
            print('not answered, so suggested or recommended values were kept for: ' + ', '.join(res['defaulted']))
        d = res['defaults']
        cam = d.get('camera', {})
        print(
            f'new specs get: view {d.get("view")}, size {d.get("size")}, palette {d.get("palette")}, '
            f'camera pitch {cam.get("pitch")} and scale {cam.get("scale")}'
        )
        _off_style(res)
        return
    res = S.status()
    if not res['recorded']:
        print(res['next'])
        s = res['suggested']
        print(f'Suggested from {s["source"]}: spritekiln style set {S.suggest_args(s)} (then the other answers)')
        return
    st = res['style']
    print(f'Art style of {res["project"]}, recorded {st.get("recorded")}.')
    print('Every asset follows it; it changes only when the user explicitly asks.')
    for line in S.describe(st):
        print(line)
    if res['guide']:
        print(f'what each answer means for a model or an animation: {res["guide"]}')
    _off_style(res)


def _off_style(res):
    off = res.get('off_style') or []
    if off:
        print(f'{len(off)} spec(s) do not match the style (update and re-render them if the user wants):')
        for o in off:
            diffs = ', '.join(f'{k} {have} (style: {want})' for k, (have, want) in o['differs'].items())
            print(f'  {o["spec"]}: {diffs}')


def cmd_update(a):
    import subprocess

    from . import config
    from . import update as U

    if a.files:
        _refreshed(U.refresh())
        return
    inst = U.installation()
    newest = U.latest()
    newer = U.version_key(newest) > U.version_key(__version__)
    print(f'SpriteKiln {__version__} (installed with {inst["kind"]}); the latest on PyPI is {newest}')
    if a.check:
        print('a new version is available: run `spritekiln update`' if newer else 'up to date')
        note = U.stale_note()
        if note:
            print('note:', note)
        return
    if newer:
        if inst['command'] is None:
            print(f'upgrade it with: {inst["display"]}')
            return 0 if inst['kind'] == 'source' else 1
        print('$ ' + ' '.join(inst['command']), flush=True)
        rc, now = U.upgrade(inst)
        if rc or not now or U.version_key(now) <= U.version_key(__version__):
            raise SpriteKilnError(
                f'the upgrade did not finish (exit code {rc}, installed: {now or "unknown"}); run it by hand: '
                f'{inst["display"]}'
            )
        print(f'SpriteKiln {__version__} -> {now}', flush=True)
    else:
        print('SpriteKiln is up to date')
    if not config.find():
        print('not inside a game folder: run `spritekiln update --files` in each project to refresh its AI files')
        return
    if newer:  # the new version writes its own files
        return subprocess.run([sys.executable, '-m', 'spritekiln', 'update', '--files']).returncode
    if U.stale_note():
        _refreshed(U.refresh())
    else:
        print("this project's AI files are up to date")


def _refreshed(res):
    print(f'AI files of {res["root"]} refreshed with SpriteKiln {__version__} (assistants: {", ".join(res["ais"])}):')
    for p in res['written']:
        print('  ', os.path.relpath(p, res['root']))
    if res['addon']:
        print(f'Godot addon {res["addon"]["was"]} -> {res["addon"]["now"]} in {res["addon"]["path"]}')
    print('spritekiln.toml, specs and renders were not touched')


def cmd_mcp(a):
    from .mcp_server import main

    main()


def cmd_palette(a):
    import numpy as np

    from . import palette as P

    if a.action == 'ramp':
        if a.steps < 2:
            raise SpriteKilnError('--steps: a ramp needs at least 2 colours')
        try:
            r = P.ramp(a.input, a.steps, a.hue_shift)
        except ValueError:
            raise SpriteKilnError(f'{a.input!r}: give a colour like "#5d4f6c"') from None
        print('[' + ', '.join(f'"{c}"' for c in r) + ']')
        return
    from .ref import cutout, load

    cut, mask, used = cutout(load(a.input))
    y = P.palette_yaml(P.families(P.extract(np.asarray(cut), mask, a.k)), a.steps)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
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
    from .godot import ADDONS, _find_project, export_godot, install_addon

    addon = 'pxforge' if a.prog == 'pxforge' else 'spritekiln'  # the old command keeps Hunt Tower's PxSprite2D
    if not a.spec and not a.install_addon:
        raise SpriteKilnError('give a spec (or use --install-addon alone)')
    project = _find_project(a.project, start=a.spec)
    if a.install_addon:
        install_addon(project, True, addon)
        print('addon installed ->', os.path.join(project, 'addons', addon))
        if not a.spec:
            return
    sp = _spec(a.spec)
    cfg = config.load(a.spec)
    dest = a.dest or (cfg.get('export_dir') if cfg.get('engine') == 'godot' else None) or ADDONS[addon][1]
    w = export_godot(sp, project, dest, lit=a.lit, update_addon=a.update_addon, render_dir=a.render_dir, addon=addon)
    print(f'{sp["name"]} -> {w["res"]}/')
    print('  scene:', w['scene'])
    print('  SpriteFrames:', w['frames'] + ('  (+ _lit, _canvas)' if 'lit' in w else ''))
    if 'emissive' in w:
        print('  emissive:', w['emissive'])
    if w['addon_installed']:
        print(
            '  addon installed in',
            os.path.join(project, 'addons', addon),
            '(enable it in Project > Project Settings > Plugins if needed)',
        )


def cmd_new(a):
    from . import api
    from .style import missing_note

    path = api.new(a.name, a.template, a.dir, a.ref, view=a.view, extends=a.extends)
    print('created', path)
    note = missing_note(path)
    if note:
        _note('note: ' + note)


def cmd_kits(a):
    from . import api

    res = api.kits(a.name)
    if a.name:
        k = res
        print(f'kit {k["name"]} ({k["origin"]}, {k["license"] or "no licence given"}): {k["summary"]}')
        print(f'  file: {k["file"]}')
        print(
            f'  attaches at {k["at"]} (`at:` in the use), shown on {k["host"]}; materials: {", ".join(k["materials"])}'
        )
        print(k['params_text'] or '  no params')
        if k['channels_text']:
            print(f'{k["channels_text"]}\n  (in a spec they are named {k["name"]}_<channel>, or <as>_<channel>)')
        print(f'use: [{{kit: {k["name"]}, as: {k["name"]}, at: {k["at"]}, with: {{...}}}}]')
        return
    w = max((len(k['name']) for k in res), default=0)
    for k in res:
        print(f'{k["name"]:<{w}}  {k["at"]:<8} {k["summary"]}' + (' (project)' if k['origin'] == 'project' else ''))
    print('`spritekiln kits <name>` shows its params; a spec adds one with use: [{kit: <name>, as: ..., at: ...}]')


DIRS = ['s', 'se', 'e', 'ne', 'n', 'nw', 'w', 'sw']


def _preview_args(s):
    s.add_argument('--bg', metavar='IMAGE', help='preview over this image (a game floor capture, tiled at 1 px = 1 px)')
    s.add_argument('--tint', metavar='LIGHT', help='scene light for previews: 0.7,0.7,1.0 or #b3b5ff (emissive stays)')
    _backend_arg(s)


def _backend_arg(s):
    s.add_argument(
        '--backend',
        choices=['auto', 'numpy', 'numba'],
        help='renderer: numba (spritekiln[fast], about 6x faster) or numpy; auto (default): numba if installed',
    )


def _positive(text):
    try:
        n = int(text)
    except ValueError:
        n = 0
    if n < 1:
        raise argparse.ArgumentTypeError(f'{text!r}: give a whole number of at least 1')
    return n


def build_parser(prog='spritekiln'):
    from .style import CHOICES as STYLE_CHOICES
    from .style import PREVIEW_FIELDS

    p = argparse.ArgumentParser(
        prog=prog, description='Procedural SDF models in YAML -> animated 8-direction pixel art'
    )
    p.add_argument('--version', action='version', version=f'{prog} {__version__}')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('validate', help='check a spec')
    s.add_argument('spec')
    s.add_argument('--strict', action='store_true', help='treat warnings (unknown keys, no version header) as errors')
    s.set_defaults(f=cmd_validate)

    s = sub.add_parser('spec', help='map of a spec file (outline), or the numbered lines of some blocks (show)')
    s.add_argument('action', choices=['outline', 'show'])
    s.add_argument('spec')
    s.add_argument('paths', nargs='*', help='show: block paths, e.g. parts.helm animations.walk.keys[2]')
    s.add_argument('--json', action='store_true', help='outline: as JSON')
    s.add_argument(
        '--resolved', action='store_true', help='show: the blocks as the renderer sees them (mirrored, defaults)'
    )
    s.set_defaults(f=cmd_spec)

    s = sub.add_parser('pose', help='quick preview of one pose (rest by default)')
    s.add_argument('spec')
    s.add_argument('--anim')
    s.add_argument('--frame', type=int, default=0)
    s.add_argument('--dirs', help='e.g. s,se,e or all')
    s.add_argument(
        '--scale',
        type=_positive,
        default=None,
        help='largest zoom of the preview PNG (default 4, 12 with --focus; lowered by whole steps to fit an AI '
        'image budget)',
    )
    s.add_argument(
        '--draft', action='store_true', help='one sample per pixel: about 6x faster, rougher edges (iterate with it)'
    )
    s.add_argument('--no-crop', action='store_true', help='show whole frames instead of cropping around the sprite')
    s.add_argument(
        '--focus',
        help='close-up of a bone and what hangs below it (head: the head, hair, eyes, headwear), or of parts by name',
    )
    _preview_args(s)
    s.add_argument('-o', '--out')
    s.set_defaults(f=cmd_pose)

    s = sub.add_parser('render', help='render animations and export atlas, JSON, GIFs and QA')
    s.add_argument('spec')
    s.add_argument('--anims', help='comma-separated (default: all)')
    s.add_argument('--dirs', help='comma-separated (default: all of the spec)')
    s.add_argument('-o', '--out')
    s.add_argument('--jobs', type=_positive, help='worker processes')
    s.add_argument('--force', action='store_true', help='ignore the render cache')
    s.add_argument('--size', type=_positive, help='frame size (32, 48, 64, 96, 128...), same framing')
    s.add_argument(
        '--godot',
        nargs='?',
        const='',
        metavar='PROJECT',
        help='after rendering, export to a Godot project (default: $SPRITEKILN_GODOT_PROJECT)',
    )
    s.add_argument('--export', action='store_true', help="after rendering, export to the project's engine")
    s.add_argument(
        '--draft',
        action='store_true',
        help='one sample per pixel, previews only (GIFs and contact sheets in preview-draft/; no atlas, JSON, QA)',
    )
    _preview_args(s)
    s.set_defaults(f=cmd_render)

    s = sub.add_parser('godot', help='export a rendered spec to a Godot 4 project (SpriteFrames + scene)')
    s.add_argument('spec', nargs='?')
    s.add_argument('--project', help='folder with project.godot (default: $SPRITEKILN_GODOT_PROJECT)')
    s.add_argument('--dest', help='folder inside the project (default: assets/spritekiln)')
    s.add_argument('--render-dir', help='render folder (default: <spec dir>/out/<name>; for renders made with -o)')
    s.add_argument('--lit', action='store_true', help='the scene uses the SpriteFrames with the normal map (Light2D)')
    s.add_argument('--install-addon', action='store_true', help='install/update addons/spritekiln in the project')
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
    s.add_argument('--scale', type=_positive, default=4, help='zoom of the sheets (default 4)')
    s.add_argument('--jobs', type=_positive)
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
    s.add_argument(
        '--force', action='store_true', help='rewrite an existing spritekiln.toml (a recorded art style is kept)'
    )
    s.add_argument(
        '--view',
        choices=['topdown', 'side'],
        help='default camera for new specs: top-down 3/4 (default) or side-scroller',
    )
    s.set_defaults(f=cmd_init)

    s = sub.add_parser('style', help="show or record the project's art style (asked before the first asset)")
    s.add_argument('action', nargs='?', default='show', choices=['show', 'set', 'preview'])
    s.add_argument('spec', nargs='?', help='preview: the spec to show (default: the humanoid template)')
    g = s.add_argument_group('answers (set)')
    g.add_argument('--view', choices=['topdown', 'side'], help='top-down 3/4 or side-scroller')
    g.add_argument('--height', type=_positive, help='px on screen of a human-sized character (sets camera.scale)')
    g.add_argument('--size', type=_positive, help='frame px for it (default: from --height)')
    g.add_argument('--scale', type=float, help='camera.scale directly (default: from --height)')
    g.add_argument('--directions', type=int, choices=[8, 4, 2], help='8 or 4 (top-down), 2 (side view)')
    g.add_argument('--mirror', choices=['yes', 'no'], help='render only right-facing directions; engines flip')
    g.add_argument('--palette', help='palette for new specs: built-in name, project palette or file')
    g.add_argument('--colors', help='the colour mood in a few words (e.g. "dark, desaturated")')
    g.add_argument('--outline', choices=STYLE_CHOICES['outline'], help='outer outline (applied by the renderer)')
    g.add_argument('--outline-color', help='the one outline colour of --outline dark (default: darkest ramp tone)')
    g.add_argument('--shading', choices=STYLE_CHOICES['shading'], help='soft (all tones), flat (2), toon (3, hard)')
    g.add_argument('--lines', choices=STYLE_CHOICES['lines'], help='inner lines: between parts, + folds, or none')
    g.add_argument('--highlights', choices=['yes', 'no'], help='material finishes add highlights')
    g.add_argument('--dither', choices=STYLE_CHOICES['dither'], help='ordered dither between tones')
    g.add_argument('--light', choices=STYLE_CHOICES['light'], help='light preset')
    g.add_argument('--proportions', choices=STYLE_CHOICES['proportions'])
    g.add_argument(
        '--face',
        choices=STYLE_CHOICES['face'],
        help='minimal (eyes only, no nose), simple (+ a brow or nose hint on big heads), detailed',
    )
    g.add_argument('--animation', choices=STYLE_CHOICES['animation'])
    g.add_argument('--snap', choices=['yes', 'no'], help='root and torso move in whole pixels (less boiling)')
    g.add_argument('--references', nargs='+', metavar='REF', help='games, artists or image paths to match')
    g.add_argument('--notes', help='anything else the style must respect')
    pg = s.add_argument_group('preview')
    pg.add_argument('--field', action='append', choices=PREVIEW_FIELDS, help='only these rows (repeatable)')
    pg.add_argument('--dir', default='se', choices=DIRS, help='direction (default se)')
    pg.add_argument('--anim', help='a pose of this animation instead of the rest pose')
    pg.add_argument('--frame', type=int, default=0)
    pg.add_argument('--zoom', type=_positive, default=4, help='largest zoom (default 4)')
    pg.add_argument('-o', '--out')
    s.set_defaults(f=cmd_style)

    s = sub.add_parser('update', help="upgrade SpriteKiln and refresh this project's AI files")
    s.add_argument('--check', action='store_true', help='only say whether a new version is available')
    s.add_argument(
        '--files', action='store_true', help="only rewrite this project's AI files with the installed version"
    )
    s.set_defaults(f=cmd_update)

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
    s.add_argument('--steps', type=_positive, default=6)
    s.add_argument('--hue-shift', type=float, default=22)
    s.add_argument('--k', type=_positive, default=10)
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
    s.add_argument('--k', type=_positive, default=10)
    s.add_argument('-o', '--out')
    _backend_arg(s)
    s.set_defaults(f=cmd_ref)

    s = sub.add_parser('new', help='create a spec from a template')
    s.add_argument('name')
    s.add_argument('--template', help='humanoid or side_humanoid (default: side_humanoid for a side view)')
    s.add_argument('--dir', help='parent folder (default: <specs of spritekiln.toml>/characters or specs/characters)')
    s.add_argument('--ref', help='splash art to copy next to the spec')
    s.add_argument(
        '--view', choices=['topdown', 'side'], help='camera preset (default: the project default or topdown)'
    )
    s.add_argument(
        '--extends', action='store_true', help='a short spec that extends the template instead of a copy of it'
    )
    s.set_defaults(f=cmd_new)

    s = sub.add_parser('kits', help="list the kits a spec can `use` (built-in and the project's), or one kit")
    s.add_argument('name', nargs='?', help='show this kit: its params with their comments')
    s.set_defaults(f=cmd_kits)

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
        if a.cmd not in ('init', 'update', 'mcp'):
            _stale_note()
        from . import backend

        backend.use(getattr(a, 'backend', None))
        rc = a.f(a)
    except SpriteKilnError as e:
        print(f'error: {e}', file=sys.stderr)
        rc = 1
    except OSError as e:  # a folder given as a file, a locked or missing path
        print(f'error: {e.filename or ""}: {e.strerror or e}', file=sys.stderr)
        rc = 1
    except KeyboardInterrupt:
        print('interrupted', file=sys.stderr)
        rc = 130
    if rc:
        sys.exit(rc)


if __name__ == '__main__':
    main()
