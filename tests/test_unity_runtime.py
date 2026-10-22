"""The Unity package (integrations/unity) against Unity. Set SPRITEKILN_UNITY_BIN to a Unity 6 editor (Unity.exe):
the package then compiles against its assemblies (needs `dotnet`, no license) and, with an activated license that
allows batch mode, runs inside the editor (the first import of a fresh project takes a few minutes)."""

import json
import os
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from spritekiln import api

from conftest import FIXTURES, REPO, stage_spec

UNITY = os.environ.get('SPRITEKILN_UNITY_BIN')
pytestmark = pytest.mark.skipif(not UNITY or not os.path.exists(UNITY), reason='set SPRITEKILN_UNITY_BIN')
MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')

CHECKS = os.path.join(REPO, 'tests', 'unity', 'KilnChecks.cs')


CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.1</TargetFramework>
    <LangVersion>9.0</LangVersion>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="{pkg}/Runtime/*.cs" />
    <Compile Include="{pkg}/Editor/*.cs" />
    <Compile Include="{pkg}/Samples~/*/*.cs" />
    <Compile Include="KilnChecks.cs" />
    <Reference Include="{managed}/*.dll" Private="false" />
  </ItemGroup>
</Project>
"""


@pytest.mark.skipif(not shutil.which('dotnet'), reason='needs the .NET SDK')
def test_package_compiles_against_unity(tmp_path):
    managed = os.path.join(os.path.dirname(UNITY), 'Data', 'Managed', 'UnityEngine')
    pkg = os.path.join(REPO, 'integrations', 'unity')
    (tmp_path / 'check.csproj').write_text(CSPROJ.format(pkg=pkg, managed=managed), encoding='utf-8')
    shutil.copy(CHECKS, tmp_path / 'KilnChecks.cs')
    out = subprocess.run(['dotnet', 'build', '-nologo'], cwd=tmp_path, capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stdout[-4000:]


def make_project(root):
    """A Unity project with the package (by file: path), three exported renders and the checks."""
    work = root / 'work'
    game = root / 'game'
    (game / 'Assets' / 'Editor').mkdir(parents=True)
    (game / 'Packages').mkdir()
    pkg = os.path.join(REPO, 'integrations', 'unity').replace('\\', '/')
    manifest = {'dependencies': {'com.lucasjramos.spritekiln': f'file:{pkg}'}}
    (game / 'Packages' / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    shutil.copy(CHECKS, game / 'Assets' / 'Editor' / 'KilnChecks.cs')
    for name, extra in (('mirrored', 'mirror: true\n'), ('minimal_side', None)):
        text = open(MINIMAL, encoding='utf-8').read().replace('name: minimal', f'name: {name}')
        if extra is None:
            text = text.replace('directions: 4\n', 'view: side\n').replace('camera: {pitch: 38, ', 'camera: {')
            text = text.replace('shadow: {rx: 7, ry: 2.5, alpha: 120}\n', '')
        else:
            text += extra
        p = work / 'specs' / 'characters' / name / f'{name}.yaml'
        p.parent.mkdir(parents=True)
        p.write_text(text, encoding='utf-8')
        res = api.render(str(p), ['idle', 'attack'], jobs=1)
        api.export(str(p), 'unity', res['dir'], dest=str(game / 'Assets' / 'SpriteKiln'))
    stage_spec(work, MINIMAL)  # palettes
    return game


def test_package_in_unity(tmp_path):
    game = make_project(tmp_path)
    log = tmp_path / 'unity.log'
    subprocess.run(
        [
            UNITY,
            '-batchmode',
            *(['-force-d3d11'] if os.name == 'nt' else []),  # a GPU for the picture; batch mode defaults to none
            '-projectPath',
            str(game),
            '-executeMethod',
            'KilnChecks.Run',
            '-logFile',
            str(log),
        ],
        capture_output=True,
        timeout=1800,
    )
    result = game / 'kiln_result.json'
    text = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
    if not result.exists() and 'No valid Unity Editor license' in text:
        pytest.skip('Unity has no license for batch mode (sign in to Unity Hub)')
    assert result.exists(), text[-4000:]
    r = json.loads(result.read_text(encoding='utf-8'))
    assert 'exception' not in r, r['exception']
    assert r['sheet'] and r['emissive']
    assert r['directions'] == ['s', 'e', 'n', 'w>e']
    assert r['anims'] == ['idle', 'attack!']
    assert r['clips'] == sorted(f'{a}_{d}' for a in ('idle', 'attack') for d in 'senw')
    px, py, ex, ey = r['pivot']
    assert px == pytest.approx(ex) and py == pytest.approx(ey)
    assert r['ppu'] == 32 and r['secondary'] == 1 and r['filter'] == 'Point'
    assert r['clip_events'][0].endswith(':windup') and r['clip_loop'] == [False, True] and r['clip_w_flip'] == 1
    ev = r['events']
    # frame 0's event fires inside the call, once; the finish handler starts idle, whose frame 0 has step_l
    assert ev == ['attack:windup', 'after-play', 'attack:hit', 'finished:attack', 'idle:step_l']
    assert r['after'] == ['idle', 'True']
    flipped, flip_x, same_sprite, both, west_x, minus_east_x, dy, ddepth = r['mirror']
    assert flipped and flip_x and same_sprite and both
    assert west_x == pytest.approx(minus_east_x) and dy == pytest.approx(0) and ddepth == pytest.approx(0)
    assert r['face'] == ['w', 'n', 's', 'e']
    assert r['emissive_child']
    assert r['side'] == ['e', 'w'] and r['side_view'] == 'side'
    assert r['side_facing'] == ['e', 'w']
    # the listener's nested Play fires idle's frame 0 first; the windup still reports its own clip
    assert sorted(r['unity_event_names']) == ['attack:windup', 'idle:step_l']
    shot = game / 'kiln_shot.png'
    if shot.exists():  # the editor had a GPU: mirrored w is exactly e flipped around the pivot
        img = np.asarray(Image.open(shot).convert('RGBA'))
        cells = [img[:, 32 * i : 32 * i + 32] for i in range(4)]
        assert all(c[..., 3].any() for c in cells)
        assert np.array_equal(cells[3], cells[1][:, ::-1])
