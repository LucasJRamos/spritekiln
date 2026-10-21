# pxforge

Modelos 3D procedurais (SDF) descritos em YAML → **pixel art animada em 8 direções** (top-down 3/4),
com paleta limitada com hue shift, contorno seletivo, linhas internas e limpeza de pixels. Feito para
ser operado por agentes do Claude (Opus) — veja `CLAUDE.md` e `.claude/`.

## Instalar
```
pip install -r requirements.txt        # numpy, pillow, pyyaml (opcional: rembg para splash arts)
```

## Usar
```
python -m pxforge validate specs/characters/gargula/gargula.yaml
python -m pxforge pose     specs/characters/gargula/gargula.yaml --dirs all
python -m pxforge render   specs/characters/gargula/gargula.yaml            # 8 dir × idle/walk/attack
python -m pxforge new      minha_heroina --ref caminho/splash.png
python -m pxforge ref prep specs/characters/minha_heroina/splash.png
python -m pxforge ref compare specs/characters/minha_heroina/minha_heroina.yaml specs/characters/minha_heroina/splash.png --dir se
```
Saídas em `specs/characters/<nome>/out/<nome>/`: atlas PNG, JSON (Aseprite + bloco pxforge), normal map,
emissive, GIFs, contact sheets e `qa.json`.

## Com o Claude Code (Opus)
Abra esta pasta no Claude Code e peça, por exemplo:
- "Crie o modelo desta splash art (anexo) e anime idle, walk e attack."
- "A gárgula está muito magra na vista ne; corrija e renderize de novo."
Skills: `pxforge`, `pxforge-splash-to-model`, `pxforge-animation`. Agentes: `character-modeler`, `animator`,
`pixel-art-director` (todos `model: opus`).

## Godot 4
```
python -m pxforge godot specs/characters/gargula/gargula.yaml --project D:/GameProjects/tower-hunt   # ou render ... --godot
```
Gera `assets/pxforge/<nome>/`: atlas + JSON, `<nome>.tres` (SpriteFrames, clips `<anim>_<dir>`, duração
exata por frame), `<nome>_lit.tres` (CanvasTexture + normal map para Light2D), `<nome>_emissive.tres` e
`<nome>.tscn` com o node `PxSprite2D` (`integrations/godot/addons/pxforge`, instalado automaticamente):
`play_anim`, `face(velocity)`, sinais `px_event(anim, evento)` e `px_finished(anim)`.

## MonoGame
`integrations/monogame/PxSprite.cs`: `PxSheet.Load(...)` + `PxAnimator` (8 direções a partir do vetor de
movimento, durações por frame, eventos `hit`/`step_l`...). Use `SamplerState.PointClamp`.

## Estrutura
```
pxforge/        sdf · expr · spec · rig · anim · render · pixelize · palette · ref · qa · export · pipeline · cli
specs/          palettes/ · templates/humanoid.yaml · characters/gargula · characters/cacador
.claude/        skills/ (pxforge, pxforge-splash-to-model, pxforge-animation) · agents/
docs/ROADMAP.md tiles, props, VFX, iluminação
legacy/         primeira versão (scripts da gárgula 4 direções), só referência
```

## License
Code, docs and integrations: [MIT](LICENSE). Example assets (gargoyle, cacador, props, the humanoid
template, the gothic/props palettes): [CC0 1.0](LICENSES/CC0-1.0.txt). Showcase assets (Templar and
Huntress from Hunt Tower: specs, splash arts, palettes, renders): © 2026 Lucas Ramos / PlayRPG, all
rights reserved, included for demonstration only ([terms](LICENSES/LicenseRef-Showcase.txt)).
[`REUSE.toml`](REUSE.toml) maps every path to its license.
