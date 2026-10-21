# addons/pxforge (Godot 4)

Instalado automaticamente por `pxforge godot <spec>` (ou `pxforge godot --install-addon`).
Ative em Projeto > Configurações do Projeto > Plugins.

## PxSprite2D (extends AnimatedSprite2D)
- `sheet: JSON` — `<nome>.json` do pxforge (pivô, direções, loop, eventos).
- `emissive_frames: SpriteFrames` — opcional, camada emissiva em blend aditivo (olhos, magia).
- `play_anim(&"walk", restart=false)` · `face(velocity)` · `set_facing(&"ne")` · `facing_vector()`
- sinais: `px_event(anim, event)` (hit, windup, step_l, step_r...) e `px_finished(anim)`.
- origem do node = ponto no chão sob o personagem (bom para `y_sort_enabled`).

Os clips do SpriteFrames chamam-se `<anim>_<dir>` (ex. `attack_ne`), com `speed = 1` e duração por
frame em segundos (ms do pxforge / 1000). `<nome>_lit.tres` usa CanvasTexture com normal map para
`PointLight2D`/`DirectionalLight2D`; troque `sprite_frames` por ele (ou exporte com `--lit`).
