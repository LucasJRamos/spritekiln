"""The MonoGame runtime (integrations/monogame) and example, built with the .NET SDK. Set SPRITEKILN_MONOGAME=1 to run
them (they restore MonoGame from NuGet; the example opens a window for a moment)."""

import json
import os
import subprocess

import pytest
from PIL import Image

from spritekiln import api

from conftest import FIXTURES, REPO, stage_spec

pytestmark = pytest.mark.skipif(not os.environ.get('SPRITEKILN_MONOGAME'), reason='set SPRITEKILN_MONOGAME=1')
MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')


def test_animator(tmp_path):
    stage_spec(tmp_path, MINIMAL)
    spec = tmp_path / 'specs' / 'characters' / 'mirrored' / 'mirrored.yaml'
    spec.parent.mkdir(parents=True)
    text = open(MINIMAL, encoding='utf-8').read().replace('name: minimal', 'name: mirrored')
    spec.write_text(text + 'mirror: true\n', encoding='utf-8')
    res = api.render(str(spec), ['idle', 'attack'], jobs=1)
    out = subprocess.run(
        ['dotnet', 'run', '--project', os.path.join(REPO, 'tests', 'monogame'), '--', res['json']],
        capture_output=True,
        text=True,
        timeout=600,
    )
    line = next((ln for ln in out.stdout.splitlines() if ln.startswith('PXRESULT ')), None)
    assert line, out.stdout[-3000:] + out.stderr[-3000:]
    r = json.loads(line[len('PXRESULT ') :])
    ev = r['events']
    # frame 0's event fires inside the call, once; the finish handler starts idle, whose frame 0 has step_l
    assert ev == ['attack:windup', 'after-play', 'attack:hit', 'finished:attack', 'idle:step_l']
    assert r['after'] == ['idle', 'False']
    assert r['directions'] == ['s', 'e', 'n', 'w>e']
    flipped, same_source, both, west_x, minus_east_x, dy, ddepth = r['mirror']
    assert flipped and same_source and both
    assert west_x == pytest.approx(minus_east_x) and dy == pytest.approx(0) and ddepth == pytest.approx(0)
    assert r['face'] == ['w', 'n', 's', 'e']


def test_example_runs(tmp_path):
    example = os.path.join(REPO, 'examples', 'monogame')
    build = subprocess.run(['dotnet', 'build', '-nologo', example], capture_output=True, text=True, timeout=900)
    assert build.returncode == 0, build.stdout[-3000:]
    exe = os.path.join(example, 'bin', 'Debug', 'net8.0', 'KilnDemo' + ('.exe' if os.name == 'nt' else ''))
    shot = tmp_path / 'shot.png'
    run = subprocess.run([exe, '--shot', str(shot)], capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    assert run.stdout.split() == [
        'event',
        'walk:step_l',
        'event',
        'walk:step_r',
        'event',
        'attack:windup',
        'event',
        'attack:hit',
    ]
    img = Image.open(shot)
    assert img.size == (320, 180) and len(img.getcolors(100000) or []) > 50  # the scene, not a blank frame
