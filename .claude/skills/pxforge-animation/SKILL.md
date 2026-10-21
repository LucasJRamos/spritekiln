---
name: pxforge-animation
description: Escreve e ajusta animações pxforge (idle, walk, run, attack, hit, death, cast) com bons princípios de animação para pixel art 64px em 8 direções — timing por frame, antecipação, smear, squash/stretch, loops sem emenda e eventos de gameplay. Use ao criar ou melhorar qualquer animação de um spec pxforge.
---

# Animação no pxforge

Leia `../pxforge/SPEC.md` (seção animations). Animações só mexem em **canais**; se faltar um grau de
liberdade (ex. capa balançar), crie um canal novo, use-o numa expressão de bone/parte e anime-o.

## Escolha do modo
- **Ciclos** (idle, walk, run, hover): `frames` + `channels` com expressões em `p` (0..2π). Garantem loop
  perfeito se tudo for periódico em `p` (sin/cos de `p`, `2*p`...). Nunca use `t` em loops.
- **Ações** (attack, hit, death, cast, dash): `keys`, 1 key = 1 frame, `ms` por frame. Pose a pose.

## Contagem e timing (referência para 64 px)
| animação | frames | ms/frame |
|---|---|---|
| idle | 4–8 | 120–180 |
| walk | 8 | 90–110 |
| run | 6–8 | 70–90 |
| attack leve | 5–7 | antecipação 100–170, golpe 40–60, recuperação 100–130 |
| attack pesado | 7–10 | antecipação segurada 170–250 |
| hit | 3–4 | 60–90 |
| death | 6–10 | 90–140, último frame longo (400+) |

## Princípios aplicados aos canais
- **Antecipação**: 1–2 keys indo ao contrário do golpe (twist oposto, mão para trás, `squash` < 1,
  `bob` negativo). A key mais extrema é a mais longa.
- **Golpe**: 1 frame curto com `smear_*` (arc) e `squash` > 1 (stretch), `root` avançando (lunge).
  Em pixel art o frame de impacto vale mais que interpolação: não suavize o golpe com tweens.
- **Follow-through**: o corpo passa do ponto (twist além), smear desaparecendo (`smear_fade` 0.6–0.7),
  apêndices (cauda, capa, asas) atrasados em fase.
- **Overlap**: partes secundárias com a mesma frequência mas fase atrasada: `tail: "0.7*sin(p - 0.8)"`.
- **Amplitude em pixels**: com `camera.scale` s, 1 px = s unidades. Idle: 1–2 px (`bob` ≈ 0.05).
  Movimentos < 0.5 px piscam/tremem; > 3 px no idle parecem nervosos.
- **Walk**: pés em `[x, lift*pos(-sin(p)), z0 + stride*cos(p)]` (lado R com sinais invertidos), `bob`
  em `cos(2p)` (mais baixo nos contatos), `twist` ombros opostos aos quadris, braços opostos às pernas.
  Ciclo é in-place (o jogo move o personagem); o pé de apoio desliza para trás na tela, é o esperado.
- **Eventos**: marque `event: hit` no frame de impacto, `windup` na antecipação, `step_l/step_r` nos
  contatos — vão para o JSON e o `PxAnimator.OnEvent` do MonoGame.

## Checagem
1. `pose --anim <a> --frame <i> --dirs s,e,n,se` nos frames-chave antes de renderizar.
2. `render --anims <a>` → abra `preview/contact_<a>.png` (linhas = direções, colunas = frames) e o GIF.
3. QA: "emenda do loop" (último→primeiro salta) = canal não periódico; "frames idênticos" = key sem
   mudança; "cortado na borda" = gesto grande demais para o enquadramento.
4. Confira as **diagonais** e `n`: um golpe lindo em `s` pode sumir atrás do corpo em `n` — às vezes
   vale aumentar o arco do smear ou elevar a mão.
