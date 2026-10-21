---
name: pxforge-splash-to-model
description: Transforma uma splash art / concept art de personagem original em um modelo pxforge (spec YAML) fiel à arte e legível em pixel art 64px nas 8 direções. Use quando o usuário fornecer uma imagem de personagem e pedir o modelo, o sprite ou as animações dele.
---

# Splash art → modelo pxforge

Objetivo: capturar a **identidade** do personagem (silhueta, proporções, formas marcantes, paleta) — não
copiar pinceladas. A 64 px só sobrevive o que é grande e contrastado. Leia antes `../pxforge/SKILL.md` e
`../pxforge/SPEC.md`.

## 1. Preparar a referência
```
python -m pxforge new <nome> --ref <caminho/splash.png>          # cria specs/characters/<nome>/
python -m pxforge ref prep specs/characters/<nome>/splash.png     # -> splash_ref/cutout.png, palette.yaml, ref.json
```
- Abra (Read) a splash original **e** `cutout.png`. Se o recorte pegou fundo ou cortou partes, rode de novo
  com `--tol` (maior = mais agressivo), peça ao usuário uma PNG com transparência, ou instale `rembg`.
- Decida qual **direção** a arte mostra (frontal = `s`, 3/4 frontal = `se`/`sw`, perfil = `e`/`w`).

## 2. Escrever o brief (no topo do spec)
Antes de qualquer geometria, preencha `brief:` olhando a imagem:
```
brief:
  summary: uma frase de quem é e como se porta
  reference: splash.png (vista se)
  proportions: "cabeça = 1/4 da altura; ombros 1.6x a largura do quadril; pernas curtas"
  must_keep: [3-6 traços que identificam o personagem a distância]
  simplify: [o que vai sumir ou virar forma única a 64px]
  palette_notes: [materiais e cores dominantes]
```
Regra: no máximo 5–6 `must_keep`. Ornamentos pequenos viram uma mancha de cor ou somem. Exagere o que
é icônico (chapéu, arma, cabelo, capa) — em pixel art de 64 px o exagero é fidelidade.

## 3. Paleta
`splash_ref/palette.yaml` traz famílias de cor com rampas hue-shifted já prontas (`fam1`, `fam2`...).
Copie para `specs/palettes/<nome>.yaml`, **renomeie** as rampas (skin, cloth, hair, metal...), descarte
famílias de fundo/ruído e una famílias quase iguais. Ajuste manual com
`python -m pxforge palette ramp "#hex" --steps 5`. 3–6 materiais + 1 emissivo é o ideal.
No spec: `palette: [../../palettes/gothic.yaml, ../../palettes/<nome>.yaml]` (gothic traz fx_* e base).

## 4. Bloco de massas (blockout)
Parta do template (`humanoid.yaml`) ou de um spec parecido. Ordem:
1. **Escala do mundo**: altura total ≈ 1.6–2.0; ajuste `torso_rot.pos` (altura da pelve), comprimentos do IK.
2. **Massas grandes**: torso, cabeça (escala do bone `head`), quadril, pernas — só elipsoides/cones.
3. Rode `pose --dirs all` e `ref compare <spec> <splash> --dir <dir>`.
4. Itere até **IoU ≥ 0.70** na direção da arte e as dicas por faixa não apontarem desvios grandes.
   As dicas dizem em que altura o sprite está largo/estreito demais — corrija a parte daquela altura.
   Não persiga IoU acima de ~0.85: a splash tem perspectiva/pose própria; legibilidade vale mais.

## 5. Formas marcantes e materiais
Adicione um `must_keep` por vez (chifres = `chain`, capa = `membrane` ou cone aberto com `cut`, arma =
`box`/`cylinder` num frame de mão, cabelo = elipsoides com `blend`). Depois de cada um: `pose --dirs all`.
Cheque as **8 direções**, não só a da arte: o lado de trás e os perfis precisam fazer sentido. Invente o
que a splash não mostra de forma coerente com o design e registre a decisão no `brief`.

## 6. Comparação final e revisão
```
python -m pxforge ref compare <spec> <splash> --dir <dir>     # -> out/compare_<dir>.png
```
Abra a folha (referência | sprite | overlay de silhueta | 8 direções | paletas). Chame o agente
`pixel-art-director` com a folha + splash para uma crítica. Aplique as correções de prioridade alta.

## 7. Animar
Com o modelo aprovado, siga `pxforge-animation`. Personalidade da splash (pesado, ágil, arrogante)
deve aparecer no idle e no timing do ataque.

## Armadilhas
- Splash art com pose dinâmica (perna levantada, arma erguida): compare com um frame de animação
  parecido (`--anim attack --frame 2`) em vez da pose de repouso.
- Arte cortada (sem pés): o IoU fica inválido — compare só proporções da parte visível e avise.
- Personagem com arma maior que o corpo: deixe a arma fora do recorte de comparação (anote no brief) e
  confira margem no QA.
