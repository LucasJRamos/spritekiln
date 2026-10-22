# Roadmap do pxforge

Estado atual (v0.1): personagens e props por spec YAML → 8 direções, animação por expressão e pose a pose,
VFX de smear, normal map + emissive, export Aseprite/MonoGame, QA automático, fluxo splash art → modelo,
skills e agents (Opus), export para Godot 4 (`pxforge godot`: SpriteFrames + CanvasTexture + cena com PxSprite2D).

## 1. Cenários e tiles (próxima prioridade)
Mesmo motor, mesma câmera (pitch 38°, mesma luz), para que chão/paredes casem com os personagens.
- `kind: tile` com `grid: {w: 1.0, d: 1.0}`: a câmera é travada no tamanho do tile (ex. 32 px de largura
  = 1 unidade); render de 1 direção.
- **Tileset de chão por dual-grid (15/16 peças)**: o spec descreve o material A e B (ex. pedra / terra) e
  uma função de borda; o gerador renderiza as 16 combinações de cantos (máscara 4-bit) e monta a folha.
  Variações (3–4 por peça) com `noise(seed)` nas expressões para quebrar repetição.
- **Paredes modulares** (top-down 3/4 mostra topo + face): peças reta, canto interno, canto externo, fim,
  porta, com altura em unidades; face recebe a mesma luz.
- **Seamless**: renderizar com margem e recortar ao centro para que as bordas emendem; QA de emenda
  comparando bordas opostas.
- Export: atlas + JSON com regras de autotile para o MonoGame (Tiled .tsx opcional).

## 2. Props de cenário
Já funciona com `kind: prop` + `directions: 1` (ou 4/8 para props giráveis). Próximo: biblioteca de
specs base (tocha, caixão, estátua, porta, grade, lápide, candelabro, baú) e animações simples
(chama tremulando com `noise`, porta abrindo).

## 3. Efeitos (VFX)
- Primitivas de partícula: `burst` (n esferas emissivas com sementes), `ring` (torus que cresce),
  `trail` (cone ao longo de uma curva), `beam`.
- Animações de VFX independentes (impacto, magia, sangue, poeira dos passos) exportadas como atlas
  próprio com pivô, para o jogo instanciar em eventos (`hit`, `step_l`).
- Dithering ordenado opcional só para VFX translúcidos (fumaça, névoa).

## 4. Iluminação
- O normal map exportado (espaço de câmera) permite luz dinâmica 2D no MonoGame: shader simples
  `N·L` por luz pontual + emissive aditivo. Feito: `integrations/monogame/KilnLit.fx` + `examples/monogame`.
- Opção de render "albedo plano" (sem luz assada) para jogos com iluminação totalmente dinâmica.
- Luzes locais no spec (tocha do próprio personagem) via `light.points`.

## 5. Ferramenta / UX
- `pxforge watch`: re-renderiza o `pose` ao salvar o YAML (loop rápido para editar à mão).
- Visualizador HTML local (animação, direção, zoom, fundo, onion skin) lendo o JSON exportado.
- Velocidade: cache por parte e numba opcional (5–10×) para personagens de 128 px.
