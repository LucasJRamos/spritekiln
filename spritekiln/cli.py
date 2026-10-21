"""pxforge command line.  Run `python -m pxforge -h`."""
import argparse
import json
import os
import shutil
import sys
import time

import numpy as np


def _spec(path):
    from . import spec as S
    try:
        return S.load(path)
    except Exception as e:  # noqa
        sys.exit(f'erro ao carregar spec: {e}')


def cmd_validate(a):
    from . import spec as S
    sp = _spec(a.spec)
    probs = S.validate(sp)
    if probs:
        print('INVÁLIDO:'); [print('  -', p) for p in probs]
        sys.exit(1)
    from .anim import frames_of
    print(f'OK: {sp["name"]} - {len(sp["parts"])} partes, {len(sp["bones"])} bones, '
          f'{len(sp["directions"])} direções, animações: ' +
          ', '.join(f'{k}({len(frames_of(sp, k))})' for k in sp['animations']))


def cmd_pose(a):
    """Quick look: one pose in several directions, zoomed (cheap; use it while modelling)."""
    from .pipeline import frame_image
    from .anim import frames_of
    from .rig import rest_env
    from .export import upscale
    sp = _spec(a.spec)
    env = frames_of(sp, a.anim)[a.frame][0] if a.anim else rest_env(sp)
    dirs = [d for d in sp['directions'] if not a.dirs or d[0] in a.dirs.split(',')]
    from . import spec as S
    if a.dirs == 'all' or (not a.dirs and len(sp['directions']) < 8 and sp['kind'] == 'character'):
        dirs = S.DIRECTIONS8
    t = time.time()
    imgs = [frame_image(sp, env, y, maps=False)[0] for _, y in dirs]
    out = a.out or os.path.join(sp['_dir'], 'out', f'pose_{a.anim or "rest"}_{a.frame}.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    upscale(np.concatenate(imgs, 1), a.scale).save(out)
    print(f'{out}  ({", ".join(d for d, _ in dirs)}; {time.time() - t:.1f}s)')


def cmd_render(a):
    from .pipeline import render_all
    from .export import export
    from . import qa
    if a.size:
        os.environ['PXFORGE_SIZE'] = str(a.size)
    t = time.time()
    sp, anims, dlist, out = render_all(os.path.abspath(a.spec), a.anims.split(',') if a.anims else None,
                                       a.dirs.split(',') if a.dirs else None, a.jobs, a.force)
    dst = a.out or os.path.join(sp['_dir'], 'out', sp['name'] + (f'_{a.size}' if a.size else ''))
    meta = export(sp, anims, dlist, out, dst)
    rep = qa.check(sp, anims, dlist, out)
    with open(os.path.join(dst, 'qa.json'), 'w', encoding='utf-8') as fh:
        json.dump(rep, fh, indent=1, ensure_ascii=False)
    print(f'{len(out)} frames em {time.time() - t:.0f}s -> {dst}')
    print(qa.summary(rep))
    print('revisão visual: ' + ', '.join(os.path.join(dst, 'preview', f'contact_{x}.png') for x in anims))
    if a.godot is not None:
        from .godot import export_godot, _find_project
        w = export_godot(sp, _find_project(a.godot or None), render_dir=dst)
        print(f'godot: {w["scene"]}')


def cmd_palette(a):
    from . import palette as P
    if a.action == 'ramp':
        r = P.ramp(a.input, a.steps, a.hue_shift)
        print('[' + ', '.join(f'"{c}"' for c in r) + ']')
        return
    from .ref import load, cutout
    img = load(a.input)
    cut, mask, used = cutout(img)
    fams = P.families(P.extract(np.asarray(cut), mask, a.k))
    y = P.palette_yaml(fams, a.steps)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(y); print('salvo', a.out)
    print(y)


def cmd_ref(a):
    from . import ref as R
    from . import palette as P
    if a.action == 'prep':
        img = R.load(a.image)
        cut, mask, used = R.cutout(img, tol=a.tol)
        dst = a.out or os.path.splitext(a.image)[0] + '_ref'
        os.makedirs(dst, exist_ok=True)
        cut.save(os.path.join(dst, 'cutout.png'))
        m = R.metrics(mask)
        fams = P.families(P.extract(np.asarray(cut), mask, a.k))
        open(os.path.join(dst, 'palette.yaml'), 'w', encoding='utf-8').write(P.palette_yaml(fams))
        info = dict(method=used, size=cut.size, metrics=m,
                    families=[dict(base=f['base'], share=round(f['share'], 3), neutral=f['neutral'],
                                   hue=round(f['hue'])) for f in fams])
        json.dump(info, open(os.path.join(dst, 'ref.json'), 'w'), indent=1)
        print(f'recorte ({used}) -> {dst}/cutout.png  | paleta -> {dst}/palette.yaml')
        print(f'aspecto altura/largura {m["aspect"]:.2f}; perfil de largura por faixa (topo->base): '
              + ' '.join(f'{v:.2f}' for v in m['width_profile']))
        if used == 'border':
            print('obs: fundo removido por cor de borda; confira cutout.png (se cortou errado use --tol, '
                  'uma PNG com transparência, ou instale rembg)')
        return
    # compare
    from .pipeline import frame_image
    from .anim import frames_of
    from .rig import rest_env
    from . import spec as S
    sp = _spec(a.spec)
    img = R.load(a.image)
    cut, mask, used = R.cutout(img, tol=a.tol)
    env = frames_of(sp, a.anim)[a.frame][0] if a.anim else rest_env(sp)
    lut = dict(S.DIRECTIONS8)
    spr = frame_image(sp, env, lut[a.dir], maps=False)[0]
    smask = spr[..., 3] == 255
    res, ga, gb = R.compare_masks(mask, smask)
    turn = [frame_image(sp, env, y, maps=False)[0] for _, y in S.DIRECTIONS8]
    cols = R.ref_palette(cut, mask)
    out = a.out or os.path.join(sp['_dir'], 'out', f'compare_{a.dir}.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    R.sheet(cut, spr, turn, (ga, gb), cols, sp['materials'], out, f'{sp["name"]} ({a.anim or "rest"})')
    json.dump(res, open(os.path.splitext(out)[0] + '.json', 'w'), indent=1, ensure_ascii=False)
    print(f'IoU silhueta ({a.dir}): {res["iou"]:.3f}   (>0.80 ótimo, 0.65-0.80 ok, <0.65 refazer proporções)')
    for h in res['hints'][:8]:
        print('  -', h)
    print('folha de comparação:', out)


def cmd_godot(a):
    from .godot import export_godot, _find_project, install_addon, DEFAULT_DEST
    project = _find_project(a.project)
    if a.install_addon:
        print('addon', 'atualizado' if install_addon(project, True) else 'instalado', '->',
              os.path.join(project, 'addons', 'pxforge'))
        if not a.spec:
            return
    if not a.spec:
        sys.exit('informe o spec (ou use --install-addon sozinho)')
    sp = _spec(a.spec)
    w = export_godot(sp, project, a.dest or DEFAULT_DEST, lit=a.lit, update_addon=a.update_addon)
    print(f'{sp["name"]} -> {w["res"]}/')
    print('  cena pronta:', w['scene'])
    print('  SpriteFrames:', w['frames'] + ('  (+ _lit, _canvas)' if 'lit' in w else ''))
    if 'emissive' in w:
        print('  emissivo:', w['emissive'])
    if w['addon_installed']:
        print('  addon instalado em', os.path.join(project, 'addons', 'pxforge'),
              '(ative em Projeto > Configurações > Plugins se ainda não estiver)')


def cmd_new(a):
    from . import resources
    tpl = resources.template(a.template)
    if not tpl:
        sys.exit(f'template não encontrado: {a.template} (disponíveis: {", ".join(resources.templates())})')
    dst_dir = os.path.join(a.dir, a.name)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f'{a.name}.yaml')
    if os.path.exists(dst):
        sys.exit(f'já existe: {dst}')
    txt = open(tpl, encoding='utf-8').read().replace('name: TEMPLATE', f'name: {a.name}')
    open(dst, 'w', encoding='utf-8').write(txt)
    if a.ref:
        shutil.copy(a.ref, os.path.join(dst_dir, 'splash' + os.path.splitext(a.ref)[1]))
    print('criado', dst)


def main(argv=None):
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding='utf-8', errors='replace')
        except Exception:  # noqa
            pass
    p = argparse.ArgumentParser(prog='pxforge', description='SDF 3D -> pixel art em 8 direções')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('validate', help='checa o spec YAML'); s.add_argument('spec'); s.set_defaults(f=cmd_validate)
    s = sub.add_parser('pose', help='preview rápido de uma pose (rest por padrão)')
    s.add_argument('spec'); s.add_argument('--anim'); s.add_argument('--frame', type=int, default=0)
    s.add_argument('--dirs', help='ex.: s,se,e ou all'); s.add_argument('--scale', type=int, default=4)
    s.add_argument('-o', '--out'); s.set_defaults(f=cmd_pose)
    s = sub.add_parser('render', help='renderiza animações + exporta atlas/JSON/GIF/QA')
    s.add_argument('spec'); s.add_argument('--anims'); s.add_argument('--dirs'); s.add_argument('-o', '--out')
    s.add_argument('--jobs', type=int); s.add_argument('--force', action='store_true')
    s.add_argument('--size', type=int, help='32/48/64/128: re-escala a câmera mantendo o enquadramento')
    s.add_argument('--godot', nargs='?', const='', metavar='PROJETO',
                   help='após renderizar, exporta para o projeto Godot (padrão: $PXFORGE_GODOT_PROJECT)')
    s.set_defaults(f=cmd_render)
    s = sub.add_parser('godot', help='exporta o render de um spec para um projeto Godot 4 (SpriteFrames + cena)')
    s.add_argument('spec', nargs='?'); s.add_argument('--project', help='pasta com project.godot (ou $PXFORGE_GODOT_PROJECT)')
    s.add_argument('--dest', help=f'pasta dentro do projeto (padrão: {"assets/pxforge"})')
    s.add_argument('--lit', action='store_true', help='cena usa o SpriteFrames com normal map (Light2D)')
    s.add_argument('--install-addon', action='store_true', help='instala/atualiza addons/pxforge no projeto')
    s.add_argument('--update-addon', action='store_true', help='sobrescreve o addon no projeto ao exportar')
    s.set_defaults(f=cmd_godot)
    s = sub.add_parser('palette', help='rampas com hue shift / extrair de imagem')
    s.add_argument('action', choices=['ramp', 'extract']); s.add_argument('input', help='cor base (#hex) ou imagem')
    s.add_argument('--steps', type=int, default=6); s.add_argument('--hue-shift', type=float, default=22)
    s.add_argument('--k', type=int, default=10); s.add_argument('-o', '--out'); s.set_defaults(f=cmd_palette)
    s = sub.add_parser('ref', help='splash art: preparar referência e comparar com o modelo')
    s.add_argument('action', choices=['prep', 'compare'])
    s.add_argument('a1', help='prep: imagem | compare: spec'); s.add_argument('a2', nargs='?', help='compare: imagem')
    s.add_argument('--dir', default='s', help='direção que a splash art mostra (s, se, e, ...)')
    s.add_argument('--anim'); s.add_argument('--frame', type=int, default=0); s.add_argument('--tol', type=float)
    s.add_argument('--k', type=int, default=10); s.add_argument('-o', '--out'); s.set_defaults(f=cmd_ref)
    s = sub.add_parser('new', help='cria um personagem a partir de um template')
    s.add_argument('name'); s.add_argument('--template', default='humanoid')
    s.add_argument('--dir', default=os.path.join('specs', 'characters')); s.add_argument('--ref', help='splash art')
    s.set_defaults(f=cmd_new)
    a = p.parse_args(argv)
    if a.cmd == 'ref':
        if a.action == 'prep':
            a.image = a.a1
        else:
            if not a.a2:
                p.error('ref compare SPEC IMAGEM')
            a.spec, a.image = a.a1, a.a2
    a.f(a)


if __name__ == '__main__':
    main()
