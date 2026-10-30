<p align="center">
  <img src="showcase/huntress/from_this_to_this.png" alt="A splash art de uma pistoleira ao lado do sprite em pixel art em 8 direções" width="100%">
</p>

# SpriteKiln

[English](README.md) | **Português (BR)** | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

**Sprites animados em pixel art a partir de modelos 3D procedurais, feitos para serem operados por IAs de
programação.**

Um personagem é um arquivo YAML pequeno: esqueleto, formas 3D, materiais e animações. O SpriteKiln renderiza
isso em pixel art em 8 direções (top-down 3/4) ou de perfil (visão lateral), com duração exata por frame,
eventos de gameplay, pontos de encaixe, normal map para luz dinâmica e camada emissiva, pronto para Godot,
Unity, MonoGame ou qualquer engine que leia spritesheets do Aseprite.

Você não precisa escrever o YAML. Seu assistente de programação (Claude Code, Codex, Gemini, Copilot,
Cursor) escreve, a partir de uma descrição ou de uma splash art: edita a spec, renderiza, **olha as
imagens** e corrige o que vê. Você dirige.

<p align="center">
  <img src="showcase/thor/turnaround.gif" alt="Thor, um deus da tempestade com um martelo, em idle nas 8 direções" height="220">
  <img src="showcase/ranger/turnaround.gif" alt="Uma patrulheira com braços mecânicos e uma besta de guerra, em idle nas 8 direções" height="220">
  <img src="showcase/rin-7/run.gif" alt="RIN-7, uma duelista cyberpunk, correndo nos dois perfis da visão lateral" height="220">
  <br>
  <sub>Thor (top-down, 100 px de altura) · a Patrulheira (top-down, 64 px) · RIN-7 (visão lateral, 48 px): feitos pelo Claude Code com o SpriteKiln a partir de splash arts. <a href="#showcase">Mais abaixo</a>.</sub>
</p>

## Por quê
- **Consistente por construção.** Uma câmera, uma luz e uma paleta para todos os assets, em todas as
  direções e frames. A caminhada para nordeste não destoa do ataque para sudoeste.
- **Barato de mudar.** "Aumenta o chapéu" ou "deixa o preparo do golpe mais lento" é uma linha, não 300
  frames redesenhados.
- **Pronto para o jogo.** Duração por frame, eventos (`hit`, `step_l`, `windup`) no frame certo, sockets
  (canos de arma, mãos, pontos de impacto), pivô no chão para ordenar por Y, normal map e mapa emissivo.
- **Feito para IAs.** Um conjunto de instruções para qualquer assistente, servidor MCP cujas ferramentas
  devolvem imagens, JSON Schema da spec, erros com `arquivo:linha:coluna` e uma revisão de direção de arte
  em números para assistentes que não enxergam.
- **Python puro, em qualquer sistema.** numpy, Pillow e PyYAML; sem GPU, sem Blender. Testado em Windows,
  macOS e Linux.

## Instalação

Python 3.10 ou mais novo. Instale o comando `spritekiln` com o [pipx](https://pipx.pypa.io), que o deixa
isolado e no PATH:

**Windows** (PowerShell; ainda sem Python? `winget install Python.Python.3.13` e abra um terminal novo)

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install "spritekiln[mcp]"
```

**macOS** (Terminal, com o [Homebrew](https://brew.sh))

```bash
brew install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

**Linux** (Debian/Ubuntu; no Fedora `sudo dnf install pipx`, no Arch `sudo pacman -S python-pipx`)

```bash
sudo apt install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

Depois abra um terminal novo e confira com `spritekiln --version`. O `[mcp]` adiciona as ferramentas para
assistentes de IA; só para a linha de comando, `pipx install spritekiln` basta. Para renders cerca de 6×
mais rápidos, instale `"spritekiln[mcp,fast]"` em vez disso (um renderizador compilado; Macs com Intel
continuam com o comum). uv, ambiente virtual, atualização e solução de problemas:
[Instale o SpriteKiln](docs/tutorials/install.md) (em inglês).

### Atualização

| Sua versão | Rode |
|---|---|
| 0.2 ou posterior | `spritekiln update` numa pasta de jogo (atualiza do mesmo jeito que você instalou e renova as instruções de IA dessa pasta), depois `spritekiln update --files` nas suas outras pastas de jogo |
| 0.1.0 | `pipx upgrade spritekiln` (ou `uv tool upgrade spritekiln`), depois `spritekiln update --files` em cada pasta de jogo |
| qualquer uma, para adicionar o renderizador rápido | `pipx install --force "spritekiln[mcp,fast]"` (ou `uv tool install --force "spritekiln[mcp,fast]"`) |

Num ambiente virtual no Windows, rode `python -m spritekiln update`. Assets renderizados de novo numa versão
nova podem ficar diferentes (a 0.3 mudou o sombreamento): o [changelog](CHANGELOG.md) diz o que mudou.

## Início rápido

Os comandos são iguais em todos os sistemas.

### 1. Prepare a pasta (uma vez)

Abra um terminal na pasta do seu jogo, ou numa pasta vazia se você só quer os sprites, e diga ao SpriteKiln
para qual engine são os sprites e qual assistente de IA vai fazê-los:

```
spritekiln init --engine godot --ai claude
```

| `--engine` | Para | Os exports vão para |
|---|---|---|
| `godot` | Godot 4 | `assets/spritekiln/`, com SpriteFrames e uma cena pronta |
| `unity` | Unity 2022.3+ | `Assets/SpriteKiln/` |
| `monogame` | MonoGame | `Content/sprites/` |
| `generic` | qualquer outra engine, ou ainda sem jogo | `sprites/`: atlas PNG e JSON compatível com Aseprite |

| `--ai` | Assistente |
|---|---|
| `claude` | Claude Code |
| `codex` | Codex |
| `gemini` | Gemini CLI |
| `copilot` | GitHub Copilot |
| `cursor` | Cursor |
| `generic` | qualquer outro agente que leia o `AGENTS.md` |

Vários assistentes de uma vez, separados por vírgula: `--ai claude,cursor`. O `init` grava o
`spritekiln.toml` (as specs ficam em `art/specs/`, os exports na pasta acima), as instruções que o seu
assistente lê antes de começar e a configuração do servidor MCP pelo qual ele chama o SpriteKiln. Detalhes:
[Use o SpriteKiln com a sua IA](docs/tutorials/use-with-your-ai.md) (em inglês).

### 2. Peça um sprite ao seu assistente

Abra a pasta no seu assistente e descreva o personagem:

> Faça um goblin batedor encapuzado com uma espada curta. Comece pelo template, confira as 8 direções,
> depois renderize idle, walk e attack e exporte.

Na primeira vez, antes de fazer qualquer coisa, o assistente faz uma entrevista sobre o estilo de arte:
visão top-down ou lateral, quantos pixels de altura um personagem tem na tela, direções, cores, contorno e
sombreamento, proporções, quanto detalhe o rosto mostra, o ritmo da animação e as suas referências. As
respostas vão para o `spritekiln.toml` (`spritekiln style` mostra); todos os sprites seguintes seguem esse
estilo, que só muda quando você pede ("de agora em diante, sem contorno").

Depois ele escreve a spec, renderiza, olha as imagens e corrige o que vê. Você revisa os GIFs em
`art/specs/characters/<nome>/out/<nome>/preview/` e pede mudanças ("chapéu maior", "golpe mais rápido").
Tem uma splash art? Entregue a ele: [A partir da sua splash art, com uma IA](docs/tutorials/splash-art.md)
(em inglês).

### 3. Ou faça à mão

Os mesmos comandos que o assistente roda:

```
spritekiln style set --height 48 --outline selective                 # o estilo de arte, uma vez (todas as respostas: -h)
spritekiln new knight                                                # art/specs/characters/knight/knight.yaml
spritekiln pose art/specs/characters/knight/knight.yaml --dirs all   # uma pose nas 8 direções, ~1 s cada
spritekiln render art/specs/characters/knight/knight.yaml --export   # todas as animações, exportadas para a engine
```

Edite o YAML entre um `pose` e outro:
[Seu primeiro personagem em 10 minutos](docs/tutorials/first-character.md) (em inglês) mostra o passo a passo.

## Showcase

<p align="center">
  <img src="showcase/rin-7/in_game.jpg" alt="RIN-7 acertando um corte num segurança, num mercado de neon sob a chuva" width="100%">
  <br>
  <sub>RIN-7 e o segurança numa cena de teste no Godot: sprites do SpriteKiln iluminados pelo neon por meio dos seus normal maps. A cidade, a chuva e o brilho do corte são da cena.</sub>
</p>

| RIN-7 · visão lateral, 48 px | A Patrulheira · top-down, 64 px | Thor · top-down, 100 px |
|---|---|---|
| ![O corte duplo da RIN-7 nos dois perfis](showcase/rin-7/attack.gif) | ![A Patrulheira disparando a besta](showcase/ranger/attack.gif) | ![A martelada de Thor no chão](showcase/thor/ult_slam.gif) |
| 7 animações (idle, run, jump, rise, fall, land, attack), 84 frames | 4 animações em 8 direções (idle, run, dash, attack), 288 frames | 13 animações em 8 direções, 696 frames de 128 px |
| [splash → sprite](showcase/rin-7/from_this_to_this.png) | [splash → sprite](showcase/ranger/from_this_to_this.png) | [splash → sprite](showcase/thor/from_this_to_this.png) |

Feitos pelo Claude Code seguindo a [receita](docs/agent/recipe.md) (modelador, diretor de arte, animador).
A RIN-7 e a Patrulheira vêm de projetos de teste da 0.3, e Thor, de um da 0.1; o Templário e a Caçadora
foram feitos para o jogo **Hunt Tower**. Todos eles, com mais animações: [`showcase/`](showcase).

## Novidades

**0.3** (2026-10-30)
- **Formas mais nítidas:** perfis extrudados e de revolução, tubos, cascas e cortes dão bordas bem definidas
  a lâminas, placas, abas de chapéu e capas, em vez de bolhas infladas.
- **Materiais legíveis:** acabamentos (metal, soft, matte, glossy) com brilhos, vincos e luzes de borda, e
  pintura de superfície para faixas, rebites e emblemas.
- **Seu estilo, aplicado:** o renderizador aplica a todos os assets o contorno, o sombreamento
  (soft, flat, toon), as linhas internas, o dither e a luz do projeto; `spritekiln style preview` mostra
  as opções lado a lado.
- **Bases e kits:** `extends: humanoid` e 20 kits prontos (armas, escudos, chapéus e elmos, capas, cintos,
  cabeças e cabelos), para que um personagem declare só o que é dele.
- **Primeiros personagens melhores:** kits de cabeça e cabelo, uma pergunta sobre rostos na entrevista de
  estilo e vistas de perto com `pose --focus head`.
- **Mais rápido:** frames 1,5–3× mais rápidos com limites mais justos, cerca de 6× mais com `[fast]` e
  prévias com `--draft`.

**0.2** (2026-10-25)
- Antes do primeiro asset, o assistente faz uma entrevista sobre o estilo de arte e grava as respostas no
  `spritekiln.toml`; todos os assets seguintes seguem esse estilo.
- `spritekiln update` atualiza o SpriteKiln e renova as instruções de IA das suas pastas de jogo.

Todo o resto: [CHANGELOG](CHANGELOG.md).

## Como funciona

```
spec.yaml ──► esqueleto + IK ──► formas SDF ──► render por raymarch ──► pixelização ──► atlas + JSON
 (ossos,      (expressões por    (elipsoides,     (cor, normais,           (rampas de paleta,   + normal map
  formas,      frame: ciclos,     extrusões,       profundidade, pintura;   contornos, linhas,  + mapa emissivo
  kits,        keys, eventos)     revoluções,      supersampling 3x,        estilo do projeto)  + GIFs, QA
  animações)                      tubos, cortes)   luz fixa no mundo)                           -> sua engine
```

A luz é fixa no mundo e o modelo gira, então o sombreamento fica coerente entre as direções. Cada render
gera um relatório de QA (cortes na borda do frame, paleta, estabilidade da silhueta) e folhas de contato
para revisar.

## Recursos
- **Estilo de arte:** antes do primeiro asset, o assistente pergunta sobre visão, tamanho na tela, direções,
  cores, contorno, sombreamento, proporções, rostos e animação; o projeto guarda as respostas e o
  renderizador aplica o visual (contorno, sombreamento soft/flat/toon, linhas internas, brilhos, dither, luz)
  a todos os assets. `spritekiln style preview` mostra as opções lado a lado.
- **Modelagem:** ossos com expressões (`"0.045*sin(p)"`), IK de 2 ossos, peças espelhadas `_L`/`_R` e formas
  bem definidas: perfis extrudados e de revolução, tubos, cascas, cortes por plano, junções chanfradas e em
  degraus. Materiais com rampas de paleta e acabamentos (metal, soft, matte, glossy), vincos e brilhos de
  borda, pintura de superfície (faixas, rebites, cruzes sem geometria nova), emissivo e glow, membranas de
  dupla face.
- **Bases e kits:** `extends: humanoid` e 20 kits prontos (armas, escudos, chapéus e elmos, capas, cintos,
  cabeças e cabelos) com parâmetros, para que um personagem declare só o que é dele: o exemplo do cavaleiro
  tem cerca de 20 linhas.
- **Animação:** ciclos por expressões ou keyframes, com duração por frame, tweens e easing, smears, ajustes
  por direção, eventos e metas de timing conferidas pelo `validate` (ex.: "impacto aos 300 ms").
- **Visões:** top-down 3/4 em 8 (ou 4, ou 1) direções, ou visão lateral para jogos de plataforma
  (`view: side`, com um template que tem run, jump, rise, fall e land); `mirror: true` renderiza só as
  direções voltadas para a direita (a engine espelha o resto) em designs simétricos.
- **A partir de uma splash art:** `ref prep` recorta o personagem e extrai a paleta; `ref compare` pontua a
  silhueta contra o modelo (IoU corrigido pela inclinação da câmera) e diz o que mudar.
- **Revisão:** `spritekiln review` mede faixa de valores, contraste, pixels por material e legibilidade, e
  mostra o sprite sobre o chão do seu jogo (`--bg`) sob a luz do jogo (`--tint`); `pose --focus head`
  mostra um rosto de perto.
- **Velocidade:** um renderizador compilado (`[fast]`, cerca de 6× mais rápido), prévias em rascunho e um
  cache de render que reilumina um frame sem traçá-lo de novo.
- **Saída:** atlas, normal map e mapa emissivo, JSON compatível com Aseprite ([formato](docs/format.md)),
  sockets por frame, GIFs e folhas de contato.

## Engines

| Engine | O que vem | Guia |
|---|---|---|
| **Godot 4** | node `KilnSprite2D`, SpriteFrames e cena pronta; um plugin de editor monta tudo a partir de um JSON arrastado para o editor | [godot.md](docs/engines/godot.md) · [exemplo](examples/godot) |
| **Unity 2022.3+** | pacote UPM: importer `.kiln` (sprites, normal map, AnimationClips) e `KilnAnimator` | [unity.md](docs/engines/unity.md) |
| **MonoGame** | runtime `KilnSprite.cs` e shader de luz com normal map `KilnLit.fx` | [monogame.md](docs/engines/monogame.md) · [exemplo](examples/monogame) |
| **Outras** | JSON compatível com Aseprite: Phaser, LÖVE, Defold, GameMaker... | [generic.md](docs/engines/generic.md) |

Todos os runtimes reproduzem do mesmo jeito: durações exatas, eventos no frame a que pertencem, sockets, a
direção mais próxima de uma velocidade, direções espelhadas.

## Assistentes de IA

| Assistente | `--ai` | Instruções | Ferramentas MCP |
|---|---|---|---|
| Claude Code | `claude` | `CLAUDE.md`, skills e os agentes modelador / animador / diretor de arte | `.mcp.json` |
| Codex | `codex` | `AGENTS.md` | `~/.codex/config.toml` (adicionado à mão) |
| Gemini CLI | `gemini` | `GEMINI.md` | `.gemini/settings.json` |
| GitHub Copilot | `copilot` | `.github/copilot-instructions.md` | `.vscode/mcp.json` |
| Cursor | `cursor` | `.cursor/rules/spritekiln.mdc` | `.cursor/mcp.json` |
| Qualquer outro agente | `generic` | `AGENTS.md` | |

`spritekiln init --ai claude,codex,...` gera todos eles a partir de uma fonte só
([`docs/agent/`](docs/agent)). A receita para um personagem novo a partir de uma splash art: um modelador
constrói a forma, um diretor de arte compara com a arte, o modelador corrige, um animador anima e o diretor
revisa de novo ([recipe.md](docs/agent/recipe.md)).

## Saiba mais
- [Instale o SpriteKiln](docs/tutorials/install.md) (Windows, macOS, Linux; pipx, uv ou ambiente virtual)
- [Seu primeiro personagem em 10 minutos](docs/tutorials/first-character.md)
- [A partir da sua splash art, com uma IA](docs/tutorials/splash-art.md)
- [Animações e eventos](docs/tutorials/animations.md)
- [Um personagem de plataforma (visão lateral)](docs/tutorials/platformer.md)
- [Use o SpriteKiln com a sua IA](docs/tutorials/use-with-your-ai.md) (arquivos de instruções e ferramentas MCP)
- [Referência da spec](docs/agent/spec.md) · [Formato de saída](docs/format.md) · [Roadmap](docs/ROADMAP.md)
- [Showcase](showcase) · [Como contribuir](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · Traduções: [English](README.md), [한국어](README.ko.md), [日本語](README.ja.md),
  [简体中文](README.zh-CN.md)

## Licença
Código, documentação e integrações: [MIT](LICENSE). Assets de exemplo (a gárgula, o caçador, o cavaleiro, a
Wren, os props de caixotes, lampião a gás e boneco de treino, os templates e kits, as paletas gothic e props,
os sprites dos exemplos): [CC0 1.0](LICENSES/CC0-1.0.txt). Assets do showcase (Templário e Caçadora do
Hunt Tower, com a mina da Caçadora: specs, splash arts, paletas, renders e capturas do jogo; RIN-7, a
Patrulheira e Thor: splash arts, renders e capturas): © 2026 Lucas Ramos (Hunt Tower: Lucas Ramos / PlayRPG),
todos os direitos reservados, incluídos só para demonstração ([termos](LICENSES/LicenseRef-Showcase.txt)).
O [`REUSE.toml`](REUSE.toml) associa cada caminho à sua licença.
