<p align="center">
  <img src="showcase/huntress/from_this_to_this.png" alt="총잡이 캐릭터의 스플래시 아트와 8방향 픽셀 아트 스프라이트" width="100%">
</p>

# SpriteKiln

[English](README.md) | [Português (BR)](README.pt-BR.md) | **한국어** | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

**절차적 3D 모델로 만드는 애니메이션 픽셀 아트 스프라이트. 코딩 AI가 다루도록 설계되었습니다.**

캐릭터는 작은 YAML 파일 하나입니다. 뼈대, 부드러운 3D 도형, 재질, 애니메이션을 담습니다. SpriteKiln은
이를 8방향(탑다운 3/4) 또는 측면(사이드 뷰) 픽셀 아트로 렌더링합니다. 프레임별 정확한 지속 시간, 게임플레이
이벤트, 부착 지점(소켓), 동적 조명용 노멀 맵, 발광 레이어를 포함하며 Godot, Unity, MonoGame 또는 Aseprite
스프라이트 시트를 읽는 모든 엔진에서 바로 쓸 수 있습니다.

YAML을 직접 쓸 필요는 없습니다. 코딩 어시스턴트(Claude Code, Codex, Gemini, Copilot, Cursor)가 설명이나
스플래시 아트를 보고 스펙을 작성하고, 렌더링하고, **이미지를 직접 확인한 뒤** 보이는 문제를 고칩니다. 당신은
방향만 잡아 주면 됩니다.

<p align="center">
  <img src="showcase/huntress/turnaround.gif" alt="8방향으로 대기 중인 헌트리스" height="220">
  <img src="showcase/templar/turnaround.gif" alt="8방향으로 대기 중인 템플러" height="220">
  <img src="docs/images/tutorials/platformer-run.gif" alt="사이드 뷰 플랫포머 캐릭터 렌이 양쪽 방향으로 달리는 모습" height="220">
</p>

## 왜 SpriteKiln인가
- **구조적으로 일관됨.** 모든 에셋이 하나의 카메라, 조명, 팔레트를 모든 방향과 프레임에서 공유합니다.
- **수정이 저렴함.** "모자를 키워 줘", "공격 준비 동작을 느리게"는 300프레임을 다시 그리는 일이 아니라 한 줄
  수정입니다.
- **게임에 바로 사용.** 프레임별 지속 시간, 올바른 프레임의 이벤트(`hit`, `step_l`, `windup`), 소켓(총구, 손,
  타격 지점), Y 정렬을 위한 지면 피벗, 노멀 맵과 발광 맵.
- **AI를 위해 설계.** 모든 어시스턴트를 위한 하나의 지침 세트, 이미지를 반환하는 MCP 서버, 스펙용 JSON Schema,
  `파일:줄:열` 형식의 오류, 이미지를 볼 수 없는 어시스턴트를 위한 수치 기반 아트 디렉션 리뷰.
- **순수 Python, 모든 OS.** numpy, Pillow, PyYAML만 사용합니다. GPU도 Blender도 필요 없습니다. Windows,
  macOS, Linux에서 테스트되었습니다.

## 설치

Python 3.10 이상이 필요합니다. [pipx](https://pipx.pypa.io)로 `spritekiln` 명령을 설치하세요. 다른 패키지와
격리되고 PATH에 등록됩니다.

**Windows** (PowerShell. Python이 없다면 `winget install Python.Python.3.13` 후 새 터미널을 여세요)

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install "spritekiln[mcp]"
```

**macOS** (터미널, [Homebrew](https://brew.sh) 사용)

```bash
brew install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

**Linux** (Debian/Ubuntu 기준. Fedora: `sudo dnf install pipx`, Arch: `sudo pacman -S python-pipx`)

```bash
sudo apt install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

그다음 새 터미널을 열고 `spritekiln --version`으로 확인하세요. `[mcp]`는 AI 어시스턴트용 도구를 추가합니다.
명령줄만 쓴다면 `pipx install spritekiln`으로 충분합니다. uv, 가상 환경, 업그레이드, 문제 해결은
[Install SpriteKiln](docs/tutorials/install.md)(영어)을 참고하세요.

## 빠른 시작

모든 OS에서 동일합니다:

```
spritekiln new knight                                   # 템플릿에서 specs/characters/knight/knight.yaml 생성
spritekiln render specs/characters/knight/knight.yaml   # 아틀라스, JSON, 맵, GIF -> .../out/knight/
```

그다음 어시스턴트에게 맡기세요: *"이 기사를 짧은 검을 든 두건 쓴 고블린 정찰병으로 바꿔 줘. 렌더링 전에
8방향을 모두 확인해."* 게임 프로젝트를 설정하려면 프로젝트 폴더에서 `spritekiln init --engine godot --ai claude`를
실행하세요. 자세한 내용은 [Use SpriteKiln with your AI](docs/tutorials/use-with-your-ai.md)(영어)를 참고하세요.

## 작동 방식

```
spec.yaml ──► 뼈대 + IK ──► SDF 도형 ──► 레이마칭 렌더 ──► 픽셀화 ──► 아틀라스 + JSON
```

조명은 월드에 고정되고 모델이 회전하므로 모든 방향에서 음영이 일관됩니다. 렌더링할 때마다 QA 보고서와 검토용
컨택트 시트가 생성됩니다.

## 엔진

| 엔진 | 제공 기능 | 가이드 |
|---|---|---|
| **Godot 4** | `KilnSprite2D` 노드, SpriteFrames, 완성된 씬. 렌더 JSON에서 이를 만들어 주는 에디터 플러그인 | [godot.md](docs/engines/godot.md) · [예제](examples/godot) |
| **Unity 2022.3+** | UPM 패키지: `.kiln` 임포터(스프라이트, 노멀 맵, AnimationClip)와 `KilnAnimator` | [unity.md](docs/engines/unity.md) |
| **MonoGame** | `KilnSprite.cs` 런타임과 노멀 맵 조명 셰이더 `KilnLit.fx` | [monogame.md](docs/engines/monogame.md) · [예제](examples/monogame) |
| **기타** | Aseprite 호환 JSON: Phaser, LÖVE, Defold, GameMaker... | [generic.md](docs/engines/generic.md) |

## AI 어시스턴트
`spritekiln init --ai claude,codex,gemini,copilot,cursor`는 하나의 원본([`docs/agent/`](docs/agent))에서 각
어시스턴트용 지침을 생성하고 MCP 서버(`spritekiln mcp`)를 등록합니다. 스플래시 아트로 새 캐릭터를 만드는
레시피: 모델러가 형태를 만들고, 아트 디렉터가 원본 아트와 비교하고, 모델러가 수정하고, 애니메이터가 애니메이션을
만들고, 디렉터가 다시 검토합니다([recipe.md](docs/agent/recipe.md)).

## 쇼케이스
템플러와 헌트리스는 게임 **Hunt Tower**를 위해 스플래시 아트를 바탕으로, 위 레시피를 따르는 Claude Code가
SpriteKiln으로 만들었습니다. 더 많은 이미지, 애니메이션, 게임 캡처는 [`showcase/`](showcase)에 있습니다.

## 더 알아보기
전체 문서는 영어로 되어 있습니다: [README](README.md), [설치](docs/tutorials/install.md),
[첫 캐릭터](docs/tutorials/first-character.md),
[스플래시 아트에서 시작하기](docs/tutorials/splash-art.md), [애니메이션과 이벤트](docs/tutorials/animations.md),
[플랫포머 캐릭터](docs/tutorials/platformer.md), [스펙 레퍼런스](docs/agent/spec.md),
[출력 형식](docs/format.md), [로드맵](docs/ROADMAP.md), [기여 방법](CONTRIBUTING.md).

## 라이선스
코드, 문서, 통합: [MIT](LICENSE). 예제 에셋(가고일, 사냥꾼, 렌, 소품(상자, 가스등, 훈련용 허수아비), 템플릿,
gothic 및 props 팔레트, 예제 스프라이트): [CC0 1.0](LICENSES/CC0-1.0.txt). 쇼케이스 에셋(Hunt Tower의 템플러와
헌트리스, 헌트리스의 지뢰: 스펙, 스플래시 아트, 팔레트, 렌더, 게임 캡처): © 2026 Lucas Ramos / PlayRPG, 모든 권리
보유, 시연 목적으로만 포함([조건](LICENSES/LicenseRef-Showcase.txt)).
