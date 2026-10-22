<p align="center">
  <img src="showcase/huntress/from_this_to_this.png" alt="枪手角色的原画与8方向像素风精灵" width="100%">
</p>

# SpriteKiln

[English](README.md) | [Português (BR)](README.pt-BR.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | **简体中文**

**用程序化3D模型生成动画像素风精灵，专为编程AI驱动而设计。**

一个角色就是一个小小的YAML文件：骨骼、平滑的3D形状、材质和动画。SpriteKiln将其渲染为8方向（俯视3/4视角）或
侧视（横版）的像素画，带有逐帧精确时长、游戏事件、挂点（socket）、用于动态光照的法线贴图和自发光层，可直接用于
Godot、Unity、MonoGame，或任何能读取Aseprite精灵表的引擎。

你不需要亲手写YAML。你的编程助手（Claude Code、Codex、Gemini、Copilot、Cursor）会根据描述或原画编写规格文件、
渲染、**查看图像**，并修正它看到的问题。你只需把握方向。

<p align="center">
  <img src="showcase/huntress/turnaround.gif" alt="女猎手在8个方向待机" height="220">
  <img src="showcase/templar/turnaround.gif" alt="圣殿骑士在8个方向待机" height="220">
  <img src="docs/images/tutorials/platformer-run.gif" alt="横版平台角色Wren朝左右两个方向奔跑" height="220">
</p>

## 为什么选择它
- **天生一致。** 所有资源在每个方向、每一帧都共用同一个相机、光照和调色板。
- **修改成本低。** "把帽子加大"或"把攻击蓄力放慢"只是改一行，而不是重画300帧。
- **直接用于游戏。** 逐帧时长、落在正确帧上的事件（`hit`、`step_l`、`windup`）、挂点（枪口、手、命中点）、
  用于Y排序的地面锚点、法线贴图和自发光贴图。
- **为AI设计。** 一套适用于所有助手的说明、返回图像的MCP服务器、规格文件的JSON Schema、`文件:行:列`格式的
  错误信息，以及为看不到图像的助手提供的数值化美术评审。
- **纯Python，任何系统。** 只依赖numpy、Pillow和PyYAML，无需GPU，无需Blender。已在Windows、macOS和Linux上测试。

## 安装

需要Python 3.10或更高版本。使用 [pipx](https://pipx.pypa.io) 安装 `spritekiln` 命令，它与其他软件包隔离，
并会加入PATH：

**Windows**（PowerShell。还没有Python？先运行 `winget install Python.Python.3.13`，再打开新的终端）

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install "spritekiln[mcp]"
```

**macOS**（终端，使用 [Homebrew](https://brew.sh)）

```bash
brew install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

**Linux**（以Debian/Ubuntu为例；Fedora用 `sudo dnf install pipx`，Arch用 `sudo pacman -S python-pipx`）

```bash
sudo apt install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

然后打开新的终端，用 `spritekiln --version` 检查。`[mcp]` 为AI助手添加工具；只用命令行的话，
`pipx install spritekiln` 就够了。uv、虚拟环境、升级和常见问题，请参阅 [Install SpriteKiln](docs/tutorials/install.md)（英文）。

## 快速开始

在所有系统上都一样：

```
spritekiln new knight                                   # 从模板创建 specs/characters/knight/knight.yaml
spritekiln render specs/characters/knight/knight.yaml   # 图集、JSON、贴图、GIF -> .../out/knight/
```

然后交给你的助手：*"把这个骑士改成一个戴兜帽、拿短剑的哥布林斥候。渲染之前检查全部8个方向。"* 要配置游戏项目，
在项目文件夹中运行 `spritekiln init --engine godot --ai claude`；详情请参阅
[Use SpriteKiln with your AI](docs/tutorials/use-with-your-ai.md)（英文）。

## 工作原理

```
spec.yaml ──► 骨骼 + IK ──► SDF形状 ──► 光线步进渲染 ──► 像素化 ──► 图集 + JSON
```

光源固定在世界空间中，由模型旋转，因此各个方向的明暗保持一致。每次渲染都会生成QA报告和用于检查的预览表。

## 引擎

| 引擎 | 提供的内容 | 指南 |
|---|---|---|
| **Godot 4** | `KilnSprite2D` 节点、SpriteFrames 和现成场景；编辑器插件可从渲染JSON生成它们 | [godot.md](docs/engines/godot.md) · [示例](examples/godot) |
| **Unity 2022.3+** | UPM包：`.kiln` 导入器（精灵、法线贴图、AnimationClip）和 `KilnAnimator` | [unity.md](docs/engines/unity.md) |
| **MonoGame** | `KilnSprite.cs` 运行时和法线贴图光照着色器 `KilnLit.fx` | [monogame.md](docs/engines/monogame.md) · [示例](examples/monogame) |
| **其他** | 兼容Aseprite的JSON：Phaser、LÖVE、Defold、GameMaker…… | [generic.md](docs/engines/generic.md) |

## AI助手
`spritekiln init --ai claude,codex,gemini,copilot,cursor` 从同一份源文件（[`docs/agent/`](docs/agent)）为每个助手
生成说明，并注册MCP服务器（`spritekiln mcp`）。根据原画制作新角色的流程：建模师搭建形体，美术总监与原画对比，
建模师修改，动画师制作动画，美术总监再次评审（[recipe.md](docs/agent/recipe.md)）。

## 作品展示
圣殿骑士和女猎手是为游戏 **Hunt Tower** 制作的：由遵循上述流程的Claude Code根据原画用SpriteKiln完成。更多图片、
动画和游戏截图见 [`showcase/`](showcase)。

## 了解更多
完整文档为英文：[README](README.md)、[安装](docs/tutorials/install.md)、[第一个角色](docs/tutorials/first-character.md)、
[从你的原画开始](docs/tutorials/splash-art.md)、[动画与事件](docs/tutorials/animations.md)、
[平台游戏角色](docs/tutorials/platformer.md)、[规格参考](docs/agent/spec.md)、[输出格式](docs/format.md)、
[路线图](docs/ROADMAP.md)、[参与贡献](CONTRIBUTING.md)。

## 许可
代码、文档和引擎集成：[MIT](LICENSE)。示例资源（石像鬼、猎人、Wren、道具（木箱、煤气灯、训练假人）、模板、
gothic和props调色板、示例中的精灵）：[CC0 1.0](LICENSES/CC0-1.0.txt)。展示资源（Hunt Tower的圣殿骑士和女猎手，
以及女猎手的地雷：规格文件、原画、调色板、渲染图和游戏截图）：© 2026 Lucas Ramos / PlayRPG，保留所有权利，仅用于
演示（[条款](LICENSES/LicenseRef-Showcase.txt)）。
