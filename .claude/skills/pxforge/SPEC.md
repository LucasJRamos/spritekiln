# pxforge — referência do spec YAML

Um personagem/prop é **um arquivo YAML** (`specs/characters/<nome>/<nome>.yaml`). O toolkit lê o spec, monta um
esqueleto, gera geometria SDF (primitivas suaves), renderiza em câmera top-down 3/4 e converte para pixel art.

```
pxforge: 1
name: gargula            # nome dos arquivos exportados
kind: character          # character | prop
size: 64                 # pixels do frame (32/48/64/128); `render --size` re-escala sem editar
directions: 8            # 1 | 4 | 8 | [s, e, n, w]
palette: ../../palettes/gothic.yaml   # ou lista de arquivos
camera: {pitch: 38, scale: 0.050, center: [0, 1.0, 0]}   # scale = unidades de mundo por pixel
shadow: {rx: 13.5, ry: 4.5, alpha: 120}                  # elipse no chão (px); `shadow: null` desliga
light:  {dir: [-0.55, 1, 0.45], rim: [0.8, 0.35, -0.9], rim_strength: 0.45, ambient: 0.12}
brief: {...}             # texto livre: resumo, must_keep, simplify, referência (o toolkit ignora)
materials: {...}
channels: {...}
bones: {...}
ik: {...}
parts: {...}
animations: {...}
```

## Unidades e eixos
- Mundo em "metros de jogo": personagem humano ≈ 1.6–1.9 de altura. Chão em `y = 0`.
- **+Y para cima, +Z = frente do personagem** (direção `s` = olhando para a câmera), **+X = lado esquerdo do
  personagem** (aparece à direita da tela na direção `s`).
- Com `scale: 0.05`, 1 pixel = 0.05 unidade. Movimento de 1px de respiração ≈ 0.05 de `bob`.
- Direções: `s, se, e, ne, n, nw, w, sw` = yaw 0, 45, 90, 135, 180, -135, -90, -45 (graus). A luz é fixa
  no mundo e o modelo gira, então o sombreamento é coerente entre direções.

## Expressões
Qualquer número/vetor pode ser string com expressão: `"[0, 0.78 + bob, 0]"`, `"0.045*sin(p)"`.
- Listas viram vetores numpy (`[1,0,0] + [0,1,0]` soma).
- Variáveis: todos os canais, `p` (fase 0..2π no ciclo), `t` (0..1), `f` (frame), `n` (nº de frames),
  `yaw` (direção sendo renderizada, graus) e `dir` (`"s"`, `"se"`...) — valem em **todo lugar**, inclusive
  nos canais das animações: trapaceie por direção direto na key, como pixel artists fazem
  (`rifle_pitch: "-0.08 + -0.2*pulse(yaw, 0, 70)"`, `bob: "0.02*(dir == 'n')"`). O nº de frames não pode
  depender da direção.
- Funções: `sin cos tan abs min max sqrt clamp lerp/mix unit smoothstep pulse(x,c,w) pos(x)=max(0,x)
  neg(x) roty rotx rotz v(x,y,z) radians floor sign exp noise(x,seed)`, constantes `pi tau`, operador `@`.

## materials
```
materials:
  stone: {ramp: stone}                         # rampa da paleta; índice 0 = contorno
  wing:  {ramp: wing, two_sided: true}         # membranas finas: luz dos dois lados
  eye:   {ramp: eye, emissive: true, band: 3, glow: {color: "#ff5a1f", mix: 0.55, radius: 1}}
  mouth: {ramp: mouth, bands: [1, 2], line: false}
```
Campos: `ramp` (nome ou lista de hex), `emissive` (sem luz, sem contorno; usa `band`), `bands: [lo, hi]`
(faixa de índices usada pela luz), `line` (participa das linhas internas), `line_band` (cor da linha interna,
padrão 1), `outline` (contorno externo), `two_sided`, `glow`, `gamma` (curva luz→banda, padrão 1.05).

## channels
Valores animáveis com default. Escalares ou vetores. Tudo que a animação muda passa por aqui.
`root` (vetor) é especial: desloca o frame `root` (lunge, pulo) e a sombra o acompanha.

## Espelhamento `_L` / `_R`
Escreva **só o lado `_L` (x positivo)**. Todo bone/ik/part/canal cujo nome tem `_L` ganha um gêmeo `_R`
automático (renomeando `_L→_R` em tudo, inclusive expressões). No gêmeo, vetores locais têm x negado e
rotações Euler viram `(rx, -ry, -rz)`.
- **Canais `_R` usam a mesma convenção do `_L`**: x positivo = para fora do corpo. Pose simétrica =
  mesmos valores nos dois lados. Mão direita cruzando para o lado esquerdo = x negativo em `hand_R`.
- **Não use canais assimétricos globais (`twist`, `roll`, `head_yaw`) dentro de expressões de itens `_L`**
  — eles seriam espelhados. Ponha-os num bone central e faça o `_L` herdar dele (veja `legyaw`, `wingbase`).
- Para algo só de um lado (espada na mão direita), use um nome sem `_L`, ex. `sword` com `space: wrist_R`.

## bones
```
bones:
  torso_rot: {parent: root, pos: "[0, 0.78 + bob, 0]", rot: "[lean, twist, roll]"}
  pelvis:    {parent: torso_rot, scale: "[1/sqrt(squash), squash, 1/sqrt(squash)]"}
  head:      {parent: headbase, rot: "[head_pitch, head_yaw, 0]", scale: 1.3}
  sole_L:    {parent: footyaw, at: ankle_L, rot: "[pitch_foot_L, 0.15, 0]"}
```
- `pos` no espaço do pai; `rot` Euler em radianos `[x, y, z]` aplicado como Ry·Rz·Rx (yaw, roll, pitch).
- `scale` escalar ou vetor (squash & stretch). Raios das primitivas escalam junto.
- `inherit_rot: false` / `inherit_scale: false`: só a posição segue o pai.
- `at: <frame>`: a origem vem de outro frame (ex. pé posicionado no tornozelo do IK) e a rotação do `parent`.

## ik (2 ossos)
```
ik:
  arm_L: {start: shoulder_L, space: torso_rot, target: hand_L, lengths: [0.36, 0.36],
          pole: [0.5, -0.1, -1.0], pole_space: torso_rot, up: [0, 0, 1], joint: elbow_L, end: wrist_L}
```
Cria os frames `joint` e `end` (eixo z local = direção do antebraço). `target` é um ponto em `space`
(normalmente um canal). `pole` = para onde o cotovelo/joelho aponta. `up` (opcional) define o eixo y do frame
final — use `[0,0,1]` em braços que pendem na vertical.

## parts (geometria)
```
parts:
  torso:
    material: stone
    space: pelvis          # coordenadas das primitivas neste frame (padrão root)
    blend: 0.09            # união suave entre as primitivas da parte
    line: true             # linhas internas onde esta parte sobrepõe outra
    when: "smear_w > 0"    # parte condicional
    prims: [...]
    cut: [...]             # primitivas subtraídas (cut_blend)
```
Pontos podem ser `[x,y,z]` (no `space`), `"@frame"` (origem de um frame), `{at: frame, off: [x,y,z]}`
ou `{between: ["@a", "@b"], t: 0.45}`.

Primitivas (um item = um mapa de uma chave):
| tipo | campos |
|---|---|
| `sphere` | `c, r` |
| `ellipsoid` | `c, r:[rx,ry,rz], rot:[x,y,z]` ou `align: [p0, p1]` (eixo z de p0→p1) |
| `cone` | `a, b, r:[r1, r2]` (cápsula afunilada — membros, chifres, garras) |
| `chain` | `pts: [...], r: [...]` (sequência de cones — cauda, tentáculo, chifre curvo) |
| `box` | `c, half:[hx,hy,hz], rot, round` (lâminas, armaduras, props) |
| `cylinder` | `a, b, r, round` |
| `torus` | `c, R, r, rot` (anéis, auréolas, correntes) |
| `tri` | `a, b, c, th` |
| `membrane` | `hub, ring:[...], th, scallop:[idx...], scallop_depth, fill_root` (asas, capas, velas) |
| `arc` | `c, r, a0, a1, width, fade, dip, segments` — VFX de smear; use `materials: [tail, mid, core]` |

## animations
**Ciclo por expressão** (loops: idle, walk, run, voar):
```
idle:
  frames: 8
  ms: 130                    # ou lista por frame
  events: {0: step_l}        # vão para o JSON (gameplay)
  channels: {bob: "0.045*sin(p) - 0.01", tail: "0.7*sin(p)"}
```
**Pose a pose** (ataques, hit, morte): cada key = 1 frame; canais não citados voltam ao default
(`carry: true` herda da key anterior).
```
attack:
  loop: false
  keys:
    - {ms: 170, event: windup, set: {...}}          # antecipação segurada
    - {ms: 55, set: {..., smear_w: 0.11}}           # golpe rápido com smear
    - {ms: 120, set: {...}, tween: 1, ease: out}    # gera 1 frame interpolado até a próxima key
```

## sockets (pontos de encaixe)
```
sockets:
  muzzle_L: {bone: pistol_L, offset: [0, 0.042, 0.50], when: "gun < 0.5"}   # gêmeo muzzle_R automático
  hand_L: {bone: wrist_L}
  hit: {bone: hammer, offset: [0, 0, 0.6]}
```
`bone` = qualquer frame (bone, joint/end de IK, `root`); `offset` no espaço dele; `when` falso = `null` no
quadro. O JSON traz, por animação/direção/quadro, `[x, y, depth]`: px relativos ao pivô e profundidade
(> 0 na frente do corpo, < 0 atrás). No Godot: `get_socket(&"muzzle_R")`. Ponha o socket no centro do
efeito que o jogo vai criar (clarão, impacto), não na ponta da arma.

## timing (tempos-alvo)
```
timing: {shoot_r: {release: 2f, total: 7f}, attack: {hit: 150ms}}   # fps 60, tolerância 1 quadro
```
`validate` e o QA reprovam se o evento (ou o total do clip) cair fora do alvo. Um evento no frame i dispara
quando o frame i aparece (soma das durações anteriores). Opcional: `timing: {fps: 30, tolerance: 2, ...}`.

## review (metas de direção de arte)
```
review: {min_lstar: 20, tint: [0.68, 0.71, 1.02], background: floor.png, materials: {lining: {min_px: 30}}}
```
Viram avisos do QA; `review` (comando) mede tudo e gera folhas: L* (mediana/p90) sob a luz `tint`, contraste
com o chão, px por material e direção, bandas usadas, IoU com a splash corrigido para a câmera, comparação
com outro asset (`--against`).

## Saídas de `pxforge render`
`out/<nome>/`: `<nome>.png` (atlas: uma linha por animação×direção), `<nome>.json` (formato Aseprite +
bloco `spritekiln` — `pxforge` pelo comando antigo — com direções, yaw, pivô, câmera, durações, eventos e
sockets; ver `docs/format.md`), `<nome>_normal.png` (normal map em espaço de
câmera, para luz dinâmica), `<nome>_emissive.png`, `preview/<anim>_8dir.gif`, `preview/contact_<anim>.png`
(folha para revisão visual), `qa.json`. Cache em `.kilncache/` (use `--force` ou `spritekiln cache clear`).
