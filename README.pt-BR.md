<p align="center">
  <img src="showcase/huntress/from_this_to_this.png" alt="A splash art de uma pistoleira ao lado do sprite em pixel art em 8 direções" width="100%">
</p>

# SpriteKiln

**Sprites animados em pixel art a partir de modelos 3D procedurais, feitos para serem operados por IAs de
programação.**

Um personagem é um arquivo YAML pequeno: esqueleto, formas 3D suaves, materiais e animações. O SpriteKiln
renderiza isso em pixel art em 8 direções (top-down 3/4) ou de perfil (visão lateral), com duração exata
por frame, eventos de gameplay, pontos de encaixe, normal map para luz dinâmica e camada emissiva, pronto
para Godot, Unity, MonoGame ou qualquer engine que leia folhas do Aseprite.

Você não precisa escrever o YAML. Seu assistente de programação (Claude Code, Codex, Gemini, Copilot,
Cursor) escreve, a partir de uma descrição ou de uma splash art: edita a spec, renderiza, **olha as
imagens** e corrige o que vê. Você dirige.

<p align="center">
  <img src="showcase/huntress/turnaround.gif" alt="A Caçadora em idle nas 8 direções" height="220">
  <img src="showcase/templar/turnaround.gif" alt="O Templário em idle nas 8 direções" height="220">
</p>

## Por quê
- **Consistente por construção.** Uma câmera, uma luz e uma paleta para todos os assets, em todas as
  direções e frames.
- **Barato de mudar.** "Aumenta o chapéu" ou "deixa o preparo do golpe mais lento" é uma linha, não 300
  frames redesenhados.
- **Pronto para o jogo.** Duração por frame, eventos (`hit`, `step_l`, `windup`) no frame certo, sockets
  (canos de arma, mãos, pontos de impacto), pivô no chão para ordenar por Y, normal map e emissivo.
- **Feito para IAs.** Um conjunto de instruções para qualquer assistente, servidor MCP cujas ferramentas
  devolvem imagens, JSON Schema da spec, erros com `arquivo:linha:coluna` e uma revisão de direção de arte
  em números para assistentes que não enxergam.
- **Python puro.** numpy, Pillow e PyYAML; sem GPU, sem Blender.

## Começo rápido

```
pip install spritekiln
spritekiln new cavaleiro                                       # specs/characters/cavaleiro/cavaleiro.yaml, do template
spritekiln render specs/characters/cavaleiro/cavaleiro.yaml   # atlas, JSON, mapas, GIFs -> .../out/cavaleiro/
```

Depois passe para o seu assistente: *"Transforme este cavaleiro num goblin batedor encapuzado com uma
espada curta. Confira as 8 direções antes de renderizar."* Veja
[Use o SpriteKiln com a sua IA](docs/tutorials/use-with-your-ai.md) (em inglês) para preparar um projeto de
jogo (`spritekiln init --engine godot --ai claude`).

## Como funciona

```
spec.yaml ──► esqueleto + IK ──► formas SDF ──► render por raymarch ──► pixelização ──► atlas + JSON
```

A luz é fixa no mundo e o modelo gira, então o sombreamento fica coerente entre as direções. Cada render
gera um relatório de QA e folhas de contato para revisar.

## Engines

| Engine | O que vem | Guia |
|---|---|---|
| **Godot 4** | node `KilnSprite2D`, SpriteFrames e cena pronta; plugin de editor que monta tudo a partir do JSON | [godot.md](docs/engines/godot.md) · [exemplo](examples/godot) |
| **Unity 2022.3+** | pacote UPM: importer `.kiln` (sprites, normal map, AnimationClips) e `KilnAnimator` | [unity.md](docs/engines/unity.md) |
| **MonoGame** | runtime `KilnSprite.cs` e shader de luz com normal map `KilnLit.fx` | [monogame.md](docs/engines/monogame.md) · [exemplo](examples/monogame) |
| **Outras** | JSON compatível com Aseprite: Phaser, LÖVE, Defold, GameMaker... | [generic.md](docs/engines/generic.md) |

## Assistentes de IA
`spritekiln init --ai claude,codex,gemini,copilot,cursor` escreve as instruções de cada um a partir de uma
fonte só ([`docs/agent/`](docs/agent)) e registra o servidor MCP (`spritekiln mcp`). A receita para um
personagem novo a partir de splash art: um modelador constrói a forma, um diretor de arte revisa contra a
arte, o modelador corrige, um animador anima e o diretor revisa de novo ([recipe.md](docs/agent/recipe.md)).

## Showcase
O Templário e a Caçadora foram feitos com o SpriteKiln para o jogo **Hunt Tower**, a partir das splash
arts, pelo Claude Code seguindo essa receita. Mais imagens, animações e capturas do jogo em
[`showcase/`](showcase).

## Saiba mais
A documentação completa está em inglês: [README](README.md), [primeiro personagem](docs/tutorials/first-character.md),
[a partir da sua splash art](docs/tutorials/splash-art.md), [animações e eventos](docs/tutorials/animations.md),
[personagem de plataforma](docs/tutorials/platformer.md), [referência da spec](docs/agent/spec.md),
[formato de saída](docs/format.md), [roadmap](docs/ROADMAP.md), [como contribuir](CONTRIBUTING.md).

## Licença
Código, documentação e integrações: [MIT](LICENSE). Assets de exemplo (a gárgula, o caçador, os props
caixotes, lampião a gás e boneco de treino, os templates, as paletas gothic e props, os sprites dos
exemplos): [CC0 1.0](LICENSES/CC0-1.0.txt). Assets do showcase (Templário e Caçadora do Hunt Tower, com a
mina da Caçadora: specs, splash arts, paletas, renders e capturas do jogo): © 2026 Lucas Ramos / PlayRPG,
todos os direitos reservados, incluídos só para demonstração ([termos](LICENSES/LicenseRef-Showcase.txt)).
