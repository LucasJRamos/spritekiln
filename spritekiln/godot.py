"""Export `spritekiln render` output into a Godot 4 project.

For a spec whose render exists in `<spec dir>/out/<name>/`, writes to `<project>/<dest>/<name>/`:
  <name>.png, <name>_normal.png, <name>_emissive.png, <name>.json   (copied from the render)
  <name>.tres          SpriteFrames: one animation per "<anim>_<dir>", exact per-frame durations
  <name>_lit.tres      SpriteFrames whose atlas is a CanvasTexture (diffuse + normal) -> Light2D works
  <name>_canvas.tres   CanvasTexture (diffuse + normal map)
  <name>_emissive.tres SpriteFrames over the emissive atlas (only when the atlas is not empty)
  <name>.tscn          scene: PxSprite2D (addons/pxforge) already wired with frames + sheet JSON

Also installs/updates `addons/pxforge` in the project when missing (or with --update-addon).
"""
import json
import os
import shutil

from . import resources
from .errors import ExportError

ADDON_SRC = resources.data_dir('godot_addon')
DEFAULT_DEST = 'assets/pxforge'


def _q(s):
    """Godot resource string literal."""
    return json.dumps(str(s), ensure_ascii=False)


def _res(dest_res, *parts):
    return dest_res.rstrip('/') + '/' + '/'.join(parts)


def _find_project(explicit=None):
    p = explicit or os.environ.get('SPRITEKILN_GODOT_PROJECT') or os.environ.get('PXFORGE_GODOT_PROJECT')
    if not p:
        raise ExportError('no Godot project: use --project <folder> or set SPRITEKILN_GODOT_PROJECT')
    p = os.path.abspath(p)
    if not os.path.exists(os.path.join(p, 'project.godot')):
        raise ExportError(f'not a Godot project (no project.godot): {p}')
    return p


def install_addon(project, update=False):
    dst = os.path.join(project, 'addons', 'pxforge')
    if os.path.exists(dst) and not update:
        return False
    if not os.path.exists(ADDON_SRC):
        raise ExportError(f'Godot addon not found in {ADDON_SRC}')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(ADDON_SRC, dst, ignore=shutil.ignore_patterns('*.uid', '.godot'))
    return True


def _sprite_frames_tres(meta, atlas_res, atlas_type='Texture2D'):
    """Build a SpriteFrames .tres. speed = 1 fps so frame duration (s) = ms / 1000 exactly."""
    px = meta['pxforge']
    frames = meta['frames']
    regions = {}          # (x, y, w, h) -> sub id
    lines_sub = []
    anims_txt = []
    for a, A in px['animations'].items():
        loop = 'true' if A.get('loop', True) else 'false'
        for d, D in A['directions'].items():
            items = []
            for key, ms in zip(D['frames'], D['durations']):
                r = frames[key]['frame']
                rk = (r['x'], r['y'], r['w'], r['h'])
                if rk not in regions:
                    sid = f'AtlasTexture_{len(regions)}'
                    regions[rk] = sid
                    lines_sub.append(f'[sub_resource type="AtlasTexture" id="{sid}"]\n'
                                     f'atlas = ExtResource("1_atlas")\n'
                                     f'region = Rect2({rk[0]}, {rk[1]}, {rk[2]}, {rk[3]})\n')
                items.append('{\n"duration": %s,\n"texture": SubResource("%s")\n}' % (round(ms / 1000.0, 4), regions[rk]))
            anims_txt.append('{\n"frames": [%s],\n"loop": %s,\n"name": &"%s_%s",\n"speed": 1.0\n}'
                             % (', '.join(items), loop, a, d))
    head = (f'[gd_resource type="SpriteFrames" load_steps={len(regions) + 2} format=3]\n\n'
            f'[ext_resource type="{atlas_type}" path={_q(atlas_res)} id="1_atlas"]\n\n')
    return head + '\n'.join(lines_sub) + '\n[resource]\nanimations = [' + ', '.join(anims_txt) + ']\n'


def _canvas_texture_tres(diffuse_res, normal_res):
    return ('[gd_resource type="CanvasTexture" load_steps=3 format=3]\n\n'
            f'[ext_resource type="Texture2D" path={_q(diffuse_res)} id="1"]\n'
            f'[ext_resource type="Texture2D" path={_q(normal_res)} id="2"]\n\n'
            '[resource]\ndiffuse_texture = ExtResource("1")\nnormal_texture = ExtResource("2")\n')


def _scene_tscn(name, frames_res, json_res, emissive_res, pivot, first_anim):
    ext = [f'[ext_resource type="Script" path="res://addons/pxforge/px_sprite_2d.gd" id="1_script"]',
           f'[ext_resource type="SpriteFrames" path={_q(frames_res)} id="2_frames"]',
           f'[ext_resource type="JSON" path={_q(json_res)} id="3_sheet"]']
    if emissive_res:
        ext.append(f'[ext_resource type="SpriteFrames" path={_q(emissive_res)} id="4_emissive"]')
    body = [f'[node name="{name}" type="AnimatedSprite2D"]',
            'texture_filter = 1',
            'sprite_frames = ExtResource("2_frames")',
            f'animation = &"{first_anim}"',
            'centered = false',
            f'offset = Vector2({-round(pivot["x"])}, {-round(pivot["y"])})',
            'script = ExtResource("1_script")',
            'sheet = ExtResource("3_sheet")']
    if emissive_res:
        body.append('emissive_frames = ExtResource("4_emissive")')
    return (f'[gd_scene load_steps={len(ext) + 1} format=3]\n\n' + '\n'.join(ext) + '\n\n'
            + '\n'.join(body) + '\n')


def _write(path, text):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)


def _has_pixels(png):
    try:
        from PIL import Image
        import numpy as np
        return bool(np.asarray(Image.open(png).convert('RGBA'))[..., 3].any())
    except Exception:  # noqa
        return os.path.exists(png)


def export_godot(spec, project, dest=DEFAULT_DEST, lit=False, update_addon=False, render_dir=None):
    """spec: loaded spec dict (needs name/_dir). Returns dict with written paths."""
    name = spec['name']
    src = render_dir or os.path.join(spec['_dir'], 'out', name)
    jpath = os.path.join(src, f'{name}.json')
    if not os.path.exists(jpath):
        raise ExportError(f'render not found: {jpath}  (run `spritekiln render` first)')
    with open(jpath, encoding='utf-8') as fh:
        meta = json.load(fh)
    px = meta['pxforge']
    dest = dest.replace('\\', '/').strip('/')
    if dest.startswith('res://'):
        dest = dest[6:].strip('/')
    out_dir = os.path.join(project, *dest.split('/'), name)
    os.makedirs(out_dir, exist_ok=True)
    res = 'res://' + dest + '/' + name
    written = {}

    # 1. copy render products
    for f in (meta['meta']['image'], px.get('normal_map'), px.get('emissive_map'), f'{name}.json'):
        if f and os.path.exists(os.path.join(src, f)):
            shutil.copy2(os.path.join(src, f), os.path.join(out_dir, f))
            written[f] = os.path.join(out_dir, f)

    # 2. resources
    atlas_res = _res(res, meta['meta']['image'])
    frames_path = os.path.join(out_dir, f'{name}.tres')
    _write(frames_path, _sprite_frames_tres(meta, atlas_res))
    written['frames'] = frames_path

    lit_frames_res = None
    nm = px.get('normal_map')
    if nm and os.path.exists(os.path.join(out_dir, nm)):
        canvas_path = os.path.join(out_dir, f'{name}_canvas.tres')
        _write(canvas_path, _canvas_texture_tres(atlas_res, _res(res, nm)))
        lit_path = os.path.join(out_dir, f'{name}_lit.tres')
        lit_frames_res = _res(res, f'{name}_lit.tres')
        _write(lit_path, _sprite_frames_tres(meta, _res(res, f'{name}_canvas.tres'), 'CanvasTexture'))
        written['canvas'] = canvas_path; written['lit'] = lit_path

    emissive_res = None
    em = px.get('emissive_map')
    if em and os.path.exists(os.path.join(out_dir, em)) and _has_pixels(os.path.join(out_dir, em)):
        em_path = os.path.join(out_dir, f'{name}_emissive.tres')
        _write(em_path, _sprite_frames_tres(meta, _res(res, em)))
        emissive_res = _res(res, f'{name}_emissive.tres')
        written['emissive'] = em_path
    elif em and os.path.exists(os.path.join(out_dir, em)):
        os.remove(os.path.join(out_dir, em)); written.pop(em, None)

    # 3. scene
    anims = list(px['animations'])
    first = 'idle' if 'idle' in anims else anims[0]
    first_dir = px['directions'][0]
    scene_path = os.path.join(out_dir, f'{name}.tscn')
    frames_res = lit_frames_res if (lit and lit_frames_res) else _res(res, f'{name}.tres')
    _write(scene_path, _scene_tscn(name, frames_res, _res(res, f'{name}.json'), emissive_res, px['pivot'],
                                   f'{first}_{first_dir}'))
    written['scene'] = scene_path

    written['addon_installed'] = install_addon(project, update_addon)
    written['res'] = res
    return written
