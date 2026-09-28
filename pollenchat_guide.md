# PollenChat 使い方ガイド

PollenChat は [PollinationsAI](https://pollinations.ai/) 向けのクリーンな CLI チャットクライアントです。

## 起動

```bash
python pollenchat.py
```

初回起動時に名前を聞かれます。Enter で環境変数のデフォルト値が使われます。

```
[~] Fetching available models from PollinationsAI...
[OK] 7 models available.

[+] Your name (Enter for 'user'): Taro
[OK] Welcome, Taro! Type [help] for commands.

Taro[default] :
```

プロンプトの `[default]` は現在のセッシン名です。

---

## 基本的なチャット

コマンド以外をそのまま入力すると、AI と会話できます。

```
Taro[default] : PythonでFizzBuzzを書いて

PollenChat (openai): もちろんです。以下にPythonコードを示します。
```python
for i in range(1, 101):
    if i % 15 == 0:
        print("FizzBuzz")
    ...
```
```

ストリーミングモードでは、AI の応答が1文字ずつリアルタイムに表示されます。

---

## モデル切り替え

```
Taro[default] : [model]

Available models:
  [ ] 1. openai
  [ ] 2. mistral
  [ ] 3. llama
  [*] 4. claude
  ...

[+] Select model (number or name, Enter to keep claude): mistral
[OK] Model set to: mistral
```

---

## システムプロンプト

```
Taro[default] : [system]

Current system prompt:
  You are a helpful assistant.

[+] Enter new prompt (empty line = keep, [reset] = default):
あなたは優秀なPythonプログラマーです。簡潔に回答してください。

[OK] System prompt updated.
```

`[reset]` と入力するとデフォトに戻ります。

---

## temperature / max_tokens

```
Taro[default] : [config]

Current configuration:
  temperature : 0.7
  max_tokens  : (unset / server default)

[+] temperature (current: 0.7, Enter=keep, 0.0-2.0): 1.2
[OK] temperature set to 1.2

[+] max_tokens (current: (unset), Enter=keep, 'none'=unset): 2048
[OK] max_tokens set to 2048
```

- `temperature`: 0.0（決定的）〜 2.0（創造的）
- `max_tokens`: `none` で未設定に戻せます

---

## ストリーミングモードの切り替え

```
Taro[default] : [stream]
[OK] Streaming mode: OFF (batch)
```

バッチモードでは、APIから全文が返ってきてから一括表示されます。

---

## 画像生成

```
Taro[default] : [image]

Image Generation Mode
  Current: 1024x1024, seed=random

[image] Taro: a cat wearing a space suit
[~] Generating image... prompt: a cat wearing a space suit... | size: 1024x1024 | seed: 48291
[OK] Image saved: pollen_images/img_20260929_143052_a_cat_wearing_a_space_s.png
```

画像モード内で使えるサブコマンド:

```
[image] Taro: [size]
[+] width (current: 1024): 768
[+] height (current: 1024): 768
[OK] Size set to 768x768

[image] Taro: [seed]
[+] seed (current: random, 'none'=random): 42
[OK] Seed fixed to 42
```

シードを固定すると、同じプロンプトで同じ画像を再現できます。

---

## マルチライン入力

```
Taro[default] : [long]
[+] Multiline mode. Enter text, then a blank line to finish:
def hello():
    print("Hello, world!")

[Input preview]:
def hello():
    print("Hello, world!")
```

---

## ファイルのインポート

```
Taro[default] : [import]
[+] File path: notes.md
[OK] Loaded 12,340 characters.
[Preview]: # プロジェクト仕様書 ...

[+] Question about this file (Enter to send file content only): 要約して
```

> 200KB を超えるファイルは確認プロンプトが表示されます。

---

## 会話履歴の検索

```
Taro[default] : [search]
[+] Search keyword: Python

3 match(es):
  [1]Taro: PythonでFizzBuzz書いて
  [5]AI: Pythonのリスト内包表記は...
  [8]Taro: Pythonのデコータって何？
```

---

## Markdown の再表示とコード保存

```
Taro[default] : [render]
--- Rendered (Markdown) ---
▶ python
for i in range(1, 101): ...
◀
---------------------------

Taro[default] : [savecode]
Code blocks found: 1
  1. [python] 5 lines — for i in range...

[+] Select block number (Enter = 1, [all] = save each): 1
[+] Filename (Enter for 'snippet.py'): fizzbuzz.py
[OK] Code saved: pollen_codes/fizzbuzz.py
```

---

## セッションのエクスポート

```
Taro[default] : [export]
[+] Export filename (Enter for auto): project_discussion
[+] Include system prompt in export? y/N: n
[OK] Exported to: pollen_exports/project_discussion.md
```

---

## Undo とトークン概算

```
Taro[default] : [undo]
[OK] Undid last exchange (2 message(s)). History now: 5 messages.

Taro[default] : [token]
Token estimate (default):
  Approximate tokens : 1,234
  Total characters   : 5,678
  ASCII chars        : 3,456
  Non-ASCII chars    : 2,222
  ※ This is a rough estimate. Actual tokenizer counts may differ.
```

---

## 複数セッョン管理

### 新規セッション作成

```
Taro[default] : [new]
[+] New session name: work
[OK] Created and switched to 'work'

Taro[work] : プロジェクトAの要件を整理して
```

### セッション切り替え

```
Taro[work] : [switch]

Sessions:
  [*] 1. default (3 messages)
  [ ] 2. work (2 messages)

[+] Switch to (number or name): default
[OK] Switched to 'default' (3 messages)

Taro[default] :
```

### セッションのリネーム

```
Taro[default] : [rename]
[+] Rename 'default' to: hobby
[OK] Renamed 'default' → 'hobby'
```

### セッションの削除

```
Taro[hobby] : [delete]
[+] Delete session (name, Enter=cancel): work
[!] Really delete 'work'? type 'yes': yes
[OK] Deleted 'work'
```

> 現在アクティブなセッションは削除できません。削除前に `[switch]` で別のセッションに移ってください。

### 自動保存・自動読込

終了時に全セッションが自動保存され、次回起動時に自動で復元されます。

```
Taro[hobby] : [exit]
Bye bye, Taro!
[OK] All sessions saved.
```

---

## 便利なワークフロー例

### 仕事と趣味を分ける

```
[ new ] → work
[ system ] → あなたは優秀な技術顧問です。
（仕事の相談）
[ switch ] → default
[ rename ] → hobby
（趣味の雑談）
```

### 長文ドキュメントを読み込んで質問

```
[ import ] → spec.md → 「この仕様書に不足している項目は？」
```

### コード生成 → 保存 → エクスポート

```
「FastAPIのCRUDサンプルを書いて」
[ savecode ] → 1 → crud.py
[ export ] → fastapi_chat.md → n
```

---

## コマンド早見表

| コマンド | 用途 |
|---------|------|
| `[model]` | AIモデルを切り替え |
| `[system]` | システムプロンプトを設定 |
| `[config]` | temperature / max_tokens を調整 |
| `[stream]` | ストリーミング ON/OFF 切り替え |
| `[image]` | 画像生成モード |
| `[long]` | マルチライン入力 |
| `[import]` | .md / .txt ファイルを読込んで送信 |
| `[search]` | 会話履歴を検索 |
| `[render]` | 直前の応答をMarkdown再表示 |
| `[savecode]` | コードブロックをファイル保存 |
| `[export]` | 会話をMarkdownファイルにエクスポート |
| `[undo]` | 直前のやり取りを削除 |
| `[token]` | 概算トークン数を表示 |
| `[sessions]` | セッション一覧 |
| `[switch]` | セッション切り替え |
| `[new]` | 新規セッション作成 |
| `[rename]` | セッション名変更 |
| `[delete]` | セッション削除 |
| `[clear]` | 現在のセッション履歴をクリア |
| `[history]` | 現在のセッション履歴を表示 |
| `[help]` | ヘルプ表示 |
| `[exit]` | 終了（自動保存あり） |

---

## トラブルシューティング

### HTTP 429 (Rate Limited)

PollinationsAI の無料 tier にはレート制限があります。数秒〜数十秒待ってから再試行してください。

### モデルが応答しない

`[model]` で別のモデルに切り替えてみてください。PollinationsAI のモデル可用性は変動します。

### セッショが復元されない

`sessions/` ディレクトリ内の `.json` ファイルを確認してください。手動でファイルを移動した場合は、起動時に自動読込されます。

### 巨大なファイルの送信を防ぎたい

`[import]` は 200KB を超えるファイルで確認プロンプトを表示します。それ以上のサイズ制限を設けたい場合は、スクリプト内の `IMPORT_MAX_BYTES` を変更してください。
