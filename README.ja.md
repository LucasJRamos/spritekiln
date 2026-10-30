<p align="center">
  <img src="showcase/huntress/from_this_to_this.png" alt="ガンスリンガーのスプラッシュアートと、その8方向のピクセルアートスプライト" width="100%">
</p>

# SpriteKiln

[English](README.md) | [Português (BR)](README.pt-BR.md) | [한국어](README.ko.md) | **日本語** | [简体中文](README.zh-CN.md)

**プロシージャル3Dモデルから、アニメーション付きのピクセルアートスプライトを。コーディングAIが操作することを
前提に設計されています。**

キャラクターは小さなYAMLファイル1つです。骨格、3D形状、マテリアル、アニメーションを記述します。
SpriteKilnはそれを8方向（トップダウン3/4）または横向き（サイドビュー）のピクセルアートにレンダリングします。
フレームごとの正確な表示時間、ゲームプレイ用イベント、アタッチポイント（ソケット）、動的ライティング用の
ノーマルマップ、発光レイヤーを備え、Godot、Unity、MonoGame、またはAsepriteのスプライトシートを読めるあらゆる
エンジンですぐに使えます。

YAMLを自分で書く必要はありません。コーディングアシスタント（Claude Code、Codex、Gemini、Copilot、Cursor）が
説明やスプラッシュアートからスペックを書き、レンダリングし、**画像を見て**、気づいた点を直します。あなたは方向性を
示すだけです。

<p align="center">
  <img src="showcase/thor/turnaround.gif" alt="ハンマーを持つ嵐の神Thorが8方向で待機する様子" height="220">
  <img src="showcase/ranger/turnaround.gif" alt="機械の腕と戦闘用クロスボウを持つレンジャーが8方向で待機する様子" height="220">
  <img src="showcase/rin-7/run.gif" alt="サイバーパンクの決闘者RIN-7がサイドビューで左右両方向に走る様子" height="220">
  <br>
  <sub>Thor（トップダウン、身長100 px）· レンジャー（トップダウン、64 px）· RIN-7（サイドビュー、48 px）：Claude CodeがスプラッシュアートをもとにSpriteKilnで作成。<a href="#ショーケース">続きは下に</a>。</sub>
</p>

## なぜSpriteKilnなのか
- **構造的に一貫している。** すべてのアセットが、すべての方向とフレームで同じカメラ、ライト、パレットを共有します。
  北東向きの歩行と南西向きの攻撃で、見た目がずれることはありません。
- **変更が安い。** 「帽子を大きく」「攻撃の溜めを遅く」は300フレームの描き直しではなく、1行の修正です。
- **そのままゲームに使える。** フレームごとの表示時間、正しいフレームに付いたイベント（`hit`、`step_l`、
  `windup`）、ソケット（銃口、手、命中点）、Yソート用の接地ピボット、ノーマルマップと発光マップ。
- **AIのための設計。** どのアシスタントにも使える1組の指示、画像を返すMCPサーバー、スペックのJSON Schema、
  `file:line:column` 形式のエラー、画像を見られないアシスタント向けの数値によるアートディレクションレビュー。
- **純粋なPython、どのOSでも。** numpy、Pillow、PyYAMLのみ。GPUもBlenderも不要です。Windows、macOS、Linuxで
  テスト済みです。

## インストール

Python 3.10以上が必要です。`spritekiln` コマンドは [pipx](https://pipx.pypa.io) でインストールします。他の
パッケージから隔離され、PATHに追加されます。

**Windows**（PowerShell。Pythonがなければ `winget install Python.Python.3.13` を実行し、新しいターミナルを開く）

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install "spritekiln[mcp]"
```

**macOS**（ターミナル、[Homebrew](https://brew.sh) を使用）

```bash
brew install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

**Linux**（Debian/Ubuntuの例。Fedoraは `sudo dnf install pipx`、Archは `sudo pacman -S python-pipx`）

```bash
sudo apt install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

その後、新しいターミナルを開いて `spritekiln --version` で確認してください。`[mcp]` はAIアシスタント向けの
ツールを追加します。コマンドラインだけなら `pipx install spritekiln` で十分です。代わりに
`"spritekiln[mcp,fast]"` をインストールすると、レンダリングが約6倍速くなります（コンパイル済みのレンダラーで、
Intel Macでは通常のレンダラーのままです）。uv、仮想環境、アップグレード、トラブルシューティングは
[SpriteKilnのインストール](docs/tutorials/install.md)（英語）を参照してください。

### アップグレード

| お使いのバージョン | 実行するコマンド |
|---|---|
| 0.2以降 | いずれかのゲームフォルダで `spritekiln update`（インストールしたときと同じ方法でアップグレードし、そのフォルダのAI向け指示を更新します）、続いてほかのゲームフォルダで `spritekiln update --files` |
| 0.1.0 | `pipx upgrade spritekiln`（または `uv tool upgrade spritekiln`）、続いて各ゲームフォルダで `spritekiln update --files` |
| 任意（高速レンダラーを追加する場合） | `pipx install --force "spritekiln[mcp,fast]"`（または `uv tool install --force "spritekiln[mcp,fast]"`） |

Windowsの仮想環境では `python -m spritekiln update` を実行してください。新しいバージョンでレンダリングし直した
アセットは、見た目が変わることがあります（0.3では陰影が変わりました）。変更点は[変更履歴](CHANGELOG.md)に
まとめてあります。

## クイックスタート

コマンドはどのOSでも同じです。

### 1. フォルダの準備（最初に一度だけ）

ゲームのフォルダ（スプライトだけが欲しい場合は空のフォルダ）でターミナルを開き、スプライトを使うエンジンと、
スプライトを作るAIアシスタントをSpriteKilnに伝えます：

```
spritekiln init --engine godot --ai claude
```

| `--engine` | 対象 | エクスポート先 |
|---|---|---|
| `godot` | Godot 4 | `assets/spritekiln/`（SpriteFramesとすぐ使えるシーン付き） |
| `unity` | Unity 2022.3+ | `Assets/SpriteKiln/` |
| `monogame` | MonoGame | `Content/sprites/` |
| `generic` | その他のエンジン、またはゲームがまだない場合 | `sprites/`：PNGアトラスとAseprite互換JSON |

| `--ai` | アシスタント |
|---|---|
| `claude` | Claude Code |
| `codex` | Codex |
| `gemini` | Gemini CLI |
| `copilot` | GitHub Copilot |
| `cursor` | Cursor |
| `generic` | `AGENTS.md` を読むその他のエージェント |

複数のアシスタントはカンマで区切ります：`--ai claude,cursor`。`init` は `spritekiln.toml`（スペックは
`art/specs/`、エクスポートは上のフォルダ）、アシスタントが作業前に読む指示、そしてアシスタントがSpriteKilnを
呼び出すMCPサーバーの設定を書き出します。詳しくは
[AIアシスタントでSpriteKilnを使う](docs/tutorials/use-with-your-ai.md)（英語）を参照してください。

### 2. アシスタントにスプライトを頼む

アシスタントでフォルダを開き、キャラクターを説明します：

> 短剣を持ったフード姿のゴブリン斥候を作って。テンプレートから始めて、8方向すべてを確認してから、idle、walk、
> attackをレンダリングしてエクスポートして。

最初の一回は、何かを作る前にアシスタントがアートスタイルについてインタビューします：トップダウンかサイドビューか、
画面上でキャラクターの身長が何ピクセルか、方向数、色、輪郭線と陰影、プロポーション、顔をどこまで描き込むか、
アニメーションの感触、参考資料。回答は `spritekiln.toml` に記録され（`spritekiln style` で表示）、以降の
スプライトはすべてそれに従い、あなたが頼んだときだけ変わります（「これからは輪郭線なしで」）。

その後、アシスタントがスペックを書き、レンダリングし、画像を見て直します。あなたは
`art/specs/characters/<name>/out/<name>/preview/` のGIFを確認して、変更を頼むだけです（「帽子を大きく」
「振りを速く」）。スプラッシュアートがあれば渡しましょう：
[スプラッシュアートからAIで作る](docs/tutorials/splash-art.md)（英語）。

### 3. 手作業で行う場合

アシスタントが実行するのと同じコマンドです：

```
spritekiln style set --height 48 --outline selective                 # アートスタイル（一度だけ。全項目は -h）
spritekiln new knight                                                # art/specs/characters/knight/knight.yaml
spritekiln pose art/specs/characters/knight/knight.yaml --dirs all   # 1つのポーズを8方向で、各方向およそ1秒
spritekiln render art/specs/characters/knight/knight.yaml --export   # 全アニメーションを描画し、エンジンへエクスポート
```

`pose` の合間にYAMLを編集します。[10分で作る最初のキャラクター](docs/tutorials/first-character.md)（英語）で
手順をたどれます。

## ショーケース

<p align="center">
  <img src="showcase/rin-7/in_game.jpg" alt="雨の降るネオンの市場で警備員を斬りつけるRIN-7" width="100%">
  <br>
  <sub>Godotのテストシーンに置いたRIN-7と警備員：SpriteKilnのスプライトが、ノーマルマップを通してネオンの光に照らされています。街並み、雨、斬撃の光はシーン側で描いたものです。</sub>
</p>

| RIN-7 · サイドビュー、48 px | レンジャー · トップダウン、64 px | Thor · トップダウン、100 px |
|---|---|---|
| ![左右両方向でのRIN-7の二連斬り](showcase/rin-7/attack.gif) | ![クロスボウを撃つレンジャー](showcase/ranger/attack.gif) | ![Thorのハンマーによる叩きつけ](showcase/thor/ult_slam.gif) |
| 7クリップ（idle、run、jump、rise、fall、land、attack）、84フレーム | 8方向で4クリップ（idle、run、dash、attack）、288フレーム | 8方向で13クリップ、696フレーム（フレームサイズ128 px） |
| [スプラッシュ → スプライト](showcase/rin-7/from_this_to_this.png) | [スプラッシュ → スプライト](showcase/ranger/from_this_to_this.png) | [スプラッシュ → スプライト](showcase/thor/from_this_to_this.png) |

Claude Codeが[レシピ](docs/agent/recipe.md)（モデラー、アートディレクター、アニメーター）に従って作りました。
RIN-7とレンジャーは0.3、Thorは0.1のテストプロジェクトから生まれ、TemplarとHuntressはゲーム **Hunt Tower** の
ために作られました。全員分を、さらに多くのアニメーションとあわせて [`showcase/`](showcase) で公開しています。

## 更新情報

**0.3**（2026-10-30）
- **よりシャープな形状：** 押し出し・回転プロファイル、チューブ、シェル、カットにより、刃、装甲板、帽子のつば、
  マントが膨らんだ塊ではなく、くっきりしたエッジを持つようになりました。
- **ひと目で見分けられるマテリアル：** ハイライト、しわ、エッジライトを伴う仕上げ（metal、soft、matte、
  glossy）と、帯、リベット、紋章を描く表面ペイント。
- **スタイルをそのまま反映：** レンダラーがプロジェクトの輪郭線、陰影（soft、flat、toon）、内側の線、ディザ、
  ライトをすべてのアセットに適用します。`spritekiln style preview` で選択肢を並べて比べられます。
- **ベースとキット：** `extends: humanoid` と20種類の組み込みキット（武器、盾、帽子・兜、マント、ベルト、
  頭部と髪）により、キャラクターには固有の部分だけを書けば済みます。
- **最初のキャラクターの質が向上：** 頭部と髪のキット、スタイルインタビューでの顔についての質問、
  `pose --focus head` によるクローズアップ。
- **高速化：** より厳密なバウンディングでフレームの描画が1.5〜3倍高速に、`[fast]` ではさらに約6倍、
  `--draft` プレビューも追加。

**0.2**（2026-10-25）
- 最初のアセットを作る前に、アシスタントがアートスタイルについてインタビューし、`spritekiln.toml` に
  記録します。以降のアセットはすべてそれに従います。
- `spritekiln update` がSpriteKilnをアップグレードし、ゲームフォルダのAI向け指示を更新します。

そのほかの変更はすべて[CHANGELOG](CHANGELOG.md)にあります。

## しくみ

```
spec.yaml ───────► 骨格 + IK ──────► SDF形状 ───► レイマーチング描画 ──► ピクセル化 ──────► アトラス + JSON
 (ボーン、         (フレームごとの   (楕円体、    (色、法線、深度、      (パレットランプ、  + ノーマルマップ
  形状、            式：サイクル、    押し出し、   ペイント、3倍の        輪郭線、          + 発光マップ
  キット、          キー、イベント)   回転体、     解像度で描画、         内側の線、        + GIF、QA
  アニメーション)                     チューブ、   ワールド固定ライト)    プロジェクトの    -> エンジンへ
                                      カット)                             スタイル)
```

ライトはワールドに固定され、モデルが回転するため、すべての方向で陰影が一貫します。レンダリングのたびに
QAレポート（はみ出し、パレット、シルエットの安定性）と確認用のコンタクトシートが出力されます。

## 機能
- **アートスタイル：** 最初のアセットの前に、アシスタントが視点、画面上のサイズ、方向数、色、輪郭線、陰影、
  プロポーション、顔、アニメーションについて質問します。回答はプロジェクトに保存され、レンダラーがその見た目
  （輪郭線、soft/flat/toonの陰影、内側の線、ハイライト、ディザ、ライト）をすべてのアセットに適用します。
  `spritekiln style preview` で選択肢を並べて比べられます。
- **モデリング：** 式で動かすボーン（`"0.045*sin(p)"`）、2ボーンIK、左右対称の `_L`/`_R` パーツ、そして
  くっきりした形状：押し出し・回転プロファイル、チューブ、シェル、平面カット、面取り・段付きのブレンド。
  マテリアルはパレットランプと仕上げ（metal、soft、matte、glossy）、しわとエッジハイライト、表面ペイント
  （ジオメトリを増やさずに帯、リベット、十字を描く）、発光とグロー、両面の膜。
- **ベースとキット：** `extends: humanoid` と、パラメーター付きの20種類の組み込みキット（武器、盾、帽子・兜、
  マント、ベルト、頭部と髪）。キャラクターは固有の部分だけを書けばよく、騎士のサンプルは約20行です。
- **アニメーション：** 式またはキーフレームによるサイクル、フレームごとの表示時間、トゥイーンとイージング、
  スミア、方向ごとのチート、イベント、`validate` がチェックするタイミング目標（例：「300 msで命中」）。
- **視点：** 8方向（または4方向、1方向）のトップダウン3/4、またはプラットフォーマー向けのサイドビュー
  （`view: side`。run、jump、rise、fall、landを備えたテンプレート付き）。左右対称のデザインなら
  `mirror: true` で右向きの方向だけをレンダリングし、残りはエンジンが反転します。
- **スプラッシュアートから：** `ref prep` がキャラクターを切り抜いてパレットを抽出し、`ref compare` が
  シルエットをモデルと比べて採点し（ピッチ補正済みIoU）、何を変えるべきかを示します。
- **レビュー：** `spritekiln review` が明度の幅、コントラスト、マテリアルごとのピクセル数、視認性を測り、
  ゲームの床（`--bg`）の上で、そのライト（`--tint`）を当ててスプライトをプレビューします。
  `pose --focus head` で顔をクローズアップできます。
- **速度：** コンパイル済みレンダラー（`[fast]`、約6倍高速）、ドラフトプレビュー、フレームを再トレースせずに
  ライティングだけやり直せるレンダーキャッシュ。
- **出力：** アトラス、ノーマルマップと発光マップ、Aseprite互換JSON（[フォーマット](docs/format.md)）、
  フレームごとのソケット、GIFとコンタクトシート。

## エンジン

| エンジン | 提供されるもの | ガイド |
|---|---|---|
| **Godot 4** | `KilnSprite2D` ノード、SpriteFrames、すぐ使えるシーン。ドロップしたJSONからそれらを作るエディタープラグイン | [godot.md](docs/engines/godot.md) · [サンプル](examples/godot) |
| **Unity 2022.3+** | UPMパッケージ：`.kiln` インポーター（スプライト、ノーマルマップ、AnimationClip）と `KilnAnimator` | [unity.md](docs/engines/unity.md) |
| **MonoGame** | `KilnSprite.cs` ランタイムとノーマルマップ対応ライトシェーダー `KilnLit.fx` | [monogame.md](docs/engines/monogame.md) · [サンプル](examples/monogame) |
| **その他** | Aseprite互換JSON：Phaser、LÖVE、Defold、GameMaker… | [generic.md](docs/engines/generic.md) |

どのランタイムも同じように再生します：正確な表示時間、本来のフレームで発生するイベント、ソケット、速度に
もっとも近い方向の選択、反転した方向。

## AIアシスタント

| アシスタント | `--ai` | 指示 | MCPツール |
|---|---|---|---|
| Claude Code | `claude` | `CLAUDE.md`、スキル、モデラー／アニメーター／アートディレクターのエージェント | `.mcp.json` |
| Codex | `codex` | `AGENTS.md` | `~/.codex/config.toml`（手動で追加） |
| Gemini CLI | `gemini` | `GEMINI.md` | `.gemini/settings.json` |
| GitHub Copilot | `copilot` | `.github/copilot-instructions.md` | `.vscode/mcp.json` |
| Cursor | `cursor` | `.cursor/rules/spritekiln.mdc` | `.cursor/mcp.json` |
| その他のエージェント | `generic` | `AGENTS.md` | |

`spritekiln init --ai claude,codex,...` は、ひとつの原本（[`docs/agent/`](docs/agent)）からこれらを書き出します。
スプラッシュアートから新しいキャラクターを作るレシピ：モデラーが形を作り、アートディレクターが原画と比べて
レビューし、モデラーが修正し、アニメーターがアニメーションを付け、ディレクターがもう一度レビューします
（[recipe.md](docs/agent/recipe.md)）。

## さらに詳しく
ドキュメントは英語です。
- [SpriteKilnのインストール](docs/tutorials/install.md)（Windows、macOS、Linux。pipx、uv、または仮想環境）
- [10分で作る最初のキャラクター](docs/tutorials/first-character.md)
- [スプラッシュアートからAIで作る](docs/tutorials/splash-art.md)
- [アニメーションとイベント](docs/tutorials/animations.md)
- [プラットフォーマーのキャラクター（サイドビュー）](docs/tutorials/platformer.md)
- [AIアシスタントでSpriteKilnを使う](docs/tutorials/use-with-your-ai.md)（指示ファイルとMCPツール）
- [スペックリファレンス](docs/agent/spec.md) · [出力フォーマット](docs/format.md) · [ロードマップ](docs/ROADMAP.md)
- [ショーケース](showcase) · [コントリビュート](CONTRIBUTING.md) · [変更履歴](CHANGELOG.md) · 翻訳：
  [English](README.md)、[Português (BR)](README.pt-BR.md)、[한국어](README.ko.md)、[简体中文](README.zh-CN.md)

## ライセンス
コード、ドキュメント、各エンジン連携：[MIT](LICENSE)。サンプルアセット（ガーゴイル、ハンター、騎士、Wren、
小道具（木箱、ガス灯、訓練用人形）、テンプレートとキット、gothic・propsパレット、サンプルのスプライト）：
[CC0 1.0](LICENSES/CC0-1.0.txt)。ショーケースのアセット（Hunt TowerのTemplarとHuntress、Huntressの地雷：
スペック、スプラッシュアート、パレット、レンダー、ゲーム画面のキャプチャ。RIN-7、レンジャー、Thor：
スプラッシュアート、レンダー、キャプチャ）：© 2026 Lucas Ramos（Hunt Tower：Lucas Ramos / PlayRPG）、
無断転載禁止、デモ目的でのみ収録（[条件](LICENSES/LicenseRef-Showcase.txt)）。
[`REUSE.toml`](REUSE.toml) が各パスのライセンスを定めています。
