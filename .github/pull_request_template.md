## What and why

## Checks
- [ ] `pytest` passes (and `pytest -m slow` if the renderer changed)
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] Goldens updated on purpose, with the reason in the commit message (or no visual change)
- [ ] Docs updated (`docs/agent/` sources regenerated with `python -m spritekiln.agents` if touched)
