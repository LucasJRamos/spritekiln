---
name: pxforge
description: Cria e edita personagens, monstros e props em pixel art animada em 8 direções (top-down 3/4) com o toolkit pxforge (modelo 3D por SDF em YAML -> render -> pixel art). Use para qualquer pedido de sprite, animação, spritesheet, pose, direção, paleta ou ajuste visual de um asset deste projeto.
---

# pxforge — operar o toolkit

O pxforge transforma um **spec YAML** (esqueleto + primitivas SDF + materiais + animações) em pixel art
limpa: paleta limitada com hue shift, contorno seletivo, linhas internas, limpeza de pixels, 8 direções
coerentes (é o mesmo modelo 3D girado). Referência completa do formato: `SPEC.md` nesta pasta — leia
antes de editar um spec.

## Comandos (rodar na raiz do toolkit)
```
python -m pxforge validate <spec.yaml>                 # sempre depois de editar
python -m pxforge pose <spec.yaml> [--anim walk --frame 3] [--dirs all|s,se,e]   # preview barato
python -m pxforge render <spec.yaml> [--anims idle,walk] [--dirs s,e] [--size 48] [--jobs N]
python -m pxforge ref prep <splash.png>                # recorte, paleta e proporções da splash art
python -m pxforge ref compare <spec.yaml> <splash.png> --dir se   # IoU + dicas + folha de comparação
python -m pxforge palette ramp "#5d4f6c" --steps 6     # rampa com hue shift
python -m pxforge palette extract <img>                # paleta YAML a partir de imagem
python -m pxforge new <nome> [--template humanoid] [--ref splash.png]
```
`pose` custa ~1 s por direção; `render` completo de 3 animações × 8 direções ≈ 190 frames (minutos).
Itere com `pose` e só renderize tudo no fim.

## Loop de trabalho (sempre)
1. **Ler** o spec e o `brief:`. Se não há spec: `pxforge new` (template humanoide) ou parta de
   `specs/characters/gargula/gargula.yaml` para criaturas.
2. **Editar** pouco por vez (uma parte ou uma key).
3. `validate` → corrigir até OK (as mensagens dizem o caminho exato do erro).
4. `pose --dirs all` e **olhar a imagem** (Read no PNG). Conferir silhueta em s, e, n e uma diagonal.
5. Repetir 2–4. Para animação, `pose --anim X --frame i` nos frames-chave.
6. `render` → ler o resumo do QA e os `preview/contact_<anim>.png`. Erros de QA (sprite cortado, frame
   vazio) são bloqueantes. Para revisão crítica, chame o agente `pixel-art-director`.
7. Relatar ao usuário: o que mudou, caminhos dos GIFs/contact sheets, avisos de QA restantes.

## Regras de legibilidade a 64 px (top-down 3/4, pitch 38°)
- Cabeça grande (1.2–1.4×) e silhueta com 2–3 formas marcantes (chifres, asas, arma, capa). Detalhe
  menor que ~2 px (0.1 unidade com scale 0.05) some ou vira ruído.
- Partes finas: raio mínimo ≈ 0.025 com scale 0.05 (garras, lâminas); abaixo disso quebram.
- Cores: 1 rampa por material, 4–6 tons; poucos materiais (3–6). Emissivos (olhos, magia) são o acento.
- Coisas que se projetam para trás/para longe sobem na tela (perspectiva 3/4): cheque diagonais —
  peças finas vistas de lado viram "palitos"; ajuste o ângulo ou use `yaw` numa expressão para trapacear.
- Deixe ≥2 px de margem em todos os frames (QA avisa). Se cortar: aumente `camera.scale` (zoom out)
  ou reduza o gesto naquele frame.
- Não mexa no `pitch` da câmera de um personagem só: todos os assets do jogo devem compartilhar
  pitch, luz e escala (`camera.scale` igual entre personagens do mesmo tamanho de mundo).

## Onde ficam as coisas
```
pxforge/            código (sdf, rig, anim, render, pixelize, export, qa, ref, palette, cli)
specs/palettes/     paletas compartilhadas (gothic.yaml)
specs/templates/    humanoid.yaml
specs/characters/<nome>/<nome>.yaml  + out/ (gerado) + splash art de referência
integrations/monogame/PxSprite.cs     runtime para MonoGame (atlas + JSON + eventos)
```
Skills relacionadas: `pxforge-splash-to-model` (criar a partir de splash art), `pxforge-animation`
(animar). Agentes: `character-modeler`, `animator`, `pixel-art-director`.
