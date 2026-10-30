<p align="center">
  <img src="showcase/huntress/from_this_to_this.png" alt="총잡이의 스플래시 아트와 그 옆에 놓인 8방향 픽셀 아트 스프라이트" width="100%">
</p>

# SpriteKiln

[English](README.md) | [Português (BR)](README.pt-BR.md) | **한국어** | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

**절차적 3D 모델로 만드는 애니메이션 픽셀 아트 스프라이트. 코딩 AI가 다루도록 설계되었습니다.**

캐릭터는 작은 YAML 파일 하나입니다. 뼈대, 3D 도형, 재질, 애니메이션을 담습니다. SpriteKiln은 이를 8방향(탑다운
3/4) 또는 측면(사이드 뷰) 픽셀 아트로 렌더링합니다. 프레임별 정확한 지속 시간, 게임플레이 이벤트, 부착
지점(소켓), 동적 조명용 노멀 맵, 발광 레이어를 포함하며 Godot, Unity, MonoGame 또는 Aseprite 스프라이트 시트를
읽는 모든 엔진에서 바로 쓸 수 있습니다.

YAML을 직접 쓸 필요는 없습니다. 코딩 어시스턴트(Claude Code, Codex, Gemini, Copilot, Cursor)가 설명이나
스플래시 아트를 바탕으로 대신 씁니다. 스펙을 수정하고, 렌더링하고, **이미지를 직접 보고** 눈에 띄는 문제를
고칩니다. 여러분은 감독만 하면 됩니다.

<p align="center">
  <img src="showcase/thor/turnaround.gif" alt="망치를 든 폭풍의 신 Thor가 8방향으로 대기하는 모습" height="220">
  <img src="showcase/ranger/turnaround.gif" alt="기계 팔과 전투용 석궁을 갖춘 레인저가 8방향으로 대기하는 모습" height="220">
  <img src="showcase/rin-7/run.gif" alt="사이버펑크 결투가 RIN-7이 사이드 뷰에서 양쪽 방향으로 달리는 모습" height="220">
  <br>
  <sub>Thor(탑다운, 키 100 px) · 레인저(탑다운, 64 px) · RIN-7(사이드 뷰, 48 px): Claude Code가 스플래시 아트를 바탕으로 SpriteKiln으로 만들었습니다. <a href="#쇼케이스">아래에서 더 보기</a>.</sub>
</p>

## 왜 SpriteKiln인가
- **구조적으로 일관됨.** 모든 에셋이 하나의 카메라, 조명, 팔레트를 모든 방향과 프레임에서 공유합니다. 북동쪽
  걷기와 남서쪽 공격 사이에 어긋남이 생기지 않습니다.
- **수정이 저렴함.** "모자를 키워 줘", "공격 준비 동작을 느리게"는 300프레임을 다시 그리는 일이 아니라 한 줄
  수정입니다.
- **게임에 바로 사용.** 프레임별 지속 시간, 올바른 프레임의 이벤트(`hit`, `step_l`, `windup`), 소켓(총구, 손,
  타격 지점), Y 정렬을 위한 지면 피벗, 노멀 맵과 발광 맵.
- **AI를 위해 설계.** 모든 어시스턴트를 위한 하나의 지침 세트, 이미지를 반환하는 MCP 서버, 스펙용 JSON Schema,
  `file:line:column` 형식의 오류, 이미지를 볼 수 없는 어시스턴트를 위한 수치 기반 아트 디렉션 리뷰.
- **순수 Python, 모든 OS.** numpy, Pillow, PyYAML만 사용합니다. GPU도 Blender도 필요 없습니다. Windows, macOS,
  Linux에서 테스트되었습니다.

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
명령줄만 쓴다면 `pipx install spritekiln`으로 충분합니다. `"spritekiln[mcp,fast]"`를 대신 설치하면 렌더링이 약
6배 빨라집니다(컴파일된 렌더러이며, Intel Mac은 기존 렌더러를 그대로 사용합니다). uv, 가상 환경, 업그레이드,
문제 해결은 [SpriteKiln 설치](docs/tutorials/install.md)(영어)를 참고하세요.

### 업그레이드

| 사용 중인 버전 | 실행할 명령 |
|---|---|
| 0.2 이상 | 게임 폴더 하나에서 `spritekiln update`(설치했던 방식 그대로 업그레이드하고 그 폴더의 AI 지침을 갱신합니다), 이어서 나머지 게임 폴더에서 `spritekiln update --files` |
| 0.1.0 | `pipx upgrade spritekiln`(또는 `uv tool upgrade spritekiln`), 이어서 각 게임 폴더에서 `spritekiln update --files` |
| 모든 버전, 빠른 렌더러를 추가할 때 | `pipx install --force "spritekiln[mcp,fast]"`(또는 `uv tool install --force "spritekiln[mcp,fast]"`) |

Windows의 가상 환경에서는 `python -m spritekiln update`를 실행하세요. 새 버전으로 다시 렌더링한 에셋은 모습이
달라질 수 있습니다(0.3에서 음영이 바뀌었습니다). 바뀐 내용은 [변경 내역](CHANGELOG.md)에 있습니다.

## 빠른 시작

명령은 모든 OS에서 동일합니다.

### 1. 폴더 설정 (한 번만)

게임 폴더에서, 또는 스프라이트만 필요하다면 빈 폴더에서 터미널을 열고, 스프라이트를 사용할 엔진과 스프라이트를
만들 AI 어시스턴트를 SpriteKiln에 알려 주세요:

```
spritekiln init --engine godot --ai claude
```

| `--engine` | 대상 | 내보내기 위치 |
|---|---|---|
| `godot` | Godot 4 | `assets/spritekiln/` (SpriteFrames와 바로 쓸 수 있는 씬 포함) |
| `unity` | Unity 2022.3+ | `Assets/SpriteKiln/` |
| `monogame` | MonoGame | `Content/sprites/` |
| `generic` | 그 밖의 엔진, 또는 아직 게임이 없을 때 | `sprites/`: PNG 아틀라스와 Aseprite 호환 JSON |

| `--ai` | 어시스턴트 |
|---|---|
| `claude` | Claude Code |
| `codex` | Codex |
| `gemini` | Gemini CLI |
| `copilot` | GitHub Copilot |
| `cursor` | Cursor |
| `generic` | `AGENTS.md`를 읽는 그 밖의 에이전트 |

여러 어시스턴트는 쉼표로 구분합니다: `--ai claude,cursor`. `init`은 `spritekiln.toml`(스펙은 `art/specs/`,
내보내기는 위 폴더), 어시스턴트가 작업 전에 읽는 지침, 그리고 어시스턴트가 SpriteKiln을 호출하는 MCP 서버
설정을 만듭니다. 자세한 내용: [AI와 함께 SpriteKiln 사용하기](docs/tutorials/use-with-your-ai.md)(영어).

### 2. 어시스턴트에게 스프라이트 요청

어시스턴트에서 폴더를 열고 캐릭터를 설명하세요:

> 짧은 검을 든 두건 쓴 고블린 정찰병을 만들어 줘. 템플릿에서 시작하고, 8방향을 모두 확인한 다음 idle, walk,
> attack을 렌더링해서 내보내.

처음에는 무엇이든 만들기 전에 어시스턴트가 아트 스타일에 대해 인터뷰합니다: 탑다운 또는 측면 시점, 화면에서
캐릭터의 키가 몇 픽셀인지, 방향, 색, 외곽선과 음영, 비율, 얼굴을 얼마나 자세히 표현할지, 애니메이션의 느낌,
참고 자료. 답변은 `spritekiln.toml`에 저장되고(`spritekiln style`로 확인), 이후의 모든 스프라이트가 이를
따르며, 여러분이 요청할 때만 바뀝니다("이제부터 외곽선 없이").

그다음 어시스턴트가 스펙을 작성하고, 렌더링하고, 이미지를 보고 눈에 띄는 문제를 고칩니다. 여러분은
`art/specs/characters/<name>/out/<name>/preview/`의 GIF를 검토하고 수정을 요청하면 됩니다("모자를 더 크게",
"휘두르기를 더 빠르게"). 스플래시 아트가 있다면 넘겨주세요:
[AI와 함께 스플래시 아트에서 시작하기](docs/tutorials/splash-art.md)(영어).

### 3. 또는 직접 하기

어시스턴트가 실행하는 것과 같은 명령입니다:

```
spritekiln style set --height 48 --outline selective                 # 아트 스타일, 한 번만 (모든 답변: -h)
spritekiln new knight                                                # art/specs/characters/knight/knight.yaml
spritekiln pose art/specs/characters/knight/knight.yaml --dirs all   # 한 포즈를 8방향으로, 방향당 약 1초
spritekiln render art/specs/characters/knight/knight.yaml --export   # 모든 애니메이션을 렌더링해 엔진으로 내보내기
```

`pose`를 실행하는 사이사이에 YAML을 수정하세요. 자세한 과정은
[10분 만에 만드는 첫 캐릭터](docs/tutorials/first-character.md)(영어)에서 차근차근 안내합니다.

## 쇼케이스

<p align="center">
  <img src="showcase/rin-7/in_game.jpg" alt="비 내리는 네온 시장에서 경비원을 베는 RIN-7" width="100%">
  <br>
  <sub>Godot 테스트 씬 속 RIN-7과 경비원: SpriteKiln 스프라이트가 노멀 맵을 통해 네온 조명을 받습니다. 도시, 비, 참격의 빛은 씬에서 연출한 것입니다.</sub>
</p>

| RIN-7 · 사이드 뷰, 48 px | 레인저 · 탑다운, 64 px | Thor · 탑다운, 100 px |
|---|---|---|
| ![양쪽 측면에서 본 RIN-7의 2연속 베기](showcase/rin-7/attack.gif) | ![석궁을 쏘는 레인저](showcase/ranger/attack.gif) | ![Thor의 망치 내려치기](showcase/thor/ult_slam.gif) |
| 클립 7개(idle, run, jump, rise, fall, land, attack), 84프레임 | 8방향 클립 4개(idle, run, dash, attack), 288프레임 | 8방향 클립 13개, 696프레임(프레임 크기 128 px) |
| [스플래시 → 스프라이트](showcase/rin-7/from_this_to_this.png) | [스플래시 → 스프라이트](showcase/ranger/from_this_to_this.png) | [스플래시 → 스프라이트](showcase/thor/from_this_to_this.png) |

모두 [레시피](docs/agent/recipe.md)(모델러, 아트 디렉터, 애니메이터)를 따라 Claude Code가 만들었습니다.
RIN-7과 레인저는 0.3, Thor는 0.1의 테스트 프로젝트에서 나왔고, Templar와 Huntress는 게임 **Hunt Tower**용으로
제작되었습니다. 모든 캐릭터와 더 많은 애니메이션은 [`showcase/`](showcase)에서 볼 수 있습니다.

## 새로운 기능

**0.3** (2026-10-30)
- **더 선명한 형태:** 돌출·회전 프로파일, 튜브, 셸, 절단 덕분에 칼날, 판금, 모자 챙, 망토가 부푼 덩어리가
  아니라 날카로운 모서리를 갖습니다.
- **잘 읽히는 재질:** 하이라이트, 주름, 엣지 라이트를 갖춘 마감(금속, 소프트, 무광, 유광)과 띠, 리벳, 엠블럼을
  그리는 표면 페인트.
- **여러분의 스타일 그대로:** 렌더러가 프로젝트의 외곽선, 음영(소프트, 플랫, 툰), 내부 선, 디더링, 조명을 모든
  에셋에 적용합니다. `spritekiln style preview`로 선택지를 나란히 비교할 수 있습니다.
- **베이스와 키트:** `extends: humanoid`와 내장 키트 20종(무기, 방패, 모자류, 망토, 벨트, 머리와 헤어) 덕분에
  캐릭터에는 고유한 부분만 적으면 됩니다.
- **더 나은 첫 캐릭터:** 머리·헤어 키트, 스타일 인터뷰의 얼굴 관련 질문, `pose --focus head` 클로즈업.
- **더 빠른 속도:** 더 꼭 맞는 경계 덕분에 프레임이 1.5–3배 빨라졌고, `[fast]`로는 약 6배 더 빨라지며,
  `--draft` 미리보기도 생겼습니다.

**0.2** (2026-10-25)
- 첫 에셋을 만들기 전에 어시스턴트가 아트 스타일에 대해 인터뷰하고 그 내용을 `spritekiln.toml`에 기록합니다.
  이후의 모든 에셋이 이를 따릅니다.
- `spritekiln update`가 SpriteKiln을 업그레이드하고 게임 폴더의 AI 지침을 갱신합니다.

그 밖의 변경 사항: [CHANGELOG](CHANGELOG.md).

## 작동 방식

```
spec.yaml ──► 뼈대 + IK ─────► SDF 도형 ───► 레이마칭 렌더 ────► 픽셀화 ──► 아틀라스 + JSON
 (본,          (프레임별 수식:  (타원체,      (색, 노멀,          (팔레트 램프,      + 노멀 맵
  도형,         사이클, 키,      돌출,         깊이, 페인트;       외곽선, 선,       + 발광 맵
  키트,         이벤트)          회전,         3배 슈퍼샘플링,     프로젝트의        + GIF, QA
  애니메이션)                    튜브, 절단)   고정된 월드 조명)   스타일)           -> 여러분의 엔진
```

조명은 월드에 고정되고 모델이 회전하므로 모든 방향에서 음영이 일관됩니다. 렌더링할 때마다 QA 보고서(클리핑,
팔레트, 실루엣 안정성)와 검토용 컨택트 시트가 생성됩니다.

## 기능
- **아트 스타일:** 첫 에셋을 만들기 전에 어시스턴트가 시점, 화면상 크기, 방향, 색, 외곽선, 음영, 비율, 얼굴,
  애니메이션에 대해 묻습니다. 프로젝트가 답변을 보관하고, 렌더러가 그 스타일(외곽선, 소프트/플랫/툰 음영, 내부
  선, 하이라이트, 디더링, 조명)을 모든 에셋에 적용합니다. `spritekiln style preview`로 선택지를 나란히 비교할
  수 있습니다.
- **모델링:** 수식(`"0.045*sin(p)"`)으로 움직이는 본, 2본 IK, 좌우 대칭 `_L`/`_R` 파트, 선명한 형태를 만드는
  도형(돌출·회전 프로파일, 튜브, 셸, 평면 절단, 모따기·계단식 블렌드). 재질은 팔레트 램프와 마감(금속, 소프트,
  무광, 유광), 주름과 가장자리 하이라이트, 표면 페인트(새 지오메트리 없이 띠, 리벳, 십자 문양), 발광과 글로우,
  양면 막을 지원합니다.
- **베이스와 키트:** `extends: humanoid`와 파라미터를 받는 내장 키트 20종(무기, 방패, 모자류, 망토, 벨트,
  머리와 헤어) 덕분에 캐릭터에는 고유한 부분만 적으면 됩니다. 기사 예제는 약 20줄입니다.
- **애니메이션:** 수식이나 키프레임으로 만드는 사이클, 프레임별 타이밍, 트윈과 이징, 스미어, 방향별 보정,
  이벤트, `validate`가 검사하는 타이밍 목표(예: "300 ms에 타격").
- **시점:** 8방향(또는 4방향, 1방향) 탑다운 3/4, 또는 플랫포머용 사이드 뷰(`view: side`, run, jump, rise,
  fall, land가 들어 있는 템플릿 제공). 대칭 디자인은 `mirror: true`로 오른쪽을 향한 방향만
  렌더링합니다(나머지는 엔진이 뒤집습니다).
- **스플래시 아트에서:** `ref prep`이 캐릭터를 잘라 내고 팔레트를 추출합니다. `ref compare`는 실루엣을 모델과
  비교해 점수를 매기고(피치 보정 IoU) 무엇을 바꿀지 알려 줍니다.
- **리뷰:** `spritekiln review`는 명도 범위, 대비, 재질별 픽셀 수, 가독성을 측정하고, 게임 바닥(`--bg`) 위에서
  게임 조명(`--tint`)을 받은 스프라이트를 미리 보여 줍니다. `pose --focus head`는 얼굴을 가까이서 보여 줍니다.
- **속도:** 컴파일된 렌더러(`[fast]`, 약 6배 빠름), 초안 미리보기, 프레임을 다시 트레이싱하지 않고 조명만 다시
  입히는 렌더 캐시.
- **출력:** 아틀라스, 노멀 맵과 발광 맵, Aseprite 호환 JSON([형식](docs/format.md)), 프레임별 소켓, GIF와
  컨택트 시트.

## 엔진

| 엔진 | 제공 기능 | 가이드 |
|---|---|---|
| **Godot 4** | `KilnSprite2D` 노드, SpriteFrames, 바로 쓸 수 있는 씬. 에디터 플러그인이 끌어다 놓은 JSON으로 이를 만들어 줍니다 | [godot.md](docs/engines/godot.md) · [예제](examples/godot) |
| **Unity 2022.3+** | UPM 패키지: `.kiln` 임포터(스프라이트, 노멀 맵, AnimationClip)와 `KilnAnimator` | [unity.md](docs/engines/unity.md) |
| **MonoGame** | `KilnSprite.cs` 런타임과 노멀 맵 조명 셰이더 `KilnLit.fx` | [monogame.md](docs/engines/monogame.md) · [예제](examples/monogame) |
| **기타** | Aseprite 호환 JSON: Phaser, LÖVE, Defold, GameMaker... | [generic.md](docs/engines/generic.md) |

모든 런타임은 똑같이 재생합니다: 정확한 지속 시간, 해당 프레임에 맞춰 발생하는 이벤트, 소켓, 속도 벡터에 가장
가까운 방향, 미러링된 방향.

## AI 어시스턴트

| 어시스턴트 | `--ai` | 지침 | MCP 도구 |
|---|---|---|---|
| Claude Code | `claude` | `CLAUDE.md`, 스킬, 모델러 / 애니메이터 / 아트 디렉터 에이전트 | `.mcp.json` |
| Codex | `codex` | `AGENTS.md` | `~/.codex/config.toml`(직접 추가) |
| Gemini CLI | `gemini` | `GEMINI.md` | `.gemini/settings.json` |
| GitHub Copilot | `copilot` | `.github/copilot-instructions.md` | `.vscode/mcp.json` |
| Cursor | `cursor` | `.cursor/rules/spritekiln.mdc` | `.cursor/mcp.json` |
| 그 밖의 에이전트 | `generic` | `AGENTS.md` | |

`spritekiln init --ai claude,codex,...`는 하나의 원본([`docs/agent/`](docs/agent))에서 이 파일들을 생성합니다.
스플래시 아트로 새 캐릭터를 만드는 레시피: 모델러가 형태를 만들고, 아트 디렉터가 원본 아트와 비교해 검토하고,
모델러가 수정하고, 애니메이터가 애니메이션을 만들고, 디렉터가 다시
검토합니다([recipe.md](docs/agent/recipe.md)).

## 더 알아보기
튜토리얼과 레퍼런스 문서는 영어로 되어 있습니다.
- [SpriteKiln 설치](docs/tutorials/install.md)(Windows, macOS, Linux; pipx, uv 또는 가상 환경)
- [10분 만에 만드는 첫 캐릭터](docs/tutorials/first-character.md)
- [AI와 함께 스플래시 아트에서 시작하기](docs/tutorials/splash-art.md)
- [애니메이션과 이벤트](docs/tutorials/animations.md)
- [플랫포머 캐릭터(사이드 뷰)](docs/tutorials/platformer.md)
- [AI와 함께 SpriteKiln 사용하기](docs/tutorials/use-with-your-ai.md)(지침 파일과 MCP 도구)
- [스펙 레퍼런스](docs/agent/spec.md) · [출력 형식](docs/format.md) · [로드맵](docs/ROADMAP.md)
- [쇼케이스](showcase) · [기여 방법](CONTRIBUTING.md) · [변경 내역](CHANGELOG.md) · 번역:
  [English](README.md), [Português (BR)](README.pt-BR.md), [日本語](README.ja.md),
  [简体中文](README.zh-CN.md)

## 라이선스
코드, 문서, 통합: [MIT](LICENSE). 예제 에셋(가고일, 사냥꾼, 기사, Wren, 상자·가스등·훈련용 허수아비 소품,
템플릿과 키트, gothic 및 props 팔레트, 예제의 스프라이트): [CC0 1.0](LICENSES/CC0-1.0.txt). 쇼케이스
에셋(Hunt Tower의 Templar와 Huntress, Huntress의 지뢰: 스펙, 스플래시 아트, 팔레트, 렌더, 게임 캡처; RIN-7,
레인저, Thor: 스플래시 아트, 렌더, 캡처): © 2026 Lucas Ramos(Hunt Tower: Lucas Ramos / PlayRPG), 모든 권리
보유, 시연 목적으로만 포함([조건](LICENSES/LicenseRef-Showcase.txt)). [`REUSE.toml`](REUSE.toml)에 모든 경로의
라이선스가 정리되어 있습니다.
