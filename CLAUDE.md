# pxforge — instruções para o Claude

Toolkit para criar personagens, monstros e props originais em **pixel art animada em 8 direções**
(top-down 3/4, padrão 64x64) a partir de modelos 3D procedurais (SDF) descritos em YAML.
Operado com **Claude Opus** (agents em `.claude/agents/` usam `model: opus`).

## Como trabalhar aqui
- Para qualquer tarefa de asset, carregue a skill `pxforge` (e `pxforge-splash-to-model` quando houver
  splash art, `pxforge-animation` para animações). Formato completo: `.claude/skills/pxforge/SPEC.md`.
- Delegue: `character-modeler` (geometria/paleta), `animator` (animações), `pixel-art-director` (revisão,
  não edita). Para um personagem novo a partir de splash art: modeler → director → modeler (correções) →
  animator → director → render final.
- Sempre `python -m pxforge validate` depois de editar um spec e **olhe as imagens** geradas (Read no PNG)
  antes de afirmar que algo está bom.
- Itere com `pose` (barato). `render` completo só no fim (≈190 frames por personagem).
- Specs ficam em `specs/characters/<nome>/<nome>.yaml`; saídas em `specs/characters/<nome>/out/` (geradas,
  não editar à mão). Cache em `.kilncache/` (pode apagar; `spritekiln cache info|prune|clear`).
- Mantenha consistência entre assets do jogo: mesmo `camera.pitch` (38), mesma `light`, `camera.scale`
  proporcional ao tamanho de mundo, paletas em `specs/palettes/`.
- Código em `spritekiln/` (Python puro: numpy, pillow, pyyaml); `pxforge/` é só um shim de compatibilidade
  (`python -m pxforge` continua funcionando). Ao mudar o código, rode `.venv/Scripts/python.exe -m pytest`
  (unitários + golden images; veja `docs/LAUNCH.md`).

## Comandos
```
python -m pxforge validate|pose|render|review|ref|palette|new|godot|cache  (-h em cada um)
```
Use o Python do `.venv/` desta pasta (`.venv/Scripts/python.exe -m pxforge ...`).

## Godot (tower-hunt)
O jogo fica em `D:/GameProjects/tower-hunt` e chama o toolkit via `tools/px.cmd` de lá. `python -m pxforge
godot <spec>` (ou `render <spec> --godot`) exporta `out/<nome>/` para `<projeto>/assets/pxforge/<nome>/`
(SpriteFrames .tres, CanvasTexture com normal map, cena .tscn com PxSprite2D) e instala
`integrations/godot/addons/pxforge` no projeto. Projeto alvo: `--project` ou `$PXFORGE_GODOT_PROJECT`.
Código do exporter em `pxforge/godot.py`; runtime GDScript em `integrations/godot/addons/pxforge/`.
