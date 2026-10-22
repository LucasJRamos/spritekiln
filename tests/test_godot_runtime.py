"""The Godot addon running inside Godot (headless). Set SPRITEKILN_GODOT_BIN to a Godot 4 binary to run it."""

import json
import math
import os
import shutil
import subprocess

import pytest

from spritekiln import api
from spritekiln.godot import install_addon

from conftest import FIXTURES, stage_spec

GODOT = os.environ.get('SPRITEKILN_GODOT_BIN')
pytestmark = pytest.mark.skipif(not GODOT or not os.path.exists(GODOT), reason='set SPRITEKILN_GODOT_BIN')
MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')

CHECKS = r"""
extends SceneTree

var r := {}
var early
var t := 0
var tk := 0
var early_events := []


func _initialize() -> void:
	# 1. building from a raw render without the CLI
	var built := KilnBuilder.build("res://raw/minimal/minimal.json")
	r["built"] = built.keys()
	var sf: SpriteFrames = load(built["frames"])
	var loops := sf.get_animation_loop(&"attack_s")
	r["built_idle_s"] = [sf.get_frame_count(&"idle_s"), sf.get_frame_duration(&"idle_s", 0), loops]
	# 2. play_anim() before the node enters the tree: frame-0 events fire once
	early = (load("res://assets/spritekiln/minimal/minimal.tscn") as PackedScene).instantiate()
	early.anim_event.connect(func(a, e): early_events.append("%s:%s" % [a, e]))
	early.play_anim(&"attack", true)
	root.add_child(early)
	# 3. mirrored directions (spec with mirror: true)
	var m = (load("res://assets/spritekiln/mirrored/mirrored.tscn") as PackedScene).instantiate()
	root.add_child(m)
	m.play_anim(&"idle", true)
	m.set_facing(&"e")
	var east = m.get_socket(&"staff_tip")
	r["mirror_dirs"] = m.direction_names()
	m.set_facing(&"w")
	r["mirror_w"] = [m.clip_name(), m.flip_h, m.offset.x]
	var west = m.get_socket(&"staff_tip")
	r["mirror_socket_x"] = [east.x, west.x, east.y == west.y]
	m.face(Vector2(-1, 0))
	r["face_left"] = m.facing
	# 4. timing contract: stepped by hand at 60 fps, an event lands on the first tick that reaches its frame
	var timed = (load("res://assets/spritekiln/minimal/minimal.tscn") as PackedScene).instantiate()
	root.add_child(timed)
	timed.set_process(false)
	var ticks := []
	timed.anim_event.connect(func(a, e): ticks.append("%s@%d" % [e, tk]))
	timed.anim_finished.connect(func(a): ticks.append("finished@%d" % tk))
	timed.play_anim(&"attack", true)
	for i in 60:
		tk += 1
		timed.advance(1.0 / 60.0)
	r["ticks"] = ticks
	r["after_finish"] = [timed.is_playing(), timed.frame]
	timed.set_facing(&"nope")
	r["bad_facing"] = timed.facing
	# 5. a side-view sprite starts in its own direction
	var side = (load("res://assets/spritekiln/minimal_side/minimal_side.tscn") as PackedScene).instantiate()
	root.add_child(side)
	r["side"] = [side.facing, side.animation, side.direction_names()]


func _process(_d: float) -> bool:
	t += 1
	if t == 5:
		r["early_events"] = early_events
		r["early_playing"] = [early.is_playing(), early.animation]
		print("PXRESULT " + JSON.stringify(r))
		return true
	return false
"""


def test_addon_in_godot(tmp_path):
    game = tmp_path / 'game'
    game.mkdir()
    (game / 'project.godot').write_text('config_version=5\n\n[application]\n\nconfig/name="kiln"\n', encoding='utf-8')
    specs = []
    for name, extra in (('minimal', ''), ('mirrored', 'mirror: true\n'), ('minimal_side', None)):
        text = open(MINIMAL, encoding='utf-8').read().replace('name: minimal', f'name: {name}')
        if extra is None:  # side view, letting the preset choose camera, directions and shadow
            text = text.replace('directions: 4\n', 'view: side\n').replace('camera: {pitch: 38, ', 'camera: {')
            text = text.replace('shadow: {rx: 7, ry: 2.5, alpha: 120}\n', '')
        else:
            text += extra
        p = tmp_path / 'specs' / 'characters' / name / f'{name}.yaml'
        p.parent.mkdir(parents=True)
        p.write_text(text, encoding='utf-8')
        specs.append(str(p))
    stage_spec(tmp_path, MINIMAL)  # shared palettes next to the specs
    for spec in specs:
        res = api.render(spec, ['idle', 'attack'], jobs=1)
        api.export(spec, 'godot', res['dir'], project=str(game))
    raw = game / 'raw' / 'minimal'
    raw.mkdir(parents=True)
    for f in os.listdir(os.path.join(os.path.dirname(specs[0]), 'out', 'minimal')):
        if f.endswith(('.png', '.json')) and f != 'qa.json':
            shutil.copy2(os.path.join(os.path.dirname(specs[0]), 'out', 'minimal', f), raw / f)
    install_addon(str(game), True)
    (game / 'checks.gd').write_text(CHECKS.lstrip(), encoding='utf-8')
    subprocess.run([GODOT, '--headless', '--path', str(game), '--import'], capture_output=True, timeout=300)
    out = subprocess.run(
        [GODOT, '--headless', '--path', str(game), '--script', 'res://checks.gd'],
        capture_output=True,
        text=True,
        timeout=300,
    )
    line = next((ln for ln in out.stdout.splitlines() if ln.startswith('PXRESULT ')), None)
    assert line, out.stdout[-2000:] + out.stderr[-2000:]
    r = json.loads(line[len('PXRESULT ') :])
    assert set(r['built']) == {'frames', 'canvas', 'lit', 'emissive', 'scene'}
    assert r['built_idle_s'] == [4, pytest.approx(0.15), False]  # 4 frames of 150 ms, attack does not loop
    # frame 0's event fired once (auto_play did not replay the clip); later frames may follow by now
    assert r['early_events'][0] == 'attack:windup' and r['early_events'].count('attack:windup') == 1
    assert r['early_playing'][1] == 'attack_s'
    assert r['mirror_dirs'] == ['s', 'e', 'n', 'w']
    assert r['mirror_w'][0] == 'idle_e' and r['mirror_w'][1] is True and r['mirror_w'][2] == -16
    east, west, same_y = r['mirror_socket_x']
    assert west == pytest.approx(-east) and same_y
    assert r['face_left'] == 'w'
    assert r['side'][0] == 'e' and r['side'][1] == 'idle_e' and r['side'][2] == ['e', 'w']
    clip = json.loads((game / 'assets' / 'spritekiln' / 'minimal' / 'minimal.json').read_text(encoding='utf-8'))
    clip = clip['spritekiln']['animations']['attack']['directions']['s']
    expected, start = [], 0
    for i, ms in enumerate(clip['durations']):
        tick = 0 if i == 0 else math.ceil(start * 60 / 1000 - 1e-6)
        expected += [f'{e}@{tick}' for e in clip['events'].get(str(i), [])]
        start += ms
    expected.append(f'finished@{math.ceil(start * 60 / 1000 - 1e-6)}')
    assert r['ticks'] == expected
    assert r['after_finish'] == [False, len(clip['durations']) - 1]  # stopped on the last frame
    assert r['bad_facing'] == 's'  # an unknown direction is ignored


EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'examples', 'godot')
DRIVE = r"""
extends SceneTree

var t := 0
var log := []


func _initialize() -> void:
	change_scene_to_file("res://main.tscn")


func _process(_d: float) -> bool:
	t += 1
	if t == 2:
		var sprite = current_scene.get_node("Player/Gargula")
		sprite.anim_event.connect(func(a, e): log.append("%s:%s" % [a, e]))
		sprite.anim_finished.connect(func(a): log.append("finished:%s" % a))
	if t == 5:
		Input.action_press(&"ui_right")
	if t == 60:
		Input.action_release(&"ui_right")
		Input.action_press(&"ui_accept")
	if t == 62:
		Input.action_release(&"ui_accept")
	if t == 130:
		var p = current_scene.get_node("Player")
		var s = p.get_node("Gargula")
		log.append("x>0:%s facing:%s anim:%s" % [p.position.x > 0, s.facing, s.anim])
		print("PXRESULT " + JSON.stringify(log))
		return true
	return false
"""


def test_example_project_runs(tmp_path):
    game = tmp_path / 'example'
    shutil.copytree(EXAMPLE, game, ignore=shutil.ignore_patterns('.godot', '*.import', '*.uid'))
    (game / 'drive.gd').write_text(DRIVE.lstrip(), encoding='utf-8')
    subprocess.run([GODOT, '--headless', '--path', str(game), '--import'], capture_output=True, timeout=300)
    out = subprocess.run(
        [GODOT, '--headless', '--path', str(game), '--script', 'res://drive.gd', '--fixed-fps', '60'],
        capture_output=True,
        text=True,
        timeout=300,
    )
    line = next((ln for ln in out.stdout.splitlines() if ln.startswith('PXRESULT ')), None)
    assert line, out.stdout[-2000:] + out.stderr[-2000:]
    assert 'SCRIPT ERROR' not in out.stdout + out.stderr
    log = json.loads(line[len('PXRESULT ') :])
    # walk steps, then the attack's windup, hit and end (845 ms = 51 ticks), back to idle facing east
    assert log[:2] == ['walk:step_l', 'walk:step_r']
    assert log[-4:] == ['attack:windup', 'attack:hit', 'finished:attack', 'x>0:true facing:e anim:idle']
